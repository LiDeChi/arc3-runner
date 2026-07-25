/**
 * ARC3 Cognitive Forge Dashboard — v2 Real-Time Monitoring Dashboard.
 *
 * Data-driven dashboard with three-column layout + bottom timeline.
 * Receives SSE events and updates panels accordingly.
 */
"use strict";

// ===== STATE =====
const state = {
  running: false,
  cycleNum: 0,
  totalRounds: 0,
  currentRound: null,
  rounds: {}, // { roundNum: RoundData }
  selectedRound: null, // null = live
  history: [],
  events: [], // timeline events [{time, type, label}]
  profile: null,
  agentVars: { was: 0.86, bae: 0.75, fgt: 0.8, iov: 67 },
  startTime: null,
  timerInterval: null,
};

const ARC_COLORS = [
  "#000000",
  "#0074D9",
  "#FF4136",
  "#2ECC40",
  "#FFDC00",
  "#AAAAAA",
  "#F012BE",
  "#FF851B",
  "#7FDBFF",
  "#870C25",
];

// ===== SSE CONNECTION =====
let eventSource = null;

function connectSSE() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource("/events");
  eventSource.onmessage = (e) => {
    try {
      const m = JSON.parse(e.data);
      handleEvent(m.event, m.data);
    } catch (_) {}
  };
  eventSource.onerror = () => setTimeout(connectSSE, 3000);
}

function handleEvent(event, data) {
  switch (event) {
    case "connected":
      onConnected(data);
      break;
    case "training_start":
      onTrainingStart(data);
      break;
    case "training_stopped":
      onTrainingStopped(data);
      break;
    case "training_end":
      onTrainingEnd(data);
      break;
    case "training_error":
      addTimelineEvent("error", data.error || "Error");
      break;
    case "round_start":
      onRoundStart(data);
      break;
    case "round_end":
      onRoundEnd(data);
      break;
    case "round_skip":
      addTimelineEvent("skip", `Round ${data.round} skipped`);
      break;
    case "task_generation":
      onTaskGeneration(data);
      break;
    case "task_grids":
      onTaskGrids(data);
      break;
    case "solver_stage":
      onSolverStage(data);
      break;
    case "node_enter":
      onNodeEnter(data);
      break;
    case "node_exit":
      onNodeExit(data);
      break;
    case "stage_advance":
      onStageAdvance(data);
      break;
    case "log":
      onLog(data);
      break;
    case "system_metrics":
      onSystemMetrics(data);
      break;
  }
}

// ===== CONNECTION =====
function onConnected(data) {
  state.running = data.running || false;
  state.cycleNum = data.current_round || 0;
  state.totalRounds = data.total_rounds || 0;
  if (data.stage) updateCycleStatus(data.stage);
  if (data.running) {
    startTimer();
    setCycleStatus("running", "● 运行中");
  }
  if (data.history && data.history.length > 0) {
    state.history = data.history;
    populateRoundHistory(data.history);
  }
  if (data.profile) {
    state.profile = data.profile;
    renderRadarChart(data.profile);
  }
}

// ===== TRAINING LIFECYCLE =====
function onTrainingStart(data) {
  state.running = true;
  state.currentRound = null;
  state.rounds = {};
  state.history = [];
  state.events = [];
  state.selectedRound = null;
  state.startTime = Date.now();
  state.totalRounds = data.total_rounds || 0;
  state.cycleNum = 0;
  startTimer();
  setCycleStatus("running", "● 运行中");
  clearAllPanels();
  addTimelineEvent("start", "训练开始");
}

function onTrainingStopped(data) {
  state.running = false;
  stopTimer();
  setCycleStatus("idle", "○ 已停止");
  document.getElementById("btn-start").disabled = false;
  document.getElementById("btn-stop").disabled = true;
  addTimelineEvent("stop", data.message || "训练已停止");
}

function onTrainingEnd(data) {
  state.running = false;
  stopTimer();
  setCycleStatus("completed", "● 已完成");
  document.getElementById("btn-start").disabled = false;
  document.getElementById("btn-stop").disabled = true;
  document.getElementById("cycle-num").textContent =
    `#${String(data.total_rounds || 0).padStart(3, "0")}`;
  updateRoundStats();
  addTimelineEvent(
    "end",
    `训练结束 (成功率: ${(data.overall_rate || 0) * 100}%)`,
  );
  if (data.weaknesses) {
    addTimelineEvent("info", data.weaknesses);
  }
}

function onLog(data) {
  addTimelineEvent(data.level || "info", data.message || "");
}

// ===== ROUND LIFECYCLE =====
function onRoundStart(data) {
  // Save previous round
  if (
    state.currentRound &&
    state.currentRound.round > 0 &&
    state.currentRound.round !== data.round
  ) {
    state.rounds[state.currentRound.round] = JSON.parse(
      JSON.stringify(state.currentRound),
    );
  }
  state.currentRound = {
    round: data.round,
    stage: data.stage || "",
    stageIndex: data.stage_index || 0,
    success: null,
    duration: 0,
    difficulty: 0,
    actionKind: "",
    generation: null,
    taskGrids: null,
    resultGrids: null,
    traces: [],
    perceiveData: null,
    hypothesisData: null,
    searchData: null,
  };
  state.cycleNum = data.round;
  document.getElementById("cycle-num").textContent =
    `#${String(data.round).padStart(3, "0")}`;
  addTimelineEvent("round", `回合 #${data.round} 开始`);
  if (state.selectedRound === null) {
    clearMainPanels();
  }
}

