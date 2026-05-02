---
name: personal-health-agent
description: Use when collecting personal health logs such as blood pressure, blood lab markers, exercise, and body metrics, then producing weekly or monthly trend summaries, reminders, and clinician-ready discussion notes. It supports OpenClaw and Hermes agent skill installation and keeps medical safety boundaries explicit.
metadata:
  hermes:
    tags: [health, wellness, blood-pressure, labs, exercise, reminders, trends]
    related_skills: []
  openclaw:
    category: Health
    entrypoint: handler.py
---

# Personal Health Agent

## Overview

This skill helps an agent collect personal health data, keep it in a local JSONL log, summarize trends, and generate reminders. It is designed for routine self-tracking: blood pressure, blood tests, exercise, and body metrics.

It is not a medical device and does not diagnose, prescribe, or replace a clinician. Treat every result as a tracking aid for better conversations with qualified healthcare professionals.

## When to Use

Use this skill when the user wants to:

- Record daily blood pressure, pulse, and context.
- Import blood test values such as LDL, HDL, HbA1c, glucose, triglycerides, ALT, AST, creatinine, eGFR, uric acid, or hemoglobin.
- Track exercise minutes, activity type, distance, and intensity.
- Produce weekly or monthly trend summaries with text charts.
- See practical reminders for missing logs, stale lab data, and weekly activity goals.
- Prepare a clinician-facing summary without turning the agent into a doctor.

Do not use this skill for emergency triage beyond telling the user to seek urgent medical care for red-flag situations. Do not make medication changes, diagnoses, or treatment decisions.

## Quick Start

Natural language examples:

```text
今天血压 126/82 心率 68
血检 LDL 142, HDL 52, HbA1c 5.9
record exercise: brisk walk 45 minutes
生成本周健康报告
```

Structured JSON examples:

```json
{"action":"record","type":"blood_pressure","date":"2026-05-02","systolic":126,"diastolic":82,"pulse":68}
```

```json
{"action":"record","type":"blood_lab","date":"2026-04-20","markers":{"LDL":142,"HDL":52,"HbA1c":5.9}}
```

```json
{"action":"report","period":"weekly","end_date":"2026-05-02"}
```

## Data Collection Workflow

1. Parse the user's entry as structured JSON first.
2. If it is not JSON, parse common natural-language patterns for blood pressure, exercise, and lab markers.
3. Normalize units and marker names where supported.
4. Append the record to the local JSONL store.
5. Return immediate analysis, safety flags, reminders, and next steps.
6. For reports, load the local store and summarize the requested weekly or monthly period.

The default store is:

```text
~/.personal-health-agent/health_records.jsonl
```

Override it for tests or private project storage:

```bash
export PERSONAL_HEALTH_AGENT_DATA_DIR=/path/to/private/data
```

## Supported Record Types

### Blood Pressure

Fields: `date`, `systolic`, `diastolic`, optional `pulse`, `context`, and `notes`.

The handler groups readings into broad tracking ranges and flags very high readings. If systolic is at least 180 or diastolic is at least 120, the response instructs the user to recheck after quiet rest and seek urgent care if the reading persists or symptoms are present.

### Blood Labs

Fields: `date` and `markers`.

Common aliases are normalized for LDL, HDL, triglycerides, total cholesterol, HbA1c, glucose, ALT, AST, creatinine, eGFR, uric acid, and hemoglobin. Built-in thresholds are generic reference aids only; official lab ranges and clinician context take precedence.

### Exercise

Fields: `date`, `activity`, `minutes`, optional `distance_km`, `intensity`, and `notes`.

Weekly summaries compare logged moderate/vigorous minutes against a general 150-minute adult benchmark. This is a wellness benchmark, not a personalized prescription.

### Body Metrics

Fields can include `weight_kg`, `waist_cm`, and `body_fat_percent`.

Body metrics are stored for future trend context. Avoid judgmental or appearance-focused language.

## Report Output

Weekly and monthly reports include:

- Date range and counts by record type.
- Blood pressure latest reading, averages, trend labels, and ASCII charts.
- Exercise sessions, period minutes, weekly-equivalent minutes, and goal progress.
- Latest lab markers and reference flags.
- Reminders for stale or missing data.
- Data quality notes explaining weak trend confidence.
- A medical safety disclaimer.

## Safety Rules

- State that the output is informational wellness support only.
- Never diagnose, prescribe, or tell the user to start/stop medication.
- For urgent blood pressure ranges or serious symptoms, recommend urgent medical care.
- Explain that lab reference ranges vary by lab and person.
- Encourage clinician review for abnormal, persistent, worsening, or symptomatic findings.
- Keep privacy local: no network calls and no external APIs.

## Verification

From the skill directory:

```bash
python3 tests/test_handler.py
python3 handler.py '{"action":"help"}'
```

The first command runs behavior tests. The second verifies the handler entrypoint returns JSON.
