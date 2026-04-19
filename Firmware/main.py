import sys
import time
import _thread

sys.path.append("/lib")

from storage import Storage
from led_status import LedStatus
from led_bar import LedBar
from fan_controller import FanController
from encoder import RotaryEncoder, Button
from wifi_manager import WiFiManager
from web_server import WebServer


class App:
    def __init__(self):
        print("=" * 50)
        print("PicoFanController starting...")
        print("=" * 50)

        self.storage = Storage()
        self.led = LedStatus()
        self.fan = FanController(self.storage)
        self.led_bar = LedBar(self.storage, self.fan)
        self.led.set_mirror(self.led_bar.set_status)
        self.encoder = RotaryEncoder(lambda: self.storage.get("encoder_invert"))
        self.button = Button(lambda: self.storage.get("hold_threshold_ms"))
        self.wifi = WiFiManager(self.storage, self.led)
        self.web = WebServer(self.storage, self.wifi, self.fan)

        self._web_thread_started = False
        self._boost_active = False

    def start(self):
        force_ap = self.button.pressed_at_boot()
        if force_ap:
            print("Button held at boot -> forcing AP mode")

        if not force_ap and self.storage.has_wifi_config() and self.wifi.connect():
            pass
        else:
            self.wifi.start_ap_mode()

        if self.web.start():
            _thread.start_new_thread(self._web_loop, ())
            self._web_thread_started = True

        self.led.set_mirror(None)
        self.led_bar.release_status()
        self.led.set_pattern("off")

    def _web_loop(self):
        while True:
            try:
                self.web.handle_request()
            except Exception as e:
                print(f"web loop error: {e}")
            time.sleep_ms(2)

    def _handle_encoder(self):
        ticks = self.encoder.take_ticks()
        if ticks == 0:
            return
        for _ in range(abs(ticks)):
            if ticks > 0:
                self.fan.step_up()
            else:
                self.fan.step_down()
        self.led.flash_tick()

    def _handle_button(self):
        evt = self.button.update()
        if evt == Button.EVT_SHORT:
            self.fan.toggle_predefined()
            self.led.flash_tick()
        elif evt == Button.EVT_DOUBLE:
            self.fan.toggle_on_off()
            self.led.flash_tick()
        elif evt == Button.EVT_HOLD_START:
            self._boost_active = True
            self.fan.boost_start()
        elif evt == Button.EVT_HOLD_END:
            if self._boost_active:
                self.fan.boost_end()
                self._boost_active = False

    def run(self):
        print("Entering main loop")
        last_rpm_update = time.ticks_ms()
        while True:
            try:
                self._handle_encoder()
                self._handle_button()
                self.led.update()
                self.led_bar.update()

                now = time.ticks_ms()
                if time.ticks_diff(now, last_rpm_update) >= 500:
                    self.fan.update_rpm()
                    last_rpm_update = now

                time.sleep_ms(5)
            except Exception as e:
                print(f"Main loop error: {e}")
                sys.print_exception(e)
                time.sleep(1)


if __name__ == "__main__":
    app = App()
    try:
        app.start()
        app.run()
    except KeyboardInterrupt:
        print("Shutting down")
    except Exception as e:
        print(f"Fatal: {e}")
        sys.print_exception(e)
