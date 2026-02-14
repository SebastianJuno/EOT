from __future__ import annotations

import csv
import io
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .schemas import CompareResult, FaultMetric

SCL_NOTE = "Assessment support aligned to SCL Delay and Disruption Protocol concepts; not legal advice."


def _metric_rows(label: str, metric: FaultMetric) -> list[list[str | float]]:
    return [
        [label, "client_days", metric.client_days],
        [label, "contractor_days", metric.contractor_days],
        [label, "neutral_days", metric.neutral_days],
        [label, "unassigned_days", metric.unassigned_days],
        [label, "excluded_low_confidence_days", metric.excluded_low_confidence_days],
        [label, "client_pct", metric.client_pct],
        [label, "contractor_pct", metric.contractor_pct],
        [label, "neutral_pct", metric.neutral_pct],
    ]


def build_csv(result: CompareResult) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "status",
            "change_category",
            "requires_user_input",
            "auto_reason",
            "flow_on_from_right_uids",
            "auto_overridden",
            "left_uid",
            "right_uid",
            "left_name",
            "right_name",
            "confidence",
            "confidence_band",
            "cause_tag",
            "reason_code",
            "attribution_status",
            "task_slippage_days",
            "included_in_totals",
            "protocol_hint",
            "changed_fields",
        ]
    )

    for diff in result.diffs:
        changed_fields = ", ".join(
            f"{change.field}: {change.left_value} -> {change.right_value}" for change in diff.evidence
        )
        writer.writerow(
            [
                diff.status,
                diff.change_category,
                diff.requires_user_input,
                diff.auto_reason or "",
                ",".join(str(uid) for uid in diff.flow_on_from_right_uids),
                diff.auto_overridden,
                diff.left_uid,
                diff.right_uid,
                diff.left_name,
                diff.right_name,
                diff.confidence,
                diff.confidence_band,
                diff.cause_tag,
                diff.reason_code,
                diff.attribution_status,
                diff.task_slippage_days,
                diff.included_in_totals,
                diff.protocol_hint,
                changed_fields,
            ]
        )

    writer.writerow([])
    writer.writerow(["Fault Allocation Summary"])
    writer.writerow(["metric", "field", "value"])

    for row in _metric_rows("project_finish_impact_days", result.fault_allocation.project_finish_impact_days):
        writer.writerow(row)
    for row in _metric_rows("task_slippage_days", result.fault_allocation.task_slippage_days):
        writer.writerow(row)

    writer.writerow([])
    writer.writerow(["SCL Reference", SCL_NOTE])

    return buffer.getvalue().encode("utf-8")


def _draw_fault_metric(c: canvas.Canvas, y: float, title: str, metric: FaultMetric) -> float:
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, y, title)
    y -= 14
    c.setFont("Helvetica", 9)
    c.drawString(50, y, f"Client: {metric.client_days} days ({metric.client_pct}%)")
    y -= 12
    c.drawString(50, y, f"Contractor: {metric.contractor_days} days ({metric.contractor_pct}%)")
    y -= 12
    c.drawString(50, y, f"Neutral: {metric.neutral_days} days ({metric.neutral_pct}%)")
    y -= 12
    c.drawString(50, y, f"Unassigned: {metric.unassigned_days} days")
    y -= 12
    c.drawString(50, y, f"Excluded low-confidence: {metric.excluded_low_confidence_days} days")
    return y - 16


def build_pdf(result: CompareResult, output_path: Path) -> Path:
    c = canvas.Canvas(str(output_path), pagesize=A4)
    _, height = A4
    y = height - 40

    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "Programme Difference Evidence Pack")
    y -= 24

    c.setFont("Helvetica", 10)
    summary = result.summary
    c.drawString(
        40,
        y,
        (
            f"Action required: {summary.action_required_tasks} | Auto-resolved: {summary.auto_resolved_tasks} | "
            f"Flow-on auto: {summary.auto_flow_on_tasks} | Identity conflicts: {summary.identity_conflict_tasks}"
        ),
    )
    y -= 14
    c.drawString(
        40,
        y,
        (
            f"Changed: {summary.changed_tasks} | Added: {summary.added_tasks} | "
            f"Removed: {summary.removed_tasks} | Unchanged: {summary.unchanged_tasks}"
        ),
    )
    y -= 14
    c.drawString(40, y, f"Project finish delay (base): {summary.project_finish_delay_days} days")
    y -= 24

    y = _draw_fault_metric(c, y, "Fault Allocation - Project Finish Impact", result.fault_allocation.project_finish_impact_days)
    y = _draw_fault_metric(c, y, "Fault Allocation - Task Slippage", result.fault_allocation.task_slippage_days)

    c.setFont("Helvetica-Oblique", 8)
    c.drawString(40, max(y, 60), SCL_NOTE)

    c.showPage()
    y = height - 40
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Task-Level Evidence")
    y -= 20

    for diff in result.diffs:
        if y < 90:
            c.showPage()
            y = height - 40
            c.setFont("Helvetica-Bold", 12)
            c.drawString(40, y, "Task-Level Evidence")
            y -= 20

        name = diff.left_name or diff.right_name or "Unknown"
        c.setFont("Helvetica-Bold", 9)
        c.drawString(
            40,
            y,
            (
                f"[{diff.status.upper()}] {name} | Category: {diff.change_category} | "
                f"Action required: {diff.requires_user_input} | Attr: {diff.attribution_status}"
            )[:150],
        )
        y -= 12

        c.setFont("Helvetica", 8)
        c.drawString(
            55,
            y,
            (
                f"Cause: {diff.cause_tag} | Reason code: {diff.reason_code or '-'} | "
                f"Slippage days: {diff.task_slippage_days}"
            )[:130],
        )
        y -= 11

        if diff.auto_reason:
            c.drawString(55, y, f"Auto reason: {diff.auto_reason}"[:130])
            y -= 11

        if not diff.evidence:
            c.drawString(55, y, "No field-level differences.")
            y -= 12
            continue

        for change in diff.evidence:
            line = f"- {change.field}: {change.left_value} -> {change.right_value}"
            c.drawString(55, y, line[:130])
            y -= 11
            if y < 90:
                c.showPage()
                y = height - 40
                c.setFont("Helvetica", 8)

    c.save()
    return output_path