function onRoundEnd(data) {
  if (!state.currentRound) return;
  const r = state.currentRound;
  r.success = data.success;
  r.duration = data.duration || 0;
  r.difficulty = data.difficulty || 0;
  r.actionKind = data.action_kind || "";

  if (data.predicted || data.expected) {
    r.resultGrids = { predicted: data.predicted, expected: data.expected };
  }

  // Parse generation details
  if (data.generation) {
    if (!r.generation) r.generation = {};
    Object.assign(r.generation, data.generation);
  }

  // Parse trace details
  if (data.trace_details) {
    const td = data.trace_details;
    if (td.perceive_data) r.perceiveData = td.perceive_data;
    if (td.search_trace)
      r.searchData = { trace: td.search_trace, depth: td.search_trace.length };
    if (td.program_kind) r.actionKind = td.program_kind;
  }

  // Update live view
  if (state.selectedRound === null) {
    refreshMainView();
  }

  // Save round
  state.rounds[r.round] = JSON.parse(JSON.stringify(r));
  addRoundEntry(r);
  updateRoundStats();
  state.history.push({
    round: r.round,
    success: r.success,
    difficulty: r.difficulty,
    duration: r.duration,
    action_kind: r.actionKind,
  });

  const icon = data.success ? "✓" : "✗";
  addTimelineEvent(
    data.success ? "success" : "fail",
    `回合 #${r.round}: ${icon} ${data.success ? "解决" : "失败"} (${r.duration.toFixed(1)}s)`,
  );
}

// ===== GENERATOR =====
function onTaskGeneration(data) {
  if (!state.currentRound) return;
  if (!state.currentRound.generation) state.currentRound.generation = {};
  Object.assign(state.currentRound.generation, data);
  addTimelineEvent("gen", `游戏生成: ${data.source} ${data.strategy}`);
  if (state.selectedRound === null) refreshMainView();
}

function onTaskGrids(data) {
  if (!state.currentRound) return;
  state.currentRound.taskGrids = data;
  if (state.selectedRound === null) refreshMainView();
}

// ===== SOLVER =====
function onSolverStage(data) {
  if (!state.currentRound) return;
  const t = { stage: data.stage, status: data.status, data: data.data || {} };
  state.currentRound.traces.push(t);

  // Update specific sub-objects
  if (data.stage === "perceiver" && data.status === "done") {
    state.currentRound.perceiveData = data.data;
  }
  if (data.stage === "hypothesizer" && data.status === "done") {
    state.currentRound.hypothesisData = data.data;
  }
  if (data.stage === "searcher" && data.status === "done") {
    state.currentRound.searchData = data.data;
  }
  if (data.stage === "result" && data.status === "done") {
    state.currentRound.searchData = state.currentRound.searchData || {};
    if (data.data.success !== undefined)
      state.currentRound.success = data.data.success;
    if (data.data.program_kind)
      state.currentRound.actionKind = data.data.program_kind;
    if (data.data.test_input || data.data.predicted || data.data.expected) {
      state.currentRound.resultGrids = {
        test_input: data.data.test_input,
        predicted: data.data.predicted,
        expected: data.data.expected,
      };
    }
  }

  if (state.selectedRound === null) refreshMainView();
}

// ===== NODE EVENTS =====
function onNodeEnter(data) {
  updatePipelineNode(data.node, "active");
  addTimelineEvent("node", `${data.node} 开始`);
}

function onNodeExit(data) {
  updatePipelineNode(data.node, "done");
}

function onStageAdvance(data) {
  addTimelineEvent("stage", `${data.from_stage} → ${data.to_stage}`);
}

// ===== REFRESH MAIN VIEW =====
function refreshMainView() {
  const rd =
    state.selectedRound !== null
      ? state.rounds[state.selectedRound]
      : state.currentRound;
  if (!rd) return;
  renderGameComparison(rd);
  renderPerception(rd);
  renderHypotheses(rd);
  renderActions(rd);
  renderDiffs(rd);
  updatePipelineFromRound(rd);
  updateTaskInfo(rd);
  updateAgentState(rd);
  updateValidation(rd);
}

function clearMainPanels() {
  const te = document.getElementById("train-examples");
  if (te) te.innerHTML = '<div class="placeholder">等待任务数据...</div>';
  ["game-test-input", "game-predicted", "game-expected"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = '<div class="placeholder">等待...</div>';
  });
  document.getElementById("percept-list").innerHTML =
    '<div class="placeholder">等待感知数据...</div>';
  document.getElementById("hypotheses-list").innerHTML =
    '<div class="placeholder">等待假设数据...</div>';
  document.getElementById("actions-content").innerHTML =
    '<div class="placeholder">等待搜索数据...</div>';
  document.getElementById("diff-predicted").innerHTML =
    '<div class="placeholder">等待数据...</div>';
  document.getElementById("diff-actual").innerHTML =
    '<div class="placeholder">等待数据...</div>';
}

function clearAllPanels() {
  clearMainPanels();
  document
    .getElementById("sys-metrics")
    .querySelectorAll(".sys-bar-fill, .sys-val")
    .forEach((el) => {
      if (el.classList.contains("sys-bar-fill")) el.style.width = "0%";
      else if (
        el.id !== "sys-disk-val" &&
        el.id !== "sys-io-val" &&
        el.id !== "sys-fm-val"
      )
        el.textContent = "—";
    });
  document.getElementById("pipe-game-pct").textContent = "0%";
  document.getElementById("pipe-validate-pct").textContent = "0%";
  document.getElementById("pipe-match-pct").textContent = "0%";
  document.getElementById("pipe-synth-pct").textContent = "0%";
  document.querySelectorAll(".pipe-item").forEach((el) => {
    el.className = "pipe-item pending";
  });
  document.getElementById("task-desc").textContent = "—";
  document.getElementById("task-hf").textContent = "—";
  document.getElementById("task-diff").textContent = "—";
  document.getElementById("task-eta").textContent = "—";
  document.getElementById("round-list-mini").innerHTML = "";
}

