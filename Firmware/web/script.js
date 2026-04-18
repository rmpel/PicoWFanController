const $ = (id) => document.getElementById(id);

const settingFields = [
  "predefined_speed", "boost_speed", "min_speed", "step",
  "hold_threshold_ms", "tach_pulses_per_rev", "pwm_polarity", "device_name",
  "encoder_invert", "led_brightness",
];

// Once the user touches any settings input or its nudge button,
// stop overwriting that field until they Save (or Discard).
const dirty = new Set();

function markDirty(key) {
  if (dirty.has(key)) return;
  dirty.add(key);
  $("save-msg").textContent = "Unsaved changes.";
  $("save-settings").classList.add("dirty");
  $("discard-settings").style.display = "";
}

function clearDirty() {
  dirty.clear();
  $("save-msg").textContent = "";
  $("save-settings").classList.remove("dirty");
  $("discard-settings").style.display = "none";
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
    $("current-speed").textContent = j.speed;
    $("rpm").textContent = j.rpm;
    const tp = $("toggle-power");
    if (tp) tp.textContent = j.fan_enabled ? "Turn fan off" : "Turn fan on";
    $("wifi-status").textContent = j.wifi.mode === "sta"
      ? `${j.wifi.ssid} (${j.wifi.ip})`
      : j.wifi.mode;
    $("device-name-display").textContent = j.device_name;
    document.title = j.device_name;
    if (document.activeElement !== $("speed-input")) {
      $("speed-input").value = j.speed;
    }
    for (const k of settingFields) {
      const el = $(k);
      if (!el) continue;
      if (dirty.has(k) || document.activeElement === el) continue;
      setInput(el, j.settings[k]);
    }
  } catch (e) {
    console.error(e);
  }
}

async function call(path) {
  const r = await fetch(path);
  return r.json();
}

document.querySelectorAll("button[data-action]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const a = btn.dataset.action;
    if (a === "up") await call("/fancontrol/up");
    else if (a === "down") await call("/fancontrol/down");
    else if (a === "push") await call("/fancontrol/push");
    else if (a === "toggle-power") await call("/fancontrol/toggle-power");
    else if (a === "set-speed") {
      const v = parseInt($("speed-input").value, 10);
      if (!isNaN(v)) await call(`/fancontrol/set-speed?speed=${v}`);
    }
    fetchStatus();
  });
});

settingFields.forEach((k) => {
  const el = $(k);
  if (!el) return;
  const evt = el.type === "checkbox" ? "change" : "input";
  el.addEventListener(evt, () => markDirty(k));
});

document.querySelectorAll("button.nudge").forEach((btn) => {
  btn.addEventListener("click", () => {
    const field = btn.dataset.field;
    const dir = parseInt(btn.dataset.dir, 10);
    const el = $(field);
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

$("save-settings").addEventListener("click", async () => {
  const payload = {};
  for (const k of dirty) {
    const el = $(k);
    if (!el) continue;
    const v = readInput(el);
    if (v !== null) payload[k] = v;
  }
  if (Object.keys(payload).length === 0) return;
  const r = await fetch("/fancontrol/settings", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
  const j = await r.json();
  if (j.ok) {
    clearDirty();
    $("save-msg").textContent = "Saved.";
    setTimeout(() => { $("save-msg").textContent = ""; }, 2000);
    fetchStatus();
  } else {
    $("save-msg").textContent = "Save failed.";
  }
});

$("discard-settings").addEventListener("click", () => {
  clearDirty();
  fetchStatus();
});

fetchStatus();
setInterval(fetchStatus, 1500);
