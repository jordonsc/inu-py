import argparse
import logging
import random
import time

from textual import widgets, containers, events, validation, on
from textual.app import App, ComposeResult

from inu import Inu, InuHandler, const, Status
from inu.schema import settings, Heartbeat
from inu.schema.command import Trigger, Jog, Ota, Reboot
from micro_nats import error as mn_error, model
from micro_nats.jetstream.protocol.consumer import Consumer, ConsumerConfig
from micro_nats.util import Time


class InfoWidget(widgets.Static):
    def compose(self) -> ComposeResult:
        # Device status
        stat = widgets.Static(classes="info_sub", id="info_status")
        stat.mount(widgets.Static(f"Status\n ", classes="setting_title"))
        stat.mount(widgets.Checkbox("Enabled", disabled=True, id="stat_enabled"))
        stat.mount(widgets.Checkbox("Locked", disabled=True, id="stat_locked"))
        stat.mount(widgets.Checkbox("Active", disabled=True, id="stat_active"))
        stat.mount(widgets.Static("", id="stat_info"))
        yield stat

        # Device heartbeat
        hb = widgets.Static(classes="info_sub", id="info_hb")
        hb.mount(widgets.Static("Heartbeat\n", classes="setting_title"))
        hb.mount(containers.Horizontal(
            widgets.Static(f" :heart: ", id="hb_heart"),
            widgets.Rule(id="hb_progress", line_style="heavy")
        ))
        hb.mount(widgets.Static("", id="dvc_build"))
        hb.mount(widgets.Static("", id="dvc_address"))
        yield hb

        # Send device commands
        cmd = widgets.Static(classes="info_sub", id="info_cmd")
        cmd.mount(widgets.Static("Command Dispatch", classes="setting_title"))
        cmd.mount(widgets.Button("Toggle Enabled", id="btn_enabled"))
        cmd.mount(widgets.Button("Toggle Locked", id="btn_locked"))
        cmd.mount(widgets.Button("Send Trigger", id="btn_trigger"))
        cmd.mount(widgets.Input("0", validators=validation.Integer(minimum=0, maximum=9999), id="trg_code"))
        cmd.mount(widgets.Button("Interrupt", id="btn_interrupt"))
        yield cmd

        # Send OTA request
        ota = widgets.Static(classes="info_sub", id="info_maintenance")
        ota.mount(widgets.Static("Maintenance", classes="setting_title"))
        ota.mount(widgets.Button("Begin OTA", id="btn_ota"))
        ota.mount(widgets.Input("0", validators=validation.Integer(minimum=0, maximum=99), id="ota_version"))
        ota.mount(widgets.Button("Reboot", id="btn_reboot"))
        yield ota

        # Jog (robotics only)
        jog = widgets.Static(classes="info_sub", id="info_jog")
        jog.mount(widgets.Static("Jog Controls\n", classes="setting_title"))
        jog.mount(widgets.Checkbox("Jog mode", id="btn_jog_mode"))
        jog.mount(widgets.Input("A0", id="jog_device"))
        yield jog


class JogWidget(widgets.Static):
    def compose(self) -> ComposeResult:
        yield widgets.Markdown(f"# JOG MODE ENABLED")
        container = widgets.Static("", classes="info_container")
        container.mount(widgets.Static(f"Press ESC to exit jog mode"))

        jog_grid = widgets.Static(id="jog_grid")
        jog_grid.mount(widgets.Static("Device", classes="setting_subtitle"))
        jog_grid.mount(widgets.Static("", id="jog_device_info", classes="setting_setting"))
        jog_grid.mount(widgets.Static("Distance", classes="setting_subtitle"))
        jog_grid.mount(widgets.Static("1 mm", id="jog_distance", classes="setting_setting"))
        jog_grid.mount(widgets.Static("Speed", classes="setting_subtitle"))
        jog_grid.mount(widgets.Static("2 mm/s", id="jog_speed", classes="setting_setting"))
        container.mount(jog_grid)

        container.mount(widgets.Static(f":arrow_left: and :arrow_right: to decrease/increase jog distance"))
        container.mount(widgets.Static(f":arrow_up: and :arrow_down: to jog the selected device"))

        yield container


