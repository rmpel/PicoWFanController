import json
import socket
import time
import os
import hashlib
import binascii

from config import WEB_PORT, LED_COUNT


UPLOAD_PATH = "/fancontrol/files/upload"
STAGING_DIR = "/staging"
LISTABLE_DIRS = ("/lib", "/web")
LISTABLE_ROOT_EXTS = (".py", ".json")
PROTECTED = {"/settings.json"}
MAX_NON_UPLOAD_BODY = 8192
UPLOAD_CHUNK = 1024


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
        out[k] = _url_decode(v)
    return out


def _url_decode(s):
    s = s.replace("+", " ")
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "%" and i + 2 < len(s):
            try:
                out.append(chr(int(s[i+1:i+3], 16)))
                i += 3
                continue
            except ValueError:
                pass
        out.append(c)
        i += 1
    return "".join(out)


def _parse_path(raw):
    if "?" in raw:
        p, qs = raw.split("?", 1)
    else:
        p, qs = raw, ""
    return p, _parse_query(qs)


def _safe_rel_path(p):
    """Validate a target path. Return normalized path with leading '/', or None."""
    if not p:
        return None
    if p.startswith("/"):
        p = p[1:]
    if not p:
        return None
    if ".." in p.split("/"):
        return None
    for ch in p:
        if not (ch.isalpha() or ch.isdigit() or ch in "._-/"):
            return None
    return "/" + p


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _is_dir(path):
    try:
        return (os.stat(path)[0] & 0x4000) != 0
    except OSError:
        return False


def _mkdir_p(path):
    parts = [p for p in path.split("/") if p]
    cur = ""
    for part in parts:
        cur = cur + "/" + part
        if not _exists(cur):
            try:
                os.mkdir(cur)
            except OSError:
                pass


