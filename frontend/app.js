const apiBase = "";

const compareForm = document.getElementById("compare-form");

const previewCard = document.getElementById("preview-card");
const summaryCard = document.getElementById("summary-card");
const allocationCard = document.getElementById("allocation-card");
const manualCard = document.getElementById("manual-card");
const diffCard = document.getElementById("diff-card");
const errorCard = document.getElementById("error-card");

const errorText = document.getElementById("error-text");
const summary = document.getElementById("summary");
const allocation = document.getElementById("allocation");
const diffBody = document.getElementById("diff-body");
const overrideList = document.getElementById("override-list");

const previewLeafOnly = document.getElementById("preview-leaf-only");
const previewShowSummaries = document.getElementById("preview-show-summaries");
const previewShowBaseline = document.getElementById("preview-show-baseline");
const previewShowDeps = document.getElementById("preview-show-deps");
const previewMeta = document.getElementById("preview-meta");
const previewPageText = document.getElementById("preview-page-text");
const previewLinkHint = document.getElementById("preview-link-hint");
const previewMatchBody = document.getElementById("preview-match-body");
const previewLeftSelect = document.getElementById("preview-left-select");
const previewRightSelect = document.getElementById("preview-right-select");
const timelineAxis = document.getElementById("timeline-axis");
const timelineAxisWrap = document.getElementById("timeline-axis-wrap");
const timelineLeft = document.getElementById("timeline-left");
const timelineRight = document.getElementById("timeline-right");
const timelineLeftWrap = document.getElementById("timeline-left-wrap");
const timelineRightWrap = document.getElementById("timeline-right-wrap");

const overrides = [];

const state = {
  previewSessionId: null,
  previewRows: [],
  previewMeta: null,
  previewOffset: 0,
  previewLimit: 200,
  previewIncludeSummaries: false,
  previewShowBaseline: false,
  previewShowDeps: true,
  previewLeftOptions: [],
  previewRightOptions: [],
  selectedLeftUid: null,
  selectedRightUid: null,
  syncGuard: false,
  currentResult: null,
  analysisStatus: {
    pairs: new Map(),
    leftOnly: new Map(),
    rightOnly: new Map(),
  },
  lastRun: null,
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function showError(message) {
  errorCard.hidden = false;
  errorText.textContent = message;
}

function clearError() {
  errorCard.hidden = true;
  errorText.textContent = "";
}

function buildColumnMap(side) {
  return {
    uid: document.getElementById(`${side}-col-uid`).value,
    name: document.getElementById(`${side}-col-name`).value,
    start: document.getElementById(`${side}-col-start`).value,
    finish: document.getElementById(`${side}-col-finish`).value,
    duration_minutes: document.getElementById(`${side}-col-duration`).value,
    percent_complete: document.getElementById(`${side}-col-pct`).value,
    predecessors: document.getElementById(`${side}-col-preds`).value,
    is_summary: document.getElementById(`${side}-col-summary`).value,
    baseline_start: document.getElementById(`${side}-col-baseline-start`).value,
    baseline_finish: document.getElementById(`${side}-col-baseline-finish`).value,
  };
}

function buildMetricHtml(title, metric) {
  return `
    <div class="metric">
      <h3>${title}</h3>
      <p><strong>Client:</strong> ${metric.client_days} days (${metric.client_pct}%)</p>
      <p><strong>Contractor:</strong> ${metric.contractor_days} days (${metric.contractor_pct}%)</p>
      <p><strong>Neutral:</strong> ${metric.neutral_days} days (${metric.neutral_pct}%)</p>
      <p><strong>Unassigned:</strong> ${metric.unassigned_days} days</p>
      <p><strong>Excluded low-confidence:</strong> ${metric.excluded_low_confidence_days} days</p>
    </div>
  `;
}

function renderAllocation(json) {
  const fa = json.fault_allocation;
  allocation.innerHTML = `
    <div class="allocation-grid">
      ${buildMetricHtml("Project Finish Impact", fa.project_finish_impact_days)}
      ${buildMetricHtml("Task Slippage", fa.task_slippage_days)}
    </div>
  `;
}

function reasonOptions(selected) {
  const options = [
    ["", "none"],
    ["instruction_change", "instruction change"],
    ["late_information", "late information"],
    ["contractor_productivity", "contractor productivity"],
    ["weather", "weather"],
    ["third_party_statutory", "third-party/statutory"],
    ["other", "other"],
  ];
  return options
    .map(([val, label]) => `<option value="${val}" ${selected === val ? "selected" : ""}>${label}</option>`)
    .join("");
}

function causeOptions(selected) {
  const options = ["unassigned", "client", "contractor", "neutral"];
  return options
    .map((val) => `<option value="${val}" ${selected === val ? "selected" : ""}>${val}</option>`)
    .join("");
}

function renderOverrides() {
  overrideList.innerHTML = overrides
    .map((o, i) => `<li>#${i + 1}: ${o.left_uid} -> ${o.right_uid}</li>`)
    .join("");
}

function parseDate(value) {
  if (!value) return null;
  const dt = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(dt.getTime())) return null;
  return dt;
}

