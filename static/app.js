/* ============================================================
   APII Scraper — Control Panel JS
   ============================================================ */

"use strict";

// ── State ───────────────────────────────────────────────────
const state = {
  jobs:            {},
  refreshInterval: null,
  explorer: {
    page:   1,
    limit:  50,
    total:  0,
    pages:  0,
    rows:   [],
  },
};

// ── API helper ──────────────────────────────────────────────
function apiBase() {
  return document.getElementById("api-base-url").value.trim().replace(/\/$/, "");
}

async function apiFetch(path, opts = {}) {
  const url = apiBase() + path;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${body}`);
  }
  return res.json();
}

// ── Health check ────────────────────────────────────────────
async function checkHealth() {
  const dot  = document.getElementById("api-dot");
  const text = document.getElementById("api-status-text");
  try {
    await apiFetch("/health");
    dot.className  = "dot online";
    text.textContent = "API online";
  } catch {
    dot.className  = "dot offline";
    text.textContent = "API offline";
  }
}

// ── Navigation ──────────────────────────────────────────────
function initNav() {
  document.querySelectorAll(".nav-item").forEach(link => {
    link.addEventListener("click", e => {
      e.preventDefault();
      const view = link.dataset.view;
      switchView(view);
    });
  });
}

function switchView(view) {
  document.querySelectorAll(".nav-item").forEach(l => l.classList.remove("active"));
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));

  const link = document.querySelector(`[data-view="${view}"]`);
  if (link) link.classList.add("active");

  const section = document.getElementById(`view-${view}`);
  if (section) section.classList.add("active");

  if (view === "jobs")    loadJobs();
  if (view === "stats")   loadStats();
}

// ── Toast ───────────────────────────────────────────────────
let toastTimer = null;
function toast(msg, type = "info") {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.className = `toast visible ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("visible"), 4500);
}

// ── Trigger helpers ─────────────────────────────────────────
function setLoading(btn, loading) {
  if (loading) {
    btn.disabled = true;
    btn.dataset.origHtml = btn.innerHTML;
    const icon = btn.querySelector(".btn-icon");
    if (icon) icon.textContent = "◌";
    btn.classList.add("loading");
  } else {
    btn.disabled = false;
    if (btn.dataset.origHtml) btn.innerHTML = btn.dataset.origHtml;
    btn.classList.remove("loading");
  }
}

async function triggerJob(btn, path, body = {}) {
  setLoading(btn, true);
  try {
    const res = await apiFetch(path, {
      method:  "POST",
      body:    JSON.stringify(body),
    });
    const jobId = res.job_id;
    state.jobs[jobId] = { id: jobId, name: res.job_id, status: "queued", result: null };
    toast(`Job started · ${jobId.slice(0, 8)}…`, "success");

    // Update running badge
    updateRunningBadge();

    // Switch to jobs view after short delay
    setTimeout(() => switchView("jobs"), 800);

  } catch (err) {
    toast(`Error: ${err.message}`, "error");
  } finally {
    setLoading(btn, false);
  }
}

// ── Pipeline triggers ───────────────────────────────────────
function initPipeline() {
  // Full pipeline
  document.getElementById("btn-pipeline").addEventListener("click", async function() {
    const sector = document.getElementById("pipeline-sector").value.trim();
    const csv    = document.getElementById("pipeline-csv").checked;
    const params = new URLSearchParams({ export_csv: csv });
    if (sector) params.set("sector", sector);
    await triggerJob(this, `/api/scrape/pipeline?${params}`);
  });

  // Stage 1
  document.getElementById("btn-industrial").addEventListener("click", async function() {
    const sector = document.getElementById("ind-sector").value.trim();
    const csv    = document.getElementById("ind-csv").checked;
    const params = new URLSearchParams({ export_csv: csv });
    if (sector) params.set("sector", sector);
    await triggerJob(this, `/api/scrape/industrial?${params}`);
  });

  // Stage 2
  document.getElementById("btn-linkedin-urls").addEventListener("click", async function() {
    await triggerJob(this, "/api/scrape/linkedin-urls");
  });

  // Stage 3
  document.getElementById("btn-linkedin-enrich").addEventListener("click", async function() {
    await triggerJob(this, "/api/scrape/linkedin-enrich");
  });
}

