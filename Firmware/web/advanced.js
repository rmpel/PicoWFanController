const { $, initSettings, markDirty, dirty } = window.fanui;

const settingFields = [
  "device_name", "pwm_polarity", "encoder_invert", "led_invert",
];

let ledCount = 0;
let correctionBuilt = false;

function buildGrid(count, values) {
  const grid = $("led-correction-grid");
  grid.innerHTML = "";
  for (let i = 0; i < count; i++) {
    const cell = document.createElement("label");
    cell.className = "led-cell";

    const label = document.createElement("span");
    label.textContent = `LED ${i}`;
    cell.appendChild(label);

    const input = document.createElement("input");
    input.type = "number";
    input.min = 0;
    input.max = 100;
    input.step = 1;
    input.value = values[i] ?? 100;
    input.dataset.idx = i;
    input.addEventListener("input", () => markDirty("led_correction"));
    cell.appendChild(input);

    grid.appendChild(cell);
  }
  correctionBuilt = true;
}

function readCorrection() {
  const inputs = $("led-correction-grid").querySelectorAll("input");
  const out = [];
  inputs.forEach((el) => {
    let v = parseInt(el.value, 10);
    if (isNaN(v)) v = 100;
    if (v < 0) v = 0;
    if (v > 100) v = 100;
    out.push(v);
  });
  return out;
}

function onStatus(j) {
  const n = j.led_count || 0;
  const values = j.settings.led_correction || [];
  if (!correctionBuilt || n !== ledCount) {
    ledCount = n;
    buildGrid(n, values);
  } else if (!dirty.has("led_correction")) {
    const inputs = $("led-correction-grid").querySelectorAll("input");
    inputs.forEach((el, i) => {
      if (document.activeElement !== el) {
        el.value = values[i] ?? 100;
      }
    });
  }
}

function buildPayload(dirtySet) {
  const payload = {};
  for (const k of dirtySet) {
    if (k === "led_correction") continue;
    const el = $(k);
    if (!el) continue;
    if (el.type === "checkbox") payload[k] = el.checked;
    else if (el.type === "number") {
      const v = parseInt(el.value, 10);
      if (!isNaN(v)) payload[k] = v;
    } else payload[k] = el.value;
  }
  if (dirtySet.has("led_correction")) {
    payload.led_correction = readCorrection();
  }
  return payload;
}

$("correction-reset").addEventListener("click", () => {
  const inputs = $("led-correction-grid").querySelectorAll("input");
  inputs.forEach((el) => { el.value = 100; });
  markDirty("led_correction");
});

initSettings(settingFields, { onStatus, buildPayload });