function daysBetween(fromDate, toDate) {
  return Math.max(1, Math.ceil((toDate.getTime() - fromDate.getTime()) / 86400000) + 1);
}

function statusForRow(row) {
  if (row.left && row.right) {
    const key = `${row.left.uid}:${row.right.uid}`;
    return state.analysisStatus.pairs.get(key) || "";
  }
  if (row.left && !row.right) {
    return state.analysisStatus.leftOnly.get(String(row.left.uid)) || "";
  }
  if (!row.left && row.right) {
    return state.analysisStatus.rightOnly.get(String(row.right.uid)) || "";
  }
  return "";
}

function barClass(side, status, isSelected) {
  const classes = [side === "left" ? "timeline-bar-left" : "timeline-bar-right"];
  if (status === "changed") classes.push("timeline-bar-changed");
  if (status === "added") classes.push("timeline-bar-added");
  if (status === "removed") classes.push("timeline-bar-removed");
  if (isSelected) classes.push("timeline-bar-selected");
  return classes.join(" ");
}

function renderTimelineAxis() {
  const meta = state.previewMeta;
  if (!meta || !meta.timeline_start || !meta.timeline_finish) {
    timelineAxis.innerHTML = "";
    return;
  }

  const start = parseDate(meta.timeline_start);
  const finish = parseDate(meta.timeline_finish);
  if (!start || !finish) {
    timelineAxis.innerHTML = "";
    return;
  }

  const width = 1600;
  const xStart = 220;
  const xEnd = width - 16;
  const totalDays = daysBetween(start, finish);
  const monthTicks = [];
  const cursor = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), 1));
  while (cursor <= finish) {
    monthTicks.push(new Date(cursor.getTime()));
    cursor.setUTCMonth(cursor.getUTCMonth() + 1);
  }

  const parts = [
    `<rect x="0" y="0" width="${width}" height="42" fill="#fffdfa"/>`,
    `<line x1="${xStart}" y1="28" x2="${xEnd}" y2="28" stroke="#b9b3a7" stroke-width="1"/>`,
  ];

  for (const tick of monthTicks) {
    const day = daysBetween(start, tick);
    const x = xStart + ((Math.min(totalDays, Math.max(1, day)) - 1) / totalDays) * (xEnd - xStart);
    const label = tick.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
    parts.push(`<line x1="${x}" y1="12" x2="${x}" y2="30" stroke="#c8c2b8" stroke-width="1"/>`);
    parts.push(`<text x="${x + 3}" y="11" font-size="10" fill="#595347">${escapeHtml(label)}</text>`);
  }

  timelineAxis.setAttribute("viewBox", `0 0 ${width} 42`);
  timelineAxis.innerHTML = parts.join("");
}

