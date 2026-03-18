const width = 32;
const height = 24;

const canvas = document.getElementById("image");
const ctx = canvas.getContext("2d");

const minGradientLabel = document.getElementById("minGradientLabel");
const midGradientLabel = document.getElementById("midGradientLabel");
const maxGradientLabel = document.getElementById("maxGradientLabel");

const minTempEl = document.getElementById("minTemp");
const maxTempEl = document.getElementById("maxTemp");
const avgTempEl = document.getElementById("avgTemp");
const medianTempEl = document.getElementById("medianTemp");
const stdevTempEl = document.getElementById("stdevTemp");
const rangeTempEl = document.getElementById("rangeTemp");
const hotPixelsEl = document.getElementById("hotPixels");
const hotspotStrengthEl = document.getElementById("hotspotStrength");

const histogramEl = document.getElementById("histogram");

let lastData = null;
let blockSize = 20;

// ---------------------------
// GRADIENT (RESTORED EXACT)
// ---------------------------
const gradientSize = 1000;
const gradientLookupTable = [];

const gradientStops = [
  { pos: 0, color: [0, 0, 0] },
  { pos: 0.33, color: [204, 0, 119] },
  { pos: 0.66, color: [255, 215, 0] },
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
    Math.min(wrapper.clientWidth / width, wrapper.clientHeight / height)
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
function temperatureToColor(temp, min, max) {
  const v = (temp - min) / (max - min);
  const i = Math.min(
    Math.max(Math.floor(v * (gradientSize - 1)), 0),
    gradientSize - 1
  );
  const c = gradientLookupTable[i];
  return `rgb(${c[0]},${c[1]},${c[2]})`;
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

// ---------------------------
// HISTOGRAM STATE
// ---------------------------
const histogramHistory = [];
const maxHistory = 10;

// ---------------------------
// MAIN DRAW
// ---------------------------
function drawHeatmap(data) {
  mirrorThermalImage(data);

  let min = data[0];
  let max = data[0];
  let minIdx = 0;
  let maxIdx = 0;

  let sum = 0;

  for (let i = 0; i < data.length; i++) {
    const v = data[i];
    sum += v;

    if (v < min) {
      min = v;
      minIdx = i;
    }
    if (v > max) {
      max = v;
      maxIdx = i;
    }
  }

  const avg = sum / data.length;
  const mid = (min + max) / 2;

  // gradient labels
  minGradientLabel.textContent = `${min.toFixed(1)}°C`;
  midGradientLabel.textContent = `${mid.toFixed(1)}°C`;
  maxGradientLabel.textContent = `${max.toFixed(1)}°C`;

  // draw heatmap
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const v = data[y * width + x];
      ctx.fillStyle = temperatureToColor(v, min, max);
      ctx.fillRect(x * blockSize, y * blockSize, blockSize, blockSize);
    }
  }

  // -------- stats --------
  const sorted = Array.from(data).sort((a, b) => a - b);
  const median = sorted[Math.floor(sorted.length / 2)];

  let variance = 0;
  let hotPixels = 0;
  const hotThreshold = 60;

  for (let v of data) {
    const d = v - avg;
    variance += d * d;
    if (v > hotThreshold) hotPixels++;
  }

  const stdev = Math.sqrt(variance / data.length);
  const range = max - min;
  const hotspotStrength = max - median;

  minTempEl.textContent = `Min: ${min.toFixed(1)} °C`;
  maxTempEl.textContent = `Max: ${max.toFixed(1)} °C`;
  avgTempEl.textContent = `Avg: ${avg.toFixed(1)} °C`;
  medianTempEl.textContent = `Median: ${median.toFixed(1)} °C`;
  stdevTempEl.textContent = `Std Dev: ${stdev.toFixed(2)}`;
  rangeTempEl.textContent = `Range: ${range.toFixed(1)} °C`;
  hotPixelsEl.textContent = `Hot Pixels: ${hotPixels}`;
  hotspotStrengthEl.textContent = `Hotspot Strength: ${hotspotStrength.toFixed(
    1
  )} °C`;

  // -------- histogram --------
  histogramHistory.push([...data]);
  if (histogramHistory.length > maxHistory) histogramHistory.shift();

  const traces = histogramHistory.map((arr, i) => ({
    x: arr,
    type: "histogram",
    opacity: 0.2 + (0.8 * (i + 1)) / histogramHistory.length,
    marker: { color: "#00d1ff" },
    autobinx: false,
    xbins: { start: 20, end: 80, size: 1 },
  }));

  Plotly.react(
    histogramEl,
    traces,
    {
      margin: { t: 20, l: 40, r: 20, b: 40 },
      barmode: "overlay",
      paper_bgcolor: "#0f0f1a",
      plot_bgcolor: "#1a1a2e",
      font: { color: "#eee" },
    },
    { displayModeBar: false }
  );
}

// ---------------------------
// FETCH LOOP (EXACT TIMING)
// ---------------------------
function fetchLoop() {
  const start = Date.now();
  const minDelay = 2000; // 2 Hz

  fetch("/byte_array")
    .then((r) => r.arrayBuffer())
    .then((buf) => {
      const data = new Float32Array(buf);

      if (data.length === width * height) {
        lastData = data;
        drawHeatmap(data);
      }
    })
    .catch(console.error)
    .finally(() => {
      const elapsed = Date.now() - start;
      setTimeout(fetchLoop, Math.max(minDelay - elapsed, 0));
    });
}

fetchLoop();

// ---------------------------
// RESET
// ---------------------------
const modal = document.getElementById("resetModal");

document.getElementById("resetButton").onclick = () => {
  modal.classList.add("active");
};

document.getElementById("cancelReset").onclick = () => {
  modal.classList.remove("active");
};

document.getElementById("confirmReset").onclick = () => {
  fetch("/hw_reset");
};
