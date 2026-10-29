# Code Walkthrough: Runtime BPMN Adaptation Platform

This document explains the implementation step by step and file by file. Paths are relative to the project root.

## 1. End-to-end execution flow

1. `bpmn_adapt.cli` or `bpmn_adapt.gui.app` receives a process-folder path and user request.
2. `RuntimeAdaptationApplication` loads configuration and creates DB, LLM, embedding, RAG, and agent services.
3. `ingest_folder()` validates and reads the selected folder without changing source files.
4. The DB stores the process definition, source BPMN version, narrative, rules, resources, and runtime states.
5. Existing `RagData.txt` examples are imported as source evidence with folder/version provenance.
6. `OrchestratorAgent` opens an auditable run and invokes `AnalystAgent`.
7. `AnalystAgent` combines authoritative DB facts, compatible RAG evidence, and an LLM response. Deterministic checks override advisory evidence.
8. If approved, `ModelerAgent` resolves the actual BPMN target, applies an atomic remove or re-add, and builds a token-migration plan.
9. `ExperimenterAgent` validates migration targets and invokes the bounded token-marking simulator.
10. On failure, structured Experimenter feedback returns to the Modeler within the retry limit.
11. On success, the Orchestrator stores the new process version, marks the run approved, and indexes the approved case in RAG with complete lineage.
12. JSON results and candidate BPMN are written under the run-specific output directory.

## 2. Project and configuration files

### `pyproject.toml`

Defines the installable `bpmn-adapt` package, Python version, optional PostgreSQL/semantic/dev dependencies, package-resource handling for prompt files, and the `bpmn-adapt` console entry point. The core deliberately has no mandatory third-party dependencies, allowing offline reproduction.

### `.env.example`

Documents every supported environment variable: LLM mode/provider/model/base URL/key, timeouts, retries, rate limits, embedding provider/model, database URL, RAG mode, output root, and agent retry budget. It contains no usable secret.

### `.gitignore`

Excludes `.env`, virtual environments, bytecode, coverage data, databases, generated run outputs, and execution-ledger scratch data.

### `README.md`

Provides the architecture summary, quick-start commands, component list, and test command.

## 3. Configuration and domain contracts

### `src/bpmn_adapt/config.py`

- `Settings.from_env()` converts environment variables into typed settings.
- Live LLM mode requires an API key; mock mode is the default.
- The RAG mode is restricted to `hybrid`, `semantic`, `syntactic`, or `none`.
- `fingerprint()` hashes all public configuration while removing the API key. This fingerprint is saved in provenance and evaluation records.

### `src/bpmn_adapt/domain/models.py`

Defines immutable dataclasses exchanged between components:

- process facts: `Rule`, `ResourceFact`, `TokenState`, `RuntimeState`, and `ProcessDefinition`;
- versioning/request contracts: `ProcessVersion`, `AdaptationRequest`, and `OperationType`;
- analysis/RAG contracts: `RetrievedEvidence`, `FeasibilityDecision`, and `DecisionStatus`;
- modeling contracts: `AtomicChange`, `MigrationPlan`, and `CandidateModel`;
- experiment/result contracts: `ExperimentScenario`, `ExperimentReport`, `RunProvenance`, and `AdaptationResult`.

`Serializable.to_dict()` recursively converts dataclasses, paths, enums, collections, and nested contracts into JSON-safe values.

### Package `__init__.py` files

The `__init__.py` files identify Python packages and re-export their public entry points. They contain no workflow logic.

## 4. Folder ingestion

### `src/bpmn_adapt/ingestion/discovery.py`

- `ingest_folder()` validates a visible folder and required files.
- It discovers `.bpmn`, `.bpmn2`, `.bpmn2.xml`, and `.xml` models without assuming fixed filenames.
- It identifies narrative files while excluding rules, resources, generated outputs, and quality-score files.
- It parses numbered rules, line-based resources, runtime states, RAG blocks, and test-case blocks.
- It returns a `ProcessBundle` containing typed facts plus original request texts.
- All reads use UTF-8 with BOM support; the function never writes into the source folder.

## 5. BPMN representation and mutation

### `src/bpmn_adapt/bpmn/graph.py`

- `BpmnGraph.from_xml()` parses BPMN XML while retaining the original XML tree and namespaces.
- `_refresh()` creates the node and sequence-flow indexes.
- `predecessors()` and `successors()` expose control-flow relations.
- `resolve_node()` resolves an ID, exact name, or natural-language reference using normalized token overlap.
- `clone()` deep-copies a model before mutation.
- `to_xml()` serializes the candidate model.

### `src/bpmn_adapt/bpmn/mutation.py`

- `remove_element()` rejects unknown targets, events, gateways, and ambiguous multi-entry/multi-exit activities.
- For a safe single-entry/single-exit task, it removes the task and adjacent flows, then creates a direct predecessor-to-successor flow.
- If a token is located on the removed task, the migration maps it to the sole successor.
- It returns `MutationResult`, containing the candidate graph, atomic change, and migration plan.