function renderTimelinePanel(side, svgEl) {
  const meta = state.previewMeta;
  const rows = state.previewRows;
  if (!meta) {
    svgEl.innerHTML = "";
    return;
  }

  const start = parseDate(meta.timeline_start);
  const finish = parseDate(meta.timeline_finish);
  const width = 1600;
  const xStart = 220;
  const xEnd = width - 16;
  const rowHeight = 22;
  const topPad = 8;
  const barHeight = 12;
  const contentHeight = topPad + rows.length * rowHeight + 12;
  const totalDays = start && finish ? daysBetween(start, finish) : 1;
  const showBaseline = state.previewShowBaseline;
  const showDeps = state.previewShowDeps;

  const bars = [];
  const barIndex = new Map();
  const parts = [`<rect x="0" y="0" width="${width}" height="${contentHeight}" fill="#ffffff"/>`];

  rows.forEach((row, idx) => {
    const y = topPad + idx * rowHeight;
    const task = side === "left" ? row.left : row.right;
    const label = task ? task.name : "-";

    parts.push(`<line x1="0" y1="${y + rowHeight}" x2="${width}" y2="${y + rowHeight}" class="timeline-grid-line"/>`);
    parts.push(`<text x="8" y="${y + 15}" class="timeline-row-label">${escapeHtml(label)}</text>`);

    if (!task || !task.start || !task.finish || !start || !finish) {
      return;
    }

    const s = parseDate(task.start);
    const f = parseDate(task.finish);
    if (!s || !f) {
      return;
    }

    const sDay = daysBetween(start, s);
    const fDay = daysBetween(start, f);
    const x1 = xStart + ((Math.max(1, sDay) - 1) / totalDays) * (xEnd - xStart);
    const x2 = xStart + (Math.min(totalDays, Math.max(1, fDay)) / totalDays) * (xEnd - xStart);
    const w = Math.max(3, x2 - x1);
    const status = statusForRow(row);
    const selected = (side === "left" && state.selectedLeftUid === task.uid) || (side === "right" && state.selectedRightUid === task.uid);

    if (showBaseline && task.baseline_start && task.baseline_finish) {
      const bs = parseDate(task.baseline_start);
      const bf = parseDate(task.baseline_finish);
      if (bs && bf) {
        const bsDay = daysBetween(start, bs);
        const bfDay = daysBetween(start, bf);
        const bx1 = xStart + ((Math.max(1, bsDay) - 1) / totalDays) * (xEnd - xStart);
        const bx2 = xStart + (Math.min(totalDays, Math.max(1, bfDay)) / totalDays) * (xEnd - xStart);
        const bw = Math.max(2, bx2 - bx1);
        parts.push(`<rect x="${bx1}" y="${y + 6}" width="${bw}" height="4" class="timeline-baseline" rx="2" ry="2"/>`);
      }
    }

    parts.push(
      `<rect data-side="${side}" data-uid="${task.uid}" x="${x1}" y="${y + (rowHeight - barHeight) / 2}" width="${w}" height="${barHeight}" rx="3" ry="3" class="${barClass(side, status, selected)}"/>`
    );

    bars.push({ uid: task.uid, rowY: y, x1, x2, predecessors: task.predecessors || [] });
    barIndex.set(task.uid, { y, x1, x2 });
  });

  let depCount = 0;
  const depLimit = 350;
  if (showDeps) {
    for (const bar of bars) {
      if (depCount >= depLimit) {
        break;
      }
      for (const predUid of bar.predecessors) {
        if (depCount >= depLimit) {
          break;
        }
        const pred = barIndex.get(predUid);
        if (!pred) {
          continue;
        }
        depCount += 1;
        const fromX = pred.x2;
        const fromY = pred.y + rowHeight / 2;
        const toX = bar.x1;
        const toY = bar.rowY + rowHeight / 2;
        const bendX = fromX + 10;
        parts.push(
          `<path class="timeline-dep-line" d="M ${fromX} ${fromY} L ${bendX} ${fromY} L ${bendX} ${toY} L ${toX} ${toY}"/>`
        );
      }
    }
  }

  svgEl.setAttribute("viewBox", `0 0 ${width} ${contentHeight}`);
  svgEl.innerHTML = parts.join("");

  svgEl.querySelectorAll("rect[data-side]").forEach((el) => {
    el.addEventListener("click", async () => {
      const sideName = el.getAttribute("data-side");
      const uid = Number(el.getAttribute("data-uid"));
      if (!uid) {
        return;
      }
      if (sideName === "left") {
        state.selectedLeftUid = uid;
      } else {
        state.selectedRightUid = uid;
      }
      renderPreviewSelectionHint();
      renderTimelinePanel("left", timelineLeft);
      renderTimelinePanel("right", timelineRight);

      if (state.selectedLeftUid && state.selectedRightUid) {
        await applyPreviewEdits([{ left_uid: state.selectedLeftUid, right_uid: state.selectedRightUid }]);
        state.selectedLeftUid = null;
        state.selectedRightUid = null;
        renderPreviewSelectionHint();
      }
    });
  });

  return depCount >= depLimit;
}