class SettingsWidget(widgets.Static):
    def __init__(self, setting_name: str, config: tuple, **kwargs) -> None:
        super().__init__(classes="box", **kwargs)
        (cfg_type, cfg_hint, cfg_min, cfg_max) = config
        self.setting_name = setting_name
        self.setting_type = cfg_type

        self.hint_widget = widgets.Static(f"<{cfg_type}> {cfg_hint}", classes="setting_hint")
        id = f"setting_{setting_name}"

        if cfg_type == "int":
            self.input_widget = widgets.Input(validators=validation.Integer(minimum=cfg_min, maximum=cfg_max), id=id)
        elif cfg_type == "bool":
            self.input_widget = widgets.Checkbox("False", id=id)
        else:
            self.input_widget = widgets.Input(validators=[], id=id)

    def compose(self) -> ComposeResult:
        yield widgets.Static(f"{self.setting_name}", classes="setting_title")
        yield self.hint_widget
        yield self.input_widget

    @on(widgets.Checkbox.Changed)
    def update_checkbox(self, event: widgets.Checkbox.Changed) -> None:
        self.input_widget.label.truncate(0)
        self.input_widget.label.append(str(event.value))

    def set_value(self, val):
        if self.setting_type == 'bool':
            self.input_widget.value = bool(val)
        else:
            self.input_widget.value = str(val)

    def get_value(self):
        if self.setting_type == 'bool':
            return bool(self.input_widget.value)
        elif self.setting_type == 'int':
            # str -> float -> int conversions prevent issues with "12.0" still validating as int
            return int(float(self.input_widget.value))
        else:
            return self.input_widget.value