Re-add restoration is implemented in the Modeler because it needs both the current version and the original BPMN oracle.

## 6. Persistence

### `src/bpmn_adapt/persistence/repositories.py`

Defines persistence-boundary errors: unsupported DB configuration and attempts to index an unapproved RAG case.

### `src/bpmn_adapt/persistence/base.py`

Contains the shared DB-API repository implementation and schema. Tables cover:

- processes and version lineage;
- rules, resources, and runtime states;
- orchestration runs and provenance events;
- requests, decisions, candidates, and simulations;
- RAG cases and retrieval logs.

Important behavior:

- source process ingestion is idempotent;
- candidate versions retain `parent_version_id` lineage;
- `get_latest_version()` selects the current leaf version for re-add;
- only approved runs can create RAG cases;
- revocation marks evidence inactive instead of deleting it;
- retrieval filters use process, operation, source version, and active status.

### `src/bpmn_adapt/persistence/sqlite.py`

Creates the default SQLite connection, enables foreign keys, creates parent directories, and configures dictionary-like rows.

### `src/bpmn_adapt/persistence/postgres.py`

Creates an optional PostgreSQL connection using `psycopg` and the same repository behavior. The optional dependency is required only when a PostgreSQL URL is selected.

### `src/bpmn_adapt/persistence/__init__.py`

`create_database()` selects SQLite or PostgreSQL from `ADAPT_DATABASE_URL` and returns a clear error for unsupported URLs or a missing PostgreSQL driver.

## 7. LLM and embedding integration

### `src/bpmn_adapt/llm/client.py`

Defines the provider-neutral `LLMClient` and `EmbeddingClient` protocols plus the normalized `LLMError`.

### `src/bpmn_adapt/llm/mock.py`

Implements deterministic, schema-keyed mock responses. It is used by tests and offline reproduction so repeated runs receive identical LLM outputs.

### `src/bpmn_adapt/llm/openai_compatible.py`

Implements an OpenAI-compatible `/chat/completions` client with:

- system/user messages;
- JSON-object response mode;
- configurable timeout and retry count;
- exponential backoff;
- normalized failures that do not expose the API key.

### `src/bpmn_adapt/llm/embedding.py`

Implements dependency-free signed feature hashing and cosine similarity. Signed hashing prevents accidental hash collisions from creating consistently positive similarity. A different embedding implementation can replace it through the same interface.

## 8. Prompt governance

### `src/bpmn_adapt/prompts/loader.py`

Loads only explicitly supported agent/version combinations as package resources.

### `src/bpmn_adapt/prompts/orchestrator_v1.md`

Defines sequencing, retry, provenance, and final-approval boundaries. It prohibits direct BPMN editing and approval after failed experiments.

### `src/bpmn_adapt/prompts/analyst_v1.md`

Defines DB authority, advisory RAG use, constraint citations, and the feasibility-decision JSON contract.

### `src/bpmn_adapt/prompts/modeler_v1.md`

Defines atomic BPMN changes, token migration, source-file immutability, and the model-output contract.

### `src/bpmn_adapt/prompts/experimenter_v1.md`

Defines independent testing, trace/failure reporting, and the prohibition on silently mutating or approving a candidate.

## 9. Hybrid RAG

### `src/bpmn_adapt/retrieval/service.py`

- Structured filtering restricts candidates by process, operation, source-version compatibility, and active status.
- Syntactic scoring uses normalized token overlap.
- Semantic scoring uses cosine similarity over embeddings.
- Hybrid mode combines semantic score (0.65) and syntactic score (0.35), then uses evidence ID for deterministic tie-breaking.
- `none`, `syntactic`, `semantic`, and `hybrid` modes support controlled ablations.
- Every query logs its hash, filters, component scores, final ranks, index version, and run ID.
- `index_approved()` delegates to the DB approval gate; `revoke()` preserves inactive evidence history.

## 10. Agents

### `src/bpmn_adapt/agents/analyst.py`

1. Loads current rules, resources, and states from the DB.
2. Invokes the Analyst system prompt through the injected LLM.
3. Retrieves process/version-compatible RAG evidence.
4. Applies deterministic rule/resource target checks.
5. Returns `APPROVE`, `REJECT`, or an LLM-supported alternative status with exact rule/resource/evidence IDs.

DB conflicts override an accepting historical example.

### `src/bpmn_adapt/agents/modeler.py`

1. Refuses non-approved decisions.
2. Sends the decision and any previous Experimenter failure payload to the Modeler LLM.
3. Resolves the target against actual BPMN nodes.
4. For remove, invokes the safe mutation function.
5. For re-add, restores the original oracle topology while using the latest adapted version as the parent.
6. Returns versioned XML, atomic changes, migration instructions, and checksum.

### `src/bpmn_adapt/agents/experimenter.py`

