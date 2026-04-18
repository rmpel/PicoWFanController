import machine
import network
import time

from config import (
    AP_SSID_PREFIX,
    AP_IP,
    WIFI_CONNECT_TIMEOUT_S,
    WIFI_CONNECT_RETRIES,
    mac_suffix,
)


class WiFiManager:
    def __init__(self, storage, led):
        self._storage = storage
        self._led = led
        self._sta = network.WLAN(network.STA_IF)
        self._ap = network.WLAN(network.AP_IF)
        self.is_ap_mode = False

    def start_ap_mode(self):
        print("Starting AP mode...")
        self._led.set_pattern("ap_mode")
        self._sta.active(False)
        time.sleep(0.3)
        self._ap.active(True)
        time.sleep(0.3)
        name = self._storage.get("device_name") or AP_SSID_PREFIX
        ssid = f"{name}-{mac_suffix()}"
        self._ap.config(essid=ssid, security=0)
        time.sleep(0.5)
        self._ap.ifconfig((AP_IP, "255.255.255.0", AP_IP, AP_IP))
        self.is_ap_mode = True
        print(f"AP started: SSID={ssid} IP={AP_IP}")
        return AP_IP

    def stop_ap_mode(self):
        self._ap.active(False)
        self.is_ap_mode = False

    def connect(self, ssid=None, password=None, timeout=WIFI_CONNECT_TIMEOUT_S, retries=WIFI_CONNECT_RETRIES):
        if ssid is None:
            ssid = self._storage.get("wifi_ssid")
            password = self._storage.get("wifi_password")
        if not ssid:
            return False

        self._led.set_pattern("connecting")

        for attempt in range(retries):
            print(f"WiFi connect attempt {attempt+1}/{retries} to '{ssid}'")
            self._ap.active(False)
            time.sleep(0.3)
            self._sta.active(False)
            time.sleep(0.3)
            self._sta.active(True)
            try:
                self._sta.config(pm=0xa11140)
            except Exception:
                pass

            self._sta.connect(ssid, password)

            start = time.time()
            while not self._sta.isconnected():
                self._led.update()
                status = self._sta.status()
                if status == -3:
                    print("Wrong password")
                    self._led.set_pattern("sos")
                    return False
                if status in (-1, -2):
                    break
                if time.time() - start > timeout:
                    break
                time.sleep(0.2)

            if self._sta.isconnected():
                ip = self._sta.ifconfig()[0]
                print(f"WiFi connected: {ip}")
                self._led.set_pattern("success", once=True)
                start = time.ticks_ms()
                while not self._led.is_done() and time.ticks_diff(time.ticks_ms(), start) < 5500:
                    self._led.update()
                    time.sleep_ms(20)
                return True

        print("WiFi failed")
        self._led.set_pattern("sos")
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < 3500:
            self._led.update()
            time.sleep_ms(20)
        return False

    def test_and_save(self, ssid, password):
        self.stop_ap_mode()
        time.sleep(0.5)
        if self.connect(ssid, password):
            self._storage.set_many({"wifi_ssid": ssid, "wifi_password": password})
            return True
        time.sleep(1)
        self.start_ap_mode()
        return False

    def ensure_connected(self):
        if self.is_ap_mode:
            return False
        if self._sta.isconnected():
            return True
        return self.connect()

    def get_status(self):
        if self.is_ap_mode:
            name = self._storage.get("device_name") or AP_SSID_PREFIX
            return {"mode": "ap", "ssid": f"{name}-{mac_suffix()}", "ip": AP_IP, "connected": False}
        if self._sta.isconnected():
            return {"mode": "sta", "ssid": self._storage.get("wifi_ssid"), "ip": self._sta.ifconfig()[0], "connected": True}
        return {"mode": "disconnected", "ssid": None, "ip": None, "connected": False}
