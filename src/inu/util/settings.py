import argparse
import logging
import random
import time

from textual import widgets, containers, events, validation, on
from textual.app import App, ComposeResult

from inu import Inu, InuHandler, const
from inu.schema import settings, Heartbeat
from micro_nats import error as mn_error, model
from micro_nats.jetstream.protocol.consumer import Consumer, ConsumerConfig
from micro_nats.util import Time


class InfoWidget(widgets.Static):

    def compose(self) -> ComposeResult:
        stat = widgets.Static(classes="info_sub")
        stat.mount(widgets.Static(f"Status", classes="setting_title"))
        stat.mount(widgets.Checkbox("Enabled", True, disabled=True, id="stat_enabled"))
        stat.mount(widgets.Checkbox("Active", disabled=True, id="stat_active"))
        yield stat

        hb = widgets.Static(classes="info_sub")
        hb.mount(widgets.Static(f"Heartbeat", classes="setting_title"))
        hb.mount(containers.Horizontal(
            widgets.Static(f" :heart: ", id="hb_heart"),
            widgets.Rule(id="hb_progress", line_style="heavy")
        ))
        yield hb


class SettingsWidget(widgets.Static):
    def __init__(self, setting_name: str, config: tuple, **kwargs) -> None:
        super().__init__(classes="box", **kwargs)
        (cfg_type, cfg_hint, cfg_min, cfg_max) = config
        self.setting_name = setting_name
        self.setting_type = cfg_type

        self.hint_widget = widgets.Static(f"<{cfg_type}> {cfg_hint}", classes="setting_hint")

        if cfg_type == "int":
            self.input_widget = widgets.Input(validators=validation.Integer(minimum=cfg_min, maximum=cfg_max))
        elif cfg_type == "bool":
            self.input_widget = widgets.Checkbox("False")
        else:
            self.input_widget = widgets.Input(validators=[])

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

    def __init__(self, args: argparse.Namespace):
        super().__init__()
        self.args = args
        self.logger = logging.getLogger('inu.util.settings')
        self.inu = Inu(const.Context(
            device_id=["settings", f"i{random.randint(1000, 9999)}"],
            nats_server=args.nats,
        ), self)
        self.config = None
        self.config_hint = None
        self.title = "Connecting to NATS.."
        self.device_id = self.args.device_id[0]
        self.record = None
        self.saved = True

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

        await self.mount(widgets.Markdown(self.config_hint, classes="config_hint"))
        await self.mount(widgets.Static("", classes="error_hint hidden"))

        w = []
        for config_name, config in self.config.items():
            setting = SettingsWidget(config_name, config)
            setting.set_value(getattr(self.record, config_name))
            w.append(setting)

        container = widgets.Static()
        await container.mount(InfoWidget())
        await container.mount(containers.ScrollableContainer(*w))
        await self.mount(container)

        await self.subscribe_info()
        self.set_interval(0.2, self.hb_ticker)

        def set_saved():
            self.saved = True

        self.set_timer(0.01, set_saved)

    async def subscribe_info(self):
        await self.inu.js.consumer.create(
            Consumer(const.Streams.HEARTBEAT, ConsumerConfig(
                filter_subject=const.Subjects.fqs(const.Subjects.HEARTBEAT, self.device_id),
                deliver_policy=ConsumerConfig.DeliverPolicy.NEW,
                ack_wait=Time.sec_to_nano(2),
            )), self.on_hb
        )

    async def on_hb(self, msg: model.Message):
        await self.inu.js.msg.ack(msg)

        hb = Heartbeat(msg.get_payload())
        self.hb_interval = hb.interval
        self.last_hb = time.time()
        self.get_widget_by_id("hb_heart").add_class("beat")
        self.get_widget_by_id("hb_progress").styles.width = 0

        def hb_done():
            self.get_widget_by_id("hb_heart").remove_class("beat")

        self.set_timer(0.15, hb_done)

    def hb_ticker(self):
        if self.hb_interval is None:
            return

        prog = (time.time() - self.last_hb) / self.hb_interval
        if prog > 1:
            prog = 1

        self.get_widget_by_id("hb_progress").styles.width = int(self.HB_MAX * prog)

    def _on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.set_focus(None)
        elif event.key == "up":
            self.action_focus_previous()
        elif event.key == "down":
            self.action_focus_next()

    @on(widgets.Input.Changed)
    def on_input_changed(self, _) -> None:
        self.saved = False

    @on(widgets.Checkbox.Changed)
    def on_checkbox_changed(self, _) -> None:
        self.saved = False

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
            self.title = f"Settings // {self.device_id}"
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