function renderPreviewSelectionHint() {
  const left = state.selectedLeftUid ? `Left UID ${state.selectedLeftUid}` : "left not selected";
  const right = state.selectedRightUid ? `Right UID ${state.selectedRightUid}` : "right not selected";
  previewLinkHint.textContent = `Chart-link mode: ${left}; ${right}.`;
}

function renderPreviewOptions() {
  previewLeftSelect.innerHTML = ["<option value=''>Select left task</option>"]
    .concat(state.previewLeftOptions.map((o) => `<option value="${o.uid}">${o.uid} - ${escapeHtml(o.name)}</option>`))
    .join("");
  previewRightSelect.innerHTML = ["<option value=''>Select right task</option>"]
    .concat(state.previewRightOptions.map((o) => `<option value="${o.uid}">${o.uid} - ${escapeHtml(o.name)}</option>`))
    .join("");
}

function renderPreviewMatchTable() {
  const rows = state.previewRows
    .filter((row) => row.left || row.right)
    .map((row) => {
      const leftText = row.left ? `${row.left.uid} - ${escapeHtml(row.left.name)}` : "-";
      const rightText = row.right ? `${row.right.uid} - ${escapeHtml(row.right.name)}` : "-";
      return `
        <tr>
          <td>${leftText}</td>
          <td>${rightText}</td>
          <td>${row.confidence}%</td>
          <td>${escapeHtml(row.match_reason || "")}</td>
        </tr>
      `;
    });
  previewMatchBody.innerHTML = rows.join("");
}

function renderPreview() {
  if (!state.previewMeta) {
    return;
  }

  const meta = state.previewMeta;
  previewCard.hidden = false;

  const start = meta.timeline_start || "-";
  const finish = meta.timeline_finish || "-";
  let metaText = `Type: ${meta.file_kind} | Rows: ${meta.total_rows} | Timeline: ${start} to ${finish}`;

  const from = Math.min(meta.total_rows, meta.offset + 1);
  const to = Math.min(meta.total_rows, meta.offset + meta.limit);
  previewPageText.textContent = `Showing ${meta.total_rows ? from : 0}-${to} of ${meta.total_rows}`;

  renderPreviewSelectionHint();
  renderPreviewOptions();
  renderPreviewMatchTable();
  renderTimelineAxis();
  const leftTruncated = renderTimelinePanel("left", timelineLeft);
  const rightTruncated = renderTimelinePanel("right", timelineRight);
  if (leftTruncated || rightTruncated) {
    metaText = `${metaText} | Dependency links truncated in viewport for performance.`;
  }
  previewMeta.textContent = metaText;
}

function setupScrollSync() {
  const syncPanels = (source, target) => {
    if (state.syncGuard) return;
    state.syncGuard = true;
    target.scrollTop = source.scrollTop;
    target.scrollLeft = source.scrollLeft;
    if (timelineAxisWrap) {
      timelineAxisWrap.scrollLeft = source.scrollLeft;
    }
    state.syncGuard = false;
  };

  const syncFromAxis = () => {
    if (!timelineAxisWrap || state.syncGuard) return;
    state.syncGuard = true;
    timelineLeftWrap.scrollLeft = timelineAxisWrap.scrollLeft;
    timelineRightWrap.scrollLeft = timelineAxisWrap.scrollLeft;
    state.syncGuard = false;
  };

  timelineLeftWrap.addEventListener("scroll", () => syncPanels(timelineLeftWrap, timelineRightWrap));
  timelineRightWrap.addEventListener("scroll", () => syncPanels(timelineRightWrap, timelineLeftWrap));
  if (timelineAxisWrap) {
    timelineAxisWrap.addEventListener("scroll", syncFromAxis);
  }
}

