import asyncio

from inu import error, const, Status
from inu.const import LogLevel, Priority
from inu.hardware.robotics import Robotics, actuator, apa102
from inu.hardware.switch import Switch, SwitchMode
from inu.lib.switch import SwitchManager
from inu.schema.command import Jog
from inu.schema.settings.robotics import Robotics as RoboSettings
from micro_nats.error import NotFoundError
from micro_nats.jetstream.protocol import consumer
from micro_nats.model import Message
from micro_nats.util import Time
from micro_nats.util.asynchronous import TaskPool


class RoboticsApp(SwitchManager):
    def __init__(self):
        super().__init__(RoboSettings)
        self.pool = TaskPool()
        self.robotics = Robotics(self.inu)
        self.jog_consumer = None

    def load_devices(self):
        """
        Read device configuration and bootstrap the robotics controller with device information.
        """
        devices = self.get_config(["robotics", "devices"])
        if not isinstance(devices, dict):
            raise error.Malformed(f"Malformed device configuration for robotics")

        def device_cfg(path, keys, default=None):
            for key in keys:
                if key not in path:
                    return default
                path = path[key]
            return path

        # Robotics actuators
        for device_id, spec in devices.items():
            device_type = device_cfg(spec, ["type"])
            self.logger.info(f"Adding device: {device_id} ({device_type})")

            # -- APA102 --
            if device_type in apa102.Apa102.CONFIG_ALIASES:
                self.robotics.add_device(device_id, apa102.Apa102(
                    num_leds=device_cfg(spec, ["num_leds"], 144),
                    spi_index=device_cfg(spec, ["spi"], 1),
                    segments=device_cfg(spec, ["segments"], None),
                ))

            # -- ACTUATOR --
            if device_type in actuator.Actuator.CONFIG_ALIASES:
                # limit switches
                fwd_sw = None
                rev_sw = None

                es = device_cfg(spec, ["end_stops"])
                if es:
                    if "forward" in es:
                        fwd_sw = Switch(
                            pin=device_cfg(es, ["forward", "pin"], 34),
                            mode=device_cfg(es, ["forward", "mode"], SwitchMode.NO),
                            min_active=device_cfg(es, ["forward", "min_active"], 10),
                        )
                    if "reverse" in es:
                        rev_sw = Switch(
                            pin=device_cfg(es, ["reverse", "pin"], 36),
                            mode=device_cfg(es, ["reverse", "mode"], SwitchMode.NO),
                            min_active=device_cfg(es, ["forward", "min_active"], 10),
                        )

                self.robotics.add_device(device_id, actuator.Actuator(
                    actuator.StepperDriver(
                        pulse=device_cfg(spec, ["driver", "pulse_pin"], 6),
                        direction=device_cfg(spec, ["driver", "direction_pin"], 7),
                        enabled=device_cfg(spec, ["driver", "enabled_pin"], 8),
                        alert=device_cfg(spec, ["driver", "alert_pin"], None),
                    ),
                    actuator.Screw(
                        steps_per_rev=device_cfg(spec, ["screw", "steps_per_rev"], 1600),
                        screw_lead=device_cfg(spec, ["screw", "screw_lead"], 5),
                        forward=device_cfg(spec, ["screw", "forward"], 1),
                    ),
                    device_cfg(spec, ["ramp_speed"], 150),
                    device_cfg(spec, ["halt_ramp_speed"], 300),
                    fwd_sw,
                    rev_sw,
                ))

    async def app_init(self):
        cal_seq = None
        try:
            self.load_devices()
            await self.switch_init()
            self.activate_on_switch = False

            ds = "" if len(self.robotics.devices) == 1 else "s"
            ss = "" if len(self.switches) == 1 else "es"
            self.logger.info(
                f"Robotics initialised with {len(self.robotics.devices)} device{ds} and {len(self.switches)} switch{ss}"
            )

            # Calibration settings
            cal_seq = self.inu.settings.cal_seq.strip()
            if cal_seq and cal_seq[0] != "#":
                await self.run_calibration(cal_seq)
                return

            # We'll decide if we power up enabled by checking the previous device state and determining if it is safe -
            last_status = await self.inu.js.msg.get_last(
                const.Streams.STATUS,
                const.Subjects.fqs(const.Subjects.STATUS, self.inu.device_id)

            )

            stat = Status(last_status.get_payload())
            # If we were ENABLED but not ACTIVE (eg idle), then we'll allow powering-up enabled (otherwise calibrate)
            if stat.enabled and not stat.active:
                await self.inu.log("Previous state is idle; starting enabled")
                await self.inu.status(enabled=True, active=False, status="")
                if self.inu.settings.idle_power:
                    self.robotics.set_power(True)
            else:
                if cal_seq:
                    # Auto calibration
                    await self.run_calibration(cal_seq)
                else:
                    # Cannot calibrate - user input required
                    await self.inu.log("Unsafe to start enabled; starting disabled", LogLevel.WARNING)
                    await self.inu.alert("Unsafe robotics power-up; calibration required", Priority.P3)
                    await self.inu.status(enabled=False, active=False, status="Pending calibration")
                    self.robotics.set_power(False)

        except NotFoundError:
            # No previous state found
            if cal_seq:
                # Auto calibration
                await self.run_calibration(cal_seq)
            else:
                # Cannot calibrate - user input required
                await self.inu.log("No prior state found; starting disabled", LogLevel.WARNING)
                await self.inu.status(enabled=False, active=False, status="Safe start")
                self.robotics.set_power(False)

        except Exception as e:
            self.logger.fatal(f"App init failed: {e}")

    async def app_tick(self):
        # Check if the device has gone idle long enough to deactivate the power
        if not self.inu.settings.idle_power and not self.inu.state.active and self.robotics.powered and \
                (self.robotics.get_idle_time() >= self.inu.settings.idle_period):
            await self.inu.log(f"Device idle for {self.robotics.get_idle_time()} s, powering down robotics")
            self.robotics.set_power(False)

        await self.switch_tick()

    async def on_trigger(self, code: int):
        # Check for a calibration request (code 101)
        if code == const.TriggerCode.CALIBRATE:
            if self.inu.state.enabled:
                await self.inu.log("Cannot calibrate while enabled", LogLevel.WARNING)
            else:
                cal_seq = self.inu.settings.cal_seq.strip()
                if cal_seq and cal_seq[0] != "#":
                    await self.run_calibration(cal_seq)
                else:
                    await self.inu.log("Not calibration sequence configured", LogLevel.WARNING)
            return

        if not self.inu.state.can_act():
            self.logger.info(f"Ignoring trigger: {self.inu.state}")
            return

        # Actionable sequence codes range from seq_0 to seq_5
        if 0 <= code <= 5:
            seq = f"seq_{code}"
            ctrl = getattr(self.inu.settings, seq).strip()

            if len(ctrl) == 0:
                await self.inu.log(f"Ignoring sequence {code} with no control codes", LogLevel.WARNING)
                return

            await self.inu.log(f"Execute sequence {code} // {ctrl}")

            try:
                await self.inu.activate(f"{const.Strings.SEQ} {code}")
                # robotics.run() may monopolise CPU, so sleep enough time to dispatch the status update
                await asyncio.sleep(0.05)
                await self.robotics.run(ctrl)

                if self.inu.settings.cooldown_time:
                    self.logger.info(f"Begin cooldown: {self.inu.settings.cooldown_time}")
                    await self.inu.activate(const.Strings.COOLDOWN)
                    await asyncio.sleep(self.inu.settings.cooldown_time / 1000)
                    self.logger.info("Cooldown complete")

                await self.inu.deactivate()
                await self.inu.log(f"Sequence complete")

            except error.LimitHalt:
                await self.inu.log("Limiter hit")
                await self.inu.deactivate()
                await self.inu.log(f"Sequence complete")

            except error.DeviceAlert:
                self.logger.warning("Dispatching alert and deactivating")
                await self.inu.alert(
                    f"Robotics malfunction during {const.Strings.SEQ} {code}",
                    priority=self.inu.settings.device_priority
                )
                await self.inu.log(f"Device controller alert; aborting sequence", LogLevel.ERROR)
                self.robotics.set_power(False)
                await self.inu.status(active=False, enabled=False, status="Robotics malfunction!")

            except Exception as e:
                await self.inu.log(f"Exception in robotics execution - {type(e).__name__}: {e}", LogLevel.ERROR)

    async def on_interrupt(self):
        """
        A listen-device has published an interrupt code.
        """
        if self.inu.state.active:
            if self.robotics.interrupt():
                self.logger.info("Interrupting operation")
            else:
                self.logger.info("Cannot interrupt")

    async def on_enabled_changed(self, enabled: bool):
        """
        Enabled-state changed externally.
        """
        # In versions <= 37, we also changed device power state. This is no longer coupled.
        pass

    async def on_settings_updated(self):
        await super().on_settings_updated()

        self.robotics.power_up_delay = self.inu.settings.warmup_delay

        if self.jog_consumer:
            try:
                await self.inu.js.consumer.delete(const.Streams.COMMAND, self.jog_consumer.name)
            except NotFoundError:
                pass

        subj = const.Subjects.fqs(
            [const.Subjects.COMMAND, const.Subjects.COMMAND_JOG],
            self.inu.get_central_id()
        )
        self.jog_consumer = await self.inu.js.consumer.create(
            consumer.Consumer(
                const.Streams.COMMAND,
                consumer_cfg=consumer.ConsumerConfig(
                    filter_subject=subj,
                    deliver_policy=consumer.ConsumerConfig.DeliverPolicy.NEW,
                    ack_wait=Time.sec_to_nano(3),
                )
            ), push_callback=self.on_jog,
        )
        self.logger.info(f"Listening for jogs on '{subj}'")

    async def on_jog(self, msg: Message):
        """
        We can jog an actuator remotely by sending `cmd.jog` messages. This will only work when NOT enabled and should
        be used for calibration or maintenance.
        """
        if self.inu.state.enabled:
            await self.inu.log("Cannot jog while enabled", LogLevel.WARNING)
            await self.inu.js.msg.term(msg)
            return

        if self.inu.state.active:
            await self.inu.log("Ignoring jog while active")
            await self.inu.js.msg.term(msg)
            return

        acked = False
        try:
            jog = Jog(msg.get_payload())
            jog.distance = int(jog.distance)
            jog.speed = int(jog.speed)

            if jog.device_id not in self.robotics.devices:
                await self.inu.log(f"Device {jog.device_id} not registered - cannot jog", LogLevel.WARNING)
                await self.inu.js.msg.term(msg)
                return

            if jog.distance == 0 or jog.speed <= 0:
                await self.inu.log(f"Bad jog request: {jog.distance} mm at {jog.speed} mm/s", LogLevel.WARNING)
                await self.inu.js.msg.term(msg)
                return

            acked = True
            await self.inu.js.msg.ack(msg)
            self.logger.info(f"Jog {jog.device_id} by {jog.distance} mm at {jog.speed} mm/s")

            await self.inu.activate(f"Jog {jog.device_id}: {jog.distance}x{jog.speed}")
            await asyncio.sleep(0.05)
            await self.robotics.run(f"SEL {jog.device_id}; MV {jog.distance} {jog.speed}")
            await self.inu.deactivate()

        except error.DeviceAlert:
            await self.inu.alert("Robotics malfunction during jog", priority=self.inu.settings.device_priority)
            self.robotics.set_power(False)
            await self.inu.status(active=False, enabled=False, status="Jog malfunction")

        except Exception as e:
            self.inu.log(f"Error jogging - {type(e).__name__}: {e}", LogLevel.ERROR)
            if not acked:
                await self.inu.js.msg.nack(msg)

    async def run_calibration(self, seq):
        """
        Runs provided calibration sequence and configures device status according to calibration success.
        """
        await self.inu.log("Calibrating..")

        try:
            await self.inu.activate(f"Calibrating")
            await asyncio.sleep(0.1)
            await self.robotics.run(seq)
            await asyncio.sleep(0.1)
            await self.inu.deactivate()

            await self.inu.log("Calibration success")
            await self.inu.status(enabled=True, active=False, status="")

        except error.DeviceAlert:
            await self.inu.alert(
                "Robotics malfunction during calibration sequence",
                priority=self.inu.settings.device_priority
            )
            self.robotics.set_power(False)
            await self.inu.status(active=False, enabled=False, status="Calibration malfunction")

        except Exception as e:
            await self.inu.log(f"Exception in robotics calibration - {type(e).__name__}: {e}", LogLevel.ERROR)
            await self.inu.status(enabled=False, active=False, status="Calibration failed")
            self.robotics.set_power(False)


if __name__ == "__main__":
    app = RoboticsApp()
    asyncio.run(app.run())
