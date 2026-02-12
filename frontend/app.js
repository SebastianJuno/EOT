const apiBase = "";

const compareForm = document.getElementById("compare-form");

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

const overrides = [];
let lastRun = null;
let currentResult = null;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderOverrides() {
  overrideList.innerHTML = overrides
    .map((o, i) => `<li>#${i + 1}: ${o.left_uid} -> ${o.right_uid}</li>`)
    .join("");
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

function renderResult(json) {
  currentResult = json;

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

async function submitCompare(payload) {
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

async function runAutoCompare(files, includeBaseline) {
  const payload = new FormData();
  payload.append("left_file", files.fileA);
  payload.append("right_file", files.fileB);
  payload.append("include_baseline", includeBaseline);
  payload.append("overrides_json", JSON.stringify(overrides));
  payload.append("left_column_map_json", JSON.stringify(buildColumnMap("left")));
  payload.append("right_column_map_json", JSON.stringify(buildColumnMap("right")));
  await submitCompare(payload);
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
  const fileA = document.getElementById("left-file").files[0];
  const fileB = document.getElementById("right-file").files[0];
  if (!fileA || !fileB) {
    return;
  }

  lastRun = {
    files: { fileA, fileB },
    includeBaseline: document.getElementById("include-baseline").checked,
  };

  try {
    await runAutoCompare(lastRun.files, lastRun.includeBaseline);
  } catch (error) {
    errorCard.hidden = false;
    errorText.textContent = error.message;
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
  if (!lastRun) {
    return;
  }

  try {
    await runAutoCompare(lastRun.files, lastRun.includeBaseline);
  } catch (error) {
    errorCard.hidden = false;
    errorText.textContent = error.message;
  }
});

document.getElementById("apply-inline").addEventListener("click", async () => {
  if (!currentResult) {
    return;
  }

  const assignments = [];
  const byKey = new Map((currentResult?.diffs || []).map((d) => [d.row_key, d]));
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

  try {
    await applyAttribution({ assignments });
  } catch (error) {
    errorCard.hidden = false;
    errorText.textContent = error.message;
  }
});

document.getElementById("apply-bulk").addEventListener("click", async () => {
  if (!currentResult) {
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

  try {
    await applyAttribution({ assignments: [], bulk });
  } catch (error) {
    errorCard.hidden = false;
    errorText.textContent = error.message;
  }
});
