import json
import socket
import time

from config import WEB_PORT, LED_COUNT


def _parse_query(qs):
    out = {}
    if not qs:
        return out
    for part in qs.split("&"):
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
        else:
            k, v = part, ""
        out[k] = v
    return out


def _parse_path(raw):
    if "?" in raw:
        p, qs = raw.split("?", 1)
    else:
        p, qs = raw, ""
    return p, _parse_query(qs)


class WebServer:
    def __init__(self, storage, wifi, fan):
        self._storage = storage
        self._wifi = wifi
        self._fan = fan
        self._sock = None

    def start(self):
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind(("0.0.0.0", WEB_PORT))
            self._sock.listen(5)
            self._sock.setblocking(False)
            print(f"Web server started on :{WEB_PORT}")
            return True
        except Exception as e:
            print(f"Web server start failed: {e}")
            return False

    def stop(self):
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def _read_file(self, path):
        try:
            with open(path, "rb") as f:
                return f.read()
        except Exception:
            return None

    def _send(self, client, status, content_type, body):
        if isinstance(body, str):
            body = body.encode("utf-8")
        head = (
            f"HTTP/1.1 {status}\r\n"
            f"Content-Type: {content_type}; charset=utf-8\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Cache-Control: no-store\r\n"
            f"Connection: close\r\n\r\n"
        ).encode("utf-8")
        try:
            client.sendall(head + body)
        except Exception:
            try:
                client.send(head)
                client.send(body)
            except Exception:
                pass

    def _json(self, client, status, obj):
        self._send(client, status, "application/json", json.dumps(obj))

    def _status_dict(self):
        return {
            "device_name": self._storage.get("device_name"),
            "speed": self._fan.get_duty(),
            "rpm": self._fan.get_rpm(),
            "fan_enabled": self._fan.is_enabled(),
            "led_count": LED_COUNT,
            "settings": self._storage.public(),
            "wifi": self._wifi.get_status(),
        }

    def _route(self, method, path, query, body, client):
        if path in ("/", "/index.html"):
            page = "/web/setup.html" if self._wifi.is_ap_mode else "/web/index.html"
            content = self._read_file(page)
            if content is None:
                self._send(client, "404 Not Found", "text/plain", "Not found")
            else:
                self._send(client, "200 OK", "text/html", content)
            return

        if path == "/style.css":
            content = self._read_file("/web/style.css")
            if content is None:
                self._send(client, "404 Not Found", "text/plain", "Not found")
            else:
                self._send(client, "200 OK", "text/css", content)
            return

        if path == "/script.js":
            content = self._read_file("/web/script.js")
            if content is None:
                self._send(client, "404 Not Found", "text/plain", "Not found")
            else:
                self._send(client, "200 OK", "application/javascript", content)
            return

        if path == "/common.js":
            content = self._read_file("/web/common.js")
            if content is None:
                self._send(client, "404 Not Found", "text/plain", "Not found")
            else:
                self._send(client, "200 OK", "application/javascript", content)
            return

        if path in ("/advanced", "/advanced.html"):
            content = self._read_file("/web/advanced.html")
            if content is None:
                self._send(client, "404 Not Found", "text/plain", "Not found")
            else:
                self._send(client, "200 OK", "text/html", content)
            return

        if path == "/advanced.js":
            content = self._read_file("/web/advanced.js")
            if content is None:
                self._send(client, "404 Not Found", "text/plain", "Not found")
            else:
                self._send(client, "200 OK", "application/javascript", content)
            return

        if path == "/fancontrol/status":
            self._json(client, "200 OK", self._status_dict())
            return

        if path == "/fancontrol/up":
            new = self._fan.step_up()
            self._json(client, "200 OK", {"ok": True, "speed": new})
            return

        if path == "/fancontrol/down":
            new = self._fan.step_down()
            self._json(client, "200 OK", {"ok": True, "speed": new})
            return

        if path == "/fancontrol/push":
            new = self._fan.toggle_predefined()
            self._json(client, "200 OK", {"ok": True, "speed": new})
            return

        if path == "/fancontrol/toggle-power":
            enabled = self._fan.toggle_on_off()
            self._json(client, "200 OK", {"ok": True, "fan_enabled": enabled})
            return

        if path == "/fancontrol/set-predefined":
            spd = query.get("speed")
            if spd is None:
                self._json(client, "400 Bad Request", {"ok": False, "error": "missing speed"})
                return
            try:
                val = max(0, min(100, int(spd)))
            except ValueError:
                self._json(client, "400 Bad Request", {"ok": False, "error": "invalid speed"})
                return
            self._storage.set("predefined_speed", val)
            self._json(client, "200 OK", {"ok": True, "predefined_speed": val})
            return

        if path == "/fancontrol/set-speed":
            spd = query.get("speed")
            if spd is None:
                self._json(client, "400 Bad Request", {"ok": False, "error": "missing speed"})
                return
            try:
                val = max(0, min(100, int(spd)))
            except ValueError:
                self._json(client, "400 Bad Request", {"ok": False, "error": "invalid speed"})
                return
            new = self._fan.set_speed(val)
            self._json(client, "200 OK", {"ok": True, "speed": new})
            return

        if path == "/fancontrol/settings" and method == "GET":
            self._json(client, "200 OK", self._storage.public())
            return

        if path == "/fancontrol/settings" and method == "POST":
            try:
                data = json.loads(body) if body else {}
            except ValueError:
                self._json(client, "400 Bad Request", {"ok": False, "error": "invalid json"})
                return
            allowed = {"step", "boost_speed", "min_speed", "predefined_speed",
                       "pwm_polarity", "tach_pulses_per_rev", "hold_threshold_ms",
                       "device_name", "encoder_invert", "led_brightness",
                       "led_invert", "led_correction"}
            updates = {k: v for k, v in data.items() if k in allowed}
            self._storage.set_many(updates)
            if "pwm_polarity" in updates:
                self._fan.apply_duty(self._fan.get_duty(), persist=False)
            self._json(client, "200 OK", {"ok": True, "settings": self._storage.public()})
            return

        if path == "/fancontrol/wifi" and method == "POST":
            try:
                data = json.loads(body) if body else {}
            except ValueError:
                self._json(client, "400 Bad Request", {"ok": False, "error": "invalid json"})
                return
            ssid = data.get("ssid", "")
            password = data.get("password", "")
            if not ssid:
                self._json(client, "400 Bad Request", {"ok": False, "error": "missing ssid"})
                return
            ok = self._wifi.test_and_save(ssid, password)
            self._json(client, "200 OK", {"ok": ok})
            if ok:
                time.sleep(1)
                import machine
                machine.reset()
            return

        self._send(client, "404 Not Found", "text/plain", "Not found")

    def handle_request(self):
        if not self._sock:
            return
        try:
            client, _addr = self._sock.accept()
        except OSError:
            return
        try:
            client.setblocking(True)
            client.settimeout(3.0)
            data = b""
            cl = None
            headers_end = -1
            while True:
                try:
                    chunk = client.recv(1024)
                except OSError as e:
                    print(f"recv error: {e}")
                    break
                if not chunk:
                    break
                data += chunk
                if headers_end < 0:
                    idx = data.find(b"\r\n\r\n")
                    if idx >= 0:
                        headers_end = idx
                        try:
                            headers = data[:headers_end].decode("utf-8")
                        except UnicodeError:
                            headers = ""
                        cl = 0
                        for line in headers.split("\r\n"):
                            if line.lower().startswith("content-length:"):
                                try:
                                    cl = int(line.split(":", 1)[1].strip())
                                except ValueError:
                                    cl = 0
                                break
                if headers_end >= 0:
                    body_bytes = len(data) - headers_end - 4
                    if body_bytes >= (cl or 0):
                        break

            if not data:
                return

            try:
                text = data.decode("utf-8")
            except UnicodeError:
                text = data.decode("latin1")

            head, _, body = text.partition("\r\n\r\n")
            first_line = head.split("\r\n", 1)[0]
            parts = first_line.split(" ")
            if len(parts) < 2:
                return
            method, raw_path = parts[0], parts[1]
            path, query = _parse_path(raw_path)

            if path.startswith("/fancontrol/"):
                print(f"{method} {raw_path}")

            self._route(method, path, query, body.strip("\x00").strip(), client)
        except Exception as e:
            print(f"Request error: {e}")
        finally:
            try:
                client.close()
            except Exception:
                pass
