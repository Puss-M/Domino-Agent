/* Domino Agent — zero-build research cockpit. */
"use strict";

const state = {
  analysis: null,
  health: null,
  sources: null,
  backtest: {},
  selected: null,
  edges: [],
};

const MODEL_LABELS = {
  always_up_test: "Always-up base rate",
  coin_flip_test: "Coin flip",
  mechanism_test: "Mechanism only",
  analog_test: "Historical analog only",
  hybrid_test: "Hybrid (mechanism + analog)",
  stacked_test: "Stacked",
  mechanism_calibrated_test: "Mechanism + Platt",
  analog_calibrated_test: "Analog + Platt",
  hybrid_calibrated_test: "Hybrid + Platt",
  stacked_calibrated_test: "Stacked + Platt",
  symbolic_test: "Symbolic only (E6)",
  symbolic_gated_test: "Symbolic gated (E6)",
  symbolic_blend_test: "Symbolic blend (E6)",
  lightgbm: "LightGBM (E13)",
  ridge: "Ridge (E13)",
  momentum: "Momentum (E13)",
  random: "Random (E13)",
};

const EXAMPLES = [
  "Fed raises rates by 50 basis points",
  "US CPI rises 3.5% in March, above expectations",
  "OPEC+ announces a 2 million barrels per day production cut",
  "US imposes new tariffs on Chinese goods",
  "Russia invades Ukraine",
  "SVB collapse triggers a bank run",
  "China unveils a stimulus package and cuts the reserve requirement ratio",
  "Bank of Japan raises its policy rate to 0.25%",
];

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function fmt(value, digits = 2, fallback = "—") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return fallback;
  return Number(value).toFixed(digits);
}

function pct(value, digits = 1) {
  if (value === null || value === undefined) return "—";
  return `${(Number(value) * 100).toFixed(digits)}%`;
}

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || JSON.stringify(body);
    } catch (_error) {
      /* keep status text */
    }
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json();
}

function setStatus(message, kind = "normal") {
  const node = $("#statusLine");
  node.textContent = message;
  node.style.color = kind === "error" ? "var(--crimson)" : kind === "busy" ? "var(--amber)" : "var(--muted)";
}

function renderHealth() {
  const health = state.health;
  if (!health) return;
  $("#healthChips").innerHTML = `
    <span class="chip"><strong>${health.n_events}</strong> events</span>
    <span class="chip"><strong>${health.n_mechanisms}</strong> mechanisms</span>
    <span class="chip"><strong>${health.n_channels}</strong> channels</span>
    <span class="chip"><strong>${health.data_sources}</strong> sources</span>
    <span class="chip">offline engine</span>
  `;
  $("#footerMeta").textContent = `v${health.version} · knowledge v${health.knowledge_version}`;
}

function renderExamples() {
  $("#examples").innerHTML = EXAMPLES.map(
    (example) => `<button class="example" type="button" data-example="${escapeHtml(example)}">${escapeHtml(example)}</button>`
  ).join("");
  $$(".example").forEach((button) => {
    button.addEventListener("click", () => {
      $("#headline").value = button.dataset.example;
      analyze();
    });
  });
}

async function analyze() {
  const headline = $("#headline").value.trim();
  if (!headline) {
    setStatus("Enter an event headline first.", "error");
    return;
  }
  const button = $("#analyzeBtn");
  button.disabled = true;
  $("#analyzeLabel").textContent = "Running…";
  setStatus("Extracting event → retrieving cited mechanisms → building graph…", "busy");
  const started = performance.now();
  try {
    const analysis = await fetchJSON("/api/analyze", {
      method: "POST",
      body: JSON.stringify({ headline, source_name: "user" }),
    });
    state.analysis = analysis;
    renderAnalysis(analysis);
    const elapsed = Math.round(performance.now() - started);
    $("#latencyLine").textContent = `${elapsed} ms · deterministic`;
    setStatus(
      analysis.audit.passed
        ? "Run complete. Evidence audit passed."
        : "Run complete. Audit flagged issues — read the audit panel.",
      analysis.audit.passed ? "normal" : "error"
    );
  } catch (error) {
    setStatus(`Analysis failed: ${error.message}`, "error");
  } finally {
    button.disabled = false;
    $("#analyzeLabel").textContent = "Run transmission";
  }
}

