# BPMN Adapt Workbench — Delivery Manifest

## Version 1.0.0 — Defense-Ready

## Delivery Date
2026-10-07

## Contents

### Core Code
- `src/bpmn_adapt/agents/` — 4 agents (Analyst, Modeler, Experimenter, Orchestrator)
- `src/bpmn_adapt/llm/` — LLM clients + UM adapter + Fallback client
- `src/bpmn_adapt/providers/` — ProviderManager
- `src/bpmn_adapt/gui/` — 14-tab DesktopApp + panel suite
- `src/bpmn_adapt/evaluation/` — Benchmark runner, comparison, baselines
- `src/bpmn_adapt/bpmn/` — BPMN parsing, mutation, and validation
- `src/bpmn_adapt/domain/` — Domain models and validation types
- `src/bpmn_adapt/prompts/` — Agent prompts (v2)
- `src/bpmn_adapt/persistence/` — SQLite database
- `src/bpmn_adapt/retrieval/` — RAG service

### Configuration
- `providers.example.json` — Template (committed to git)
- `providers.json` — Local configuration (gitignored, empty template)
- `.env.example` — Environment template
- `pyproject.toml` — Python packaging

### Documentation
- `README.md` — Overview
- `docs/USER_MANUAL.md` — How to use
- `docs/DEVELOPER_GUIDE.md` — How to extend
- `MANIFEST.md` — This file

### Verification
- All imports work
- CLI commands work
- GUI opens cleanly
- ProviderManager works
- UMLLMClient works
- FallbackLLMClient works
- Benchmark runner works
- Comparison generation works

## What's NOT Included
- API keys (user must provide manually)
- Dataset contents (user must provide `E:\Implemention_dataset enriched`)
- Benchmark results (user will run after configuring keys)

## How to Run
See `docs/USER_MANUAL.md`

## Known Limitations
- Groq free tier has rate limits (mitigated by mid-run key change and resume)
- Gemini requires VPN from Iran
- UM LLM has 2-second rate limit (handled by client rate limiter)
- First full benchmark run across 82 datasets takes ~4-5 hours

## Contact
Author / Research Team