// ── Jobs ────────────────────────────────────────────────────
function updateRunningBadge() {
  const running = Object.values(state.jobs).filter(j => j.status === "running" || j.status === "queued").length;
  const badge   = document.getElementById("running-badge");
  if (running > 0) {
    badge.textContent = running;
    badge.style.display = "inline-block";
  } else {
    badge.style.display = "none";
  }
}

async function loadJobs() {
  try {
    const jobs = await apiFetch("/api/scrape/jobs");
    // Merge server jobs into state (server is source of truth)
    jobs.forEach(j => { state.jobs[j.id] = j; });
    renderJobs();
    updateRunningBadge();
  } catch (err) {
    console.warn("Could not load jobs:", err.message);
  }
}

function renderJobs() {
  const container = document.getElementById("jobs-list");
  const jobs = Object.values(state.jobs).reverse(); // newest first

  if (jobs.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <span class="empty-icon">◎</span>
        <p>No jobs yet. Trigger a scraping task from the Pipeline tab.</p>
      </div>`;
    return;
  }

  container.innerHTML = jobs.map(job => jobCardHtml(job)).join("");
}

function jobCardHtml(job) {
  const resultHtml = job.result
    ? `<div class="job-result">${JSON.stringify(job.result, null, 2)}</div>`
    : job.status === "error" && job.error
    ? `<div class="job-result" style="color:var(--red)">Error: ${escHtml(job.error)}</div>`
    : "";

  const nameMap = {
    full_pipeline:          "Full Pipeline",
    industrial_all:         "APII Industrial — All Sectors",
    linkedin_url_finder:    "LinkedIn URL Finder",
    linkedin_enrich:        "LinkedIn Enrichment",
  };

  const displayName = nameMap[job.name] || job.name;

  return `
    <div class="job-card ${job.status}">
      <div>
        <div class="job-name">${escHtml(displayName)}</div>
        <div class="job-id">${escHtml(job.id)}</div>
      </div>
      <div>
        <span class="job-status ${job.status}">${job.status}</span>
      </div>
      ${resultHtml}
    </div>`;
}

function initJobs() {
  document.getElementById("btn-refresh-jobs").addEventListener("click", loadJobs);

  const autoRefresh = document.getElementById("auto-refresh");

  function startAutoRefresh() {
    if (state.refreshInterval) return;
    state.refreshInterval = setInterval(() => {
      if (document.getElementById("view-jobs").classList.contains("active")) {
        loadJobs();
      }
    }, 4000);
  }

  function stopAutoRefresh() {
    clearInterval(state.refreshInterval);
    state.refreshInterval = null;
  }

  autoRefresh.addEventListener("change", () => {
    autoRefresh.checked ? startAutoRefresh() : stopAutoRefresh();
  });

  startAutoRefresh();
}

// ── Explorer ────────────────────────────────────────────────
function initExplorer() {
  document.getElementById("btn-search").addEventListener("click", () => {
    state.explorer.page = 1;
    loadCompanies();
  });

  document.getElementById("btn-reset-filters").addEventListener("click", () => {
    document.getElementById("filter-search").value  = "";
    document.getElementById("filter-gov").value     = "";
    document.getElementById("filter-stage").value   = "";
    document.getElementById("filter-linkedin").value = "";
    state.explorer.page = 1;
    loadCompanies();
  });

  // Search on Enter
  ["filter-search", "filter-gov"].forEach(id => {
    document.getElementById(id).addEventListener("keydown", e => {
      if (e.key === "Enter") {
        state.explorer.page = 1;
        loadCompanies();
      }
    });
  });

  document.getElementById("btn-export-visible").addEventListener("click", exportVisible);
}

function buildFilterParams() {
  const params = new URLSearchParams({
    page:  state.explorer.page,
    limit: state.explorer.limit,
  });

  const search   = document.getElementById("filter-search").value.trim();
  const gov      = document.getElementById("filter-gov").value.trim();
  const stage    = document.getElementById("filter-stage").value;
  const linkedin = document.getElementById("filter-linkedin").value;

  if (search)   params.set("search", search);
  if (gov)      params.set("governorate", gov);
  if (stage)    params.set("stage", stage);
  if (linkedin) params.set("has_linkedin", linkedin);

  return params;
}

async function loadCompanies() {
  const tbody    = document.getElementById("companies-tbody");
  const meta     = document.getElementById("results-meta");
  const pagEl    = document.getElementById("pagination");

  tbody.innerHTML = `<tr class="placeholder-row"><td colspan="9">Loading…</td></tr>`;
  meta.textContent = "—";
  pagEl.innerHTML  = "";

  try {
    const params = buildFilterParams();
    const data   = await apiFetch(`/api/companies?${params}`);

    state.explorer.total = data.total;
    state.explorer.pages = data.pages;
    state.explorer.rows  = data.items;

    meta.textContent = `${data.total.toLocaleString()} companies found · page ${data.page} of ${data.pages}`;
    renderCompaniesTable(data.items);
    renderPagination(data.page, data.pages);

  } catch (err) {
    tbody.innerHTML = `<tr class="placeholder-row"><td colspan="9" style="color:var(--red)">Error: ${escHtml(err.message)}</td></tr>`;
  }
}

function renderCompaniesTable(items) {
  const tbody = document.getElementById("companies-tbody");

  if (!items || items.length === 0) {
    tbody.innerHTML = `<tr class="placeholder-row"><td colspan="9">No results found.</td></tr>`;
    return;
  }

  tbody.innerHTML = items.map(c => {
    const linkedinCell = c.linkedin_url
      ? `<a href="${escHtml(c.linkedin_url)}" target="_blank" rel="noopener">↗ View</a>`
      : `<span class="none">—</span>`;

    const stagePill = `<span class="stage-pill ${escHtml(c.scrape_stage || '')}">${escHtml(c.scrape_stage || '—')}</span>`;

    return `
      <tr>
        <td>${c.id}</td>
        <td title="${escHtml(c.name || '')}">${escHtml(truncate(c.name, 32))}</td>
        <td title="${escHtml(c.activity || '')}">${escHtml(truncate(c.activity, 30))}</td>
        <td>${escHtml(c.governorate || '—')}</td>
        <td>${escHtml(c.phone || '—')}</td>
        <td class="linkedin-cell">${linkedinCell}</td>
        <td>${stagePill}</td>
        <td>${escHtml(c.size || '—')}</td>
        <td><button class="btn-row-detail" data-id="${c.id}">Detail ›</button></td>
      </tr>`;
  }).join("");

  // Detail buttons
  tbody.querySelectorAll(".btn-row-detail").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = parseInt(btn.dataset.id);
      const company = state.explorer.rows.find(c => c.id === id);
      if (company) openModal(company);
    });
  });
}

function renderPagination(current, total) {
  const el = document.getElementById("pagination");
  if (total <= 1) { el.innerHTML = ""; return; }

  let html = "";

  // Prev
  html += `<button class="page-btn" ${current <= 1 ? "disabled" : ""} data-page="${current - 1}">‹</button>`;

  // Page numbers (show window around current)
  const pages = pageWindow(current, total);
  let prev = null;
  pages.forEach(p => {
    if (prev !== null && p - prev > 1) {
      html += `<span class="page-btn" style="cursor:default;opacity:0.4">…</span>`;
    }
    html += `<button class="page-btn ${p === current ? "active" : ""}" data-page="${p}">${p}</button>`;
    prev = p;
  });

  // Next
  html += `<button class="page-btn" ${current >= total ? "disabled" : ""} data-page="${current + 1}">›</button>`;

  el.innerHTML = html;

  el.querySelectorAll(".page-btn[data-page]").forEach(btn => {
    btn.addEventListener("click", () => {
      const page = parseInt(btn.dataset.page);
      if (page < 1 || page > total) return;
      state.explorer.page = page;
      loadCompanies();
      // Scroll to top of content
      document.querySelector(".content").scrollTo({ top: 0, behavior: "smooth" });
    });
  });
}

function pageWindow(current, total) {
  const window = 2;
  const pages = new Set([1, total]);
  for (let i = current - window; i <= current + window; i++) {
    if (i >= 1 && i <= total) pages.add(i);
  }
  return Array.from(pages).sort((a, b) => a - b);
}

function exportVisible() {
  const rows = state.explorer.rows;
  if (!rows || rows.length === 0) {
    toast("Nothing to export. Run a search first.", "error");
    return;
  }

  const keys = Object.keys(rows[0]);
  const csv  = [
    keys.join(","),
    ...rows.map(r => keys.map(k => csvCell(r[k])).join(","))
  ].join("\n");

  const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8;" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href = url;
  a.download = `companies_export_${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
  toast(`Exported ${rows.length} rows`, "success");
}

// ── Stats ───────────────────────────────────────────────────
async function loadStats() {
  const grid = document.getElementById("stats-grid");
  grid.innerHTML = `
    <div class="stat-card skeleton"></div>
    <div class="stat-card skeleton"></div>
    <div class="stat-card skeleton"></div>
    <div class="stat-card skeleton"></div>`;

  try {
    const data = await apiFetch("/api/companies/stats");
    renderStats(data);
  } catch (err) {
    grid.innerHTML = `<p style="color:var(--red);padding:20px">Error: ${escHtml(err.message)}</p>`;
  }
}

function renderStats(data) {
  const grid = document.getElementById("stats-grid");
  const byStage = data.by_stage || {};

  const total     = data.total_companies    || 0;
  const linkedin  = data.with_linkedin_url  || 0;
  const enriched  = byStage["linkedin_enriched"] || 0;
  const scraped   = byStage["scraped"]           || 0;

  grid.innerHTML = `
    <div class="stat-card">
      <div class="stat-label">Total Companies</div>
      <div class="stat-value amber">${total.toLocaleString()}</div>
      <div class="stat-sub">in database</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">LinkedIn URLs</div>
      <div class="stat-value blue">${linkedin.toLocaleString()}</div>
      <div class="stat-sub">${total ? Math.round(linkedin/total*100) : 0}% coverage</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Fully Enriched</div>
      <div class="stat-value green">${enriched.toLocaleString()}</div>
      <div class="stat-sub">linkedin_enriched stage</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Pending Stage 2</div>
      <div class="stat-value">${scraped.toLocaleString()}</div>
      <div class="stat-sub">scraped only</div>
    </div>`;

  // Stage progress bars
  const stagesEl = document.getElementById("stage-bars");
  const stageOrder = ["scraped", "linkedin_found", "linkedin_enriched"];
  const stageColors = ["", "blue", "green"];
  const stageLabels = {
    scraped:             "Stage 1 — Scraped",
    linkedin_found:      "Stage 2 — LinkedIn URL",
    linkedin_enriched:   "Stage 3 — Enriched",
  };

  const maxStage = Math.max(...stageOrder.map(s => byStage[s] || 0), 1);

  stagesEl.innerHTML = stageOrder.map((s, i) => {
    const count = byStage[s] || 0;
    const pct   = Math.round(count / maxStage * 100);
    return `
      <div class="bar-item">
        <div class="bar-label">${stageLabels[s]}</div>
        <div class="bar-track"><div class="bar-fill ${stageColors[i]}" style="width:${pct}%"></div></div>
        <div class="bar-count">${count.toLocaleString()}</div>
      </div>`;
  }).join("");

  // Governorate bars
  const govEl = document.getElementById("gov-bars");
  const govs  = data.top_governorates || [];
  const maxGov = govs.length ? govs[0].count : 1;

  govEl.innerHTML = govs.map(g => {
    const pct = Math.round(g.count / maxGov * 100);
    return `
      <div class="bar-item">
        <div class="bar-label" title="${escHtml(g.governorate)}">${escHtml(g.governorate || '—')}</div>
        <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
        <div class="bar-count">${g.count.toLocaleString()}</div>
      </div>`;
  }).join("") || `<p style="color:var(--text-dim)">No data yet.</p>`;
}

function initStats() {
  document.getElementById("btn-refresh-stats").addEventListener("click", loadStats);
}

// ── Modal ────────────────────────────────────────────────────
function openModal(company) {
  const body = document.getElementById("modal-body");

  const field = (label, val, full = false, isLink = false) => {
    const display = val && String(val).trim()
      ? (isLink ? `<a href="${escHtml(val)}" target="_blank" rel="noopener">${escHtml(val)}</a>` : escHtml(val))
      : `<span class="empty">—</span>`;
    return `
      <div class="modal-field ${full ? "full" : ""}">
        <label>${label}</label>
        <p class="${val ? "" : "empty"}">${display}</p>
      </div>`;
  };

  body.innerHTML = `
    <div class="modal-company-name">${escHtml(company.name || "Unknown")}</div>
    <div class="modal-meta">
      <span class="stage-pill ${escHtml(company.scrape_stage || '')}">${escHtml(company.scrape_stage || '—')}</span>
      <span class="tag">${escHtml(company.source || '—')}</span>
      <span class="tag">ID: ${company.id}</span>
    </div>

    <hr class="modal-divider" />

    <div class="modal-fields">
      ${field("Activity", company.activity, true)}
      ${field("Governorate", company.governorate)}
      ${field("Phone", company.phone)}
      ${field("LinkedIn URL", company.linkedin_url, false, true)}
      ${field("Website", company.website, false, true)}
      ${field("Company Size", company.size)}
      ${field("Sector", company.sector)}
      ${field("Headquarters", company.headquarters)}
      ${field("Type", company.company_type)}
      ${field("Founded", company.founded)}
      ${field("Description", company.description, true)}
    </div>

    <hr class="modal-divider" />

    <div style="display:flex;gap:10px;font-size:11px;color:var(--text-dim)">
      <span>Created: ${fmtDate(company.created_at)}</span>
      <span>·</span>
      <span>Updated: ${fmtDate(company.updated_at)}</span>
    </div>`;

  document.getElementById("modal-backdrop").style.display = "flex";
}

function closeModal() {
  document.getElementById("modal-backdrop").style.display = "none";
}

function initModal() {
  document.getElementById("modal-close").addEventListener("click", closeModal);
  document.getElementById("modal-backdrop").addEventListener("click", e => {
    if (e.target === document.getElementById("modal-backdrop")) closeModal();
  });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") closeModal();
  });
}