function renderAnalysis(analysis) {
  const event = analysis.event;
  $("#eventDate").textContent = new Date(event.published_at).toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });

  const magnitude = event.magnitude
    ? `${fmt(event.magnitude.value, 2)} ${event.magnitude.unit}`
    : "—";
  const surprise = event.surprise
    ? event.surprise.sign === "neutral" && !event.surprise.value
      ? "not quantified"
      : `${event.surprise.sign} ${event.surprise.value ? fmt(event.surprise.value, 2) : ""} ${event.surprise.unit || ""}`.trim()
    : "—";
  const sentiment = event.text_sentiment || {};
  const directionClass = ["tightening", "upside", "escalation", "supply_cut", "risk_off", "stress"].includes(
    event.direction
  )
    ? "neg"
    : ["easing", "downside", "deescalation", "supply_increase", "risk_on", "stimulus"].includes(event.direction)
      ? "pos"
      : "";

  $("#eventCard").innerHTML = `
    <h1 class="event-title">${escapeHtml(event.headline)}</h1>
    <div class="event-tags">
      <span class="tag type">${escapeHtml(event.event_type.replaceAll("_", " "))}</span>
      <span class="tag ${directionClass}">${escapeHtml(event.direction.replaceAll("_", " "))}</span>
      ${event.actor ? `<span class="tag">${escapeHtml(event.actor)}</span>` : ""}
      ${event.source?.name ? `<span class="tag">${escapeHtml(event.source.name)}</span>` : ""}
    </div>
    <div class="fact-grid">
      <div class="fact"><div class="fact-label">Actor</div><div class="fact-value">${escapeHtml(event.actor || "—")}</div></div>
      <div class="fact"><div class="fact-label">Magnitude</div><div class="fact-value">${escapeHtml(magnitude)}</div></div>
      <div class="fact"><div class="fact-label">Surprise</div><div class="fact-value">${escapeHtml(surprise)}</div></div>
      <div class="fact"><div class="fact-label">Tone polarity</div><div class="fact-value">${escapeHtml(fmt(sentiment.polarity, 2))}</div></div>
      <div class="fact"><div class="fact-label">Uncertainty</div><div class="fact-value">${escapeHtml(fmt(sentiment.uncertainty, 2))}</div></div>
      <div class="fact"><div class="fact-label">Extraction</div><div class="fact-value">${escapeHtml(event.extraction_method)}</div></div>
    </div>
    <div class="confidence">
      <div class="confidence-label"><span>extraction confidence</span><span class="mono">${pct(event.confidence, 0)}</span></div>
      <div class="bar"><span style="width:${Math.round(event.confidence * 100)}%"></span></div>
    </div>
  `;

  renderAssetTable(analysis.predictions, analysis.symbolic);
  renderMemo(analysis.memo);
  renderAudit(analysis.audit);
  renderSymbolic(analysis.symbolic);
  renderGraph(analysis.graph, analysis.predictions);
  renderSelectionDefault(analysis);
}

function renderAssetTable(predictions, symbolic) {
  const proofMap = new Map((symbolic?.proofs || []).map((proof) => [proof.asset, proof]));
  const proofLetter = { proved: "P", ambiguous: "A", not_entailed: "X", unverified: "U" };
  const rows = predictions
    .slice()
    .sort((left, right) => Math.abs(right.expected_car_bps) - Math.abs(left.expected_car_bps));
  $("#assetCount").textContent = `${rows.filter((row) => !row.abstain).length}/${rows.length} active`;
  $("#assetTable").innerHTML = rows
    .map((prediction) => {
      const prob = Math.round(prediction.p_up * 100);
      const direction = prediction.abstain ? "flat" : prediction.direction;
      return `
        <div class="asset-row" title="${escapeHtml(prediction.label)}">
          <span class="ticker">${escapeHtml(prediction.asset)}</span>
          <span class="dir ${direction}">${prediction.abstain ? "abstain" : direction}</span>
          <span class="prob"><span class="${direction}" style="width:${prob}%"></span></span>
          <span class="num">${fmt(prediction.p_up, 2)}</span>
          <span class="num">${prediction.abstain ? "—" : `${prediction.expected_car_bps > 0 ? "+" : ""}${fmt(prediction.expected_car_bps, 0)}bp`}</span>
          <span class="grade ${prediction.evidence_grade}">${prediction.evidence_grade}</span>
          <span class="proof ${proofMap.get(prediction.asset)?.status || "unverified"}" title="${escapeHtml(proofMap.get(prediction.asset)?.note || "No symbolic proof")}">${proofLetter[proofMap.get(prediction.asset)?.status] || "U"}</span>
        </div>
      `;
    })
    .join("");
}

