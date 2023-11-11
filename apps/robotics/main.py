import asyncio

from inu import error, const, Status
from inu.app import InuApp
from inu.const import LogLevel, Priority
from inu.hardware.robotics import Robotics, actuator
from inu.hardware.switch import Switch, SwitchMode
from inu.schema.command import Jog
from inu.schema.settings.robotics import Robotics as RoboSettings
from micro_nats.error import NotFoundError
from micro_nats.jetstream.protocol import consumer
from micro_nats.model import Message
from micro_nats.util import Time
from micro_nats.util.asynchronous import TaskPool


class RoboticsApp(InuApp):
    def __init__(self):
        super().__init__(RoboSettings)
        self.pool = TaskPool()
        self.robotics = Robotics()
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

        for device_id, spec in devices.items():
            device_type = device_cfg(spec, ["type"])
            if device_type == actuator.Actuator.CONFIG_CODE:
                # limit switches
                fwd_sw = None
                rev_sw = None

                es = device_cfg(spec, ["end_stops"])
                if es:
                    if "forward" in es:
                        fwd_sw = Switch(
                            pin=device_cfg(es, ["forward", "pin"], 36),
                            mode=device_cfg(es, ["forward", "mode"], SwitchMode.NO),
                        )
                        rev_sw = Switch(
                            pin=device_cfg(es, ["reverse", "pin"], 14),
                            mode=device_cfg(es, ["reverse", "mode"], SwitchMode.NO),
                        )

                self.robotics.add_device(device_id, actuator.Actuator(
                    actuator.StepperDriver(
                        pulse=device_cfg(spec, ["driver", "pulse_pin"], 33),
                        direction=device_cfg(spec, ["driver", "direction_pin"], 38),
                        enabled=device_cfg(spec, ["driver", "enabled_pin"], 8),
                    ),
                    actuator.Screw(
                        steps_per_rev=device_cfg(spec, ["screw", "steps_per_rev"], 1600),
                        screw_lead=device_cfg(spec, ["screw", "screw_lead"], 5),
                        forward=device_cfg(spec, ["screw", "forward"], 1),
                    ),
                    device_cfg(spec, ["safe_wait"]),
                    fwd_sw,
                    rev_sw,
                ))

    async def app_init(self):
        self.load_devices()

        s = "" if len(self.robotics.devices) == 1 else "s"
        self.logger.info(f"Robotics initialised with {len(self.robotics.devices)} device{s}")

        # Calibration settings
        cal_seq = self.get_config(["robotics", "calibration", "sequence"])
        always_cal = self.get_config(["robotics", "calibration", "always_calibrate"], False)

        if always_cal and cal_seq:
            await self.run_calibration(cal_seq)
            return

        # We'll decide if we power up enabled by checking the previous device state and determining if it is safe -
        try:
            last_status = await self.inu.js.msg.get_last(
                const.Streams.STATUS,
                const.Subjects.fqs(const.Subjects.STATUS, self.inu.device_id)

            )

            stat = Status(last_status.get_payload())
            # If we were ENABLED but not ACTIVE (eg idle), then we'll allow powering-up enabled (otherwise calibrate)
            if stat.enabled and not stat.active:
                await self.inu.log("Previous state is idle; starting enabled")
                await self.inu.status(enabled=True, active=False, status="")
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

    async def app_tick(self):
        pass

    async def on_trigger(self, code: int):
        if self.inu.state.active:
            await self.inu.log("Ignoring trigger while active")
            return

        # Actionable sequence codes range from seq_0 to seq_5
        if 0 <= code <= 5:
            seq = f"seq_{code}"
            ctrl = getattr(self.inu.settings, seq).strip()

            if len(ctrl) == 0:
                await self.inu.log(f"Ignoring sequence {code} with no control codes")
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
        self.robotics.set_power(enabled)

    async def on_settings_updated(self):
        await super().on_settings_updated()

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
            self.robotics.set_power(True)

        except Exception as e:
            await self.inu.log(f"Exception in robotics calibration - {type(e).__name__}: {e}", LogLevel.ERROR)
            await self.inu.status(enabled=False, active=False, status="Calibration failed")
            self.robotics.set_power(False)


if __name__ == "__main__":
    app = RoboticsApp()
    asyncio.run(app.run())