1. Invokes the Experimenter LLM with the candidate contract.
2. Checks every migration target exists in the candidate graph.
3. Runs bounded token-marking simulation.
4. Returns traces, structured failures, trace/failure counts, and token-preservation status.

### `src/bpmn_adapt/agents/orchestrator.py`

1. Creates the run and persists the request.
2. Invokes its own system prompt and records `orchestrator_started`.
3. Calls Analyst and stops cleanly on rejection.
4. Calls Modeler and Experimenter within a bounded retry loop.
5. Passes Experimenter failures into the next Modeler attempt.
6. Records errors as provenance instead of allowing unknown targets to crash the workflow.
7. On success, saves the process version before final approval.
8. Indexes the approved request only after the DB run status is `approved`.

## 11. Simulation

### `src/bpmn_adapt/simulation/engine.py`

Uses BPMN token markings instead of naive path recursion:

- exclusive/ordinary flows create alternative markings;
- parallel splits spawn one token per branch;
- parallel joins wait until all incoming tokens arrive;
- end events consume tokens and complete only when the marking is empty;
- visited markings, step limits, and state limits bound loops and branching;
- deadlocks and missing completion are returned as structured failures.

## 12. Application service

### `src/bpmn_adapt/application/service.py`

This is the single interface shared by GUI and CLI:

- `from_settings()` creates the configured DB, LLM, embedding, RAG, and agents;
- `ingest()` imports one folder and its source RAG evidence;
- `_request()` normalizes natural-language or structured operations;
- `_tokens()` maps a selected state position to a BPMN node;
- `analyse_folder()` runs analysis without mutation;
- `adapt_folder()` runs the complete agent workflow and writes results;
- `simulate_folder()` simulates the source model;
- `evaluate_folder()` runs the evaluation protocol;
- `report_folder()` returns a process/configuration inventory.

For re-add, the service selects the latest version as the current model and the source BPMN as the restoration oracle.

## 13. CLI and GUI

### `src/bpmn_adapt/cli.py`

Defines `ingest`, `index-rag`, `analyse`, `adapt`, `simulate`, `evaluate`, `report`, and `gui` commands. JSON output supports scripts and experiment pipelines.

### `src/bpmn_adapt/gui/controller.py`

Provides headless methods for every GUI operation. It calls the same application service as the CLI, enabling parity testing without opening a window.

### `src/bpmn_adapt/gui/app.py`

Implements the Tk desktop interface: folder browsing, request/target/state input, ingestion, RAG indexing, analysis, full adaptation, simulation, evaluation, reporting, and JSON result display.

## 14. Evaluation

### `src/bpmn_adapt/evaluation/runner.py`

- Loads folder-local test cases as ground truth.
- Extracts expected decision and target activity.
- Runs decision/constraint predictions for no-RAG, syntactic, semantic, hybrid, and hybrid-after-update conditions.
- Reports six separate ground-truth layers rather than one ambiguous score.
- Uses the source BPMN as the stated remove/re-add restoration oracle.
- Writes `evaluation.json` and `ablation_summary.csv` with configuration fingerprint and folder identity.

## 15. Automated tests

### `tests/test_config.py`

Tests mock defaults, live-key validation, secret-safe fingerprints, and JSON-safe contracts.

### `tests/test_ingestion_bpmn.py`

Tests heterogeneous folder ingestion, source immutability, missing inputs, safe task removal, token migration, and unsafe gateway rejection.

### `tests/test_persistence.py`

Tests authoritative fact storage, provenance, RAG approval gating, revocation, and optional PostgreSQL configuration behavior.

### `tests/test_llm_prompts.py`

Tests deterministic mock responses, embedding behavior, and the presence/version/boundaries of every agent prompt.

### `tests/test_rag.py`

Tests folder/version-compatible retrieval, complete logs, revocation exclusion, all ablation modes, and configured default mode.

### `tests/test_agents.py`

Tests DB-over-RAG authority, Modeler authorization, natural-language target resolution, migration, Experimenter traces, bounded cycles, and synchronized parallel gateways.

### `tests/test_orchestrator.py`

Tests successful approval/indexing, rejection without indexing, unknown-target provenance, and Experimenter-to-Modeler feedback on retry.

### `tests/test_application_interfaces.py`

Tests folder/request end-to-end execution, reproducible output files, GUI/CLI parity, and remove→re-add restoration through version lineage.

### `tests/test_evaluation.py`

Tests six-layer ground truth, five ablation modes, measured decision accuracy, simulation, and process reporting.

## 16. Generated research artefacts

- `experiments/runtime_bpmn.db`: default SQLite research DB.
- `experiments/runs/<run-id>/result.json`: complete typed run result.
- `experiments/runs/<run-id>/candidate.bpmn`: approved or tested candidate model.
- `experiments/runs/evaluation-<id>/evaluation.json`: multi-layer evaluation.
- `experiments/runs/evaluation-<id>/ablation_summary.csv`: RAG ablation summary.
- `experiments/validation.db` and `experiments/validation_runs/`: dataset-wide offline validation evidence.