// ── Utils ────────────────────────────────────────────────────
function escHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function truncate(str, len) {
  if (!str) return "";
  return str.length > len ? str.slice(0, len) + "…" : str;
}

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("fr-TN", { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return iso;
  }
}

function csvCell(val) {
  if (val == null) return "";
  const s = String(val);
  if (s.includes(",") || s.includes('"') || s.includes("\n")) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}
function initCsvUpload() {
  document.getElementById("btn-upload-csv").addEventListener("click", async function () {
    const fileInput = document.getElementById("csv-file-input");
    const resultEl  = document.getElementById("upload-result");

    if (!fileInput.files.length) {
      toast("Please select a CSV file first.", "error");
      return;
    }

    setLoading(this, true);
    resultEl.textContent = "";

    const form = new FormData();
    form.append("file", fileInput.files[0]);

    try {
      const res = await fetch(apiBase() + "/api/scrape/upload-csv", {
        method: "POST",
        body:   form,   // no Content-Type header — browser sets multipart boundary
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || res.statusText);
      }
      const data = await res.json();
      toast(`Import done — ${data.inserted} inserted, ${data.updated} updated, ${data.skipped} skipped`, "success");
      resultEl.textContent = `✓ ${data.rows_read} rows read · ${data.inserted} new · ${data.updated} updated · ${data.skipped} skipped`;
      fileInput.value = "";
    } catch (err) {
      toast(`Upload failed: ${err.message}`, "error");
      resultEl.textContent = `✗ ${err.message}`;
      resultEl.style.color = "var(--red)";
    } finally {
      setLoading(this, false);
    }
  });
}

