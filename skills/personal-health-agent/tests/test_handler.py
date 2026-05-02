import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path


sys.dont_write_bytecode = True

SKILL_DIR = Path(__file__).resolve().parents[1]
HANDLER_PATH = SKILL_DIR / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("personal_health_handler", HANDLER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def call(module, payload):
    raw = module.handle(json.dumps(payload, ensure_ascii=False) if isinstance(payload, dict) else payload)
    return json.loads(raw)


def test_records_structured_bp_and_exercise_then_builds_weekly_report():
    with tempfile.TemporaryDirectory() as data_dir:
        os.environ["PERSONAL_HEALTH_AGENT_DATA_DIR"] = data_dir
        module = load_handler()

        bp = call(
            module,
            {
                "action": "record",
                "type": "blood_pressure",
                "date": "2026-04-29",
                "systolic": 126,
                "diastolic": 82,
                "pulse": 68,
            },
        )
        exercise = call(
            module,
            {
                "action": "record",
                "type": "exercise",
                "date": "2026-04-30",
                "activity": "brisk walk",
                "minutes": 45,
                "intensity": "moderate",
            },
        )
        report = call(module, {"action": "report", "period": "weekly", "end_date": "2026-05-02"})

    assert bp["status"] == "recorded"
    assert exercise["status"] == "recorded"
    assert report["period"] == "weekly"
    assert report["data_counts"]["blood_pressure"] == 1
    assert report["data_counts"]["exercise"] == 1
    assert "blood_pressure_systolic" in report["trend_charts"]
    assert report["exercise"]["weekly_minutes"] == 45
    assert report["disclaimer"]


def test_natural_language_bp_record_flags_urgent_range():
    with tempfile.TemporaryDirectory() as data_dir:
        os.environ["PERSONAL_HEALTH_AGENT_DATA_DIR"] = data_dir
        module = load_handler()
        result = call(module, "今天血压 182/121, 心率 88")

    assert result["status"] == "recorded"
    assert result["record"]["type"] == "blood_pressure"
    assert result["record"]["systolic"] == 182
    assert result["record"]["diastolic"] == 121
    assert result["safety_flags"][0]["severity"] == "urgent"


def test_lab_record_normalizes_markers_and_flags_reference_ranges():
    with tempfile.TemporaryDirectory() as data_dir:
        os.environ["PERSONAL_HEALTH_AGENT_DATA_DIR"] = data_dir
        module = load_handler()
        result = call(
            module,
            {
                "action": "record",
                "type": "blood_lab",
                "date": "2026-04-20",
                "markers": {"LDL": 142, "HbA1c": 5.9, "HDL": 52},
            },
        )

    markers = result["record"]["markers"]
    flags = {item["marker"]: item for item in result["analysis"]["lab_flags"]}
    assert markers["ldl_mg_dl"] == 142
    assert markers["hba1c_percent"] == 5.9
    assert flags["ldl_mg_dl"]["status"] == "above_reference"
    assert flags["hba1c_percent"]["status"] == "above_reference"
    assert "clinician" in result["next_steps"][0].lower()


def test_monthly_report_contains_bp_trend_and_reminders():
    with tempfile.TemporaryDirectory() as data_dir:
        os.environ["PERSONAL_HEALTH_AGENT_DATA_DIR"] = data_dir
        module = load_handler()
        for date, systolic, diastolic in [
            ("2026-04-01", 118, 76),
            ("2026-04-15", 126, 80),
            ("2026-05-01", 134, 85),
        ]:
            call(
                module,
                {
                    "action": "record",
                    "type": "blood_pressure",
                    "date": date,
                    "systolic": systolic,
                    "diastolic": diastolic,
                },
            )
        report = call(module, {"action": "report", "period": "monthly", "end_date": "2026-05-02"})

    assert report["period"] == "monthly"
    assert report["blood_pressure"]["systolic_trend"] == "rising"
    assert "blood_pressure_diastolic" in report["trend_charts"]
    assert report["reminders"]


def test_empty_input_returns_easy_start_schema():
    with tempfile.TemporaryDirectory() as data_dir:
        os.environ["PERSONAL_HEALTH_AGENT_DATA_DIR"] = data_dir
        module = load_handler()
        result = call(module, "")

    assert result["status"] == "needs_input"
    assert "examples" in result
    assert "blood_pressure" in result["collection_schema"]


if __name__ == "__main__":
    tests = [
        test_records_structured_bp_and_exercise_then_builds_weekly_report,
        test_natural_language_bp_record_flags_urgent_range,
        test_lab_record_normalizes_markers_and_flags_reference_ranges,
        test_monthly_report_contains_bp_trend_and_reminders,
        test_empty_input_returns_easy_start_schema,
    ]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception as exc:
            failures += 1
            print(f"FAIL {test.__name__}: {exc.__class__.__name__}: {exc}")
    raise SystemExit(1 if failures else 0)
