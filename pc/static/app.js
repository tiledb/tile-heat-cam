// ---------------------------
// CONFIG
// ---------------------------
const width = 32;
const height = 24;

const canvas = document.getElementById("image");
const ctx = canvas.getContext("2d");

const cursorInfoEl = document.getElementById("cursorInfo");

// Gradient labels
const minGradientLabel = document.getElementById("minGradientLabel");
const midGradientLabel = document.getElementById("midGradientLabel");
const maxGradientLabel = document.getElementById("maxGradientLabel");

// Stats elements
const minTempEl = document.getElementById("minTemp");
const maxTempEl = document.getElementById("maxTemp");
const avgTempEl = document.getElementById("avgTemp");
const medianTempEl = document.getElementById("medianTemp");
const stdevTempEl = document.getElementById("stdevTemp");
const rangeTempEl = document.getElementById("rangeTemp");
const burnInEl = document.getElementById("burnInPixels");
const overtempEl = document.getElementById("overtempPixels");
const hotspotStrengthEl = document.getElementById("hotspotStrength");

const centerEl = document.getElementById("centerPos");
const hotspotEl = document.getElementById("hotspotPos");
const coldspotEl = document.getElementById("coldspotPos");

const p10El = document.getElementById("p10Val");
const p90El = document.getElementById("p90Val");
const hotAreaEl = document.getElementById("hotArea");

// Histogram
const histogramEl = document.getElementById("histogram");

let lastData = null;
let blockSize = 20;
let hoverPos = null;

// ---------------------------
// GRADIENT / SCALE
// ---------------------------
const dynamicScaleToggle = document.getElementById("dynamicScaleToggle");
const gammaSlider = document.getElementById("gammaSlider");
const gammaValueEl = document.getElementById("gammaValue");

let useDynamicScale = dynamicScaleToggle.checked;
let gamma = parseFloat(gammaSlider.value);

dynamicScaleToggle.addEventListener("change", () => {
  useDynamicScale = dynamicScaleToggle.checked;
  if (lastData) drawHeatmap(lastData);
});
gammaSlider.addEventListener("input", () => {
  gamma = parseFloat(gammaSlider.value);
  gammaValueEl.textContent = gamma.toFixed(2);
  if (lastData) drawHeatmap(lastData);
});

const fixedMin = 25;
const fixedMax = 75;

const gradientSize = 1000;
const gradientLookupTable = [];
const gradientStops = [
  { pos: 0, color: [0, 0, 0] },
  { pos: 0.1, color: [50, 0, 100] },
  { pos: 0.25, color: [204, 0, 119] },
  { pos: 0.45, color: [255, 70, 0] },
  { pos: 0.6, color: [255, 140, 0] },
  { pos: 0.75, color: [255, 215, 0] },
  { pos: 0.9, color: [255, 240, 200] },
  { pos: 1, color: [255, 255, 255] },
];

for (let i = 0; i < gradientSize; ++i) {
  const pos = i / (gradientSize - 1);
  for (let j = 0; j < gradientStops.length - 1; ++j) {
    const start = gradientStops[j];
    const end = gradientStops[j + 1];
    if (pos >= start.pos && (pos < end.pos || end.pos === 1)) {
      const local = (pos - start.pos) / (end.pos - start.pos);
      const r = start.color[0] + local * (end.color[0] - start.color[0]);
      const g = start.color[1] + local * (end.color[1] - start.color[1]);
      const b = start.color[2] + local * (end.color[2] - start.color[2]);
      gradientLookupTable.push([r | 0, g | 0, b | 0]);
      break;
    }
  }
}

// ---------------------------
// RESIZE
// ---------------------------
function resizeCanvas() {
  const wrapper = document.getElementById("heatmap-wrapper");
  blockSize = Math.floor(
    Math.min(wrapper.clientWidth / width, wrapper.clientHeight / height),
  );
  canvas.width = width * blockSize;
  canvas.height = height * blockSize;
  if (lastData) drawHeatmap(lastData);
}
window.addEventListener("resize", resizeCanvas);
resizeCanvas();

