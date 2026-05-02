# Personal Health Agent

Local-first personal health management agent for OpenClaw and Hermes Agent.

It records blood pressure, blood lab markers, exercise, and body metrics; then returns analysis, reminders, and weekly or monthly ASCII trend charts. It does not call external APIs.

## Install

OpenClaw:

```bash
./scripts/install_openclaw.sh
```

Hermes Agent:

```bash
./scripts/install_hermes.sh
```

Manual install paths:

```bash
cp -R skills/personal-health-agent ~/.openclaw/skills/
mkdir -p ~/.hermes/skills/health
cp -R skills/personal-health-agent ~/.hermes/skills/health/
```

## Use

From the skill directory:

```bash
python3 handler.py '今天血压 126/82 心率 68'
python3 handler.py '血检 LDL 142, HDL 52, HbA1c 5.9'
python3 handler.py 'record exercise: brisk walk 45 minutes'
python3 handler.py '{"action":"report","period":"weekly","end_date":"2026-05-02"}'
```

Data is stored by default at:

```text
~/.personal-health-agent/health_records.jsonl
```

Override storage:

```bash
export PERSONAL_HEALTH_AGENT_DATA_DIR=/path/to/private/health-data
```

## Verify

```bash
./scripts/verify.sh
```

## Safety

This is informational wellness support only. It does not diagnose, treat, prescribe, or replace professional medical advice. For severe symptoms, very high blood pressure, chest pain, stroke symptoms, fainting, or other emergencies, seek urgent medical care.
