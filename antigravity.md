# BPMN Runtime Adaptation Framework — Master Operational Log (Antigravity)

**Last Updated:** 2026-10-03  
**Active Working Directory:** `E:\bpmn_adapt_workbench\`  
**Active Data Directory:** `E:\Implemention_dataset enriched\`  
**Primary LLM Model:** `nvidia/nemotron-3-super-120b-a12b:free`  
**Fallback LLM Model:** `dots-studio/dots-3-note-preview:free`  
**Execution Mode:** `live` (Strict OpenRouter HTTP calls, zero mock)  

---

## 1. Project Overview & Architectural Boundaries
This project implements the 4-Agent Constraint-Aware BPMN Runtime Adaptation Framework from the master's thesis proposal (`Malekian_State_Of_The_Art.docx`).
The architecture strictly enforces:
1. **Analyst Agent**: Sole feasibility decision-maker. Evaluates incoming natural language requests against database rules, resources, instance states, and RAG precedents. Classifies rejections into four canonical categories: `RULE_CONFLICT`, `RESOURCE_CONFLICT`, `DUAL_CONFLICT`, `STATE_CONFLICT`.
2. **Modeler Agent**: Translates approved feasibility decisions into atomic BPMN `ChangeOperation` structures. Reconstructs re-added nodes via LLM generation (not oracle copying). Applies operations deterministically via `MutationEngine`.
3. **Experimenter Agent**: Hybrid deterministic + LLM evaluator. Deterministic layer (Petri-net token simulation, reachability, deadlock detection, schema validation) holds authoritative veto power. Live LLM call provides semantic validation and targeted repair feedback.
4. **Orchestrator Agent**: Top-level coordinator managing the lifecycle state machine, RAG indexation of approved runs, and the Modeler $\leftrightarrow$ Experimenter feedback retry loop (max 3 retries).
5. **No Ground Truth Leakage**: No agent or pipeline component reads `Remove_requests.txt`, `oracle_bpmn_xml`, or hardcoded dictionaries.

---

## 2. Workspace Reorganization Log (2026-10-03)
The workspace was cleanly decoupled into two sibling directories:
- `E:\Implemention_dataset enriched\`: Pure data directory containing strictly the 82 dataset folders (4 Camunda, 23 Mangler, 55 Pmo). Zero source files, zero logs, zero database files.
- `E:\bpmn_adapt_workbench\`: Pure codebase and workbench containing all code (`src/`), tests (`tests/`), scripts (`scripts/`), documentation (`docs/`), profiles (`config/`), containers (`docker/`), and runtime state (`experiments/runtime_bpmn.db`).

### Renames Pre-Move:
- `ground_truth_5x82_evaluation\` → `mock_run_5x82_archive\`
- `full_dataset_82_processes\` → `mock_run_full_dataset_archive\`

### Inventory of Moved Items:
- **16 Directories Moved:** `.github\`, `.superpowers\`, `config\`, `docker\`, `docs\`, `experiments\`, `mock_run_5x82_archive\`, `mock_run_full_dataset_archive\`, `live_evaluation_v2\`, `live_evaluation_v3\`, `paper_figures\`, `saved_initial_run_documents\`, `scratch\`, `scripts\`, `src\`, `tests\`.
- **19 Root Files Moved:** `.env`, `.env.example`, `.gitignore`, `ALL_82_DATASETS_EVALUATION_REPORT.md`, `chat.md`, `compose.yaml`, `constraints.txt`, `doc_extracted.txt`, `FIVE_REQUESTS_82_DATASETS_EVALUATION_REPORT.md`, `generate_process_datasets.py`, `JOURNAL_PAPER_EVALUATION_REPORT.md`, `Malekian_State_Of_The_Art.docx`, `pyproject.toml`, `README.md`, `requirements-dev.txt`, `requirements.txt`, `roadmap.md`, `scratch_debug.py`, `test_capture.png`.

### Verification Status:
- Verified `E:\Implemention_dataset enriched\` has 0 files and exactly 82 directories.
- Package reinstalled in editable mode (`pip install -e . --no-deps`) under Python 3.12.
- All 5 smoke tests passed with exit code 0.

---

## 3. Current Configuration State (`.env`)
```ini
ADAPT_LLM_MODE=live
ADAPT_LLM_PROVIDER=openai_compatible
ADAPT_LLM_MODEL=nvidia/nemotron-3-super-120b-a12b:free
ADAPT_LLM_FALLBACK_MODEL=dots-studio/dots-3-note-preview:free
ADAPT_EVALUATION_REPETITIONS=30
ADAPT_LLM_BASE_URL=https://openrouter.ai/api/v1
ADAPT_LLM_TIMEOUT_SECONDS=180
ADAPT_LLM_MAX_RETRIES=5
ADAPT_LLM_RETRY_BACKOFF_SECONDS=2.0
ADAPT_LLM_RATE_LIMIT_REQUESTS_PER_MINUTE=30
ADAPT_VECTOR_PATH=experiments/vector_index
ADAPT_DATABASE_URL=sqlite:///experiments/runtime_bpmn.db
ADAPT_OUTPUT_ROOT=experiments/runs
```

---

## 4. Next Step
- **Stop 3**: Applying verified code and prompt modifications across all 4 agents (`analyst.py`, `analyst_v2.md`, `experimenter.py`, `experimenter_v2.md`, `modeler.py`, `modeler_v2.md`, `orchestrator.py`, `orchestrator_v2.md`).
- Running the 10-case pilot via GUI.
- Executing the live 410-test benchmark suite.