function buildAnalysisStatus(result) {
  state.analysisStatus = {
    pairs: new Map(),
    leftOnly: new Map(),
    rightOnly: new Map(),
  };
  for (const diff of result.diffs || []) {
    if (diff.left_uid && diff.right_uid) {
      state.analysisStatus.pairs.set(`${diff.left_uid}:${diff.right_uid}`, diff.status);
    } else if (diff.left_uid) {
      state.analysisStatus.leftOnly.set(String(diff.left_uid), diff.status);
    } else if (diff.right_uid) {
      state.analysisStatus.rightOnly.set(String(diff.right_uid), diff.status);
    }
  }
}

function renderResult(json) {
  state.currentResult = json;

  summary.innerHTML = `
    <p><strong>Left leaf tasks:</strong> ${json.summary.total_left_leaf_tasks}</p>
    <p><strong>Right leaf tasks:</strong> ${json.summary.total_right_leaf_tasks}</p>
    <p><strong>Matched:</strong> ${json.summary.matched_tasks} | <strong>Changed:</strong> ${json.summary.changed_tasks}</p>
    <p><strong>Added:</strong> ${json.summary.added_tasks} | <strong>Removed:</strong> ${json.summary.removed_tasks}</p>
    <p><strong>Project finish delay (base):</strong> ${json.summary.project_finish_delay_days} days</p>
  `;

  renderAllocation(json);

  diffBody.innerHTML = json.diffs
    .map((diff) => {
      const task = diff.left_name || diff.right_name || "Unknown";
      const evidence = diff.evidence.length
        ? diff.evidence
            .map((e) => `${e.field}: ${escapeHtml(e.left_value)} -> ${escapeHtml(e.right_value)}`)
            .join("<br>")
        : "None";
      const pendingBadge =
        diff.attribution_status === "pending_low_confidence"
          ? `<span class="pending">confirm red match</span>`
          : "";

      return `
        <tr data-row-key="${diff.row_key}">
          <td><input type="checkbox" class="pick-row" data-row-key="${diff.row_key}" /></td>
          <td>${diff.status}</td>
          <td>${escapeHtml(task)}<br><small>${diff.left_uid || "-"} -> ${diff.right_uid || "-"}</small></td>
          <td><span class="chip ${diff.confidence_band}">${diff.confidence}%</span></td>
          <td>
            <select class="row-cause" data-row-key="${diff.row_key}">
              ${causeOptions(diff.cause_tag)}
            </select>
          </td>
          <td>
            <select class="row-reason" data-row-key="${diff.row_key}">
              ${reasonOptions(diff.reason_code)}
            </select>
          </td>
          <td>${diff.attribution_status} ${pendingBadge}</td>
          <td>${diff.task_slippage_days}</td>
          <td>${evidence}<br><small>${escapeHtml(diff.protocol_hint)}</small></td>
        </tr>
      `;
    })
    .join("");

  summaryCard.hidden = false;
  allocationCard.hidden = false;
  manualCard.hidden = false;
  diffCard.hidden = false;
  errorCard.hidden = true;

  buildAnalysisStatus(json);
  if (state.previewMeta) {
    renderPreview();
  }
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const json = await response.json();
  if (!response.ok) {
    throw new Error(json.error || "Request failed");
  }
  return json;
}

async function runPreviewInit(files, includeBaseline) {
  const payload = new FormData();
  payload.append("left_file", files.fileA);
  payload.append("right_file", files.fileB);
  payload.append("include_baseline", includeBaseline);
  payload.append("include_summaries", String(state.previewIncludeSummaries));
  payload.append("offset", String(state.previewOffset));
  payload.append("limit", String(state.previewLimit));
  payload.append("left_column_map_json", JSON.stringify(buildColumnMap("left")));
  payload.append("right_column_map_json", JSON.stringify(buildColumnMap("right")));

  const response = await fetch(`${apiBase}/api/preview/init`, {
    method: "POST",
    body: payload,
  });

  const json = await response.json();
  if (!response.ok) {
    throw new Error(json.error || "Preview initialization failed");
  }

  state.previewSessionId = json.session.session_id;
  state.previewRows = json.rows || [];
  state.previewMeta = json.session;
  state.previewLeftOptions = json.left_leaf_options || [];
  state.previewRightOptions = json.right_leaf_options || [];
  state.selectedLeftUid = null;
  state.selectedRightUid = null;
  state.analysisStatus = { pairs: new Map(), leftOnly: new Map(), rightOnly: new Map() };

  summaryCard.hidden = true;
  allocationCard.hidden = true;
  manualCard.hidden = true;
  diffCard.hidden = true;

  renderPreview();
}

