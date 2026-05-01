const state = {
  selected: MODEL_LINEAGE.models[0].id,
  validation: 0.55,
  expertReview: 0.45,
  iterations: 8
};

const $ = (selector) => document.querySelector(selector);

function average(key) {
  const values = MODEL_LINEAGE.models.map((model) => model.scores[key]);
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function amplificationAt(step) {
  const models = MODEL_LINEAGE.models.length;
  const surfaceComplexity =
    1 + step * (average("coherence") + average("novelty")) * 0.55;
  const validation = Math.max(0.05, state.validation);
  const expertReview = Math.max(0.05, state.expertReview);
  return (models * Math.max(1, step) * surfaceComplexity) / (validation * expertReview);
}

function simulationRows() {
  const rows = [];
  let apparentCoherence = 0.34;
  let auditPressure = 0.12;
  let risk = 0.58;

  for (let step = 1; step <= state.iterations; step += 1) {
    const amplification = amplificationAt(step);
    const reviewForce = (state.validation + state.expertReview) / 2;
    apparentCoherence = clamp(
      apparentCoherence + Math.log1p(amplification) * 0.018 + average("coherence") * 0.018,
      0,
      1
    );
    auditPressure = clamp(auditPressure + reviewForce * 0.075, 0, 1);
    risk = clamp(
      risk + Math.log1p(amplification) * 0.012 - reviewForce * 0.095,
      0,
      1
    );
    rows.push({ step, amplification, apparentCoherence, auditPressure, risk });
  }

  return rows;
}

function pairwiseDistance(a, b) {
  const keys = Object.keys(a.scores);
  const sum = keys.reduce((total, key) => {
    const diff = a.scores[key] - b.scores[key];
    return total + diff * diff;
  }, 0);
  return Math.sqrt(sum / keys.length);
}

function renderSummary() {
  $("#mission").textContent = MODEL_LINEAGE.mission;
  $("#model-count").textContent = MODEL_LINEAGE.models.length;
  $("#coherence-score").textContent = Math.round(average("coherence") * 100);
  $("#risk-score").textContent = Math.round(average("hallucination_risk") * 100);
  $("#validation-score").textContent = Math.round(average("validation_pressure") * 100);
}

function renderTimeline() {
  const container = $("#timeline");
  container.innerHTML = "";
  MODEL_LINEAGE.models.forEach((model, index) => {
    const button = document.createElement("button");
    button.className = `timeline-item ${state.selected === model.id ? "active" : ""}`;
    button.type = "button";
    button.innerHTML = `
      <span>${String(index + 1).padStart(2, "0")}</span>
      <strong>${model.name}</strong>
      <small>${model.phase}</small>
    `;
    button.addEventListener("click", () => {
      state.selected = model.id;
      render();
    });
    container.appendChild(button);
  });
}

function renderModelDetail() {
  const model = MODEL_LINEAGE.models.find((item) => item.id === state.selected);
  $("#detail-title").textContent = `${model.name} - ${model.phase}`;
  $("#detail-role").textContent = model.role;
  $("#detail-contribution").textContent = model.contribution;
  $("#detail-strengthened").textContent = model.strengthened;
  $("#detail-weakened").textContent = model.weakened;
  $("#detail-style").textContent = model.decision_style;
  $("#detail-status").textContent = model.validation_status;

  const scoreRows = $("#score-rows");
  scoreRows.innerHTML = "";
  Object.entries(model.scores).forEach(([key, value]) => {
    const row = document.createElement("div");
    row.className = "score-row";
    row.innerHTML = `
      <span>${key.replaceAll("_", " ")}</span>
      <b>${Math.round(value * 100)}</b>
      <i style="--value:${value}"></i>
    `;
    scoreRows.appendChild(row);
  });
}

function renderSimulation() {
  const rows = simulationRows();
  const last = rows[rows.length - 1];
  $("#amp-output").textContent = last.amplification.toFixed(1);
  $("#sim-risk").textContent = `${Math.round(last.risk * 100)}%`;
  $("#sim-coherence").textContent = `${Math.round(last.apparentCoherence * 100)}%`;
  $("#sim-audit").textContent = `${Math.round(last.auditPressure * 100)}%`;

  const width = 760;
  const height = 270;
  const pad = 34;
  const maxAmp = Math.max(...rows.map((row) => row.amplification));
  const x = (step) => pad + ((step - 1) / Math.max(1, state.iterations - 1)) * (width - pad * 2);
  const y = (value) => height - pad - value * (height - pad * 2);
  const ampY = (value) => {
    const normalized = Math.log1p(value) / Math.log1p(maxAmp);
    return y(normalized);
  };
  const poly = (points) => points.map(([px, py]) => `${px.toFixed(1)},${py.toFixed(1)}`).join(" ");

  $("#simulation-chart").innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Model lineage simulation chart">
      <rect x="0" y="0" width="${width}" height="${height}" rx="8" fill="#0f172a"></rect>
      <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" stroke="#64748b"></line>
      <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" stroke="#64748b"></line>
      <polyline points="${poly(rows.map((row) => [x(row.step), ampY(row.amplification)]))}" fill="none" stroke="#f59e0b" stroke-width="4"></polyline>
      <polyline points="${poly(rows.map((row) => [x(row.step), y(row.risk)]))}" fill="none" stroke="#ef4444" stroke-width="4"></polyline>
      <polyline points="${poly(rows.map((row) => [x(row.step), y(row.apparentCoherence)]))}" fill="none" stroke="#22c55e" stroke-width="4"></polyline>
      <text x="48" y="32" fill="#e2e8f0" font-size="14">orange: amplification | red: risk | green: apparent coherence</text>
    </svg>
  `;
}

function renderMatrix() {
  const matrix = $("#matrix");
  matrix.innerHTML = "";
  MODEL_LINEAGE.models.forEach((left) => {
    MODEL_LINEAGE.models.forEach((right) => {
      const distance = left.id === right.id ? 0 : pairwiseDistance(left, right);
      const cell = document.createElement("div");
      cell.className = "matrix-cell";
      cell.style.setProperty("--distance", distance);
      cell.title = `${left.name} vs ${right.name}: ${distance.toFixed(2)}`;
      cell.textContent = left.id === right.id ? "0" : distance.toFixed(2);
      matrix.appendChild(cell);
    });
  });
}

function renderReport() {
  const lines = MODEL_LINEAGE.models.map(
    (model) =>
      `${model.name}: ${model.contribution} It strengthened: ${model.strengthened} It weakened: ${model.weakened}`
  );
  $("#generated-report").value = [
    "LSC / MHLM model-lineage report",
    "",
    `Models archived: ${MODEL_LINEAGE.models.length}`,
    `Average apparent coherence: ${Math.round(average("coherence") * 100)}%`,
    `Average hallucination-risk pressure: ${Math.round(average("hallucination_risk") * 100)}%`,
    `Average validation pressure: ${Math.round(average("validation_pressure") * 100)}%`,
    "",
    "Model contributions:",
    ...lines.map((line) => `- ${line}`),
    "",
    "Interpretation:",
    "The models were not identical. GPT and Manus amplified and integrated the theory, while Gemini, Codex, and DeepSeek increasingly constrained it through uncertainty, validation, and formal critique. This is the core MHLM signal: coherence can grow before validation, so disagreement and audit pressure must be archived as first-class evidence."
  ].join("\n");
}

function bindControls() {
  $("#validation").addEventListener("input", (event) => {
    state.validation = Number(event.target.value);
    $("#validation-value").textContent = state.validation.toFixed(2);
    renderSimulation();
    renderReport();
  });
  $("#expert-review").addEventListener("input", (event) => {
    state.expertReview = Number(event.target.value);
    $("#expert-review-value").textContent = state.expertReview.toFixed(2);
    renderSimulation();
    renderReport();
  });
  $("#iterations").addEventListener("input", (event) => {
    state.iterations = Number(event.target.value);
    $("#iterations-value").textContent = state.iterations;
    renderSimulation();
  });
}

function render() {
  renderSummary();
  renderTimeline();
  renderModelDetail();
  renderSimulation();
  renderMatrix();
  renderReport();
}

bindControls();
render();