// ---------------------------
// HELPERS
// ---------------------------
function temperatureToColorEnhanced(temp, maxVal, data = null) {
  let minVal = fixedMin;
  let maxValLocal = fixedMax;

  if (useDynamicScale && data) {
    minVal = Math.min(...data);
    maxValLocal = Math.max(...data);
  }

  const clamped = Math.min(Math.max(temp, minVal), maxValLocal);
  let v = (clamped - minVal) / (maxValLocal - minVal);
  v = Math.pow(v, gamma);

  const i = Math.min(Math.floor(v * (gradientSize - 1)), gradientSize - 1);
  let [r, g, b] = gradientLookupTable[i];

  return [r, g, b];
}

function mirrorThermalImage(data) {
  for (let y = 0; y < height; ++y) {
    for (let x = 0; x < width / 2; ++x) {
      const i1 = y * width + x;
      const i2 = y * width + (width - x - 1);
      const tmp = data[i1];
      data[i1] = data[i2];
      data[i2] = tmp;
    }
  }
}

function updateLED(id, state) {
  const el = document.getElementById(id);
  if (state) {
    el.classList.add("red");
    el.classList.remove("green");
  } else {
    el.classList.add("green");
    el.classList.remove("red");
  }
}

// ---------------------------
// DRAW HEATMAP
// ---------------------------

// ---------------------------
// Gradient bar update
// ---------------------------
function updateGradientBarDynamic() {
  const bar = document.querySelector(".gradient-bar");
  const steps = 100; // number of steps for gradient
  const colors = [];

  for (let i = 0; i <= steps; i++) {
    let t = i / steps;
    t = Math.pow(t, gamma);

    let r = 0,
      g = 0,
      b = 0;
    for (let j = 0; j < gradientStops.length - 1; j++) {
      const start = gradientStops[j];
      const end = gradientStops[j + 1];
      if (t >= start.pos && (t <= end.pos || j === gradientStops.length - 2)) {
        const local = (t - start.pos) / (end.pos - start.pos);
        r = start.color[0] + local * (end.color[0] - start.color[0]);
        g = start.color[1] + local * (end.color[1] - start.color[1]);
        b = start.color[2] + local * (end.color[2] - start.color[2]);
        break;
      }
    }
    colors.push(`rgb(${r | 0},${g | 0},${b | 0})`);
  }

  if (bar)
    bar.style.background = `linear-gradient(to right, ${colors.join(",")})`;
}

