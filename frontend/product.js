/* Domino Audit Desk — calendar, notes, watchlist, digest, review. */
"use strict";

const state = {
  view: "calendar",
  calendar: null,
  notes: [],
  watchlist: [],
  digest: null,
  note: null,
  auditDesk: null,
  pendingEvent: null,
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

function esc(value) {
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

async function api(path, options = {}) {
  const response = await fetch(path, {
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
  const type = response.headers.get("content-type") || "";
  if (type.includes("application/json")) return response.json();
  return response.text();
}

function toast(message) {
  const node = $("#toast");
  node.textContent = message;
  node.hidden = false;
  window.clearTimeout(toast._timer);
  toast._timer = window.setTimeout(() => {
    node.hidden = true;
  }, 3200);
}

function dateLabel(value) {
  if (!value) return "—";
  const date = new Date(`${value}T00:00:00`);
  return date.toLocaleDateString("en-US", { month: "short", day: "2-digit", year: "numeric" });
}

function daysLabel(event) {
  if (event.is_past) return "past";
  if (event.days_until === 0) return "today";
  if (event.days_until === 1) return "tomorrow";
  return `in ${event.days_until}d`;
}

function proofMap(payload) {
  return new Map(((payload.symbolic || {}).proofs || []).map((proof) => [proof.asset, proof]));
}

function statusBadge(status) {
  const cls = status === "reviewed" ? "ok" : status === "archived" ? "medium" : "warn";
  return `<span class="badge ${cls}">${esc(status)}</span>`;
}

function setView(view) {
  state.view = view;
  state.note = null;
  $$(".desk-tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.view === view);
  });
  render();
}

function setSummary() {
  const desk = state.auditDesk || {};
  const next = desk.next_event ? `${desk.next_event.date} ${desk.next_event.title}` : "no upcoming event";
  $("#deskSummary").textContent =
    `${desk.n_upcoming || 0} upcoming · ${desk.n_drafts || 0} drafts · ${desk.n_reviewed || 0} reviewed`;
  return next;
}

function hero(kicker, title, copy) {
  return `<section class="desk-hero">
    <div><div class="desk-kicker">${esc(kicker)}</div><h1>${esc(title)}</h1><p>${esc(copy)}</p></div>
  </section>`;
}

function render() {
  const main = $("#productMain");
  if (state.view === "calendar") renderCalendar(main);
  else if (state.view === "notes") renderNotes(main);
  else if (state.view === "watchlist") renderWatchlist(main);
  else if (state.view === "digest") renderDigest(main);
  else if (state.view === "note") renderNote(main);
}

function renderCalendar(main) {
  const events = (state.calendar || {}).events || [];
  const upcoming = events.filter((event) => !event.is_past);
  const past = events.filter((event) => event.is_past);
  const cards = (list, isPast) =>
    list
      .map(
        (event) => `<article class="event-card ${isPast ? "past" : ""}">
        <div class="event-date">${esc(dateLabel(event.date))}<small>${esc(event.time || "")}</small></div>
        <div>
          <div class="event-title">${esc(event.title)}</div>
          <div class="event-meta">
            <span class="badge ${esc(event.importance || "medium")}">${esc(event.importance || "medium")}</span>
            ${esc(event.event_type)} · ${esc(event.source || "calendar")} · ${esc(daysLabel(event))}
            ${event.custom ? "· custom" : ""}
          </div>
        </div>
        <div class="event-actions">
          <button class="button solid" type="button" data-create-note="${esc(event.id)}">Create note</button>
          ${event.url ? `<a class="button ghost" href="${esc(event.url)}" target="_blank" rel="noreferrer">Source</a>` : ""}
        </div>
      </article>`
      )
      .join("");
  main.innerHTML = `
    ${hero("Audit desk", "Macro calendar", "Sourced upcoming events. Create a note before the release; review it after the outcome window.")}
    <div class="desk-grid">
      <div class="desk-metric"><div class="label">Upcoming</div><div class="value">${upcoming.length}</div><div class="sub">next 60 days</div></div>
      <div class="desk-metric"><div class="label">Saved notes</div><div class="value">${state.notes.length}</div><div class="sub">all statuses</div></div>
      <div class="desk-metric"><div class="label">Watchlist</div><div class="value">${state.watchlist.length}</div><div class="sub">assets in digest</div></div>
      <div class="desk-metric"><div class="label">Next</div><div class="value" style="font-size:15px">${esc(upcoming[0]?.title || "—")}</div><div class="sub">${esc(upcoming[0]?.date || "no event")}</div></div>
    </div>
    <div class="desk-section-head">
      <div><h2>Upcoming</h2><p>FOMC and BEA releases; add your own event when the calendar is incomplete.</p></div>
      <button class="button ghost" id="addEventBtn" type="button">Add event</button>
    </div>
    <div class="desk-list">${cards(upcoming, false) || `<div class="empty-state">No upcoming events in the window.</div>`}</div>
    <div class="desk-section-head"><div><h2>Recently passed</h2><p>Create the note, then run the post-event review.</p></div></div>
    <div class="desk-list">${cards(past, true) || `<div class="empty-state">No recent events.</div>`}</div>
  `;
  $("#addEventBtn").addEventListener("click", openCustomEvent);
  $$("[data-create-note]").forEach((button) => {
    button.addEventListener("click", () => openScenario(button.dataset.createNote));
  });
}

function openScenario(eventId) {
  const event = (state.calendar?.events || []).find((item) => item.id === eventId);
  if (!event || event.event_type !== "monetary_policy") {
    createNote(eventId);
    return;
  }
  const options = [
    {
      key: "hike25",
      title: "Hike 25bp",
      copy: "Fed raises the target range by 25bp.",
      headline: "Fed raises rates by 25 basis points",
      summary: `Scenario for ${event.title} on ${event.date}: a 25bp hike.`,
    },
    {
      key: "cut25",
      title: "Cut 25bp",
      copy: "Fed cuts the target range by 25bp.",
      headline: "Fed cuts rates by 25 basis points",
      summary: `Scenario for ${event.title} on ${event.date}: a 25bp cut.`,
    },
    {
      key: "hawkish_hold",
      title: "Hawkish hold",
      copy: "No change, but a hawkish statement.",
      headline: "Fed holds rates steady and signals a hawkish stance",
      summary: `Scenario for ${event.title} on ${event.date}: a hawkish hold.`,
    },
    {
      key: "dovish_hold",
      title: "Dovish hold",
      copy: "No change, but a dovish statement.",
      headline: "Fed holds rates steady and signals a dovish stance",
      summary: `Scenario for ${event.title} on ${event.date}: a dovish hold.`,
    },
    {
      key: "none",
      title: "No scenario",
      copy: "Run the calendar headline and let the engine abstain if no mechanism matches.",
      headline: event.title,
      summary: event.summary || "",
    },
  ];
  state.pendingEvent = { event, options };
  $("#scenarioTitle").textContent = `${event.title} · ${event.date}`;
  $("#scenarioOptions").innerHTML = options
    .map(
      (option) => `<button type="button" data-scenario="${esc(option.key)}">
        <strong>${esc(option.title)}</strong><span>${esc(option.copy)}</span>
      </button>`
    )
    .join("");
  $("#scenarioModal").hidden = false;
  document.body.style.overflow = "hidden";
  $$("#scenarioOptions [data-scenario]").forEach((button) => {
    button.addEventListener("click", () => createScenarioNote(button.dataset.scenario));
  });
}

function closeScenario() {
  $("#scenarioModal").hidden = true;
  document.body.style.overflow = "";
  state.pendingEvent = null;
}

async function createScenarioNote(scenarioKey) {
  const pending = state.pendingEvent;
  if (!pending) return;
  const option = pending.options.find((item) => item.key === scenarioKey);
  if (!option) return;
  const { event } = pending;
  closeScenario();
  try {
    toast("Running deterministic transmission…");
    const note = await api("/api/notes", {
      method: "POST",
      body: JSON.stringify({
        event_id: event.id,
        headline: option.headline,
        summary: option.summary,
        session: event.session,
        source_name: event.source,
        source_url: event.url,
        published_at: `${event.date}T00:00:00Z`,
      }),
    });
    state.notes = [note, ...state.notes];
    state.note = note;
    state.view = "note";
    await refreshAuditDesk();
    render();
    toast("Scenario note saved");
  } catch (error) {
    toast(`Could not create note: ${error.message}`);
  }
}

function renderNotes(main) {
  const rows = state.notes
    .map(
      (note) => `<tr data-note="${esc(note.id)}" style="cursor:pointer">
        <td>${esc(note.created_at?.slice(0, 10) || "")}</td>
        <td>${esc(note.headline)}<br><span class="event-meta">${esc(note.event_type)} · ${esc(note.direction)}</span></td>
        <td>${statusBadge(note.status)}</td>
        <td class="num">${note.n_proved || 0}/${note.n_ambiguous || 0}</td>
        <td class="num">${note.review ? pct(note.review.hit_rate) : "—"}</td>
      </tr>`
    )
    .join("");
  main.innerHTML = `
    ${hero("Audit desk", "Saved notes", "Every note is a deterministic analysis plus a policy result and a ledger hash. Open one to export or review.")}
    <div class="desk-toolbar">
      <input id="noteSearch" type="search" placeholder="Search headline or event type…" />
      <select id="noteStatus">
        <option value="">All statuses</option>
        <option value="draft">Draft</option>
        <option value="reviewed">Reviewed</option>
        <option value="archived">Archived</option>
      </select>
      <span class="event-meta" id="noteCount">${state.notes.length} notes</span>
    </div>
    <table class="desk-table">
      <thead><tr><th>Date</th><th>Headline</th><th>Status</th><th class="num">Proved / ambiguous</th><th class="num">Hit rate</th></tr></thead>
      <tbody id="noteRows">${rows || `<tr><td colspan="5">No notes yet. Create one from the calendar.</td></tr>`}</tbody>
    </table>
  `;
  const filter = () => {
    const query = $("#noteSearch").value.toLowerCase();
    const status = $("#noteStatus").value;
    const filtered = state.notes.filter(
      (note) =>
        (!status || note.status === status) &&
        (!query ||
          note.headline.toLowerCase().includes(query) ||
          (note.event_type || "").toLowerCase().includes(query))
    );
    $("#noteRows").innerHTML =
      filtered
        .map(
          (note) => `<tr data-note="${esc(note.id)}" style="cursor:pointer">
            <td>${esc(note.created_at?.slice(0, 10) || "")}</td>
            <td>${esc(note.headline)}<br><span class="event-meta">${esc(note.event_type)} · ${esc(note.direction)}</span></td>
            <td>${statusBadge(note.status)}</td>
            <td class="num">${note.n_proved || 0}/${note.n_ambiguous || 0}</td>
            <td class="num">${note.review ? pct(note.review.hit_rate) : "—"}</td>
          </tr>`
        )
        .join("") || `<tr><td colspan="5">No matching notes.</td></tr>`;
    $("#noteCount").textContent = `${filtered.length} notes`;
    bindNoteRows();
  };
  $("#noteSearch").addEventListener("input", filter);
  $("#noteStatus").addEventListener("change", filter);
  bindNoteRows();
}

function bindNoteRows() {
  $$("[data-note]").forEach((row) => {
    row.addEventListener("click", () => openNote(row.dataset.note));
  });
}

function renderWatchlist(main) {
  const chips = state.watchlist
    .map(
      (asset) => `<span class="asset-chip">${esc(asset)}
        <button type="button" data-remove-asset="${esc(asset)}" aria-label="Remove ${esc(asset)}">×</button>
      </span>`
    )
    .join("");
  main.innerHTML = `
    ${hero("Audit desk", "Watchlist", "The digest uses this list. Keep it small enough to read in one screen.")}
    <div class="watchlist">${chips || `<div class="empty-state">No assets yet.</div>`}</div>
    <form class="desk-inline-form" id="assetForm">
      <input name="asset" placeholder="SPY" maxlength="8" required />
      <button class="button solid" type="submit">Add asset</button>
    </form>
    <div class="desk-section-head"><div><h2>What this does</h2><p>Watchlist is a product preference, not a model input. It filters the digest and the saved-note review surface.</p></div></div>
  `;
  $("#assetForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const asset = new FormData(event.target).get("asset");
    try {
      const data = await api("/api/watchlist", { method: "POST", body: JSON.stringify({ asset }) });
      state.watchlist = data.assets;
      await refreshAuditDesk();
      render();
      toast(`${asset.toUpperCase()} added to watchlist`);
    } catch (error) {
      toast(`Could not add asset: ${error.message}`);
    }
  });
  $$("[data-remove-asset]").forEach((button) => {
    button.addEventListener("click", async () => {
      const data = await api(`/api/watchlist/${encodeURIComponent(button.dataset.removeAsset)}`, {
        method: "DELETE",
      });
      state.watchlist = data.assets;
      await refreshAuditDesk();
      render();
    });
  });
}

async function renderDigest(main) {
  main.innerHTML = `${hero("Audit desk", "Digest", "A plaintext-ready summary of the calendar, watchlist and recent notes.")}
    <div class="desk-toolbar">
      <button class="button solid" id="refreshDigest" type="button">Refresh</button>
      <button class="button ghost" id="copyDigest" type="button">Copy markdown</button>
      <a class="button ghost" href="/api/digest?days=14&format=html" target="_blank" rel="noreferrer">Open HTML</a>
    </div>
    <div class="digest-frame" id="digestFrame"><div class="placeholder">Loading digest…</div></div>`;
  $("#refreshDigest").addEventListener("click", loadDigest);
  $("#copyDigest").addEventListener("click", async () => {
    try {
      const markdown = await api("/api/digest?days=14&format=md");
      await navigator.clipboard.writeText(markdown);
      toast("Digest markdown copied");
    } catch (error) {
      toast(`Copy failed: ${error.message}`);
    }
  });
  await loadDigest();
}

async function loadDigest() {
  const target = $("#digestFrame");
  if (!target) return;
  target.innerHTML = `<div class="placeholder">Loading digest…</div>`;
  try {
    const html = await api("/api/digest?days=14&format=html");
    const iframe = document.createElement("iframe");
    iframe.title = "Macro audit digest";
    iframe.srcdoc = html;
    target.innerHTML = "";
    target.appendChild(iframe);
  } catch (error) {
    target.innerHTML = `<div class="empty-state">Digest unavailable: ${esc(error.message)}</div>`;
  }
}

async function createNote(eventId) {
  try {
    toast("Running deterministic transmission…");
    const note = await api("/api/notes", {
      method: "POST",
      body: JSON.stringify({ event_id: eventId }),
    });
    state.notes = [note, ...state.notes];
    state.note = note;
    state.view = "note";
    await refreshAuditDesk();
    render();
    toast("Note saved");
  } catch (error) {
    toast(`Could not create note: ${error.message}`);
  }
}

async function openNote(noteId) {
  try {
    state.note = await api(`/api/notes/${noteId}`);
    state.view = "note";
    render();
  } catch (error) {
    toast(`Could not open note: ${error.message}`);
  }
}

function renderNote(main) {
  const note = state.note;
  if (!note) {
    main.innerHTML = `<div class="empty-state">Note not loaded.</div>`;
    return;
  }
  const payload = note.payload || {};
  const event = payload.event || {};
  const memo = payload.memo || {};
  const symbolic = payload.symbolic || {};
  const proofs = proofMap(payload);
  const magnitude = event.magnitude || {};
  const surprise = event.surprise || {};
  const policies = symbolic.policy_results || [];
  const failed = policies.filter((policy) => !policy.passed);
  const rows = (payload.predictions || [])
    .map(
      (prediction) => `<tr>
        <td>${esc(prediction.asset)}</td>
        <td>${esc(prediction.direction)}</td>
        <td class="num">${pct(prediction.p_up)}</td>
        <td class="num">${fmt(prediction.expected_car_bps, 0)}bp</td>
        <td>${esc(proofs.get(prediction.asset)?.status || "unverified")}</td>
      </tr>`
    )
    .join("");
  const review = note.review;
  const reviewHtml = review
    ? `<div class="review-box ${review.status === "pending" ? "pending" : ""}">
        <strong>${esc(review.status)}</strong> · hit rate ${pct(review.hit_rate)} · n=${esc(review.n || 0)}
        · earliest stage: ${esc(review.attribution || "n/a")}
        ${review.review_notes ? `<p>${esc(review.review_notes)}</p>` : ""}
        ${(review.misses || []).length ? `<ul>${review.misses.map((miss) => `<li>${esc(miss)}</li>`).join("")}</ul>` : ""}
      </div>`
    : `<p class="event-meta">No post-event review yet. Run it after the outcome window.</p>`;
  main.innerHTML = `
    <div class="note-detail">
      <div class="desk-kicker">Macro event audit · ${esc(note.id)}</div>
      <h1>${esc(event.headline || note.headline)}</h1>
      <div class="note-meta">${esc(event.event_type)} · ${esc(event.direction)} · published ${esc(event.published_at)} · confidence ${pct(event.confidence)} · ${statusBadge(note.status)}</div>
      <div class="note-columns">
        <section>
          <h2>Event</h2>
          <p>Magnitude <strong>${esc(magnitude.value || "—")} ${esc(magnitude.unit || "")}</strong><br>
          Surprise <strong>${esc(surprise.value ?? "not quantified")} ${esc(surprise.unit || "")}</strong> (${esc(surprise.sign || "neutral")})</p>
          <p>${esc(memo.summary)}</p>
        </section>
        <section>
          <h2>Symbolic verification</h2>
          <p>${esc(symbolic.node_count || 0)} nodes · ${esc(symbolic.edge_count || 0)} edges · ${symbolic.acyclic ? "acyclic" : "cycle"} · coverage ${pct(symbolic.proof_coverage)}</p>
          <p>${proofs.size} assets · ${Array.from(proofs.values()).filter((p) => p.status === "proved").length} proved · ${Array.from(proofs.values()).filter((p) => p.status === "ambiguous").length} ambiguous</p>
          <div class="note-hash">ledger ${esc(symbolic.ledger_hash || note.ledger_hash)}</div>
        </section>
      </div>
      <h2>Asset views</h2>
      <table class="desk-table"><thead><tr><th>Asset</th><th>Direction</th><th class="num">P(up)</th><th class="num">5d prior</th><th>Proof</th></tr></thead><tbody>${rows}</tbody></table>
      <div class="note-columns">
        <section><h2>Transmission</h2><ul>${(memo.transmission || []).map((item) => `<li>${esc(item)}</li>`).join("")}</ul></section>
        <section><h2>What would falsify this</h2><ul>${(memo.falsifiers || []).map((item) => `<li>${esc(item)}</li>`).join("")}</ul></section>
      </div>
      <h2>Policies</h2>
      <ul>${policies.map((policy) => `<li class="${policy.passed ? "policy-pass" : "policy-fail"}">${esc(policy.id)} ${esc(policy.title)}: ${esc(policy.detail)}</li>`).join("")}</ul>
      ${failed.length ? `<p class="policy-fail">${failed.length} policy issue(s)</p>` : `<p class="policy-pass">All policies passed.</p>`}
      <h2>Post-event review</h2>
      ${reviewHtml}
      <div class="note-actions">
        <button class="button ghost" id="backToNotes" type="button">Back</button>
        <a class="button solid" href="/api/notes/${esc(note.id)}/pdf" target="_blank" rel="noreferrer">Export PDF</a>
        <button class="button ghost" id="shareNote" type="button">Copy share link</button>
        <button class="button ghost" id="reviewNote" type="button">Run review</button>
      </div>
    </div>
  `;
  $("#backToNotes").addEventListener("click", () => setView("notes"));
  $("#shareNote").addEventListener("click", async () => {
    const url = `${window.location.origin}/api/notes/${note.id}/html`;
    try {
      await navigator.clipboard.writeText(url);
      toast("Share link copied");
    } catch (_error) {
      toast(url);
    }
  });
  $("#reviewNote").addEventListener("click", async () => {
    try {
      toast("Computing realised outcomes…");
      state.note = await api(`/api/notes/${note.id}/review`, { method: "POST" });
      state.notes = state.notes.map((item) => (item.id === note.id ? { ...item, status: "reviewed" } : item));
      await refreshAuditDesk();
      render();
      toast("Review updated");
    } catch (error) {
      toast(`Review failed: ${error.message}`);
    }
  });
}

function openCustomEvent() {
  $("#customEventModal").hidden = false;
  document.body.style.overflow = "hidden";
  const date = new Date();
  date.setDate(date.getDate() + 1);
  $("#customEventForm [name='date']").value = date.toISOString().slice(0, 10);
}

function closeCustomEvent() {
  $("#customEventModal").hidden = true;
  document.body.style.overflow = "";
}

async function refreshAuditDesk() {
  try {
    state.auditDesk = await api("/api/audit-desk");
    state.watchlist = state.auditDesk.watchlist || [];
    setSummary();
  } catch (_error) {
    /* non-fatal */
  }
}

async function boot() {
  $$(".desk-tab").forEach((tab) => {
    tab.addEventListener("click", () => setView(tab.dataset.view));
  });
  $("#closeCustomEvent").addEventListener("click", closeCustomEvent);
  $("#customEventModal").addEventListener("click", (event) => {
    if (event.target.dataset.close) closeCustomEvent();
  });
  $("#closeScenario").addEventListener("click", closeScenario);
  $("#scenarioModal").addEventListener("click", (event) => {
    if (event.target.dataset.close) closeScenario();
  });
  $("#customEventForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = Object.fromEntries(new FormData(event.target).entries());
    try {
      await api("/api/calendar/custom", { method: "POST", body: JSON.stringify(payload) });
      closeCustomEvent();
      state.calendar = await api("/api/calendar?days=120&include_past=7");
      state.view = "calendar";
      render();
      toast("Custom event added");
    } catch (error) {
      toast(`Could not add event: ${error.message}`);
    }
  });
  try {
    const [calendar, watchlist, notes, desk] = await Promise.all([
      api("/api/calendar?days=120&include_past=7"),
      api("/api/watchlist"),
      api("/api/notes?limit=100"),
      api("/api/audit-desk"),
    ]);
    state.calendar = calendar;
    state.watchlist = watchlist.assets || [];
    state.notes = notes.notes || [];
    state.auditDesk = desk;
    setSummary();
    setView("calendar");
  } catch (error) {
    $("#productMain").innerHTML = `<div class="empty-state">Audit desk unavailable: ${esc(error.message)}</div>`;
  }
}

document.addEventListener("DOMContentLoaded", boot);