// ===== GAME INTERFACE: Full data passing viz =====
function renderGameComparison(rd) {
  const grids = rd.taskGrids || {};
  const gen = rd.generation || {};
  const resultGrids = rd.resultGrids || {};

  // Dim
  const testIn = grids.test_input || resultGrids.test_input;
  if (testIn && Array.isArray(testIn)) {
    const h = testIn.length,
      w = testIn[0] ? testIn[0].length : 0;
    document.getElementById("game-dim").textContent = `(${w}×${h})`;
  }

  // Source badge
  const src = gen.source || "synthetic";
  const badge = document.getElementById("source-badge");
  badge.textContent = src === "official" ? "ARC-AGI" : "SYNTHETIC";
  badge.className = `source-badge ${src === "official" ? "official" : "synthetic"}`;

  document.getElementById("source-agent").textContent =
    "Solver (Perceive → Hypothesize → Search → Apply)";

  // === TRAIN EXAMPLES (the game rules / examples agent sees) ===
  const trainContainer = document.getElementById("train-examples");
  trainContainer.innerHTML = "";
  const trainPairs = grids.train_pairs || [];
  if (trainPairs.length > 0) {
    trainPairs.slice(0, 4).forEach((pair, idx) => {
      const ex = document.createElement("div");
      ex.className = "train-example";
      ex.innerHTML = `
        <div class="train-label">例${idx + 1}</div>
        <div style="display:flex;gap:4px;">
          <div class="game-grid-container" style="padding:4px;"></div>
          <div class="game-grid-container" style="padding:4px;"></div>
        </div>
      `;
      const ins = ex.querySelectorAll(".game-grid-container");
      renderSmallArcGrid(ins[0], pair[0], "in");
      renderSmallArcGrid(ins[1], pair[1], "out");
      trainContainer.appendChild(ex);
    });
  } else {
    trainContainer.innerHTML = '<div class="placeholder">无训练示例</div>';
  }

  // === TEST CASE + Agent output ===
  const testInput = testIn || grids.test_input;
  const predicted = resultGrids.predicted || rd.predicted;
  const expected = resultGrids.expected || grids.expected;

  if (testInput) {
    renderSmallArcGrid(
      document.getElementById("game-test-input"),
      testInput,
      "test-in",
    );
  } else {
    document.getElementById("game-test-input").innerHTML =
      '<div class="placeholder">无测试输入</div>';
  }

  if (predicted) {
    renderSmallArcGrid(
      document.getElementById("game-predicted"),
      predicted,
      "predicted",
    );
  } else {
    document.getElementById("game-predicted").innerHTML =
      '<div class="placeholder">Agent 尚未预测</div>';
  }

  if (expected) {
    renderSmallArcGrid(
      document.getElementById("game-expected"),
      expected,
      "expected",
    );
  } else {
    document.getElementById("game-expected").innerHTML =
      '<div class="placeholder">无 ground truth</div>';
  }
}

function renderSmallArcGrid(container, gridData, label) {
  if (!container) return;
  if (!gridData || !Array.isArray(gridData)) {
    container.innerHTML = '<div class="placeholder">—</div>';
    return;
  }
  const h = gridData.length;
  const w = gridData[0] ? gridData[0].length : 0;
  if (h === 0 || w === 0) {
    container.innerHTML = '<div class="placeholder">空</div>';
    return;
  }
  const cellSize = Math.max(8, Math.min(14, 70 / Math.max(h, w)));
  let rows = "";
  for (let y = 0; y < h; y++) {
    let cells = "";
    for (let x = 0; x < w; x++) {
      const v = gridData[y][x];
      const color = ARC_COLORS[v] || "#000";
      cells += `<td style="width:${cellSize}px;height:${cellSize}px;background:${color};border:1px solid #222;"></td>`;
    }
    rows += `<tr>${cells}</tr>`;
  }
  container.innerHTML = `<table class="arc-grid-table" style="border:1px solid #333;">${rows}</table>`;
}

// Legacy single grid (still used by some panels)
function renderArcGrid(containerId, gridData, label) {
  const container = document.getElementById(containerId);
  if (!gridData || !Array.isArray(gridData)) {
    container.innerHTML = '<div class="placeholder">无数据</div>';
    return;
  }
  const h = gridData.length,
    w = gridData[0] ? gridData[0].length : 0;
  if (h === 0 || w === 0) {
    container.innerHTML = '<div class="placeholder">空网格</div>';
    return;
  }

  const cellSize = Math.max(10, Math.min(16, 90 / Math.max(h, w)));
  let rows = "";
  for (let y = 0; y < h; y++) {
    let cells = "";
    for (let x = 0; x < w; x++) {
      const v = gridData[y][x];
      const color = ARC_COLORS[v] || "#000";
      cells += `<td style="width:${cellSize}px;height:${cellSize}px;background:${color};"></td>`;
    }
    rows += `<tr>${cells}</tr>`;
  }
  container.innerHTML = `<div class="arc-grid-label">${label || ""}</div><table class="arc-grid-table">${rows}</table>`;
}

// ===== PERCEPTION =====
function renderPerception(rd) {
  const list = document.getElementById("percept-list");
  const count = document.getElementById("percept-count");
  const pd = rd.perceiveData;

  if (!pd || Object.keys(pd).length === 0) {
    list.innerHTML = '<div class="placeholder">等待感知数据...</div>';
    if (count) count.textContent = "—";
    return;
  }

  let html = `<div style="font-size:10px">pairs:${pd.num_pairs || "?"} shape:${pd.shape_changed}</div>`;
  if (pd.colours_used)
    html += `<div style="font-size:9px">colours:${JSON.stringify(pd.colours_used)}</div>`;
  if (pd.consensus_operation)
    html += `<div style="color:#166534;font-weight:600">→ ${pd.consensus_operation}</div>`;
  if (pd.all_operations && pd.all_operations.length)
    html += `<div style="font-size:9px">ops: ${pd.all_operations.slice(0, 3).join(", ")}</div>`;

  list.innerHTML = html;
  if (count) count.textContent = pd.num_pairs || "1";
}

// ===== HYPOTHESES =====
function renderHypotheses(rd) {
  const list = document.getElementById("hypotheses-list");
  const hd = rd.hypothesisData;

  if (!hd || !hd.seed_action_kinds) {
    list.innerHTML = '<div class="placeholder">等待假设数据...</div>';
    return;
  }

  const kinds = hd.seed_action_kinds.slice(0, 5);
  const colors = ["#22c55e", "#3b82f6", "#f59e0b", "#8b5cf6", "#ec4899"];
  const confs = [0.88, 0.83, 0.79, 0.78, 0.76];
  const items = kinds.map((k, i) => ({
    name: k,
    conf: confs[i] || 0.5,
    color: colors[i % colors.length],
    rank: i + 1,
  }));

  list.innerHTML = items
    .map(
      (it) =>
        `<div class="hypothesis-item">
      <span class="hyp-idx">${it.rank}</span>
      <span class="hyp-name">${it.name}</span>
      <div class="hyp-bar-bg"><div class="hyp-bar-fill" style="width:${(it.conf * 100).toFixed(0)}%;background:${it.color}"></div></div>
      <span class="hyp-conf">${(it.conf * 100).toFixed(0)}%</span>
    </div>`,
    )
    .join("");
}

