(function () {
const byId = (id) => document.getElementById(id);

const dirty = new Set();
let settingFields = [];
let onStatus = null;

function markDirty(key) {
  if (dirty.has(key)) return;
  dirty.add(key);
  const msg = byId("save-msg");
  if (msg) msg.textContent = "Unsaved changes.";
  const save = byId("save-settings");
  if (save) save.classList.add("dirty");
  const discard = byId("discard-settings");
  if (discard) discard.style.display = "";
}

function clearDirty() {
  dirty.clear();
  const msg = byId("save-msg");
  if (msg) msg.textContent = "";
  const save = byId("save-settings");
  if (save) save.classList.remove("dirty");
  const discard = byId("discard-settings");
  if (discard) discard.style.display = "none";
}

function setInput(el, value) {
  if (el.type === "checkbox") {
    el.checked = !!value;
  } else {
    el.value = value ?? "";
  }
}

function readInput(el) {
  if (el.type === "number") {
    const v = parseInt(el.value, 10);
    return isNaN(v) ? null : v;
  }
  if (el.type === "checkbox") return el.checked;
  return el.value;
}

async function fetchStatus() {
  try {
    const r = await fetch("/fancontrol/status");
    const j = await r.json();
    const nameEl = byId("device-name-display");
    if (nameEl) nameEl.textContent = j.device_name;
    document.title = j.device_name;
    const wifi = byId("wifi-status");
    if (wifi) {
      wifi.textContent = j.wifi.mode === "sta"
        ? `${j.wifi.ssid} (${j.wifi.ip})`
        : j.wifi.mode;
    }
    for (const k of settingFields) {
      const el = byId(k);
      if (!el) continue;
      if (dirty.has(k) || document.activeElement === el) continue;
      setInput(el, j.settings[k]);
    }
    if (onStatus) onStatus(j);
  } catch (e) {
    console.error(e);
  }
}

async function call(path) {
  const r = await fetch(path);
  return r.json();
}

function wireSettingField(key) {
  const el = byId(key);
  if (!el) return;
  const evt = el.type === "checkbox" ? "change" : "input";
  el.addEventListener(evt, () => markDirty(key));
}

function wireNudges() {
  document.querySelectorAll("button.nudge").forEach((btn) => {
    btn.addEventListener("click", () => {
      const field = btn.dataset.field;
      const dir = parseInt(btn.dataset.dir, 10);
      const el = byId(field);
      if (!el) return;
      const cur = parseInt(el.value, 10) || 0;
      const min = parseInt(el.min, 10);
      const max = parseInt(el.max, 10);
      let next = cur + dir;
      if (!isNaN(min)) next = Math.max(min, next);
      if (!isNaN(max)) next = Math.min(max, next);
      el.value = next;
      markDirty(field);
    });
  });
}

function wireSave(buildPayload) {
  const save = byId("save-settings");
  if (save) {
    save.addEventListener("click", async () => {
      const payload = buildPayload ? buildPayload(dirty) : defaultPayload();
      if (!payload || Object.keys(payload).length === 0) return;
      const r = await fetch("/fancontrol/settings", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
      });
      const j = await r.json();
      const msg = byId("save-msg");
      if (j.ok) {
        clearDirty();
        if (msg) {
          msg.textContent = "Saved.";
          setTimeout(() => { msg.textContent = ""; }, 2000);
        }
        fetchStatus();
      } else if (msg) {
        msg.textContent = "Save failed.";
      }
    });
  }
  const discard = byId("discard-settings");
  if (discard) {
    discard.addEventListener("click", () => {
      clearDirty();
      fetchStatus();
    });
  }
}

function defaultPayload() {
  const payload = {};
  for (const k of dirty) {
    const el = byId(k);
    if (!el) continue;
    const v = readInput(el);
    if (v !== null) payload[k] = v;
  }
  return payload;
}

function initSettings(fields, opts) {
  settingFields = fields.slice();
  onStatus = (opts && opts.onStatus) || null;
  fields.forEach(wireSettingField);
  wireNudges();
  wireSave(opts && opts.buildPayload);
  fetchStatus();
  setInterval(fetchStatus, 1500);
}

window.fanui = {
  $: byId, markDirty, clearDirty, setInput, readInput,
  fetchStatus, call, initSettings, defaultPayload,
  dirty,
};
})();