function drawHeatmap(data) {
  updateGradientBarDynamic();

  const sorted = Array.from(data).sort((a, b) => a - b);
  const median = sorted[Math.floor(sorted.length / 2)];

  let min = data[0],
    max = data[0],
    sum = 0;
  let burnInPixels = 0,
    overtempPixels = 0,
    hotArea = 0;

  let hotspotVal = -Infinity,
    hotspotIdx = 0;
  let coldspotVal = Infinity,
    coldspotIdx = 0;
  let centerSum = 0;

  const burnInLow = 65,
    burnInHigh = 70,
    overtempThreshold = 70;

  for (let i = 0; i < data.length; i++) {
    const v = data[i];
    sum += v;
    if (v >= burnInLow && v <= burnInHigh) burnInPixels++;
    if (v > overtempThreshold) {
      overtempPixels++;
      hotArea++;
    }
    if (v < min) {
      min = v;
      coldspotVal = v;
      coldspotIdx = i;
    }
    if (v > max) {
      max = v;
      hotspotVal = v;
      hotspotIdx = i;
    }
    centerSum += v;
  }

  const avg = sum / data.length;
  const stdev = Math.sqrt(
    data.reduce((a, v) => a + (v - avg) ** 2, 0) / data.length,
  );
  const range = max - min;
  const hotspotStrength = max - median;
  const center = centerSum / data.length;

  const h_x = hotspotIdx % width,
    h_y = Math.floor(hotspotIdx / width);
  const c_x = coldspotIdx % width,
    c_y = Math.floor(coldspotIdx / width);

  // Gradient labels
  if (useDynamicScale) {
    const currMin = Math.min(...data);
    const currMax = Math.max(...data);
    minGradientLabel.textContent = `${currMin.toFixed(1)}°C`;
    midGradientLabel.textContent = `${((currMin + currMax) / 2).toFixed(1)}°C`;
    maxGradientLabel.textContent = `${currMax.toFixed(1)}°C`;
  } else {
    minGradientLabel.textContent = `${fixedMin.toFixed(1)}°C`;
    midGradientLabel.textContent = `${((fixedMin + fixedMax) / 2).toFixed(1)}°C`;
    maxGradientLabel.textContent = `${fixedMax.toFixed(1)}°C`;
  }

  // Draw pixels
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const v = data[y * width + x];
      const color = temperatureToColorEnhanced(v, max, data);
      ctx.fillStyle = `rgb(${color[0]},${color[1]},${color[2]})`;
      ctx.fillRect(x * blockSize, y * blockSize, blockSize, blockSize);
    }
  }

  // Grid
  ctx.strokeStyle = "rgba(255,255,255,0.1)";
  ctx.lineWidth = 1;
  for (let x = 0; x <= width; x++) {
    ctx.beginPath();
    ctx.moveTo(x * blockSize, 0);
    ctx.lineTo(x * blockSize, height * blockSize);
    ctx.stroke();
  }
  for (let y = 0; y <= height; y++) {
    ctx.beginPath();
    ctx.moveTo(0, y * blockSize);
    ctx.lineTo(width * blockSize, y * blockSize);
    ctx.stroke();
  }

  // Max pixel glow
  ctx.strokeStyle = "white";
  ctx.lineWidth = 2;
  ctx.shadowColor = "white";
  ctx.shadowBlur = 15;
  ctx.strokeRect(h_x * blockSize, h_y * blockSize, blockSize, blockSize);
  ctx.shadowBlur = 0;

  // Stats panel
  updateStatsPanel({
    min,
    max,
    avg,
    median,
    stdev,
    range,
    burn_in_pixels: burnInPixels,
    overtemp_pixels: overtempPixels,
    hotspot_strength: hotspotStrength,
    center,
    hotspot_x: h_x,
    hotspot_y: h_y,
    coldspot_x: c_x,
    coldspot_y: c_y,
    p10: sorted[Math.floor(0.1 * sorted.length)],
    p90: sorted[Math.floor(0.9 * sorted.length)],
    hot_area: hotArea,
    overheat: overtempPixels > 0,
    burn_in_risk: burnInPixels > 0,
  });

  // Histogram
  let histMin = fixedMin,
    histMax = fixedMax;
  if (useDynamicScale && data) {
    histMin = Math.min(...data);
    histMax = Math.max(...data);
  }
  Plotly.react(
    histogramEl,
    [
      {
        x: data,
        type: "histogram",
        marker: { color: "#00d1ff" },
        autobinx: false,
        xbins: { start: histMin, end: histMax, size: 1 },
      },
    ],
    {
      margin: { t: 20, l: 40, r: 20, b: 40 },
      barmode: "overlay",
      paper_bgcolor: "#0f0f1a",
      plot_bgcolor: "#1a1a2e",
      font: { color: "#eee" },
      xaxis: { range: [histMin, histMax] },
    },
    { displayModeBar: false },
  );
}

// ---------------------------
// STATS PANEL
// ---------------------------
function updateStatsPanel(stats) {
  minTempEl.textContent = `Min: ${stats.min.toFixed(1)} °C`;
  maxTempEl.textContent = `Max: ${stats.max.toFixed(1)} °C`;
  avgTempEl.textContent = `Avg: ${stats.avg.toFixed(1)} °C`;
  medianTempEl.textContent = `Median: ${stats.median.toFixed(1)} °C`;
  stdevTempEl.textContent = `Std Dev: ${stats.stdev.toFixed(2)}`;
  rangeTempEl.textContent = `Range: ${stats.range.toFixed(1)} °C`;
  burnInEl.textContent = `Burn-In Pixels (65–70°C): ${stats.burn_in_pixels}`;
  overtempEl.textContent = `OverTemp Pixels (>70°C): ${stats.overtemp_pixels}`;
  hotspotStrengthEl.textContent = `Hotspot Strength: ${stats.hotspot_strength.toFixed(1)} °C`;
  centerEl.textContent = `Center: ${stats.center.toFixed(2)}`;
  hotspotEl.textContent = `Hotspot (x,y): ${stats.hotspot_x},${stats.hotspot_y}`;
  coldspotEl.textContent = `Coldspot (x,y): ${stats.coldspot_x},${stats.coldspot_y}`;
  p10El.textContent = `P10: ${stats.p10.toFixed(2)}`;
  p90El.textContent = `P90: ${stats.p90.toFixed(2)}`;
  hotAreaEl.textContent = `Hot Area (>70°C): ${stats.hot_area}`;
  updateLED("overheatFlag", stats.overheat);
  updateLED("burnInFlag", stats.burn_in_risk);
}

