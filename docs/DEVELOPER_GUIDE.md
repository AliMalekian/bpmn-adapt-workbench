# BPMN Adapt Workbench — Developer Guide

## Architecture
The workbench is organized around a 4-agent pipeline:
1. Orchestrator — coordinates the pipeline, handles feedback loops.
2. Analyst — checks feasibility against rules, resources, and runtime state.
3. Modeler — generates ChangeOperations (LLM) and applies them (deterministic).
4. Experimenter — validates the candidate (deterministic + LLM feedback).

All LLM calls go through `FallbackLLMClient` which reads `providers.json` and tries providers in priority order.

## Directory Structure
```
bpmn_adapt_workbench/
  src/bpmn_adapt/
    agents/       # Analyst, Modeler, Experimenter, Orchestrator
    llm/          # LLM clients (OpenAI-compatible, UM LLM, Fallback)
    providers/    # ProviderManager
    gui/          # Tkinter DesktopApp + panels
    evaluation/   # Benchmark runner, comparison, baselines
    bpmn/         # BPMN parsing, mutation, validation
    domain/       # Models, enums
    prompts/      # Agent prompts (v2)
    persistence/  # SQLite database
    retrieval/    # RAG
  scripts/        # Utility scripts
  tests/          # Unit and integration tests
  docs/           # Documentation
  experiments/    # Runtime data (gitignored)
  providers.json  # Local config (gitignored)
  providers.example.json # Template
```

## Adding a New Provider Type
1. Create a new client class in `src/bpmn_adapt/llm/`.
2. Implement the `complete(system_prompt, user_payload, *, schema_name) -> dict` method.
3. Add the type to `ProviderManager.build_client()`.
4. Add it to the GUI dropdown in `provider_config.py`.

## Modifying Agent Prompts
Prompts are stored in `src/bpmn_adapt/prompts/<agent>_v2.md`.
Load them via `load_prompt(agent)`. The default version is v2.
Prompts are plain text; no templating engine.

## Adding a New Evaluation Metric
1. Compute it in `evaluation/metrics.py` or in the relevant agent.
2. Add it to the per-test record in `benchmark_runner.py`.
3. Add it to the aggregated metrics in `metrics.json`.
4. Add a chart in `evaluation/comparison.py` if needed.

## Running Tests
```bash
pytest tests/
```

## Logging
Every LLM call is logged to `live_evaluation_v3/llm_calls.jsonl` (or the run-specific output directory).
Format:
```json
{
  "timestamp": "ISO-8601",
  "status": "SUCCESS|FAILED|RATE_LIMITED",
  "provider": "groq|gemini|um-llm1-gemma4|...",
  "model": "openai/gpt-oss-120b|...",
  "schema_name": "analyse|model|experiment|...",
  "attempt": 0,
  "latency_seconds": 2.34,
  "response": {},
  "system_prompt": "...",
  "user_payload": "..."
}
```

## Dataflow Contract
The 4-agent pipeline must remain:
- Orchestrator: deterministic lifecycle + LLM routing.
- Analyst: live LLM decision + token context.
- Modeler: live LLM ChangeOperation + deterministic MutationEngine.
- Experimenter: deterministic checks + live LLM feedback.
- Experimenter computes GED for RE_ADD only.
- Feedback loop: Modeler ↔ Experimenter, max 3 retries.
Do NOT change this dataflow without explicit approval.

## Extending the Screenshot Engine
`AutomatedScreenshot` supports 4 strategies (A/B/C/D).
To add a new strategy:
1. Extend `execute_strategy()` with the new strategy name.
2. Update the dropdown in `benchmark.py`.
3. Document in `USER_MANUAL.md`.

## Reporting Issues
Include:
- The exact command or GUI action.
- The raw error message.
- The relevant lines from `llm_calls.jsonl`.
- The Python version and OS.
