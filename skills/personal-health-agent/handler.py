#!/usr/bin/env python3
"""Personal Health Agent handler for OpenClaw and Hermes skills."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


DISCLAIMER = (
    "Informational wellness support only. This agent does not diagnose, treat, "
    "prescribe, or replace a qualified clinician. For severe symptoms, very high "
    "blood pressure, chest pain, stroke symptoms, fainting, or other emergencies, "
    "seek urgent medical care."
)

WEEKLY_MODERATE_EXERCISE_GOAL_MIN = 150

MARKER_ALIASES = {
    "ldl": "ldl_mg_dl",
    "ldl-c": "ldl_mg_dl",
    "low density lipoprotein": "ldl_mg_dl",
    "低密度": "ldl_mg_dl",
    "低密度脂蛋白": "ldl_mg_dl",
    "hdl": "hdl_mg_dl",
    "hdl-c": "hdl_mg_dl",
    "high density lipoprotein": "hdl_mg_dl",
    "高密度": "hdl_mg_dl",
    "高密度脂蛋白": "hdl_mg_dl",
    "triglycerides": "triglycerides_mg_dl",
    "triglyceride": "triglycerides_mg_dl",
    "tg": "triglycerides_mg_dl",
    "甘油三酯": "triglycerides_mg_dl",
    "total cholesterol": "total_cholesterol_mg_dl",
    "cholesterol": "total_cholesterol_mg_dl",
    "总胆固醇": "total_cholesterol_mg_dl",
    "hba1c": "hba1c_percent",
    "a1c": "hba1c_percent",
    "glycated hemoglobin": "hba1c_percent",
    "糖化": "hba1c_percent",
    "糖化血红蛋白": "hba1c_percent",
    "glucose": "glucose_mg_dl",
    "fasting glucose": "glucose_mg_dl",
    "fasting blood glucose": "glucose_mg_dl",
    "血糖": "glucose_mg_dl",
    "空腹血糖": "glucose_mg_dl",
    "alt": "alt_u_l",
    "丙氨酸氨基转移酶": "alt_u_l",
    "ast": "ast_u_l",
    "天门冬氨酸氨基转移酶": "ast_u_l",
    "creatinine": "creatinine_mg_dl",
    "肌酐": "creatinine_mg_dl",
    "egfr": "egfr_ml_min_1_73m2",
    "uric acid": "uric_acid_mg_dl",
    "尿酸": "uric_acid_mg_dl",
    "hemoglobin": "hemoglobin_g_dl",
    "血红蛋白": "hemoglobin_g_dl",
}

REFERENCE_RANGES = {
    "ldl_mg_dl": {"label": "LDL-C", "unit": "mg/dL", "low": None, "high": 100},
    "hdl_mg_dl": {"label": "HDL-C", "unit": "mg/dL", "low": 40, "high": None},
    "triglycerides_mg_dl": {"label": "Triglycerides", "unit": "mg/dL", "low": None, "high": 150},
    "total_cholesterol_mg_dl": {"label": "Total cholesterol", "unit": "mg/dL", "low": None, "high": 200},
    "hba1c_percent": {"label": "HbA1c", "unit": "%", "low": None, "high": 5.7},
    "glucose_mg_dl": {"label": "Glucose", "unit": "mg/dL", "low": 70, "high": 100},
    "alt_u_l": {"label": "ALT", "unit": "U/L", "low": 7, "high": 56},
    "ast_u_l": {"label": "AST", "unit": "U/L", "low": 10, "high": 40},
    "creatinine_mg_dl": {"label": "Creatinine", "unit": "mg/dL", "low": 0.6, "high": 1.3},
    "egfr_ml_min_1_73m2": {"label": "eGFR", "unit": "mL/min/1.73m2", "low": 60, "high": None},
    "uric_acid_mg_dl": {"label": "Uric acid", "unit": "mg/dL", "low": 3.5, "high": 7.2},
    "hemoglobin_g_dl": {"label": "Hemoglobin", "unit": "g/dL", "low": 12.0, "high": 17.5},
}


def handle(user_input: str) -> str:
    """Entry point expected by OpenClaw-style executable skills."""
    try:
        result = _handle(user_input or "")
    except Exception as exc:  # Return JSON even for unexpected input errors.
        result = {
            "status": "error",
            "error": f"{exc.__class__.__name__}: {exc}",
            "disclaimer": DISCLAIMER,
        }
    return json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)


def _handle(user_input: str) -> dict[str, Any]:
    text = user_input.strip()
    if not text:
        return _starter("Tell me what you want to record or ask for a report.")

    payload = _try_json(text)
    if isinstance(payload, dict):
        action = str(payload.get("action", "")).lower().strip()
        if action in {"help", "schema", "start"}:
            return _starter("Use one of the schemas below or write naturally.")
        if action in {"report", "summary", "trend", "trends"}:
            return _build_report(payload.get("period", "weekly"), payload.get("end_date"))
        if action in {"reminders", "reminder"}:
            end = _coerce_date(payload.get("end_date"))
            return {
                "status": "ok",
                "reminders": _build_reminders(_load_records(), end),
                "disclaimer": DISCLAIMER,
            }
        if action == "clear":
            return _clear_data()
        if action in {"record", "add", "log"} or payload.get("type"):
            record = _normalize_structured_record(payload)
            return _record_and_analyze(record)
        return _starter(f"Unknown action '{action}'.")

    natural = _parse_natural_language(text)
    if natural:
        return _record_and_analyze(natural)

    return _starter("I could not confidently parse that health entry.")


def _starter(message: str) -> dict[str, Any]:
    return {
        "status": "needs_input",
        "message": message,
        "examples": [
            "今天血压 126/82 心率 68",
            "record exercise: brisk walk 45 minutes",
            "血检 LDL 142, HDL 52, HbA1c 5.9",
            '{"action":"report","period":"weekly","end_date":"2026-05-02"}',
        ],
        "collection_schema": {
            "blood_pressure": {
                "action": "record",
                "type": "blood_pressure",
                "date": "YYYY-MM-DD",
                "systolic": 126,
                "diastolic": 82,
                "pulse": 68,
                "context": "morning, seated, before coffee",
            },
            "blood_lab": {
                "action": "record",
                "type": "blood_lab",
                "date": "YYYY-MM-DD",
                "markers": {"LDL": 142, "HDL": 52, "HbA1c": 5.9},
            },
            "exercise": {
                "action": "record",
                "type": "exercise",
                "date": "YYYY-MM-DD",
                "activity": "brisk walk",
                "minutes": 45,
                "intensity": "moderate",
            },
            "report": {"action": "report", "period": "weekly"},
        },
        "disclaimer": DISCLAIMER,
    }


def _try_json(text: str) -> Any:
    if not (text.startswith("{") and text.endswith("}")):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _normalize_structured_record(payload: dict[str, Any]) -> dict[str, Any]:
    record_type = str(payload.get("type", "")).lower().strip()
    record = {
        "type": record_type,
        "date": _coerce_date(payload.get("date")).isoformat(),
        "source": payload.get("source", "user"),
        "notes": payload.get("notes", ""),
    }
    if record_type == "blood_pressure":
        record.update(
            {
                "systolic": int(payload["systolic"]),
                "diastolic": int(payload["diastolic"]),
            }
        )
        if payload.get("pulse") is not None:
            record["pulse"] = int(payload["pulse"])
        if payload.get("context"):
            record["context"] = str(payload["context"])
        return record
    if record_type == "blood_lab":
        markers = payload.get("markers")
        if not isinstance(markers, dict) or not markers:
            raise ValueError("blood_lab requires a non-empty markers object")
        record["markers"] = _normalize_markers(markers)
        return record
    if record_type == "exercise":
        record.update(
            {
                "activity": str(payload.get("activity", "exercise")),
                "minutes": int(float(payload["minutes"])),
                "intensity": str(payload.get("intensity", "moderate")).lower(),
            }
        )
        if payload.get("distance_km") is not None:
            record["distance_km"] = float(payload["distance_km"])
        return record
    if record_type in {"body_metric", "body"}:
        record["type"] = "body_metric"
        for key in ("weight_kg", "waist_cm", "body_fat_percent"):
            if payload.get(key) is not None:
                record[key] = float(payload[key])
        if len(record) <= 4:
            raise ValueError("body_metric requires at least one numeric metric")
        return record
    raise ValueError("type must be blood_pressure, blood_lab, exercise, or body_metric")


def _normalize_markers(markers: dict[str, Any]) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for raw_key, raw_value in markers.items():
        key = _normalize_marker_name(str(raw_key))
        normalized[key] = float(raw_value)
    return normalized


def _normalize_marker_name(raw_key: str) -> str:
    compact = raw_key.strip().lower().replace("_", " ").replace("-", " ")
    compact = re.sub(r"\s+", " ", compact)
    if compact in MARKER_ALIASES:
        return MARKER_ALIASES[compact]
    snake = re.sub(r"[^a-z0-9]+", "_", compact).strip("_")
    return snake or "unknown_marker"


def _parse_natural_language(text: str) -> dict[str, Any] | None:
    bp = _parse_bp_text(text)
    if bp:
        return bp
    exercise = _parse_exercise_text(text)
    if exercise:
        return exercise
    lab = _parse_lab_text(text)
    if lab:
        return lab
    return None


def _parse_bp_text(text: str) -> dict[str, Any] | None:
    match = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", text)
    if not match:
        return None
    record: dict[str, Any] = {
        "type": "blood_pressure",
        "date": _extract_date(text).isoformat(),
        "systolic": int(match.group(1)),
        "diastolic": int(match.group(2)),
        "source": "natural_language",
        "notes": text,
    }
    pulse_match = re.search(r"(?:pulse|heart rate|hr|心率|脉搏)\s*[:：]?\s*(\d{2,3})", text, re.I)
    if pulse_match:
        record["pulse"] = int(pulse_match.group(1))
    return record


def _parse_exercise_text(text: str) -> dict[str, Any] | None:
    lower = text.lower()
    has_activity = any(
        token in lower
        for token in [
            "exercise",
            "walk",
            "run",
            "bike",
            "cycle",
            "swim",
            "strength",
            "yoga",
            "workout",
            "运动",
            "走路",
            "散步",
            "跑步",
            "骑行",
            "游泳",
            "力量",
            "瑜伽",
        ]
    )
    if not has_activity:
        return None
    minutes_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:minutes|minute|min|mins|m|分钟)", lower)
    if not minutes_match:
        return None
    distance_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:km|公里|千米)", lower)
    activity = "exercise"
    for token, name in [
        ("walk", "walk"),
        ("run", "run"),
        ("bike", "bike"),
        ("cycle", "cycling"),
        ("swim", "swim"),
        ("strength", "strength"),
        ("yoga", "yoga"),
        ("散步", "walk"),
        ("走路", "walk"),
        ("跑步", "run"),
        ("骑行", "cycling"),
        ("游泳", "swim"),
        ("力量", "strength"),
        ("瑜伽", "yoga"),
    ]:
        if token in lower:
            activity = name
            break
    record: dict[str, Any] = {
        "type": "exercise",
        "date": _extract_date(text).isoformat(),
        "activity": activity,
        "minutes": int(float(minutes_match.group(1))),
        "intensity": "moderate",
        "source": "natural_language",
        "notes": text,
    }
    if distance_match:
        record["distance_km"] = float(distance_match.group(1))
    return record


def _parse_lab_text(text: str) -> dict[str, Any] | None:
    lower = text.lower()
    if not any(token in lower for token in ["lab", "blood", "血检", "化验", "体检", "ldl", "hba1c", "糖化"]):
        return None
    markers: dict[str, float] = {}
    aliases = sorted(MARKER_ALIASES, key=len, reverse=True)
    for alias in aliases:
        if re.search(r"[\u4e00-\u9fff]", alias):
            pattern = re.escape(alias) + r"\s*[:：=]?\s*(\d+(?:\.\d+)?)"
        else:
            pattern = r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])\s*[:：=]?\s*(\d+(?:\.\d+)?)"
        match = re.search(pattern, lower, re.I)
        if match:
            markers[MARKER_ALIASES[alias]] = float(match.group(1))
    if not markers:
        return None
    return {
        "type": "blood_lab",
        "date": _extract_date(text).isoformat(),
        "markers": markers,
        "source": "natural_language",
        "notes": text,
    }


def _record_and_analyze(record: dict[str, Any]) -> dict[str, Any]:
    existing = _load_records()
    record = dict(record)
    record["id"] = _record_id(record, len(existing) + 1)
    record["created_at"] = datetime.now().replace(microsecond=0).isoformat()
    _append_record(record)
    all_records = existing + [record]
    analysis = _analyze_record(record, existing)
    safety_flags = _safety_flags(record, analysis)
    return {
        "status": "recorded",
        "record": record,
        "analysis": analysis,
        "safety_flags": safety_flags,
        "reminders": _build_reminders(all_records, _coerce_date(record["date"])),
        "next_steps": _next_steps(record, analysis, safety_flags),
        "disclaimer": DISCLAIMER,
    }


def _record_id(record: dict[str, Any], seq: int) -> str:
    safe_type = re.sub(r"[^a-z0-9]+", "-", str(record.get("type", "record")).lower()).strip("-")
    return f"{record.get('date', _today().isoformat())}-{safe_type}-{seq:04d}"


def _analyze_record(record: dict[str, Any], existing: list[dict[str, Any]]) -> dict[str, Any]:
    if record["type"] == "blood_pressure":
        same = [r for r in existing if r.get("type") == "blood_pressure"] + [record]
        systolic = [float(r["systolic"]) for r in sorted(same, key=lambda item: item.get("date", ""))]
        diastolic = [float(r["diastolic"]) for r in sorted(same, key=lambda item: item.get("date", ""))]
        return {
            "category": _bp_category(record["systolic"], record["diastolic"]),
            "systolic_trend": _trend_label(systolic, threshold=5),
            "diastolic_trend": _trend_label(diastolic, threshold=3),
            "note": "Use home readings as a log for clinician discussion, not as a diagnosis.",
        }
    if record["type"] == "blood_lab":
        flags = _lab_flags(record.get("markers", {}))
        return {
            "lab_flags": flags,
            "flagged_count": len([flag for flag in flags if flag["status"] != "within_reference"]),
            "note": "Reference ranges vary by lab and individual context; confirm interpretation with a clinician.",
        }
    if record["type"] == "exercise":
        return {
            "minutes": record["minutes"],
            "goal_context": f"General adult benchmark: {WEEKLY_MODERATE_EXERCISE_GOAL_MIN} minutes/week moderate activity.",
            "counts_toward_weekly_goal": record.get("intensity", "moderate") in {"moderate", "vigorous"},
        }
    return {"note": "Recorded for trend context."}


def _bp_category(systolic: int | float, diastolic: int | float) -> str:
    if systolic >= 180 or diastolic >= 120:
        return "very_high_urgent_range"
    if systolic >= 140 or diastolic >= 90:
        return "high_range_stage_2"
    if systolic >= 130 or diastolic >= 80:
        return "high_range_stage_1"
    if systolic >= 120 and diastolic < 80:
        return "elevated_range"
    return "typical_range"


def _lab_flags(markers: dict[str, float]) -> list[dict[str, Any]]:
    flags = []
    for key, value in sorted(markers.items()):
        ref = REFERENCE_RANGES.get(key)
        if not ref:
            flags.append(
                {
                    "marker": key,
                    "value": value,
                    "status": "unmapped_reference",
                    "message": "No built-in reference range; keep for trend tracking.",
                }
            )
            continue
        status = "within_reference"
        if ref["low"] is not None and value < ref["low"]:
            status = "below_reference"
        if ref["high"] is not None and value >= ref["high"]:
            status = "above_reference"
        flags.append(
            {
                "marker": key,
                "label": ref["label"],
                "value": value,
                "unit": ref["unit"],
                "reference_low": ref["low"],
                "reference_high": ref["high"],
                "status": status,
            }
        )
    return flags


def _safety_flags(record: dict[str, Any], analysis: dict[str, Any]) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    if record["type"] == "blood_pressure" and analysis.get("category") == "very_high_urgent_range":
        flags.append(
            {
                "severity": "urgent",
                "reason": "Blood pressure is in a very high range (>=180 systolic or >=120 diastolic).",
                "action": "Recheck after resting. If still very high or symptoms are present, seek urgent medical care.",
            }
        )
    if record["type"] == "blood_lab":
        flagged = [item for item in analysis.get("lab_flags", []) if item["status"] != "within_reference"]
        if flagged:
            flags.append(
                {
                    "severity": "review",
                    "reason": f"{len(flagged)} lab marker(s) are outside built-in reference thresholds.",
                    "action": "Review the official lab report and personal risk context with a clinician.",
                }
            )
    return flags


def _next_steps(record: dict[str, Any], analysis: dict[str, Any], safety_flags: list[dict[str, str]]) -> list[str]:
    if safety_flags and safety_flags[0]["severity"] == "urgent":
        return [
            "Recheck the reading after 5 minutes of quiet rest.",
            "If symptoms are present or the reading remains very high, contact urgent medical care.",
        ]
    if record["type"] == "blood_pressure":
        return [
            "Keep readings under similar conditions so trends are comparable.",
            "Share repeated high readings or symptoms with a clinician.",
        ]
    if record["type"] == "blood_lab":
        if analysis.get("flagged_count", 0):
            return ["Discuss flagged lab markers with a clinician before making treatment decisions."]
        return ["Keep the original lab report date and units for future comparison."]
    if record["type"] == "exercise":
        return ["Log the next workout and review weekly minutes against your target."]
    return ["Keep logging comparable data points for trend quality."]


def _build_report(period: Any, end_date: Any = None) -> dict[str, Any]:
    period_name = str(period or "weekly").lower()
    if period_name not in {"weekly", "monthly"}:
        period_name = "weekly"
    end = _coerce_date(end_date)
    start = end - timedelta(days=6 if period_name == "weekly" else 29)
    records = [r for r in _load_records() if start <= _coerce_date(r.get("date")) <= end]
    by_type = _group_by_type(records)
    bp_report, bp_charts = _bp_report(by_type.get("blood_pressure", []))
    exercise_report = _exercise_report(by_type.get("exercise", []), period_name)
    lab_report = _lab_report(by_type.get("blood_lab", []))
    charts = {}
    charts.update(bp_charts)
    if by_type.get("exercise"):
        charts["exercise_minutes"] = _ascii_chart(by_type["exercise"], "minutes")
    return {
        "status": "ok",
        "period": period_name,
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "data_counts": {kind: len(items) for kind, items in sorted(by_type.items())},
        "blood_pressure": bp_report,
        "exercise": exercise_report,
        "labs": lab_report,
        "trend_charts": charts,
        "reminders": _build_reminders(_load_records(), end),
        "data_quality": _data_quality(records),
        "disclaimer": DISCLAIMER,
    }


def _group_by_type(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(str(record.get("type", "unknown")), []).append(record)
    for items in grouped.values():
        items.sort(key=lambda item: item.get("date", ""))
    return grouped


def _bp_report(records: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, str]]:
    if not records:
        return {"status": "no_data"}, {}
    systolic = [float(r["systolic"]) for r in records]
    diastolic = [float(r["diastolic"]) for r in records]
    latest = records[-1]
    report = {
        "status": "ok",
        "readings": len(records),
        "latest": {
            "date": latest["date"],
            "systolic": latest["systolic"],
            "diastolic": latest["diastolic"],
            "category": _bp_category(latest["systolic"], latest["diastolic"]),
        },
        "average_systolic": round(sum(systolic) / len(systolic), 1),
        "average_diastolic": round(sum(diastolic) / len(diastolic), 1),
        "systolic_trend": _trend_label(systolic, threshold=5),
        "diastolic_trend": _trend_label(diastolic, threshold=3),
    }
    charts = {
        "blood_pressure_systolic": _ascii_chart(records, "systolic"),
        "blood_pressure_diastolic": _ascii_chart(records, "diastolic"),
    }
    return report, charts


def _exercise_report(records: list[dict[str, Any]], period_name: str) -> dict[str, Any]:
    total = sum(int(r.get("minutes", 0)) for r in records)
    goal = WEEKLY_MODERATE_EXERCISE_GOAL_MIN if period_name == "weekly" else WEEKLY_MODERATE_EXERCISE_GOAL_MIN * 4
    return {
        "status": "ok" if records else "no_data",
        "sessions": len(records),
        "weekly_minutes": total if period_name == "weekly" else round(total / 4, 1),
        "period_minutes": total,
        "goal_minutes": goal,
        "goal_progress_percent": round((total / goal) * 100, 1) if goal else 0,
    }


def _lab_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {"status": "no_data"}
    latest = records[-1]
    return {
        "status": "ok",
        "latest_date": latest["date"],
        "latest_markers": latest.get("markers", {}),
        "latest_flags": _lab_flags(latest.get("markers", {})),
    }


def _ascii_chart(records: list[dict[str, Any]], field: str, width: int = 24) -> str:
    points = [(r.get("date", ""), float(r[field])) for r in records if r.get(field) is not None]
    if not points:
        return ""
    values = [value for _, value in points]
    lo, hi = min(values), max(values)
    span = max(hi - lo, 1.0)
    lines = []
    for item_date, value in points:
        size = int(round(((value - lo) / span) * (width - 1))) + 1
        lines.append(f"{item_date} | {'#' * size:<{width}} {value:g}")
    return "\n".join(lines)


def _trend_label(values: list[float], threshold: float) -> str:
    if len(values) < 2:
        return "insufficient_data"
    delta = values[-1] - values[0]
    if delta >= threshold:
        return "rising"
    if delta <= -threshold:
        return "falling"
    return "stable"


def _build_reminders(records: list[dict[str, Any]], end: date) -> list[dict[str, str]]:
    reminders: list[dict[str, str]] = []
    by_type = _group_by_type(records)
    bp_records = by_type.get("blood_pressure", [])
    if not bp_records:
        reminders.append(
            {
                "type": "blood_pressure",
                "priority": "normal",
                "message": "No blood pressure data yet. Add a few comparable readings if BP monitoring matters for you.",
            }
        )
    else:
        last_bp = _coerce_date(bp_records[-1].get("date"))
        if (end - last_bp).days >= 3:
            reminders.append(
                {
                    "type": "blood_pressure",
                    "priority": "normal",
                    "message": "Blood pressure log is older than 3 days; record a fresh reading if you are actively monitoring.",
                }
            )
    exercise_records = [
        r for r in by_type.get("exercise", []) if end - timedelta(days=6) <= _coerce_date(r.get("date")) <= end
    ]
    weekly_minutes = sum(int(r.get("minutes", 0)) for r in exercise_records)
    if weekly_minutes < WEEKLY_MODERATE_EXERCISE_GOAL_MIN:
        reminders.append(
            {
                "type": "exercise",
                "priority": "normal",
                "message": f"{max(WEEKLY_MODERATE_EXERCISE_GOAL_MIN - weekly_minutes, 0)} moderate minutes remain toward the weekly 150-minute benchmark.",
            }
        )
    lab_records = by_type.get("blood_lab", [])
    if not lab_records:
        reminders.append(
            {
                "type": "blood_lab",
                "priority": "low",
                "message": "No lab data imported yet. Add recent blood test markers when available.",
            }
        )
    else:
        last_lab = _coerce_date(lab_records[-1].get("date"))
        if (end - last_lab).days >= 180:
            reminders.append(
                {
                    "type": "blood_lab",
                    "priority": "low",
                    "message": "Latest lab data is older than 6 months; ask your clinician whether repeat testing is appropriate.",
                }
            )
    urgent_bp = [
        r
        for r in bp_records
        if _bp_category(float(r.get("systolic", 0)), float(r.get("diastolic", 0))) == "very_high_urgent_range"
        and _coerce_date(r.get("date")) == end
    ]
    if urgent_bp:
        reminders.insert(
            0,
            {
                "type": "safety",
                "priority": "urgent",
                "message": "A very high blood pressure reading was logged today; recheck and seek urgent care if it persists or symptoms exist.",
            },
        )
    return reminders


def _data_quality(records: list[dict[str, Any]]) -> list[str]:
    notes = []
    if not records:
        return ["No records in this period."]
    typed = _group_by_type(records)
    if len(typed.get("blood_pressure", [])) == 1:
        notes.append("Blood pressure trend is weak with only one reading.")
    if "blood_lab" in typed:
        notes.append("Lab interpretation depends on the official report units and lab-specific reference ranges.")
    if not notes:
        notes.append("Enough data for a basic period snapshot; longer trends improve reliability.")
    return notes


def _clear_data() -> dict[str, Any]:
    path = _store_path()
    if path.exists():
        path.unlink()
    return {"status": "cleared", "path": str(path), "disclaimer": DISCLAIMER}


def _load_records() -> list[dict[str, Any]]:
    path = _store_path()
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    records.sort(key=lambda item: item.get("date", ""))
    return records


def _append_record(record: dict[str, Any]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _store_path() -> Path:
    root = os.environ.get("PERSONAL_HEALTH_AGENT_DATA_DIR", "~/.personal-health-agent")
    return Path(root).expanduser() / "health_records.jsonl"


def _extract_date(text: str) -> date:
    match = re.search(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})", text)
    if match:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    lower = text.lower()
    if "yesterday" in lower or "昨天" in text:
        return _today() - timedelta(days=1)
    return _today()


def _coerce_date(value: Any = None) -> date:
    if isinstance(value, date):
        return value
    if value is None or value == "":
        return _today()
    if isinstance(value, datetime):
        return value.date()
    text = str(value)
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return _extract_date(text)


def _today() -> date:
    return date.today()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    else:
        prompt = sys.stdin.read()
    print(handle(prompt))