// ---------------------------
// PLAYBACK / HISTORY
// ---------------------------
const historySlider = document.getElementById("historySlider");
const historySliderLabel = document.getElementById("historySliderLabel");
const playButton = document.getElementById("playHistory");
const liveButton = document.getElementById("liveButton");
const startInput = document.getElementById("startTime");
const endInput = document.getElementById("endTime");
const applyButton = document.getElementById("applyRange");
const playSpeedSelect = document.getElementById("playSpeed");
let playbackSpeed = parseInt(playSpeedSelect.value, 10);

playSpeedSelect.addEventListener("change", () => {
  playbackSpeed = parseInt(playSpeedSelect.value, 10);
});

let historyFrames = [];
let historyStats = [];
let historyTimes = [];
let useLiveData = true;
let playInterval = null;

applyButton.addEventListener("click", async () => {
  const startVal = startInput.value;
  const endVal = endInput.value;

  if (!startVal && !endVal) {
    alert("Select at least one time bound");
    return;
  }

  // Convert to ISO (Influx expects this)
  const startISO = startVal ? new Date(startVal).toISOString() : null;
  const endISO = endVal ? new Date(endVal).toISOString() : null;

  let url = "/history?";
  if (startISO) url += `start=${encodeURIComponent(startISO)}&`;
  if (endISO) url += `end=${encodeURIComponent(endISO)}`;

  try {
    const res = await fetch(url);
    const json = await res.json();

    historyFrames = json.frames;
    historyStats = json.stats;
    historyTimes = json.times;

    historySlider.max = historyFrames.length - 1;
    historySlider.value = historyFrames.length - 1;

    useLiveData = false;

    if (historyFrames.length > 0) {
      lastData = historyFrames[historyFrames.length - 1].flat();
      drawHeatmap(lastData);
      updateStatsPanel(historyStats[historyStats.length - 1]);

      const ts = new Date(historyTimes[historyTimes.length - 1]);
      historySliderLabel.textContent = `Time: ${ts.toLocaleString()}`;
    }
  } catch (err) {
    console.error(err);
  }
});

startInput.addEventListener("change", () => {
  if (!endInput.value) {
    endInput.value = new Date().toISOString().slice(0, 16);
  }
});

function updateLiveLabel() {
  const now = new Date();

  historySliderLabel.textContent = `Live • ${now.toLocaleTimeString()}`;

  historySliderLabel.classList.add("live");
  liveButton.classList.add("active");
}

async function fetchHistory(startTime = null) {
  try {
    const url = startTime
      ? `/history?start=${encodeURIComponent(startTime)}`
      : "/history";
    const res = await fetch(url);
    const json = await res.json();
    historyFrames = json.frames;
    historyStats = json.stats;
    historyTimes = json.times; // <--- store timestamps
    historySlider.max = historyFrames.length;
    historySlider.value = historyFrames.length;
  } catch (err) {
    console.error(err);
  }
}

function updateFromSlider() {
  let idx = parseInt(historySlider.value, 10);

  // Clamp to valid range
  if (idx >= historyFrames.length) {
    idx = historyFrames.length - 1;
  }
  if (idx < 0) idx = 0;

  const frame = historyFrames[idx];
  const stats = historyStats[idx];

  // Safety check
  if (!frame || !stats) {
    console.warn("Missing frame/stats at index:", idx);
    return;
  }

  lastData = frame.flat();
  drawHeatmap(lastData);
  updateStatsPanel(stats);

  const ts = new Date(historyTimes[idx]);
  historySliderLabel.textContent = `Time: ${ts.toLocaleString()}`;
}

historySlider.addEventListener("input", updateFromSlider);

liveButton.addEventListener("click", async () => {
  // Stop playback if running
  if (playInterval) {
    clearInterval(playInterval);
    playInterval = null;
    playButton.textContent = "▶";
    playButton.classList.remove("active");
  }

  useLiveData = true;

  // Jump slider to end
  historySlider.value = historyFrames.length;

  // Force immediate fetch + draw
  try {
    const r = await fetch("/byte_array");
    const buf = await r.arrayBuffer();
    const data = new Float32Array(buf);

    if (data.length === width * height) {
      lastData = data;
      drawHeatmap(data);
    }
  } catch (err) {
    console.error(err);
  }

  updateLiveLabel();
});