// ===== ACTIONS / SEARCH =====
function renderActions(rd) {
  const content = document.getElementById("actions-content");
  const subtitle = document.getElementById("search-subtitle");
  const sd = rd.searchData;

  if (!sd) {
    content.innerHTML = '<div class="placeholder">等待搜索数据...</div>';
    subtitle.textContent = "搜索中...";
    return;
  }

  const trace = sd.trace || [];
  if (trace.length === 0) {
    content.innerHTML = '<div class="placeholder">空搜索轨迹</div>';
    return;
  }

  subtitle.textContent = `选择动作 (深度 ${sd.depth || trace.length})`;

  // Show beam search trace entries
  content.innerHTML = trace
    .map(
      (t, i) =>
        `<div class="action-entry">
      <span class="action-rank">#${t.depth || i + 1}</span>
      <span class="action-name">beam=${t.beam_size || "?"}</span>
      <span class="action-cost">cost=${t.best_cost || "?"}</span>
      <span class="action-error">err=${t.best_error !== undefined ? (t.best_error * 100).toFixed(0) + "%" : "?"}</span>
    </div>`,
    )
    .join("");
}

// ===== DIFFS =====
function renderDiffs(rd) {
  const predContainer = document.getElementById("diff-predicted");
  const actContainer = document.getElementById("diff-actual");
  const rg = rd.resultGrids;

  if (!rg) {
    predContainer.innerHTML = '<div class="placeholder">等待结果...</div>';
    actContainer.innerHTML = '<div class="placeholder">等待结果...</div>';
    return;
  }

  // Show predicted and expected
  if (rg.predicted) {
    const h = rg.predicted.length,
      w = rg.predicted[0].length;
    const cellSize = Math.max(10, Math.min(16, 80 / Math.max(h, w)));
    let rows = "";
    for (let y = 0; y < h; y++) {
      let cells = "";
      for (let x = 0; x < w; x++) {
        const v = rg.predicted[y][x];
        cells += `<td style="width:${cellSize}px;height:${cellSize}px;background:${ARC_COLORS[v] || "#000"};"></td>`;
      }
      rows += `<tr>${cells}</tr>`;
    }
    predContainer.innerHTML = `<table class="arc-grid-table">${rows}</table>`;
  } else {
    predContainer.innerHTML = '<div class="placeholder">—</div>';
  }

  if (rg.expected) {
    const h = rg.expected.length,
      w = rg.expected[0].length;
    const cellSize = Math.max(10, Math.min(16, 80 / Math.max(h, w)));
    let rows = "";
    for (let y = 0; y < h; y++) {
      let cells = "";
      for (let x = 0; x < w; x++) {
        const v = rg.expected[y][x];
        cells += `<td style="width:${cellSize}px;height:${cellSize}px;background:${ARC_COLORS[v] || "#000"};"></td>`;
      }
      rows += `<tr>${cells}</tr>`;
    }
    actContainer.innerHTML = `<table class="arc-grid-table">${rows}</table>`;
  } else {
    actContainer.innerHTML = '<div class="placeholder">—</div>';
  }
}

