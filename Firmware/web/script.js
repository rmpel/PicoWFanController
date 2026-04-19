const { $, call, initSettings } = window.fanui;

const settingFields = [
  "predefined_speed", "boost_speed", "min_speed", "step",
  "hold_threshold_ms", "tach_pulses_per_rev", "led_brightness",
];

function onStatus(j) {
  $("current-speed").textContent = j.speed;
  $("rpm").textContent = j.rpm;
  const tp = $("toggle-power");
  if (tp) tp.textContent = j.fan_enabled ? "Turn fan off" : "Turn fan on";
  if (document.activeElement !== $("speed-input")) {
    $("speed-input").value = j.speed;
  }
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
    window.fanui.fetchStatus();
  });
});

initSettings(settingFields, { onStatus });