async function fetchPreviewRows() {
  if (!state.previewSessionId) {
    return;
  }

  const params = new URLSearchParams({
    session_id: state.previewSessionId,
    include_summaries: String(state.previewIncludeSummaries),
    offset: String(state.previewOffset),
    limit: String(state.previewLimit),
  });

  const response = await fetch(`${apiBase}/api/preview/rows?${params.toString()}`);
  const json = await response.json();
  if (!response.ok) {
    throw new Error(json.error || "Preview rows failed");
  }

  state.previewRows = json.rows || [];
  state.previewMeta = json.session;
  renderPreview();
}

async function applyPreviewEdits(edits) {
  if (!state.previewSessionId) {
    return;
  }

  const json = await postJson(`${apiBase}/api/preview/matches/apply`, {
    session_id: state.previewSessionId,
    edits,
    include_summaries: state.previewIncludeSummaries,
    offset: state.previewOffset,
    limit: state.previewLimit,
  });

  state.previewRows = json.rows || [];
  state.previewMeta = json.session;
  renderPreview();
}

async function runPreviewAnalysis() {
  if (!state.previewSessionId) {
    return;
  }
  const json = await postJson(`${apiBase}/api/preview/analyze`, {
    session_id: state.previewSessionId,
  });
  renderResult(json);
}

async function runAutoCompare(files, includeBaseline) {
  const payload = new FormData();
  payload.append("left_file", files.fileA);
  payload.append("right_file", files.fileB);
  payload.append("include_baseline", includeBaseline);
  payload.append("overrides_json", JSON.stringify(overrides));
  payload.append("left_column_map_json", JSON.stringify(buildColumnMap("left")));
  payload.append("right_column_map_json", JSON.stringify(buildColumnMap("right")));

  const response = await fetch(`${apiBase}/api/compare-auto`, {
    method: "POST",
    body: payload,
  });
  const json = await response.json();
  if (!response.ok) {
    throw new Error(json.error || "Comparison failed");
  }
  renderResult(json);
}