class Settings(InuHandler, App):
    BINDINGS = [
        ("q", "safe_exit", "exit"),
        ("Q", "exit", "(shift) force exit"),
        ("w", "apply", "write settings"),
    ]
    CSS_PATH = "../../assets/settings.tcss"
    HB_MAX = 23

    # IDs excluded from "making a change"
    EXCLUDED_IDS = ["trg_code", "stat_enabled", "stat_locked", "stat_active"]

    JOG_DIST_STEPS = [1, 5, 10, 25, 100, 250]
    JOG_SPEED_STEPS = [2, 5, 10, 20, 50, 100]

    def __init__(self, args: argparse.Namespace):
        super().__init__()
        self.args = args
        self.logger = logging.getLogger('inu.util.settings')
        self.inu = Inu(const.Context(
            device_id=["settings", f"i{random.randint(1000, 9999)}"],
            nats_server=args.nats,

        ), self)
        self.inu.nats.manager.context.auto_reconnect = False
        self.config = None
        self.config_hint = None
        self.title = "Connecting to NATS.."
        self.device_id = self.args.device_id[0]
        self.record = None
        self.saved = True
        self.jog_mode = False
        self.jog_index = 0

        self.hb_interval = None
        self.last_hb = None

    def compose(self) -> ComposeResult:
        # Header
        header = widgets.Header()
        header.tall = True
        yield header
        yield widgets.Footer()

    async def on_mount(self):
        await self.init()

        await self.mount(widgets.Markdown(self.config_hint, id="config_hint"))
        await self.mount(widgets.Static("", classes="error_hint hidden"))

        container = widgets.Static(id="main_container")
        await container.mount(InfoWidget())

        s_container = widgets.Static(id="settings_widget")
        for config_name, config in self.config.items():
            setting = SettingsWidget(config_name, config)
            setting.set_value(getattr(self.record, config_name))
            await s_container.mount(setting)

        await container.mount(s_container)
        await container.mount(JogWidget(id="jog_widget"))
        await self.mount(container)

        await self.subscribe_info()
        self.set_interval(0.2, self.hb_ticker)

        if self.device_id[0:8] != "robotics":
            self.get_widget_by_id("info_jog").styles.display = "none"

        def set_saved():
            self.saved = True

        self.set_timer(0.01, set_saved)

    async def subscribe_info(self):
        """
        Subscribes to heartbeat & status streams for the device.
        """
        await self.inu.js.consumer.create(
            Consumer(const.Streams.HEARTBEAT, ConsumerConfig(
                filter_subject=const.Subjects.fqs(const.Subjects.HEARTBEAT, self.device_id),
                deliver_policy=ConsumerConfig.DeliverPolicy.NEW,
                ack_wait=Time.sec_to_nano(2),
            )), self.on_hb
        )

        await self.inu.js.consumer.create(
            Consumer(const.Streams.STATUS, ConsumerConfig(
                filter_subject=const.Subjects.fqs(const.Subjects.STATUS, self.device_id),
                deliver_policy=ConsumerConfig.DeliverPolicy.LAST_PER_SUBJECT,
                ack_wait=Time.sec_to_nano(2),
            )), self.on_stat
        )

    async def on_stat(self, msg: model.Message):
        """
        Device status update received.
        """
        await self.inu.js.msg.ack(msg)

        stat = Status(msg.get_payload())
        self.get_widget_by_id("stat_enabled").value = stat.enabled
        self.get_widget_by_id("stat_locked").value = stat.locked
        self.get_widget_by_id("stat_active").value = stat.active
        self.get_widget_by_id("stat_info").update(stat.status)

        self.get_widget_by_id("btn_jog_mode").disabled = stat.enabled

    async def on_hb(self, msg: model.Message):
        """
        Device heartbeat received.
        """
        await self.inu.js.msg.ack(msg)

        hb = Heartbeat(msg.get_payload())
        self.hb_interval = hb.interval
        self.last_hb = time.time()
        self.get_widget_by_id("hb_heart").add_class("beat")
        self.get_widget_by_id("hb_progress").styles.width = 0
        self.get_widget_by_id("dvc_build").update(f"Build: {hb.build}")
        self.get_widget_by_id("dvc_address").update(f"Addr:  {hb.local_addr}")

        def hb_done():
            self.get_widget_by_id("hb_heart").remove_class("beat")

        self.set_timer(0.15, hb_done)

    def hb_ticker(self):
        """
        Updates the HB animation.
        """
        if self.hb_interval is None:
            return

        prog = (time.time() - self.last_hb) / self.hb_interval
        prog_bar = self.get_widget_by_id("hb_progress")
        prog_bar.remove_class("late")
        prog_bar.remove_class("offline")
        if prog <= 1:
            # Device healthy
            prog_bar.styles.width = int(self.HB_MAX * prog)
            prog_bar.styles.margin = 0
        elif prog <= 2:
            # Heartbeat late
            if prog >= 1.25:
                prog_bar.add_class("late")

            prog -= 1
            prog_bar.styles.width = self.HB_MAX - int(self.HB_MAX * prog)
            prog_bar.styles.margin = (0, 0, 0, int(self.HB_MAX * prog))
        elif prog <= 2.:
            # HB very late
            prog_bar.styles.width = 0
            prog_bar.styles.margin = 0
        else:
            # Device considered offline
            prog_bar.styles.width = self.HB_MAX
            prog_bar.styles.margin = 0
            prog_bar.add_class("offline")

    async def _on_key(self, event: events.Key) -> None:
        if self.jog_mode:
            if event.key == "escape":
                self.get_widget_by_id("btn_jog_mode").value = False
                # self.set_jog_mode(False)
            elif event.key == "up":
                await self.do_jog(True)
            elif event.key == "down":
                await self.do_jog(False)
            elif event.key == "left":
                self.jog_index = max(0, self.jog_index - 1)
                self.update_jog_hint()
            elif event.key == "right":
                self.jog_index = min(len(self.JOG_DIST_STEPS) - 1, self.jog_index + 1)
                self.update_jog_hint()

        else:
            if event.key == "escape":
                self.set_focus(None)
            elif event.key == "up":
                self.action_focus_previous()
            elif event.key == "down":
                self.action_focus_next()

    async def do_jog(self, forward: bool):
        distance = self.JOG_DIST_STEPS[self.jog_index] if forward else -self.JOG_DIST_STEPS[self.jog_index]

        jog = Jog(
            distance=distance,
            speed=self.JOG_SPEED_STEPS[self.jog_index],
            device_id=self.get_widget_by_id("jog_device").value,
        )

        await self.inu.nats.publish(
            const.Subjects.fqs([const.Subjects.COMMAND, const.Subjects.COMMAND_JOG], f"central.{self.device_id}"),
            jog.marshal()
        )

    def update_jog_hint(self):
        self.get_widget_by_id("jog_distance").update(f"{self.JOG_DIST_STEPS[self.jog_index]} mm")
        self.get_widget_by_id("jog_speed").update(f"{self.JOG_SPEED_STEPS[self.jog_index]} mm/s")

    @on(widgets.Input.Changed)
    def on_input_changed(self, event: widgets.Input.Changed) -> None:
        if event.input.id in self.EXCLUDED_IDS or event.input.id is None or event.input.id[0:4] == "btn_":
            return

        self.saved = False

    @on(widgets.Checkbox.Changed)
    def on_checkbox_changed(self, event: widgets.Checkbox.Changed) -> None:
        if event.checkbox.id == "btn_jog_mode":
            self.set_jog_mode(event.checkbox.value)

        if event.checkbox.id in self.EXCLUDED_IDS or event.checkbox.id is None or event.checkbox.id[0:4] == "btn_":
            return

        self.saved = False

    def set_jog_mode(self, enabled: bool):
        self.jog_mode = enabled

        main_display = "none" if self.jog_mode else "block"
        jog_display = "block" if self.jog_mode else "none"

        self.get_widget_by_id("jog_device_info").update(self.get_widget_by_id("jog_device").value)

        self.get_widget_by_id("settings_widget").styles.display = main_display
        self.get_widget_by_id("config_hint").styles.display = main_display
        self.get_widget_by_id("info_maintenance").styles.display = main_display
        self.get_widget_by_id("info_cmd").styles.display = main_display
        self.get_widget_by_id("info_jog").styles.display = main_display

        self.get_widget_by_id("jog_widget").styles.display = jog_display

        if self.jog_mode:
            self.set_focus(None)
            self.screen.scroll_to(0, 0, speed=100)

    async def on_button_pressed(self, event: widgets.Button.Pressed) -> None:
        trg = Trigger()
        if event.button.id == "btn_trigger":
            trg.code = int(self.get_widget_by_id("trg_code").value)
        elif event.button.id == "btn_interrupt":
            trg.code = const.TriggerCode.INTERRUPT
        elif event.button.id == "btn_enabled":
            trg.code = const.TriggerCode.ENABLE_TOGGLE
        elif event.button.id == "btn_locked":
            trg.code = const.TriggerCode.LOCK_TOGGLE
        elif event.button.id == "btn_ota":
            # OTA has a special command code, not a trigger
            ota = Ota()
            ota.version = int(self.get_widget_by_id("ota_version").value)
            await self.inu.nats.publish(
                const.Subjects.fqs([const.Subjects.COMMAND, const.Subjects.COMMAND_OTA], f"central.{self.device_id}"),
                ota.marshal()
            )
            return
        elif event.button.id == "btn_reboot":
            # Hard reboot
            reboot = Reboot()
            await self.inu.nats.publish(
                const.Subjects.fqs([const.Subjects.COMMAND, const.Subjects.COMMAND_REBOOT],
                                   f"central.{self.device_id}"),
                reboot.marshal()
            )
            return
        else:
            return

        await self.inu.nats.publish(
            const.Subjects.fqs([const.Subjects.COMMAND, const.Subjects.COMMAND_TRIGGER], f"central.{self.device_id}"),
            trg.marshal()
        )

    async def init(self):
        """
        Execute the bootstrap process.
        """
        if not await self.inu.init():
            self.exit(return_code=1, message="Could not connect to NATS server")

        dvc_id = self.device_id.split(".")

        if len(dvc_id) < 2:
            self.exit(
                return_code=1,
                message="Device IDs must contain at least two namespaces (device_type.device_name)"
            )

        try:
            cls = settings.get_device_settings_class(dvc_id[0])
            try:
                msg = await self.inu.js.msg.get_last(
                    const.Streams.SETTINGS,
                    const.Subjects.fqs(const.Subjects.SETTINGS, self.device_id)
                )
                self.record = cls(msg.get_payload())
            except mn_error.NotFoundError:
                self.record = cls()

            self.config_hint, self.config = settings.get_config_for_device(dvc_id[0])
            self.title = f"I . N . U  -  {self.device_id}"
        except ValueError:
            self.exit(return_code=1, message=f"Unknown device type ({dvc_id[0]}) for provided device ID.")
            return 3

        return 0

    def action_exit(self):
        """
        Immediately exit.
        """
        self.exit(0)

    def action_safe_exit(self):
        """
        Exit only if saved.
        """
        if self.saved:
            self.exit(0)
        else:
            self.set_error_message("not saved; Shift+Q to force exit")

    async def action_save(self):
        """
        Save the record, and quit the application on success.
        """
        if await self.save_record():
            self.exit(0)

    async def action_apply(self):
        """
        Save the record, then do nothing.
        """
        await self.save_record()

    async def save_record(self) -> bool:
        """
        Validate the record content and if valid, save the setting record to NATS.

        Returns True if it was saved, False if it failed validation. Will set the error/success message accordingly.
        """
        err = []
        for node in self.query(SettingsWidget).nodes:
            if hasattr(node.input_widget, 'validate'):
                valid = node.input_widget.validate(node.input_widget.value)
                if valid and not valid.is_valid:
                    err.append(node.setting_name)
                    continue

            setattr(self.record, node.setting_name, node.get_value())

        if len(err):
            errs = "\n * ".join(err)
            self.set_error_message(f"Validation failure on:\n * {errs}")
            return False
        else:
            self.set_working_message("Saving.. " + self.record.marshal())
            await self.inu.nats.publish(
                const.Subjects.fqs(const.Subjects.SETTINGS, self.device_id),
                self.record.marshal()
            )
            await self.inu.log(f"Updated settings for {self.device_id}")
            self.set_success_message("Record saved")
            self.saved = True
            return True

    def set_working_message(self, msg: str):
        """
        Style the error/success hint as 'in progress' and set the message.
        """
        self.clear_error_message()
        w = self.query_one("Static.error_hint")
        w.update(msg)
        w.add_class("working")
        w.remove_class("success")
        w.remove_class("hidden")

    def set_success_message(self, msg: str):
        """
        Style the error/success hint as a 'success' and set the message.
        """
        self.clear_error_message()
        w = self.query_one("Static.error_hint")
        w.update(msg)
        w.add_class("success")
        w.remove_class("working")
        w.remove_class("hidden")

        self.set_timer(3, self.conditional_clear_success_message)

    def set_error_message(self, msg: str):
        """
        Style the error/success hint as an 'error' and set the message.
        """
        self.clear_error_message()
        w = self.query_one("Static.error_hint")
        w.update(msg)
        w.remove_class("success")
        w.remove_class("working")
        w.remove_class("hidden")

    def clear_error_message(self):
        """
        Clears any error/success message hint and hides the element.
        """
        w = self.query_one("Static.error_hint")
        w.update("")
        w.add_class("hidden")
        w.remove_class("success")
        w.remove_class("working")

    def conditional_clear_success_message(self):
        """
        Hides the error/success hint only if it still contains a success message.
        """
        w = self.query_one("Static.error_hint")
        if w.has_class("success"):
            w.update("")
            w.add_class("hidden")