function renderMemo(memo) {
  const list = (items) => (items?.length ? `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : "");
  $("#memo").innerHTML = `
    <p>${escapeHtml(memo.summary)}</p>
    ${memo.transmission?.length ? `<h3>Transmission</h3>${list(memo.transmission)}` : ""}
    ${memo.asset_views?.length ? `<h3>Largest priors</h3>${list(memo.asset_views)}` : ""}
    ${memo.falsifiers?.length ? `<h3>What would falsify this</h3>${list(memo.falsifiers)}` : ""}
    ${memo.monitoring?.length ? `<h3>Monitoring</h3>${list(memo.monitoring)}` : ""}
    ${memo.citations?.length ? `<details><summary class="mono">${memo.citations.length} citations</summary>${list(memo.citations)}</details>` : ""}
    <p class="mono" style="margin-top:12px">${escapeHtml(memo.disclaimer || "")}</p>
  `;
}

function renderSymbolic(symbolic) {
  if (!symbolic) {
    $("#symbolicBadge").textContent = "—";
    $("#symbolic").innerHTML = `<div class="placeholder">No symbolic report.</div>`;
    return;
  }
  const counts = symbolic.proofs.reduce((acc, proof) => {
    acc[proof.status] = (acc[proof.status] || 0) + 1;
    return acc;
  }, {});
  $("#symbolicBadge").textContent = symbolic.acyclic ? "DAG · certified" : "cycle!";
  const ambiguity = (symbolic.qualitative || []).filter((view) => view.sign === "?");
  const failures = (symbolic.policy_results || []).filter((result) => !result.passed);
  const policyList = (symbolic.policy_results || [])
    .map((result) => {
      const cls = result.passed ? "policy-pass" : result.severity === "warning" ? "policy-warn" : "policy-fail";
      return `<li class="${cls}">${result.passed ? "✓" : "✕"} ${escapeHtml(result.id)} ${escapeHtml(result.title)} <span class="mono">${escapeHtml(result.detail || "")}</span></li>`;
    })
    .join("");
  $("#symbolic").innerHTML = `
    <div class="stats">
      <span class="stat">${symbolic.node_count} nodes</span>
      <span class="stat">${symbolic.edge_count} edges</span>
      <span class="stat">${symbolic.acyclic ? "acyclic ✓" : "cycle ✕"}</span>
      <span class="stat">coverage ${pct(symbolic.proof_coverage, 1)}</span>
      <span class="stat">proved ${counts.proved || 0}</span>
      <span class="stat">ambiguous ${counts.ambiguous || 0}</span>
    </div>
    ${
      ambiguity.length
        ? `<h3>Ambiguity (not hidden)</h3><ul>${ambiguity
            .map(
              (view) =>
                `<li><strong>${escapeHtml(view.asset)}</strong>: ${escapeHtml(view.explanation)}</li>`
            )
            .join("")}</ul>`
        : `<h3>Ambiguity</h3><div class="placeholder">None: every active asset has a definite symbolic direction.</div>`
    }
    <h3>Policies</h3>
    <ul>${policyList}</ul>
    ${failures.length ? `<div class="mono" style="margin-top:6px">${failures.length} policy issue(s)</div>` : ""}
    <div class="hash">ledger ${escapeHtml(symbolic.ledger_hash || "—")}</div>
  `;
}

function renderAudit(audit) {
  $("#auditBadge").textContent = audit.passed ? "passed" : "flagged";
  const issues = audit.issues || [];
  const warnings = audit.warnings || [];
  $("#audit").innerHTML = `
    <div class="audit-status"><span class="dot ${audit.passed ? "" : "fail"}"></span>${audit.passed ? "Evidence checks passed" : "Evidence checks flagged issues"}</div>
    <div class="mono" style="margin-bottom:8px">${audit.checked_edges} edges checked · ${audit.used_mechanisms.length} mechanisms used</div>
    ${issues.length ? `<ul>${issues.map((item) => `<li><strong>issue:</strong> ${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
    ${warnings.length ? `<ul>${warnings.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
  `;
}

const SVG_NS = "http://www.w3.org/2000/svg";

function nodeBox(node) {
  if (node.kind === "event") return { w: 220, h: 78 };
  if (node.kind === "channel") return { w: 260, h: 56 };
  return { w: 150, h: 50 };
}

function layoutGraph(graph) {
  const nodes = graph.nodes;
  const eventNodes = nodes.filter((node) => node.kind === "event");
  const channelNodes = nodes.filter((node) => node.kind === "channel");
  const assetNodes = nodes.filter((node) => node.kind === "asset");
  const positions = new Map();
  const top = 92;
  const bottom = 720;
  const height = bottom - top;

  eventNodes.forEach((node, index) => {
    const box = nodeBox(node);
    const y = 90 + (height - box.h) * (eventNodes.length === 1 ? 0.5 : index / Math.max(1, eventNodes.length - 1));
    positions.set(node.id, { x: 42, y, ...box });
  });
  const distribute = (list, x, kind) => {
    list.forEach((node, index) => {
      const box = nodeBox(node);
      const y = top + (height - box.h) * (list.length === 1 ? 0.5 : index / (list.length - 1));
      positions.set(node.id, { x, y, ...box });
    });
  };
  distribute(channelNodes, 408, "channel");
  distribute(assetNodes, 862, "asset");
  return positions;
}

function truncate(text, length) {
  const value = String(text ?? "");
  return value.length > length ? `${value.slice(0, length - 1)}…` : value;
}

function renderGraph(graph, predictions) {
  const svg = $("#graph");
  svg.innerHTML = "";
  const defs = document.createElementNS(SVG_NS, "defs");
  defs.innerHTML = `
    <marker id="arrow-pos" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#0d6b5c"></path>
    </marker>
    <marker id="arrow-neg" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#a51c30"></path>
    </marker>
    <marker id="arrow-flow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#4a4037"></path>
    </marker>
  `;
  svg.appendChild(defs);

  const positions = layoutGraph(graph);
  const edgeLayer = document.createElementNS(SVG_NS, "g");
  const nodeLayer = document.createElementNS(SVG_NS, "g");
  svg.appendChild(edgeLayer);
  svg.appendChild(nodeLayer);

  ["EVENT", "TRANSMISSION CHANNEL", "ASSET"].forEach((label, index) => {
    const text = document.createElementNS(SVG_NS, "text");
    text.setAttribute("class", "column-label");
    text.setAttribute("x", [42, 408, 862][index]);
    text.setAttribute("y", 46);
    text.textContent = label;
    svg.appendChild(text);
  });

  const predictionMap = new Map(predictions.map((prediction) => [`asset:${prediction.asset}`, prediction]));
  const edgeElements = [];

  graph.edges.forEach((edge) => {
    const source = positions.get(edge.source);
    const target = positions.get(edge.target);
    if (!source || !target) return;
    if (Math.abs(edge.weight) < 0.06) return;
    const x1 = source.x + source.w;
    const y1 = source.y + source.h / 2;
    const x2 = target.x;
    const y2 = target.y + target.h / 2;
    const mid = (x1 + x2) / 2;
    const path = document.createElementNS(SVG_NS, "path");
    const flow = edge.source === "event";
    path.setAttribute("class", `edge ${flow ? "flow" : edge.sign >= 0 ? "pos" : "neg"}`);
    path.setAttribute("d", `M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`);
    path.setAttribute("stroke-width", String(1 + Math.min(1, Math.abs(edge.weight)) * 4));
    path.setAttribute("stroke-opacity", String(0.28 + Math.min(1, Math.abs(edge.weight) * 2) * 0.6));
    path.dataset.source = edge.source;
    path.dataset.target = edge.target;
    path.dataset.mechanism = edge.mechanism_id;
    path.dataset.rationale = edge.rationale;
    path.dataset.channel = edge.channel;
    path.dataset.grade = edge.evidence_grade;
    path.dataset.citations = JSON.stringify(edge.citations || []);
    const title = document.createElementNS(SVG_NS, "title");
    title.textContent = `${edge.mechanism_id}: ${edge.rationale}`;
    path.appendChild(title);
    path.addEventListener("mouseenter", (event) => showEdgeTooltip(event, edge));
    path.addEventListener("mousemove", moveTooltip);
    path.addEventListener("mouseleave", hideTooltip);
    path.addEventListener("click", () => selectEdge(edge));
    edgeLayer.appendChild(path);
    edgeElements.push(path);
  });

  graph.nodes.forEach((node) => {
    const box = positions.get(node.id);
    if (!box) return;
    const group = document.createElementNS(SVG_NS, "g");
    group.setAttribute("class", `node ${node.kind}`);
    group.dataset.id = node.id;
    const rect = document.createElementNS(SVG_NS, "rect");
    rect.setAttribute("x", box.x);
    rect.setAttribute("y", box.y);
    rect.setAttribute("width", box.w);
    rect.setAttribute("height", box.h);
    group.appendChild(rect);

    const padding = 12;
    let label;
    let sub;
    if (node.kind === "event") {
      label = truncate(node.label, 34);
      sub = `${String(node.meta.event_type || "").replaceAll("_", " ")} · ${String(node.meta.direction || "").replaceAll("_", " ")}`;
    } else if (node.kind === "channel") {
      label = truncate(node.label, 32);
      sub = `score ${Number(node.meta.score ?? 0) >= 0 ? "+" : ""}${fmt(node.meta.score, 2)}`;
    } else {
      const prediction = predictionMap.get(node.id);
      label = prediction ? `${prediction.asset} · ${prediction.direction}` : node.label;
      sub = prediction
        ? `P(up) ${fmt(prediction.p_up, 2)} · ${prediction.expected_car_bps > 0 ? "+" : ""}${fmt(prediction.expected_car_bps, 0)}bp`
        : `${fmt(node.confidence, 2)}`;
    }
    const text = document.createElementNS(SVG_NS, "text");
    text.setAttribute("x", box.x + padding);
    text.setAttribute("y", box.y + (node.kind === "event" ? 30 : 22));
    text.textContent = label;
    group.appendChild(text);

    const subText = document.createElementNS(SVG_NS, "text");
    subText.setAttribute("class", "sub");
    subText.setAttribute("x", box.x + padding);
    subText.setAttribute("y", box.y + (node.kind === "event" ? 48 : 38));
    subText.textContent = sub;
    group.appendChild(subText);

    group.addEventListener("mouseenter", (event) => {
      edgeElements.forEach((path) => {
        const connected = path.dataset.source === node.id || path.dataset.target === node.id;
        path.classList.toggle("dim", !connected);
        path.classList.toggle("active", connected);
      });
      showNodeTooltip(event, node);
    });
    group.addEventListener("mousemove", moveTooltip);
    group.addEventListener("mouseleave", () => {
      edgeElements.forEach((path) => path.classList.remove("dim", "active"));
      hideTooltip();
    });
    group.addEventListener("click", () => selectNode(node, graph));
    nodeLayer.appendChild(group);
  });
}

function showEdgeTooltip(event, edge) {
  const tooltip = $("#tooltip");
  tooltip.innerHTML = `
    <div class="t-title">${escapeHtml(edge.mechanism_id)} · ${edge.sign >= 0 ? "positive" : "negative"}</div>
    <div>${escapeHtml(edge.rationale)}</div>
    <div class="t-meta">channel: ${escapeHtml(edge.channel)} · grade ${escapeHtml(edge.evidence_grade)} · weight ${fmt(edge.weight, 2)}</div>
  `;
  tooltip.hidden = false;
  moveTooltip(event);
}

function showNodeTooltip(event, node) {
  const tooltip = $("#tooltip");
  const meta = node.meta || {};
  tooltip.innerHTML = `
    <div class="t-title">${escapeHtml(node.label)}</div>
    <div class="t-meta">${escapeHtml(node.kind)} · confidence ${fmt(node.confidence, 2)}</div>
    ${meta.description ? `<div style="margin-top:4px">${escapeHtml(meta.description)}</div>` : ""}
  `;
  tooltip.hidden = false;
  moveTooltip(event);
}

function moveTooltip(event) {
  const tooltip = $("#tooltip");
  if (tooltip.hidden) return;
  const wrap = $(".graph-wrap").getBoundingClientRect();
  const x = Math.min(event.clientX - wrap.left + 14, wrap.width - 330);
  const y = Math.max(8, event.clientY - wrap.top + 14);
  tooltip.style.left = `${x}px`;
  tooltip.style.top = `${y}px`;
}

function hideTooltip() {
  $("#tooltip").hidden = true;
}

function selectEdge(edge) {
  state.selected = edge;
  $("#selection").innerHTML = `
    <div class="sel-title">${escapeHtml(edge.mechanism_id)} → ${escapeHtml(edge.channel)}</div>
    <div>${escapeHtml(edge.rationale)}</div>
    <div class="mono" style="margin-top:5px">sign ${edge.sign >= 0 ? "+" : "−"} · weight ${fmt(edge.weight, 2)} · grade ${escapeHtml(edge.evidence_grade)}</div>
    ${
      edge.citations?.length
        ? `<ul>${edge.citations.map((citation) => `<li>${escapeHtml(citation)}</li>`).join("")}</ul>`
        : ""
    }
  `;
}

function selectNode(node, graph) {
  const connected = graph.edges.filter((edge) => edge.source === node.id || edge.target === node.id);
  state.selected = node;
  $("#selection").innerHTML = `
    <div class="sel-title">${escapeHtml(node.label)}</div>
    <div class="mono">${escapeHtml(node.kind)} · confidence ${fmt(node.confidence, 2)} · ${connected.length} edges</div>
    ${
      connected.length
        ? `<ul>${connected
            .slice(0, 8)
            .map(
              (edge) =>
                `<li>${escapeHtml(edge.mechanism_id)} · ${escapeHtml(edge.channel)} · sign ${edge.sign >= 0 ? "+" : "−"} · ${escapeHtml(edge.rationale)}</li>`
            )
            .join("")}</ul>`
        : ""
    }
  `;
}

function renderSelectionDefault(analysis) {
  const top = analysis.channel_activations?.[0];
  if (!top) {
    $("#selection").innerHTML = `<span class="placeholder">No channel passed the evidence threshold.</span>`;
    return;
  }
  $("#selection").innerHTML = `
    <div class="sel-title">${escapeHtml(top.name)} · score ${top.score >= 0 ? "+" : ""}${fmt(top.score, 2)}</div>
    <div>${escapeHtml(
      analysis.channel_activations
        .slice(0, 3)
        .map((channel) => `${channel.name} ${channel.score >= 0 ? "+" : ""}${fmt(channel.score, 2)}`)
        .join(" · ")
    )}</div>
    <div class="mono" style="margin-top:4px">Click any edge or node to inspect its mechanism and citations.</div>
  `;
}

function openModal(id) {
  const modal = $(`#${id}`);
  modal.hidden = false;
  document.body.style.overflow = "hidden";
  const focusable = modal.querySelector("button");
  if (focusable) focusable.focus();
}

function closeModal(id) {
  $(`#${id}`).hidden = true;
  document.body.style.overflow = "";
}

async function loadBacktest() {
  openModal("backtestModal");
  const dataset = $("#datasetSelect").value;
  const body = $("#backtestBody");
  if (state.backtest[dataset]) {
    renderBacktest(state.backtest[dataset]);
    return;
  }
  body.innerHTML = `<div class="placeholder">Running walk-forward evaluation on ${escapeHtml(dataset)}…</div>`;
  try {
    state.backtest[dataset] = await fetchJSON("/api/backtest", {
      method: "POST",
      body: JSON.stringify({ dataset, window_end: 1, bootstrap_samples: 300 }),
    });
    renderBacktest(state.backtest[dataset]);
  } catch (error) {
    body.innerHTML = `<div class="empty-state">Backtest failed: ${escapeHtml(error.message)}</div>`;
  }
}

function renderBacktest(data) {
  const metrics = data.metrics || [];
  const chosen = metrics.find((metric) => metric.model === "stacked_calibrated_test") || metrics[0];
  const extraction = data.extraction || {};
  const metricCard = (label, value, sub) => `
    <div class="metric"><div class="label">${escapeHtml(label)}</div><div class="value">${escapeHtml(value)}</div><div class="sub">${escapeHtml(sub)}</div></div>
  `;
  const rows = metrics
    .map((metric) => {
      const highlight = metric.model === "stacked_calibrated_test" ? "highlight" : "";
      const ci = metric.accuracy_ci ? `[${fmt(metric.accuracy_ci[0], 2)}, ${fmt(metric.accuracy_ci[1], 2)}]` : "—";
      return `
        <tr class="${highlight}">
          <td>${escapeHtml(MODEL_LABELS[metric.model] || metric.model)}</td>
          <td class="num">${metric.n}</td>
          <td class="num">${fmt(metric.coverage, 3)}</td>
          <td class="num">${fmt(metric.accuracy, 3)}</td>
          <td class="num">${ci}</td>
          <td class="num">${fmt(metric.brier, 3)}</td>
          <td class="num">${fmt(metric.auc, 3)}</td>
          <td class="num">${fmt(metric.ece, 3)}</td>
        </tr>
      `;
    })
    .join("");
  const byAsset = (data.by_asset || [])
    .map(
      (asset) => `
        <tr>
          <td>${escapeHtml(asset.asset)}</td>
          <td class="num">${asset.n}</td>
          <td class="num">${fmt(asset.accuracy, 3)}</td>
          <td class="num">${fmt(asset.brier, 3)}</td>
          <td class="num">${asset.mean_car_bps === null ? "—" : `${asset.mean_car_bps > 0 ? "+" : ""}${fmt(asset.mean_car_bps, 0)}bp`}</td>
        </tr>
      `
    )
    .join("");
  $("#backtestBody").innerHTML = `
    <p class="hint" style="margin:0 0 12px">Benchmark: <strong>${escapeHtml(data.config.dataset)}</strong>. All model metrics below are on the held-out second half of the event sample. Stack weights and Platt calibration are fitted on the first half only. Dataset <em>fomc</em> is a stress test of action-only policy events; it is expected to expose the cost of the mechanism prior.</p>
    <div id="pitBody" class="pit"></div>
    <div id="xsBody" class="xs"></div>
    <div class="metric-grid">
      ${metricCard("Events", data.n_events, `${data.n_outcome_observations} outcome obs`)}
      ${metricCard("Window", `0..${data.config.window_end}`, "trading days")}
      ${metricCard("Directional accuracy", pct(chosen?.accuracy, 1), "stacked + calibrated")}
      ${metricCard("Brier", fmt(chosen?.brier, 3), `baseline ${fmt(metrics.find((m) => m.model === "always_up_test")?.brier, 3)}`)}
      ${metricCard("AUC", fmt(chosen?.auc, 3), "rank discrimination")}
      ${metricCard("Coverage", pct(chosen?.coverage, 1), "non-abstain")}
      ${metricCard(
        "Extraction",
        extraction.n ? pct(extraction.joint_accuracy, 0) : "n/a",
        extraction.n ? "type + direction" : "templated headlines"
      )}
      ${metricCard("Bootstrap CI", chosen?.accuracy_ci ? `${fmt(chosen.accuracy_ci[0], 2)}–${fmt(chosen.accuracy_ci[1], 2)}` : "—", "event-clustered")}
    </div>
    <table>
      <thead><tr><th>Model</th><th class="num">n</th><th class="num">Coverage</th><th class="num">Accuracy</th><th class="num">95% CI</th><th class="num">Brier</th><th class="num">AUC</th><th class="num">ECE</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <h3 class="section-title">Calibration</h3>
    ${renderCalibration(data.calibration || [])}
    <h3 class="section-title">By asset</h3>
    <table>
      <thead><tr><th>Asset</th><th class="num">n</th><th class="num">Accuracy</th><th class="num">Brier</th><th class="num">Mean CAR</th></tr></thead>
      <tbody>${byAsset}</tbody>
    </table>
    <div class="notes">
      <strong>Protocol notes</strong>
      <ul>${(data.notes || []).map((note) => `<li>${escapeHtml(note)}</li>`).join("")}</ul>
    </div>
  `;
  loadPointInTime(data.config.dataset);
  loadCrossSectional(data.config.dataset);
}

async function loadCrossSectional(dataset) {
  const el = $("#xsBody");
  if (!el) return;
  el.innerHTML = `<div class="placeholder">Running cross-sectional rank + cost audit…</div>`;
  try {
    const data = await fetchJSON(`/api/cross-sectional?dataset=${encodeURIComponent(dataset)}`);
    const rows = ["lightgbm", "ridge", "momentum", "random"]
      .map((name) => {
        const metrics = data.models[name] || {};
        const ci = metrics.gross_ls_ci
          ? `[${fmt(metrics.gross_ls_ci[0], 1)}, ${fmt(metrics.gross_ls_ci[1], 1)}]`
          : "—";
        const net10 = metrics.net_ls_bps ? metrics.net_ls_bps["10"] : null;
        return `
          <tr>
            <td>${escapeHtml(MODEL_LABELS[name] || name)}</td>
            <td class="num">${fmt(metrics.mean_rank_ic, 3)}</td>
            <td class="num">${metrics.gross_ls_bps === undefined ? "—" : `${fmt(metrics.gross_ls_bps, 1)}bp`}</td>
            <td class="num">${ci}</td>
            <td class="num">${net10 === null ? "—" : `${fmt(net10, 1)}bp`}</td>
          </tr>
        `;
      })
      .join("");
    el.innerHTML = `
      <h3 class="section-title">Cross-sectional rank (E13)</h3>
      <p class="hint" style="margin:0 0 8px">Target = within-event CAR rank. Features are strictly pre-event; net = gross − 2 × 10bp. No model replicates across datasets, so this is a protocol check, not an alpha claim.</p>
      <table>
        <thead><tr><th>Model</th><th class="num">Rank IC</th><th class="num">Gross L/S</th><th class="num">95% CI</th><th class="num">Net @10bp</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  } catch (error) {
    el.innerHTML = `<div class="empty-state">Cross-sectional audit unavailable: ${escapeHtml(error.message)}</div>`;
  }
}

async function loadPointInTime(dataset) {
  const el = $("#pitBody");
  if (!el) return;
  el.innerHTML = `<div class="placeholder">Checking point-in-time contract…</div>`;
  try {
    const audit = await fetchJSON(`/api/point-in-time?dataset=${encodeURIComponent(dataset)}`);
    const revised = (audit.revised_sources || []).join(", ") || "none";
    const cls = audit.verdict === "point_in_time" ? "pass" : "warn";
    el.innerHTML = `
      <div class="pit-card ${cls}">
        <div>
          <strong>Point-in-time: ${escapeHtml(audit.verdict.replaceAll("_", " "))}</strong>
          <span>LLM-free metric path · ${escapeHtml(String(audit.n_events))} events</span>
        </div>
        <div class="pit-detail">Revised / ex-post inputs: ${escapeHtml(revised)}</div>
      </div>
    `;
  } catch (error) {
    el.innerHTML = `<div class="empty-state">Point-in-time audit unavailable: ${escapeHtml(error.message)}</div>`;
  }
}

function renderCalibration(bins) {
  if (!bins.length) return `<div class="placeholder">No calibration bins.</div>`;
  const width = 720;
  const height = 240;
  const pad = 34;
  const plotW = width - pad * 2;
  const plotH = height - pad * 2;
  const bars = bins
    .map((bin, index) => {
      const slot = plotW / bins.length;
      const x = pad + index * slot + slot * 0.16;
      const barW = slot * 0.68;
      const predictedH = plotH * bin.mean_predicted;
      const observedH = plotH * bin.observed_frequency;
      return `
        <g>
          <rect x="${x}" y="${pad + plotH - predictedH}" width="${barW / 2 - 1}" height="${predictedH}" fill="#b9a993"></rect>
          <rect x="${x + barW / 2 + 1}" y="${pad + plotH - observedH}" width="${barW / 2 - 1}" height="${observedH}" fill="#0d6b5c"></rect>
          <text x="${x + barW / 2}" y="${height - 12}" text-anchor="middle" font-size="9" fill="#7b6f61" font-family="monospace">${bin.bin_lower.toFixed(2)}–${bin.bin_upper.toFixed(2)}</text>
          <text x="${x + barW / 2}" y="${pad + plotH - Math.max(predictedH, observedH) - 4}" text-anchor="middle" font-size="8" fill="#7b6f61" font-family="monospace">n=${bin.n}</text>
        </g>
      `;
    })
    .join("");
  return `
    <svg class="calibration-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Calibration reliability diagram">
      <line x1="${pad}" y1="${pad + plotH}" x2="${pad + plotW}" y2="${pad + plotH}" stroke="#b9a993"></line>
      <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${pad + plotH}" stroke="#b9a993"></line>
      <line x1="${pad}" y1="${pad + plotH}" x2="${pad + plotW}" y2="${pad}" stroke="#d9cdbb" stroke-dasharray="4 4"></line>
      <text x="${pad + 4}" y="${pad + 10}" font-size="9" fill="#7b6f61" font-family="monospace">observed</text>
      <text x="${pad + plotW - 4}" y="${pad + plotH - 6}" text-anchor="end" font-size="9" fill="#7b6f61" font-family="monospace">predicted</text>
      ${bars}
      <text x="${width - 8}" y="${height - 4}" text-anchor="end" font-size="9" fill="#7b6f61" font-family="monospace">grey = mean predicted · green = observed</text>
    </svg>
  `;
}

async function loadSources() {
  openModal("sourcesModal");
  const body = $("#sourcesBody");
  if (state.sources) {
    renderSources(state.sources);
    return;
  }
  body.innerHTML = `<div class="placeholder">Loading source catalog…</div>`;
  try {
    state.sources = await fetchJSON("/api/data-sources");
    renderSources(state.sources);
  } catch (error) {
    body.innerHTML = `<div class="empty-state">Could not load sources: ${escapeHtml(error.message)}</div>`;
  }
}

function renderSources(sources) {
  $("#sourcesBody").innerHTML = sources
    .map(
      (source) => `
        <div class="source-card">
          <h3>${escapeHtml(source.name)}</h3>
          <div class="meta">${escapeHtml(source.provider)} · ${escapeHtml(source.access)}</div>
          <p>${escapeHtml(source.notes)}</p>
          <div class="meta" style="margin-top:6px">PIT: ${escapeHtml(source.point_in_time)} · revision: ${escapeHtml(source.revision)} · license: ${escapeHtml(source.license)}</div>
        </div>
      `
    )
    .join("");
}

function downloadJSON() {
  if (!state.analysis) {
    setStatus("Run an analysis before exporting.", "error");
    return;
  }
  const blob = new Blob([JSON.stringify(state.analysis, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `domino-${state.analysis.event.id}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function init() {
  renderExamples();
  $("#analyzeBtn").addEventListener("click", analyze);
  $("#downloadBtn").addEventListener("click", downloadJSON);
  $("#backtestBtn").addEventListener("click", loadBacktest);
  $("#datasetSelect").addEventListener("change", () => {
    state.backtest = {};
    loadBacktest();
  });
  $("#sourcesBtn").addEventListener("click", loadSources);
  $("#closeBacktest").addEventListener("click", () => closeModal("backtestModal"));
  $("#closeSources").addEventListener("click", () => closeModal("sourcesModal"));
  $$(".modal-backdrop").forEach((backdrop) => {
    backdrop.addEventListener("click", () => {
      const modal = backdrop.closest(".modal");
      if (modal) closeModal(modal.id);
    });
  });
  $("#headline").addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") analyze();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      ["backtestModal", "sourcesModal"].forEach((id) => {
        if (!$(`#${id}`).hidden) closeModal(id);
      });
    }
  });

  try {
    state.health = await fetchJSON("/api/health");
    renderHealth();
  } catch (error) {
    setStatus(`Backend unavailable: ${error.message}`, "error");
    return;
  }
  analyze();
}

document.addEventListener("DOMContentLoaded", init);
