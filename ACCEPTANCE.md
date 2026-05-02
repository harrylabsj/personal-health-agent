# Acceptance Checklist

Objective: develop a personal health management agent installable in OpenClaw and Hermes ecosystems, with easy collection, analysis, reminders, and weekly/monthly trend charts.

- Data collection: `handler.py` records blood pressure, blood labs, exercise, and body metrics to local JSONL.
- Blood tests: lab marker normalization and reference flags cover LDL, HDL, triglycerides, total cholesterol, HbA1c, glucose, ALT, AST, creatinine, eGFR, uric acid, and hemoglobin.
- Daily blood pressure: natural-language and JSON BP entries are supported, including urgent-range safety flags.
- Exercise: activity, minutes, intensity, and distance are supported.
- Analysis: immediate record-level analysis and period reports are returned as JSON.
- Reminders: reports include stale/missing BP, lab, and exercise reminders.
- Weekly/monthly trend charts: `report` returns ASCII charts for BP and exercise series.
- Easy to use: README, examples, install scripts, and help schema are included.
- OpenClaw installability: `skill.json`, `.claw/identity.json`, `SKILL.md`, `openclaw.plugin.json`, and `.codex-plugin/plugin.json` are included.
- Hermes installability: Hermes-compatible `SKILL.md` frontmatter and `hermes/manifest.yaml` are included.
- Safety: every handler response includes a medical disclaimer and urgent BP guidance.
- Verification: run `scripts/verify.sh`.