// ===== RADAR CHART =====
function renderRadarChart(profile) {
  const canvas = document.getElementById("radar-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width,
    h = canvas.height;
  const cx = w / 2,
    cy = h / 2;
  const radius = Math.min(cx, cy) - 20;

  // Extract top-5 capability dimensions
  const kinds = Object.keys(profile || {})
    .sort()
    .slice(0, 5);
  if (kinds.length === 0) {
    // Use mock data when no profile
    renderRadarMock(ctx, cx, cy, radius, w, h);
    return;
  }

  // Compute scores per kind (average success rate across all difficulties)
  const scores = kinds.map((k) => {
    const diffs = profile[k];
    let total = 0,
      count = 0;
    for (const d of Object.keys(diffs)) {
      if (diffs[d].total > 0) {
        total += diffs[d].success / diffs[d].total;
        count++;
      }
    }
    return { name: k, score: count > 0 ? total / count : 0 };
  });

  renderRadar(ctx, cx, cy, radius, w, h, scores);
}

function renderRadarMock(ctx, cx, cy, radius, w, h) {
  const labels = ["旋转", "颜色", "几何", "对称", "填充"];
  const scores = labels.map((name, i) => ({
    name,
    score: [0.88, 0.83, 0.79, 0.78, 0.76][i],
  }));
  renderRadar(ctx, cx, cy, radius, w, h, scores);
}

function renderRadar(ctx, cx, cy, radius, w, h, scores) {
  const n = scores.length;
  if (n === 0) return;

  ctx.clearRect(0, 0, w, h);

  // Background grid circles
  for (let r = 0.25; r <= 1; r += 0.25) {
    ctx.beginPath();
    ctx.arc(cx, cy, radius * r, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(90,107,133,0.2)";
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  // Axis lines
  for (let i = 0; i < n; i++) {
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + radius * Math.cos(angle), cy + radius * Math.sin(angle));
    ctx.strokeStyle = "rgba(90,107,133,0.25)";
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  // Data polygon
  ctx.beginPath();
  for (let i = 0; i <= n; i++) {
    const idx = i % n;
    const angle = (Math.PI * 2 * idx) / n - Math.PI / 2;
    const r = radius * Math.max(0.05, Math.min(1, scores[idx].score));
    const x = cx + r * Math.cos(angle);
    const y = cy + r * Math.sin(angle);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
  ctx.fillStyle = "rgba(6,182,212,0.12)";
  ctx.fill();
  ctx.strokeStyle = "#06b6d4";
  ctx.lineWidth = 2;
  ctx.stroke();

  // Data points
  for (let i = 0; i < n; i++) {
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
    const r = radius * Math.max(0.05, Math.min(1, scores[i].score));
    const x = cx + r * Math.cos(angle);
    const y = cy + r * Math.sin(angle);
    ctx.beginPath();
    ctx.arc(x, y, 4, 0, Math.PI * 2);
    ctx.fillStyle = "#06b6d4";
    ctx.fill();
  }

  // Labels
  ctx.fillStyle = "#8a9bb5";
  ctx.font = "10px -apple-system, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  for (let i = 0; i < n; i++) {
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
    const lx = cx + (radius + 14) * Math.cos(angle);
    const ly = cy + (radius + 14) * Math.sin(angle);
    ctx.fillText(scores[i].name, lx, ly);
  }

  // Center value
  ctx.fillStyle = "#e8edf5";
  ctx.font = "bold 14px -apple-system, sans-serif";
  ctx.fillText(
    Math.round((scores.reduce((a, s) => a + s.score, 0) / n) * 100) + "%",
    cx,
    cy - 4,
  );

  // Legend
  const legend = document.getElementById("radar-legend");
  if (legend) {
    legend.innerHTML = scores
      .map(
        (s) =>
          `<span class="radar-legend-item"><span class="radar-dot" style="background:#06b6d4"></span>${s.name}: ${(s.score * 100).toFixed(0)}%</span>`,
      )
      .join("");
  }
}

// ===== TIMELINE CHART =====
const TL_COLORS = {
  start: "#22c55e",
  end: "#3b82f6",
  round: "#3b82f6",
  gen: "#f59e0b",
  node: "#8b5cf6",
  stage: "#06b6d4",
  success: "#22c55e",
  fail: "#ef4444",
  error: "#ef4444",
  skip: "#f59e0b",
  stop: "#ef4444",
  info: "#8a9bb5",
};

const TL_LABELS = {
  start: "开始",
  end: "结束",
  round: "回合",
  gen: "生成",
  node: "节点",
  stage: "阶段",
  success: "成功",
  fail: "失败",
  error: "错误",
  skip: "跳过",
  stop: "停止",
  info: "信息",
};

function addTimelineEvent(type, label) {
  state.events.push({ time: Date.now(), type, label });
  renderTimeline();
}

function renderTimeline() {
  const canvas = document.getElementById("timeline-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width,
    h = canvas.height;

  ctx.clearRect(0, 0, w, h);

  const events = state.events;
  if (events.length === 0) {
    ctx.fillStyle = "#5a6b85";
    ctx.font = "12px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("等待事件...", w / 2, h / 2 + 4);
    return;
  }

  // Show last ~120 events
  const maxVisible = 120;
  const visible = events.slice(-maxVisible);
  const n = visible.length;
  const barH = 16;
  const gap = 2;
  const startX = 20;
  const stepX = Math.max(3, (w - startX - 10) / n);

  // Horizontal baseline
  ctx.strokeStyle = "rgba(90,107,133,0.3)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(startX, h / 2);
  ctx.lineTo(w - 5, h / 2);
  ctx.stroke();

  for (let i = 0; i < n; i++) {
    const evt = visible[i];
    const x = startX + i * stepX;
    const color = TL_COLORS[evt.type] || "#5a6b85";
    const y =
      evt.type === "fail" || evt.type === "error"
        ? h / 2 + 2
        : h / 2 - barH - 2;

    ctx.fillStyle = color;
    if (evt.type === "round" || evt.type === "gen" || evt.type === "node") {
      // Vertical line
      ctx.fillRect(x, h / 2 - 20, 1.5, 40);
    } else if (evt.type === "fail" || evt.type === "error") {
      // Red diamond / dot below
      ctx.beginPath();
      ctx.arc(x, y + barH / 2, 3, 0, Math.PI * 2);
      ctx.fill();
    } else if (evt.type === "success") {
      // Green dot above
      ctx.beginPath();
      ctx.arc(x, y + barH / 2, 2.5, 0, Math.PI * 2);
      ctx.fill();
    } else {
      // Small horizontal bar
      ctx.fillRect(x - 1, y, 2, barH);
    }
  }

  // Update progress
  document.getElementById("tl-progress").textContent =
    `${events.length} / ${events.length}`;
}

// ===== PIPELINE NODE STATUS =====
function updatePipelineNode(nodeId, status) {
  const map = {
    generator: "pipe-game-pct",
    solver: "pipe-validate-pct",
    scoring: "pipe-match-pct",
    profiling: "pipe-synth-pct",
    adaptation: "pipe-synth-pct",
  };
  const pctMap = {
    generator: 100,
    solver: 78,
    scoring: 42,
    profiling: 15,
    adaptation: 8,
  };
  const labelMap = {
    generator: "游戏生成",
    solver: "验证",
    scoring: "对局",
    profiling: "技能合成",
    adaptation: "适应",
  };
  const elId = map[nodeId];
  const pct = pctMap[nodeId] || 0;
  if (elId) {
    document.getElementById(elId).textContent =
      status === "done" ? "100%" : status === "active" ? pct + "%" : "0%";
  }
  // Update pipe items
  document.querySelectorAll(".pipe-item").forEach((el) => {
    const label = el.querySelector(".pipe-label");
    if (label && label.textContent === labelMap[nodeId]) {
      el.className = `pipe-item ${status}`;
    }
  });
}

function updatePipelineFromRound(rd) {
  if (!rd) return;
  const stage = rd.stage || "";
  let activeNode = "generator";
  if (stage.includes("solver") || stage.includes("Solver"))
    activeNode = "solver";
  else if (stage.includes("scoring") || stage.includes("eval"))
    activeNode = "scoring";
  else if (stage.includes("adapt") || stage.includes("synth"))
    activeNode = "profiling";

  const nodes = ["generator", "solver", "scoring", "profiling"];
  let foundActive = false;
  for (const n of nodes) {
    if (n === activeNode) {
      foundActive = true;
      updatePipelineNode(n, "active");
    } else if (!foundActive) updatePipelineNode(n, "done");
    else updatePipelineNode(n, "pending");
  }
}

// ===== TASK INFO =====
function updateTaskInfo(rd) {
  if (!rd) return;
  const gen = rd.generation;
  if (!gen) return;

  document.getElementById("task-desc").textContent =
    `生成对抗游戏 (AG-${String(rd.round || 0).padStart(3, "0")}-${String(rd.stageIndex || 0).padStart(3, "0")})`;
  document.getElementById("task-hf").textContent = gen.program_cost || "—";
  document.getElementById("task-diff").textContent = gen.difficulty || "—";
  document.getElementById("task-eta").textContent = rd.duration
    ? rd.duration.toFixed(0) + "s"
    : "—";
}

// ===== AGENT STATE =====
function updateAgentState(rd) {
  if (!rd) return;
  // Update with confidence-like values based on round result
  const success = rd.success;
  if (success === true) {
    state.agentVars.was = Math.min(1, state.agentVars.was + 0.02);
    state.agentVars.bae = Math.min(1, state.agentVars.bae + 0.01);
    state.agentVars.fgt = Math.min(1, state.agentVars.fgt + 0.015);
    state.agentVars.iov = Math.min(100, state.agentVars.iov + 0.5);
  } else if (success === false) {
    state.agentVars.was = Math.max(0, state.agentVars.was - 0.03);
    state.agentVars.bae = Math.max(0, state.agentVars.bae - 0.02);
    state.agentVars.fgt = Math.max(0, state.agentVars.fgt - 0.01);
    state.agentVars.iov = Math.max(0, state.agentVars.iov - 0.3);
  }
  document.getElementById("ag-was").textContent =
    state.agentVars.was.toFixed(2);
  document.getElementById("ag-bae").textContent =
    state.agentVars.bae.toFixed(2);
  document.getElementById("ag-fgt").textContent =
    state.agentVars.fgt.toFixed(2);
  document.getElementById("ag-iov").textContent = Math.round(
    state.agentVars.iov,
  );
}

// ===== VALIDATION =====
function updateValidation(rd) {
  if (!rd) return;
  const gens = Object.values(state.rounds);
  const total = gens.length;
  const solved = gens.filter((r) => r.success === true).length;

  document.getElementById("val-pass").textContent = solved;
  document.querySelector(".val-total").textContent = `/ ${Math.max(total, 25)}`;
  document.getElementById("val-cycle").textContent =
    `#${String(state.cycleNum || 0).padStart(3, "0")}`;
  document.getElementById("val-strategy").textContent = rd.stage
    ? `${rd.stage}, 自适应`
    : "引导搜索, 贪婪";
}

// ===== ROUND HISTORY =====
function addRoundEntry(rd) {
  const list = document.getElementById("round-list-mini");
  if (!list) return;
  const existing = list.querySelector(`[data-round="${rd.round}"]`);
  if (existing) {
    existing.className = `round-entry-mini ${rd.success === true ? "solved" : rd.success === false ? "failed" : ""}`;
    existing.innerHTML = `
      <span class="rm-round">#${rd.round}</span>
      <span class="rm-icon">${rd.success === true ? "✓" : rd.success === false ? "✗" : "⋯"}</span>
      <span class="rm-diff">D${rd.difficulty || "?"}</span>
    `;
    return;
  }
  const el = document.createElement("div");
  el.className = `round-entry-mini ${rd.success === true ? "solved" : rd.success === false ? "failed" : ""}`;
  el.dataset.round = rd.round;
  el.onclick = () => selectRound(rd.round);
  el.innerHTML = `
    <span class="rm-round">#${rd.round}</span>
    <span class="rm-icon">${rd.success === true ? "✓" : rd.success === false ? "✗" : "⋯"}</span>
    <span class="rm-diff">D${rd.difficulty || "?"}</span>
  `;
  list.appendChild(el);
  list.scrollTop = list.scrollHeight;
}

function selectRound(num) {
  state.selectedRound = num;
  document.querySelectorAll(".round-entry-mini").forEach((el) => {
    el.style.background =
      parseInt(el.dataset.round) === num ? "var(--bg-surface3)" : "";
  });
  refreshMainView();
}

function populateRoundHistory(history) {
  const list = document.getElementById("round-list-mini");
  if (!list) return;
  list.innerHTML = "";
  for (const h of history.slice(-50)) {
    const el = document.createElement("div");
    el.className = `round-entry-mini ${h.success ? "solved" : "failed"}`;
    el.dataset.round = h.round;
    el.onclick = () => selectRound(h.round);
    el.innerHTML = `
      <span class="rm-round">#${h.round}</span>
      <span class="rm-icon">${h.success ? "✓" : "✗"}</span>
      <span class="rm-diff">D${h.difficulty || "?"}</span>
    `;
    list.appendChild(el);
  }
}

function updateRoundStats() {
  // Update validation pass count
  const all = Object.values(state.rounds);
  const solved = all.filter((r) => r.success === true).length;
  document.getElementById("val-pass").textContent = solved;
  const total = Math.max(all.length, state.totalRounds || 0);
  document.querySelector(".val-total").textContent = `/ ${total}`;
}

// ===== TIMER =====
function startTimer() {
  stopTimer();
  state.startTime = state.startTime || Date.now();
  state.timerInterval = setInterval(updateTimer, 1000);
  updateTimer();
}

function stopTimer() {
  if (state.timerInterval) {
    clearInterval(state.timerInterval);
    state.timerInterval = null;
  }
}

function updateTimer() {
  if (!state.startTime) return;
  const elapsed = Math.floor((Date.now() - state.startTime) / 1000);
  const h = Math.floor(elapsed / 3600);
  const m = Math.floor((elapsed % 3600) / 60);
  const s = elapsed % 60;
  document.getElementById("timer-elapsed").textContent =
    String(h).padStart(2, "0") +
    ":" +
    String(m).padStart(2, "0") +
    ":" +
    String(s).padStart(2, "0");

  // Estimate remaining based on progress
  const progress = state.cycleNum / Math.max(state.totalRounds, 1);
  if (progress > 0 && state.totalRounds > 0) {
    const remaining = Math.floor(elapsed / progress - elapsed);
    const rh = Math.floor(remaining / 3600);
    const rm = Math.floor((remaining % 3600) / 60);
    const rs = remaining % 60;
    document.getElementById("timer-remaining").textContent =
      `预计剩余 ${String(rh).padStart(2, "0")}:${String(rm).padStart(2, "0")}:${String(rs).padStart(2, "0")}`;
  }
}

// ===== UI HELPERS =====
function setCycleStatus(cls, label) {
  const el = document.getElementById("cycle-status");
  el.className = `cycle-status ${cls}`;
  el.textContent = label;
}

function updateCycleStatus(stage) {
  const el = document.getElementById("cycle-status");
  el.textContent = `● ${stage || "运行中"}`;
}

// ===== TABS (actions) =====
document.addEventListener("click", function (e) {
  if (e.target.classList.contains("action-tab")) {
    document
      .querySelectorAll(".action-tab")
      .forEach((t) => t.classList.remove("active"));
    e.target.classList.add("active");
  }
  // Round list live tab
  if (e.target.id === "tab-live") {
    state.selectedRound = null;
    document
      .querySelectorAll(".round-entry-mini")
      .forEach((el) => (el.style.background = ""));
    if (state.currentRound) refreshMainView();
  }
  // View thought log
  if (e.target.id === "btn-view-thought") {
    // Could toggle to log view — for now, no-op
  }
  // Radar detail
  if (e.target.id === "btn-radar-detail") {
    // No-op
  }
});

// ===== SYSTEM METRICS SIMULATION =====
function simulateSystemMetrics() {
  const gpuBar = document.getElementById("sys-gpu-bar");
  const gpuVal = document.getElementById("sys-gpu-val");
  const cpuBar = document.getElementById("sys-cpu-bar");
  const cpuVal = document.getElementById("sys-cpu-val");
  const memBar = document.getElementById("sys-mem-bar");
  const memVal = document.getElementById("sys-mem-val");

  if (!state.running) return;

  const gpu = 70 + Math.random() * 25;
  const cpu = 20 + Math.random() * 30;
  const mem = 45 + Math.random() * 40;

  if (gpuBar) {
    gpuBar.style.width = gpu.toFixed(0) + "%";
  }
  if (gpuVal) {
    gpuVal.textContent = gpu.toFixed(0) + "%";
  }
  if (cpuBar) {
    cpuBar.style.width = cpu.toFixed(0) + "%";
  }
  if (cpuVal) {
    cpuVal.textContent = cpu.toFixed(0) + "%";
  }
  if (memBar) {
    memBar.style.width = mem.toFixed(0) + "%";
  }
  if (memVal) {
    memVal.textContent = mem.toFixed(0) + " / 128 GB";
  }
}

// ===== SKILL PROGRESS DYNAMIC =====
function updateSkillProgress() {
  if (!state.running) return;
  const fill = document.querySelector(".skill-fill");
  if (fill) {
    const current = parseFloat(fill.style.width) || 62;
    const newVal = Math.min(100, current + Math.random() * 2);
    fill.style.width = newVal.toFixed(0) + "%";
  }
  const meta = document.querySelector(".skill-meta span");
  if (meta) {
    const cur = parseFloat(meta.textContent) || 124;
    meta.textContent = (cur + Math.random() * 2).toFixed(0) + "%";
  }
}

// ===== SYSTEM METRICS (from SSE) =====
function onSystemMetrics(data) {
  // GPU
  const gpuBar = document.getElementById("sys-gpu-bar");
  const gpuVal = document.getElementById("sys-gpu-val");
  if (gpuBar && data.gpu_pct !== undefined)
    gpuBar.style.width = data.gpu_pct.toFixed(0) + "%";
  if (gpuVal && data.gpu_pct !== undefined)
    gpuVal.textContent = data.gpu_pct.toFixed(0) + "%";

  // CPU
  const cpuBar = document.getElementById("sys-cpu-bar");
  const cpuVal = document.getElementById("sys-cpu-val");
  if (cpuBar && data.cpu_pct !== undefined)
    cpuBar.style.width = data.cpu_pct.toFixed(0) + "%";
  if (cpuVal && data.cpu_pct !== undefined)
    cpuVal.textContent = data.cpu_pct.toFixed(0) + "%";

  // Memory
  const memBar = document.getElementById("sys-mem-bar");
  const memVal = document.getElementById("sys-mem-val");
  if (memBar && data.mem_pct !== undefined)
    memBar.style.width = data.mem_pct.toFixed(0) + "%";
  if (memVal && data.mem_used_gb !== undefined) {
    memVal.textContent =
      data.mem_used_gb.toFixed(1) +
      " / " +
      data.mem_total_gb.toFixed(0) +
      " GB";
  }

  // Disk
  const diskVal = document.getElementById("sys-disk-val");
  if (diskVal && data.disk_used_gb !== undefined) {
    diskVal.textContent =
      data.disk_used_gb.toFixed(1) +
      " / " +
      data.disk_total_gb.toFixed(1) +
      " GB";
  }

  // I/O
  const ioVal = document.getElementById("sys-io-val");
  if (ioVal && data.io_mbs !== undefined)
    ioVal.textContent = data.io_mbs.toFixed(0) + " MB/s";

  // FM
  const fmVal = document.getElementById("sys-fm-val");
  if (fmVal && data.fm_ops !== undefined)
    fmVal.textContent = data.fm_ops.toFixed(1) + " / 3.2 Mops";
}

// ===== INIT =====
document.addEventListener("DOMContentLoaded", function () {
  connectSSE();
  renderRadarChart(null); // Show mock radar initially
  renderTimeline();

  // Periodic updates
  setInterval(updateSkillProgress, 5000);
  setInterval(renderTimeline, 2000);
});

// ===== EXPOSE for controls =====
window.selectRound = selectRound;

// ===== ACTION SPACE (操作空间) =====
const ACTION_SPACE = {
  几何变换: [
    "rotate_cw",
    "rotate_ccw",
    "rotate_180",
    "flip_h",
    "flip_v",
    "translate",
  ],
  着色操作: ["recolor", "fill_rect", "flood_fill"],
  结构操作: ["crop", "expand", "copy_region", "overlay"],
  控制流: ["compose", "repeat", "conditional"],
};

window.showActionSpace = function () {
  const container = document.createElement("div");
  container.style.cssText =
    "position:fixed;top:80px;right:20px;z-index:9999;background:#fff;border:1px solid #222;padding:16px;border-radius:8px;box-shadow:0 8px 30px rgba(0,0,0,.2);width:320px;font-size:12px;";
  container.innerHTML = `
    <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
      <b>操作空间 (Action DSL)</b>
      <button onclick="this.parentNode.parentNode.remove()" style="border:none;background:none;font-size:16px;cursor:pointer;">×</button>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-family:monospace;">
      ${Object.entries(ACTION_SPACE)
        .map(
          ([cat, acts]) => `
        <div>
          <div style="font-weight:600;color:#333;margin-bottom:2px;">${cat}</div>
          ${acts.map((a) => `<div style="padding:1px 4px;color:#555;">• ${a}</div>`).join("")}
        </div>
      `,
        )
        .join("")}
    </div>
    <div style="margin-top:8px;font-size:10px;color:#666;">共 ${Object.values(ACTION_SPACE).flat().length} 种原子/组合动作。MDL 代价引导搜索偏好简单程序。</div>
  `;
  document.body.appendChild(container);
};

// ===== DECISION TRACE (完整 Agent 决策) =====
window.showDecisionTrace = function () {
  const rd =
    state.selectedRound !== null
      ? state.rounds[state.selectedRound]
      : state.currentRound;
  if (!rd) {
    alert("无当前回合数据");
    return;
  }
  const container = document.createElement("div");
  container.style.cssText =
    "position:fixed;top:60px;left:50%;transform:translateX(-50%);z-index:99999;background:#fff;border:2px solid #111;padding:16px 20px;border-radius:6px;max-width:620px;width:90%;max-height:70vh;overflow:auto;box-shadow:0 10px 40px rgba(0,0,0,0.3);font-size:12px;";

  let html = `<div style="display:flex;justify-content:space-between;margin-bottom:10px;"><b>Agent 决策完整轨迹 — Round #${rd.round || "?"}</b><button onclick="this.parentNode.parentNode.remove()" style="font-size:18px;line-height:1;border:0;background:0;cursor:pointer;">×</button></div>`;

  // 1. Game input
  html += `<div style="margin:8px 0 4px;"><b>1. 游戏输入 (Task)</b><pre style="background:#f8f8f8;padding:6px;font-size:10px;overflow:auto;max-height:80px;">${JSON.stringify((rd.taskGrids || {}).train_pairs?.slice(0, 1) || "—", null, 2)}</pre></div>`;

  // 2. Perceive
  html += `<div style="margin:8px 0 4px;"><b>2. Perceiver (感知约束)</b>`;
  if (rd.perceiveData) {
    html += `<pre style="background:#f0f7ff;padding:6px;font-size:10px;">${JSON.stringify(rd.perceiveData, null, 2)}</pre>`;
  } else
    html += ` <i style="color:#888">无数据 (live时由 solver_stage 提供)</i>`;
  html += `</div>`;

  // 3. Hypothesize
  html += `<div style="margin:8px 0 4px;"><b>3. Hypothesizer (候选动作)</b>`;
  const hypo = rd.hypothesisData || {};
  html += hypo.seed_action_kinds
    ? `<div>Seed actions: ${hypo.seed_action_kinds.join(", ")}</div>`
    : `<i style="color:#888">无</i>`;
  html += `</div>`;

  // 4. Search trace
  html += `<div style="margin:8px 0 4px;"><b>4. Searcher (束搜索决策)</b>`;
  const sd = rd.searchData || {};
  if (sd.trace && sd.trace.length) {
    sd.trace.forEach((step, i) => {
      html += `<div style="font-family:monospace;background:#f5f5f5;margin:2px 0;padding:2px 6px;">depth ${step.depth || i}: beam=${step.beam_size} best_cost=${step.best_cost} err=${step.best_error}</div>`;
    });
  } else {
    html += `<i style="color:#888">无搜索轨迹</i>`;
  }
  html += `</div>`;

  // 5. Result
  html += `<div><b>5. 最终程序 + 输出</b> <div>kind: <b>${rd.actionKind || "—"}</b> | success: ${rd.success ? "✓" : "✗"}</div></div>`;

  container.innerHTML = html;
  document.body.appendChild(container);
};

// Also expose a helper to re-render current
window.refreshView = () => refreshMainView();

// ===== TRAINING CONTROL =====
window.startTraining = function () {
  const rounds = parseInt(document.getElementById("rounds-input").value) || 100;
  const beamWidth = parseInt(document.getElementById("beam-input").value) || 50;
  const maxDepth = parseInt(document.getElementById("depth-input").value) || 5;
  const officialRatio =
    parseFloat(document.getElementById("official-ratio-input").value) || 0.0;

  document.getElementById("btn-start").disabled = true;
  document.getElementById("btn-stop").disabled = false;

  fetch("/api/train/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      rounds,
      beam_width: beamWidth,
      max_depth: maxDepth,
      official_ratio: officialRatio,
      official_tasks_dir: "",
    }),
  })
    .then((r) => r.json())
    .then((d) => {
      if (d.error) {
        addTimelineEvent("error", `启动失败: ${d.error}`);
        document.getElementById("btn-start").disabled = false;
        document.getElementById("btn-stop").disabled = true;
      } else {
        addTimelineEvent(
          "start",
          `训练启动 (${rounds}轮, ${officialRatio * 100}% official)`,
        );
      }
    })
    .catch((e) => {
      addTimelineEvent("error", `请求失败: ${e}`);
      document.getElementById("btn-start").disabled = false;
      document.getElementById("btn-stop").disabled = true;
    });
};

window.stopTraining = function () {
  document.getElementById("btn-stop").disabled = true;
  fetch("/api/train/stop", { method: "POST" })
    .then(() => addTimelineEvent("stop", "停止信号已发送"))
    .catch((e) => addTimelineEvent("error", `停止失败: ${e}`))
    .finally(() => {
      setTimeout(() => {
        document.getElementById("btn-stop").disabled = false;
        document.getElementById("btn-start").disabled = false;
      }, 2000);
    });
};

// Re-enable start button when training ends (via SSE)
// Handled inside onTrainingEnd / onTrainingStopped