async function applyAttribution(payload) {
  const response = await fetch(`${apiBase}/api/attribution/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const json = await response.json();
  if (!response.ok) {
    throw new Error(json.error || "Attribution update failed");
  }
  renderResult(json);
}

compareForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();

  const fileA = document.getElementById("left-file").files[0];
  const fileB = document.getElementById("right-file").files[0];
  if (!fileA || !fileB) {
    return;
  }

  state.lastRun = {
    files: { fileA, fileB },
    includeBaseline: document.getElementById("include-baseline").checked,
  };
  state.previewOffset = 0;

  try {
    await runPreviewInit(state.lastRun.files, state.lastRun.includeBaseline);
  } catch (error) {
    showError(error.message);
  }
});

document.getElementById("preview-refresh").addEventListener("click", async () => {
  clearError();
  try {
    await fetchPreviewRows();
  } catch (error) {
    showError(error.message);
  }
});

document.getElementById("preview-run-analysis").addEventListener("click", async () => {
  clearError();
  try {
    await runPreviewAnalysis();
  } catch (error) {
    showError(error.message);
  }
});

document.getElementById("preview-prev").addEventListener("click", async () => {
  if (!state.previewMeta) return;
  state.previewOffset = Math.max(0, state.previewOffset - state.previewLimit);
  clearError();
  try {
    await fetchPreviewRows();
  } catch (error) {
    showError(error.message);
  }
});

document.getElementById("preview-next").addEventListener("click", async () => {
  if (!state.previewMeta || !state.previewMeta.has_more) return;
  state.previewOffset += state.previewLimit;
  clearError();
  try {
    await fetchPreviewRows();
  } catch (error) {
    showError(error.message);
  }
});

previewLeafOnly.addEventListener("change", async () => {
  state.previewIncludeSummaries = !previewLeafOnly.checked;
  previewShowSummaries.checked = state.previewIncludeSummaries;
  state.previewOffset = 0;
  clearError();
  try {
    await fetchPreviewRows();
  } catch (error) {
    showError(error.message);
  }
});

previewShowSummaries.addEventListener("change", async () => {
  state.previewIncludeSummaries = previewShowSummaries.checked;
  previewLeafOnly.checked = !state.previewIncludeSummaries;
  state.previewOffset = 0;
  clearError();
  try {
    await fetchPreviewRows();
  } catch (error) {
    showError(error.message);
  }
});

previewShowBaseline.addEventListener("change", () => {
  state.previewShowBaseline = previewShowBaseline.checked;
  renderPreview();
});

previewShowDeps.addEventListener("change", () => {
  state.previewShowDeps = previewShowDeps.checked;
  renderPreview();
});

document.getElementById("preview-apply-link").addEventListener("click", async () => {
  const leftUid = Number(previewLeftSelect.value);
  const rightUid = Number(previewRightSelect.value);
  if (!leftUid || !rightUid) {
    return;
  }
  clearError();
  try {
    await applyPreviewEdits([{ left_uid: leftUid, right_uid: rightUid }]);
  } catch (error) {
    showError(error.message);
  }
});

document.getElementById("preview-remove-link").addEventListener("click", async () => {
  const leftUid = Number(previewLeftSelect.value);
  if (!leftUid) {
    return;
  }
  clearError();
  try {
    await applyPreviewEdits([{ left_uid: leftUid, right_uid: null }]);
  } catch (error) {
    showError(error.message);
  }
});

document.getElementById("add-override").addEventListener("click", () => {
  const leftUid = Number(document.getElementById("manual-left").value);
  const rightUid = Number(document.getElementById("manual-right").value);

  if (!leftUid || !rightUid) {
    return;
  }

  overrides.push({ left_uid: leftUid, right_uid: rightUid });
  renderOverrides();
});

document.getElementById("rerun").addEventListener("click", async () => {
  if (!state.lastRun) {
    return;
  }

  clearError();
  try {
    await runAutoCompare(state.lastRun.files, state.lastRun.includeBaseline);
  } catch (error) {
    showError(error.message);
  }
});

document.getElementById("apply-inline").addEventListener("click", async () => {
  if (!state.currentResult) {
    return;
  }

  const assignments = [];
  const byKey = new Map((state.currentResult?.diffs || []).map((d) => [d.row_key, d]));
  document.querySelectorAll(".row-cause").forEach((causeEl) => {
    const rowKey = causeEl.getAttribute("data-row-key");
    const reasonEl = document.querySelector(`.row-reason[data-row-key='${rowKey}']`);
    const current = byKey.get(rowKey);
    assignments.push({
      row_key: rowKey,
      cause_tag: causeEl.value,
      reason_code: reasonEl ? reasonEl.value : "",
      confirm_low_confidence:
        current && current.confidence < 50 && current.attribution_status === "ready",
    });
  });

  clearError();
  try {
    await applyAttribution({ assignments });
  } catch (error) {
    showError(error.message);
  }
});

document.getElementById("apply-bulk").addEventListener("click", async () => {
  if (!state.currentResult) {
    return;
  }

  const rowKeys = [];
  document.querySelectorAll(".pick-row:checked").forEach((checkbox) => {
    rowKeys.push(checkbox.getAttribute("data-row-key"));
  });

  if (!rowKeys.length) {
    return;
  }

  const bulk = {
    row_keys: rowKeys,
    cause_tag: document.getElementById("bulk-cause").value,
    reason_code: document.getElementById("bulk-reason").value,
    confirm_low_confidence: document.getElementById("bulk-confirm-red").checked,
  };

  clearError();
  try {
    await applyAttribution({ assignments: [], bulk });
  } catch (error) {
    showError(error.message);
  }
});

setupScrollSync();