playButton.addEventListener("click", () => {
  if (playInterval) {
    clearInterval(playInterval);
    playInterval = null;
    playButton.textContent = "▶";
    playButton.classList.remove("active");
    return;
  }

  playButton.textContent = "⏸";
  playButton.classList.add("active");

  let idx = parseInt(historySlider.value, 10);

  playInterval = setInterval(() => {
    if (idx > historyFrames.length - 1) {
      clearInterval(playInterval);
      playInterval = null;

      useLiveData = true;
      playButton.textContent = "▶";
      playButton.classList.remove("active");

      updateLiveLabel();
      return;
    }

    // 🔥 KEY: skip frames instead of speeding timer
    const step = playbackSpeed;

    const safeIdx = Math.min(idx, historyFrames.length - 1);

    const frame = historyFrames[safeIdx];
    const stats = historyStats[safeIdx];

    if (frame && stats) {
      lastData = frame.flat();
      drawHeatmap(lastData);
      updateStatsPanel(stats);

      const ts = new Date(historyTimes[safeIdx]);
      historySliderLabel.textContent = `Time: ${ts.toLocaleString()}`;
    }

    historySlider.value = safeIdx;

    idx += step;
  }, 33); // ~30 FPS (stable & smooth)
});

// ---------------------------
// LIVE FETCH LOOP
// ---------------------------
async function fetchLoop() {
  const start = Date.now();
  const minDelay = 2000;

  if (useLiveData) {
    fetch("/byte_array")
      .then((r) => r.arrayBuffer())
      .then((buf) => {
        const data = new Float32Array(buf);
        if (data.length === width * height) {
          lastData = data;
          drawHeatmap(data);

          // ✅ keep time updating in LIVE mode
          updateLiveLabel();
        }
      })
      .catch(console.error);
  }

  const elapsed = Date.now() - start;
  setTimeout(fetchLoop, Math.max(minDelay - elapsed, 0));
}

// ---------------------------
// RESET MODAL
// ---------------------------
const modal = document.getElementById("resetModal");
document.getElementById("resetButton").onclick = () =>
  modal.classList.add("active");
document.getElementById("cancelReset").onclick = () =>
  modal.classList.remove("active");
document.getElementById("confirmReset").onclick = () => fetch("/hw_reset");

// ---------------------------
// CURSOR HOVER
// ---------------------------
canvas.addEventListener("mousemove", (e) => {
  if (!lastData) return;
  const rect = canvas.getBoundingClientRect();
  const x = Math.floor((e.clientX - rect.left) / blockSize);
  const y = Math.floor((e.clientY - rect.top) / blockSize);
  if (x >= 0 && x < width && y >= 0 && y < height) {
    const temp = lastData[y * width + x];
    cursorInfoEl.textContent = `Hover: x=${x}, y=${y}, temp=${temp.toFixed(1)}°C`;
    hoverPos = { x, y };
  } else {
    cursorInfoEl.textContent = "Hover: --";
    hoverPos = null;
  }
  drawHeatmap(lastData);
});
canvas.addEventListener("mouseleave", () => {
  cursorInfoEl.textContent = "Hover: --";
  hoverPos = null;
  drawHeatmap(lastData);
});

// ---------------------------
// INIT
// ---------------------------
fetchHistory().then(() => {
  historySlider.value = historyFrames.length;
  useLiveData = true;
});
fetchLoop();

document.addEventListener("DOMContentLoaded", () => {
  const now = new Date();
  const fiveMinAgo = new Date(now.getTime() - 5 * 60 * 1000);

  // Format for datetime-local (YYYY-MM-DDTHH:MM)
  function toLocalInputFormat(date) {
    const pad = (n) => n.toString().padStart(2, "0");
    return (
      date.getFullYear() +
      "-" +
      pad(date.getMonth() + 1) +
      "-" +
      pad(date.getDate()) +
      "T" +
      pad(date.getHours()) +
      ":" +
      pad(date.getMinutes())
    );
  }

  startInput.value = toLocalInputFormat(fiveMinAgo);
  endInput.value = toLocalInputFormat(now);
});