function initAgent() {
  const thread   = document.getElementById("agent-thread");
  const input    = document.getElementById("agent-input");
  const sendBtn  = document.getElementById("btn-agent-send");

  if (!thread || !input || !sendBtn) return;   // view not present

  // Auto-grow textarea as the user types
  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 112) + "px";
  });

  // Send on button click
  sendBtn.addEventListener("click", handleSend);

  // Send on Ctrl+Enter / Cmd+Enter
  input.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      handleSend();
    }
  });

  // ── Core send handler ─────────────────────────────────────────────────
  async function handleSend() {
    const text = input.value.trim();
    if (!text) return;

    // Disable controls while waiting
    sendBtn.disabled = true;
    input.disabled   = true;

    // Append user bubble
    appendUserMessage(text);
    input.value      = "";
    input.style.height = "auto";

    // Show typing indicator
    const typingEl = appendTypingIndicator();

    try {
      const data = await apiFetch("/api/agent/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });

      typingEl.remove();
      appendAgentMessage(data.answer, data.companies || [], data.sql_used || "");
    } catch (err) {
      typingEl.remove();
      toast("Agent error: " + (err.message || "Unknown error"), "error");
      appendAgentMessage(
        "Sorry, something went wrong. Please try again.",
        [],
        ""
      );
    } finally {
      sendBtn.disabled = false;
      input.disabled   = false;
      input.focus();
    }
  }

  // ── DOM helpers ───────────────────────────────────────────────────────

  /** Appends a user message bubble and scrolls into view. */
  function appendUserMessage(text) {
    const msg = document.createElement("div");
    msg.className = "msg msg--user";
    msg.innerHTML = `<div class="msg-body"><p>${escapeHtml(text)}</p></div>`;
    thread.appendChild(msg);
    scrollThread();
  }

  /**
   * Appends an agent message bubble with optional company chips and SQL block.
   * @param {string} answer - The natural-language answer.
   * @param {Array}  companies - Array of company objects from the API.
   * @param {string} sqlUsed - The SQL query that was executed.
   */
  function appendAgentMessage(answer, companies, sqlUsed) {
    const msg = document.createElement("div");
    msg.className = "msg msg--agent";

    const bodyEl = document.createElement("div");
    bodyEl.className = "msg-body";

    // Answer text (supports newlines)
    const answerP = document.createElement("p");
    answerP.innerHTML = escapeHtml(answer).replace(/\n/g, "<br>");
    bodyEl.appendChild(answerP);

    // Company chips (up to 20 shown, then "+N more")
    if (companies.length > 0) {
      bodyEl.appendChild(buildCompanyChips(companies));
    }

    // SQL disclosure
    if (sqlUsed) {
      bodyEl.appendChild(buildSqlDisclosure(sqlUsed));
    }

    msg.appendChild(bodyEl);
    thread.appendChild(msg);
    scrollThread();
  }

  /** Appends animated typing indicator and returns the element. */
  function appendTypingIndicator() {
    const msg = document.createElement("div");
    msg.className = "msg msg--agent msg--typing";
    msg.innerHTML = `
      <div class="msg-body">
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
      </div>`;
    thread.appendChild(msg);
    scrollThread();
    return msg;
  }

  /** Builds the company chip container. */
  function buildCompanyChips(companies) {
    const MAX_CHIPS = 20;
    const container = document.createElement("div");
    container.className = "msg-companies";

    const visible = companies.slice(0, MAX_CHIPS);

    visible.forEach((c) => {
      const chip = document.createElement("span");
      chip.className = "company-chip";

      const nameSpan = document.createElement("span");
      nameSpan.className = "chip-name";
      nameSpan.textContent = c.name || "—";

      const govSpan = document.createElement("span");
      govSpan.className = "chip-gov";
      govSpan.textContent = c.governorate ? `· ${c.governorate}` : "";

      chip.appendChild(nameSpan);
      chip.appendChild(govSpan);

      if (c.linkedin_url) {
        const link = document.createElement("a");
        link.href   = c.linkedin_url;
        link.target = "_blank";
        link.rel    = "noopener noreferrer";
        link.textContent = "in";
        link.title  = "LinkedIn";
        chip.appendChild(link);
      }

      container.appendChild(chip);
    });

    if (companies.length > MAX_CHIPS) {
      const overflow = document.createElement("span");
      overflow.className = "chip-overflow";
      overflow.textContent = `+${companies.length - MAX_CHIPS} more`;
      container.appendChild(overflow);
    }

    return container;
  }

  /** Builds the collapsible SQL <details> block. */
  function buildSqlDisclosure(sql) {
    const details = document.createElement("details");
    details.className = "sql-disclosure";

    const summary = document.createElement("summary");
    summary.textContent = "SQL ›";

    const pre = document.createElement("pre");
    pre.textContent = sql;

    details.appendChild(summary);
    details.appendChild(pre);
    return details;
  }

  /** Scrolls the thread to the latest message. */
  function scrollThread() {
    thread.scrollTop = thread.scrollHeight;
  }

  /**
   * Minimal HTML escaping — prevents XSS from company data or answers.
   * Full sanitisation is handled server-side; this is a client-side guard.
   */
  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
}


// ── Boot ─────────────────────────────────────────────────────
function init() {
  initNav();
  initPipeline();
  initJobs();
  initExplorer();
  initStats();
  initModal();
  initCsvUpload();
  initAgent();
  // Health check on load and every 30s
  checkHealth();
  setInterval(checkHealth, 30_000);

  // Also re-check whenever the URL changes
  document.getElementById("api-base-url").addEventListener("change", () => {
    checkHealth();
  });

  // Auto-load stats on boot for the indicator in badge area
  loadStats().catch(() => {});

  // Default: open explorer with empty state
  // (pipeline view is active by default from HTML)
}

document.addEventListener("DOMContentLoaded", init);