def _remove_file(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _file_size(path):
    try:
        return os.stat(path)[6]
    except OSError:
        return -1


def _walk_listing():
    out = []
    for d in LISTABLE_DIRS:
        try:
            entries = os.listdir(d)
        except OSError:
            continue
        for name in entries:
            full = d + "/" + name
            if _is_dir(full):
                continue
            out.append({"path": full, "size": _file_size(full)})
    try:
        for name in os.listdir("/"):
            full = "/" + name
            if _is_dir(full):
                continue
            for ext in LISTABLE_ROOT_EXTS:
                if name.endswith(ext):
                    out.append({"path": full, "size": _file_size(full)})
                    break
    except OSError:
        pass
    out.sort(key=lambda e: e["path"])
    return out


def _sha256_of_file(path):
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(512)
                if not chunk:
                    break
                h.update(chunk)
        return binascii.hexlify(h.digest()).decode("ascii")
    except OSError:
        return None


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

    def _serve_static(self, client, path, content_type):
        content = self._read_file(path)
        if content is None:
            self._send(client, "404 Not Found", "text/plain", "Not found")
        else:
            self._send(client, "200 OK", content_type, content)

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

    def _handle_upload(self, client, query, headers, initial_body, total_body_len):
        """Stream body to /staging/<path>, hash it, validate, atomically rename."""
        target = _safe_rel_path(query.get("path", ""))
        if not target:
            self._json(client, "400 Bad Request", {"ok": False, "error": "invalid path"})
            return
        if target in PROTECTED:
            self._json(client, "403 Forbidden", {"ok": False, "error": "protected path"})
            return
        expected_sha = (query.get("sha256") or "").lower().strip()
        if not expected_sha or len(expected_sha) != 64:
            self._json(client, "400 Bad Request", {"ok": False, "error": "missing sha256"})
            return
        try:
            expected_size = int(query.get("size", "-1"))
        except ValueError:
            expected_size = -1
        if expected_size < 0 or expected_size != total_body_len:
            self._json(client, "400 Bad Request",
                       {"ok": False, "error": "size/content-length mismatch",
                        "size": expected_size, "content_length": total_body_len})
            return

        _mkdir_p(STAGING_DIR)
        staged = STAGING_DIR + target  # e.g. /staging/lib/foo.py
        staged_dir = staged.rsplit("/", 1)[0]
        _mkdir_p(staged_dir)
        part = staged + ".part"
        _remove_file(part)

        h = hashlib.sha256()
        written = 0
        try:
            with open(part, "wb") as f:
                if initial_body:
                    f.write(initial_body)
                    h.update(initial_body)
                    written += len(initial_body)
                while written < total_body_len:
                    try:
                        chunk = client.recv(min(UPLOAD_CHUNK, total_body_len - written))
                    except OSError:
                        chunk = b""
                    if not chunk:
                        break
                    f.write(chunk)
                    h.update(chunk)
                    written += len(chunk)
        except OSError as e:
            _remove_file(part)
            self._json(client, "500 Internal Server Error",
                       {"ok": False, "error": "write failed", "detail": str(e)})
            return

        if written != total_body_len:
            _remove_file(part)
            self._json(client, "400 Bad Request",
                       {"ok": False, "error": "short upload",
                        "got": written, "expected": total_body_len})
            return

        got_sha = binascii.hexlify(h.digest()).decode("ascii")
        if got_sha != expected_sha:
            _remove_file(part)
            self._json(client, "400 Bad Request",
                       {"ok": False, "error": "sha256 mismatch",
                        "got": got_sha, "expected": expected_sha})
            return

        # Atomic-ish rename of staging .part -> staging final
        _remove_file(staged)
        try:
            os.rename(part, staged)
        except OSError as e:
            _remove_file(part)
            self._json(client, "500 Internal Server Error",
                       {"ok": False, "error": "rename to staging failed", "detail": str(e)})
            return

        # Promote staging file to live target
        target_dir = target.rsplit("/", 1)[0]
        if target_dir:
            _mkdir_p(target_dir)
        try:
            if _exists(target):
                _remove_file(target)
            os.rename(staged, target)
        except OSError as e:
            self._json(client, "500 Internal Server Error",
                       {"ok": False, "error": "rename to live failed", "detail": str(e),
                        "staged": staged})
            return

        print(f"upload: wrote {target} ({written} bytes, sha {got_sha[:12]}…)")
        self._json(client, "200 OK", {"ok": True, "path": target,
                                       "size": written, "sha256": got_sha})

    def _route(self, method, path, query, body, client):
        if path in ("/", "/index.html"):
            page = "/web/setup.html" if self._wifi.is_ap_mode else "/web/index.html"
            self._serve_static(client, page, "text/html")
            return

        if path == "/style.css":
            self._serve_static(client, "/web/style.css", "text/css")
            return

        if path == "/script.js":
            self._serve_static(client, "/web/script.js", "application/javascript")
            return

        if path == "/common.js":
            self._serve_static(client, "/web/common.js", "application/javascript")
            return

        if path in ("/advanced", "/advanced.html"):
            self._serve_static(client, "/web/advanced.html", "text/html")
            return

        if path == "/advanced.js":
            self._serve_static(client, "/web/advanced.js", "application/javascript")
            return

        if path in ("/files", "/files.html"):
            self._serve_static(client, "/web/files.html", "text/html")
            return

        if path == "/files.js":
            self._serve_static(client, "/web/files.js", "application/javascript")
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

        if path == "/fancontrol/files/list" and method == "GET":
            self._json(client, "200 OK", {"ok": True, "files": _walk_listing()})
            return

        if path == "/fancontrol/files/sha" and method == "GET":
            target = _safe_rel_path(query.get("path", ""))
            if not target or not _exists(target):
                self._json(client, "404 Not Found", {"ok": False, "error": "not found"})
                return
            sha = _sha256_of_file(target)
            if sha is None:
                self._json(client, "500 Internal Server Error", {"ok": False, "error": "read failed"})
                return
            self._json(client, "200 OK",
                       {"ok": True, "path": target, "size": _file_size(target), "sha256": sha})
            return

        if path == "/fancontrol/files/delete" and method == "POST":
            target = _safe_rel_path(query.get("path", ""))
            if not target:
                self._json(client, "400 Bad Request", {"ok": False, "error": "invalid path"})
                return
            if target in PROTECTED:
                self._json(client, "403 Forbidden", {"ok": False, "error": "protected path"})
                return
            if not _exists(target):
                self._json(client, "404 Not Found", {"ok": False, "error": "not found"})
                return
            try:
                os.remove(target)
            except OSError as e:
                self._json(client, "500 Internal Server Error",
                           {"ok": False, "error": "remove failed", "detail": str(e)})
                return
            self._json(client, "200 OK", {"ok": True, "path": target})
            return

        if path == "/fancontrol/reboot" and method == "POST":
            self._json(client, "200 OK", {"ok": True, "rebooting": True})
            try:
                client.close()
            except Exception:
                pass
            time.sleep(1)
            import machine
            machine.reset()
            return

        self._send(client, "404 Not Found", "text/plain", "Not found")

    def _read_headers(self, client):
        """Read until end-of-headers. Returns (headers_text, leftover_body_bytes) or (None, None)."""
        buf = b""
        while True:
            try:
                chunk = client.recv(1024)
            except OSError:
                return None, None
            if not chunk:
                return None, None
            buf += chunk
            idx = buf.find(b"\r\n\r\n")
            if idx >= 0:
                return buf[:idx].decode("utf-8", "replace"), buf[idx+4:]
            if len(buf) > 16384:
                return None, None

    def _content_length(self, headers_text):
        for line in headers_text.split("\r\n"):
            if line.lower().startswith("content-length:"):
                try:
                    return int(line.split(":", 1)[1].strip())
                except ValueError:
                    return 0
        return 0

    def handle_request(self):
        if not self._sock:
            return
        try:
            client, _addr = self._sock.accept()
        except OSError:
            return
        try:
            client.setblocking(True)
            client.settimeout(10.0)

            headers_text, leftover = self._read_headers(client)
            if headers_text is None:
                return

            first_line = headers_text.split("\r\n", 1)[0]
            parts = first_line.split(" ")
            if len(parts) < 2:
                return
            method, raw_path = parts[0], parts[1]
            path, query = _parse_path(raw_path)
            cl = self._content_length(headers_text)

            if path.startswith("/fancontrol/"):
                print(f"{method} {raw_path} (cl={cl})")

            # Streaming upload: do not buffer body in RAM.
            if path == UPLOAD_PATH and method == "POST":
                self._handle_upload(client, query, headers_text, leftover, cl)
                return

            # Buffer remaining body for non-upload requests, with a hard cap.
            body = leftover or b""
            if cl > MAX_NON_UPLOAD_BODY:
                self._json(client, "413 Payload Too Large",
                           {"ok": False, "error": "body too large for this endpoint"})
                return
            while len(body) < cl:
                try:
                    chunk = client.recv(min(1024, cl - len(body)))
                except OSError:
                    break
                if not chunk:
                    break
                body += chunk

            try:
                body_text = body.decode("utf-8")
            except UnicodeError:
                body_text = body.decode("latin1")

            self._route(method, path, query, body_text.strip("\x00").strip(), client)
        except Exception as e:
            print(f"Request error: {e}")
        finally:
            try:
                client.close()
            except Exception:
                pass
