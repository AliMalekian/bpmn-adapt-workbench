# Defense-Ready BPMN Adaptation Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing offline REMOVE/RE_ADD prototype into the fully evidenced, defense-ready M0–M9 platform defined by the approved completion design.

**Architecture:** Preserve the six named agents and shared application boundary, while adding deterministic planning, mutation, validation, formal verification, vector retrieval, engine, evaluation, and interface services behind small protocols. Every external integration has an offline fake/fixture and an opt-in live contract suite; final compliance statuses are generated from evidence rather than asserted manually.

**Tech Stack:** Python 3.11/3.12, SQLite, PostgreSQL/psycopg, pgvector, SentenceTransformers, durable local vectors, Camunda 8 REST, lxml/OMG XSD, PM4Py/PNML/WOFLAN, NetworkX, SciPy, statsmodels, pandas, Tkinter/ttk, pytest, coverage, Docker Compose, OpenAI-compatible HTTP.

**Spec:** `docs/superpowers/specs/2026-09-22-defense-ready-completion-design.md`

## Global Constraints

- Offline/mock mode is the default and must run without Docker, credentials, or network after dependencies/model artefacts are cached.
- SQLite remains the default authoritative DB; PostgreSQL and pgvector are opt-in live profiles using the same repository contracts.
- DB facts are authoritative and RAG is advisory; no retrieved text may bypass deterministic constraints.
- Source dataset folders are immutable; all candidates and evidence are written under the configured output root.
- LLM output is untrusted structured input and must pass schema and deterministic validation.
- No audit item becomes “fully satisfied” without code, passing tests, and a linked evidence artefact.
- All retries, searches, external calls, and simulations are bounded and record their termination status.
- Secrets never enter fingerprints, logs, screenshots, manifests, or committed configuration.
- Python 3.11 and 3.12 are supported; platform-specific behavior must be isolated behind adapters.
- The workspace is not currently a Git repository. Do not initialize or commit without user authorization; record task checkpoints in test/evidence output instead.

## Review Focus

1. **Duplicate terminal folder names:** ingestion must produce different process IDs for different canonical folders and tests in Task 4 must prove isolation.
2. **Unsupported BPMN constructs:** validators must return typed `UNSUPPORTED` diagnostics and block approval rather than crash or silently pass; covered in Tasks 7 and 8.
3. **Interrupted vector rebuild:** the prior local index must remain readable until an atomic manifest/index swap completes; covered in Task 9.
4. **External timeout after a side effect:** engine deployment/migration must be idempotent and reconcile remote state before retry; covered in Task 10.
5. **Missing or contradictory ground truth:** evaluation must mark observations `NOT_EVALUABLE` and exclude them transparently from inferential tests; covered in Task 11.

---

## Planned file map

### Root and infrastructure

- `requirements.txt`: complete installable dependency declaration.
- `requirements-dev.txt`: test, coverage, and tooling dependencies.
- `constraints.txt`: exact versions used by the evidence environment.
- `compose.yaml`: PostgreSQL/pgvector and Camunda 8 research services.
- `docker/postgres/init.sql`: schemas, roles, and pgvector extension.
- `docker/camunda/`: pinned local configuration used by Compose.
- `config/default.toml`, `config/offline.toml`, `config/integration.toml`: versioned non-secret profiles.
- `.github/workflows/tests.yml`: Python 3.11/3.12 offline CI and service-backed integration job.
- `scripts/healthcheck.py`: structured dependency/service readiness probe.
- `scripts/run_full_dataset.py`: resumable, manifest-driven dataset runner.

### Core packages

- `src/bpmn_adapt/config.py`: layered profile/env/CLI configuration and redaction.
- `src/bpmn_adapt/domain/models.py`: stable cross-component DTOs.
- `src/bpmn_adapt/planning/`: temporal states, transitions, constraints, costs, and search.
- `src/bpmn_adapt/bpmn/changes.py`: typed transactional mutation IR.
- `src/bpmn_adapt/bpmn/mutation.py`: general mutation executor and rollback.
- `src/bpmn_adapt/bpmn/xsd.py`: secure OMG schema validation.
- `src/bpmn_adapt/bpmn/semantics.py`: executable BPMN semantic rules.
- `src/bpmn_adapt/formal/`: PM4Py, PNML, WOFLAN, and external-checker adapters.
- `src/bpmn_adapt/retrieval/`: lexical, dense, vector-store, fusion, and governance services.
- `src/bpmn_adapt/engine/`: workflow-engine protocol, dry-run adapter, and Camunda 8 adapter.
- `src/bpmn_adapt/evaluation/`: baselines, metrics, statistics, evidence, and experiment runner.
- `src/bpmn_adapt/gui/panels/`: dedicated workbench panels.
- `src/bpmn_adapt/gui/workers.py`: cancellable background tasks.
- `src/bpmn_adapt/cli.py`: full command parity.
- `src/bpmn_adapt/application/service.py`: use-case composition only.

### Tests and evidence

- `tests/unit/`: deterministic isolated tests.
- `tests/contract/`: repository/vector/LLM/engine adapter contracts.
- `tests/integration/`: PostgreSQL, pgvector, dense model, PM4Py, and Camunda profiles.
- `tests/e2e/`: folder-to-result workflows and GUI/CLI parity.
- `tests/fixtures/`: valid/invalid BPMN, Petri nets, engine protocol recordings, and labeled retrieval data.
- `experiments/evidence/`: generated manifests, logs, screenshots, results, and checksums; large/runtime artefacts remain uncommitted.

---

### Task 1: M0 dependency and layered configuration foundation

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `constraints.txt`
- Create: `config/default.toml`
- Create: `config/offline.toml`
- Create: `config/integration.toml`
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Modify: `src/bpmn_adapt/config.py`
- Create: `tests/unit/test_config_profiles.py`

**Interfaces:**
- Produces: `Settings.load(profile: Path | None = None, environ: Mapping[str, str] | None = None, overrides: Mapping[str, Any] | None = None) -> Settings`
- Produces: `Settings.redacted_dict() -> dict[str, Any]`
- Produces: `Settings.validate_capabilities() -> tuple[CapabilityStatus, ...]`
- Preserves: `Settings.from_env()` as a compatibility wrapper.

- [x] **Step 1: Write failing precedence, redaction, and validation tests**

```python
def test_settings_precedence_and_secret_redaction(tmp_path, monkeypatch):
    profile = tmp_path / "profile.toml"
    profile.write_text('[llm]\nmode="live"\nmodel="profile-model"\n', encoding="utf-8")
    monkeypatch.setenv("ADAPT_LLM_MODEL", "environment-model")
    monkeypatch.setenv("ADAPT_LLM_API_KEY", "top-secret")
    settings = Settings.load(profile, overrides={"llm_model": "cli-model"})
    assert settings.llm_model == "cli-model"
    assert "top-secret" not in json.dumps(settings.redacted_dict())
```

- [x] **Step 2: Run the focused tests and confirm failure because profile loading does not exist.**
- [x] **Step 3: Split nested config parsing, environment aliases, validation, and redaction into focused helpers while keeping the public immutable `Settings` object.**
- [x] **Step 4: Declare runtime extras for database/vector, semantic, formal, statistics, engine, and GUI testing in `pyproject.toml`; mirror the complete environment in `requirements.txt` and test tooling in `requirements-dev.txt`.**
- [x] **Step 5: Add secret-free TOML profiles and expand `.env.example` with DB, vector, embedding revision/device, engine auth/tenant, planner weights/bounds, evaluator seeds/repetitions, and evidence paths.**
- [x] **Step 6: Run the focused tests, `python -m pip check`, and `python -m compileall -q src tests`; store outputs under `experiments/evidence/m0/config/`.**

### Task 2: M0 schema migrations and repository bootstrapping

**Files:**
- Create: `src/bpmn_adapt/persistence/migrations/0001_existing_schema.sql`
- Create: `src/bpmn_adapt/persistence/migrations/0002_defense_schema.sql`
- Create: `src/bpmn_adapt/persistence/migrator.py`
- Modify: `src/bpmn_adapt/persistence/base.py`
- Modify: `src/bpmn_adapt/persistence/sqlite.py`
- Modify: `src/bpmn_adapt/persistence/postgres.py`
- Create: `tests/contract/test_repository_migrations.py`

**Interfaces:**
- Produces: `MigrationRunner.upgrade(connection, dialect: str) -> MigrationReport`
- Produces: `Repository.health() -> RepositoryHealth`
- Preserves all current repository methods until Task 4 replaces callers with narrower repositories.

- [x] **Step 1: Write a test that initializes the old schema, inserts one process/run, upgrades it twice, and proves data preservation plus idempotency.**
- [x] **Step 2: Run the test and confirm failure because no migration ledger exists.**
- [x] **Step 3: Implement a `schema_migrations` ledger and dialect-aware SQL loader with one transaction per migration.**
- [x] **Step 4: Add tables for instances, temporal facts, planner runs/states/plans, validation reports, engine deployments/migrations, embedding manifests, experiment observations, approvals, and evidence artefacts.**
- [x] **Step 5: Add PostgreSQL `core` and `rag` schemas; least-privilege service roles are provisioned by Task 3's PostgreSQL initialization script while SQLite preserves the same repository contract.**
- [x] **Step 6: Run migration tests against temporary SQLite; mark PostgreSQL contract test as live and make absence of its URL a skip, not a pass.**

### Task 3: M0 reproducible services, readiness probes, and CI

**Files:**
- Create: `compose.yaml`
- Create: `docker/postgres/init.sql`
- Create: `docker/camunda/application.yaml`
- Create: `scripts/healthcheck.py`
- Create: `.github/workflows/tests.yml`
- Create: `tests/unit/test_healthcheck.py`
- Create: `tests/integration/test_service_health.py`

**Interfaces:**
- Produces: `probe_all(settings: Settings) -> tuple[CapabilityStatus, ...]`
- CLI contract: `python scripts/healthcheck.py --profile config/integration.toml --json` exits 0 only when every required capability is ready.

- [x] **Step 1: Write fake-probe tests for ready, refused, unauthorized, timeout, incompatible-version, and missing-model states.**
- [x] **Step 2: Implement HTTP/TCP/DB/model probes with redacted diagnostics and bounded timeouts.**
- [x] **Step 3: Add pinned-image Compose definitions, persistent named volumes, health checks, non-default research credentials supplied through environment variables, and no host-wide destructive cleanup command.**
- [x] **Step 4: Add offline CI for Python 3.11/3.12 and opt-in service jobs for PostgreSQL/pgvector; Camunda/live LLM jobs require explicit secrets/labels.**
- [x] **Step 5: Run offline health tests. Run `docker compose config` even when the daemon is stopped; record daemon-dependent probes as `BLOCKED_EXTERNAL`, not successful.**

### Task 4: M1 domain contracts, collision-safe identity, and repository separation

**Files:**
- Modify: `src/bpmn_adapt/domain/models.py`
- Create: `src/bpmn_adapt/domain/planning.py`
- Create: `src/bpmn_adapt/domain/validation.py`
- Create: `src/bpmn_adapt/domain/engine.py`
- Create: `src/bpmn_adapt/persistence/contracts.py`
- Create: `src/bpmn_adapt/persistence/repositories/core.py`
- Create: `src/bpmn_adapt/persistence/repositories/rag.py`
- Modify: `src/bpmn_adapt/ingestion/discovery.py`
- Create: `tests/unit/test_domain_contracts.py`
- Create: `tests/contract/test_repository_parity.py`

**Interfaces:**
- Produces: `ProcessIdentity.from_folder(path: Path, source_checksums: Sequence[str]) -> ProcessIdentity`
- Produces narrow `CoreRepository` and `RagRepository` protocols.
- Produces DTOs specified in design sections 5 and 15.

- [x] **Step 1: Write serialization/validation tests for planning, change, validation, approval, engine, and evidence DTOs.**
- [x] **Step 2: Write a collision test using two canonical paths with the same final folder name and assert distinct process IDs.**
- [x] **Step 3: Implement immutable DTOs and collision-safe IDs while retaining legacy-ID aliases for existing rows.**
- [x] **Step 4: Split authoritative and advisory repositories so Analyst composition can read both but RAG code cannot update core facts.**
- [x] **Step 5: Run the repository contract suite against SQLite; retain the PostgreSQL execution as an explicit live gate until configured.**

### Task 5: M2 temporal state-space planner and cost optimizer

**Files:**
- Create: `src/bpmn_adapt/planning/state.py`
- Create: `src/bpmn_adapt/planning/transitions.py`
- Create: `src/bpmn_adapt/planning/constraints.py`
- Create: `src/bpmn_adapt/planning/cost.py`
- Create: `src/bpmn_adapt/planning/temporal.py`
- Modify: `src/bpmn_adapt/agents/analyst.py`
- Create: `tests/unit/test_temporal_planner.py`
- Create: `tests/integration/test_analyst_planning.py`

**Interfaces:**
- Produces: `TemporalPlanner.plan(request, initial_state, model, facts, limits) -> PlanningResult`
- Produces: `CostModel.evaluate(path, normalization, weights) -> CostBreakdown`
- Analyst decisions gain selected plan, Pareto alternatives, and search diagnostics.

- [x] **Step 1: Write oracle graph tests for immediate, backward, forward-wait, Pareto, weighted-selection, infeasible, exhausted, and timeout outcomes.**
- [x] **Step 2: Run tests and confirm failures because planning package is absent.**
- [x] **Step 3: Implement canonical state hashing, constraint evaluation, reversible transition rules, and future resource-release transitions.**
- [x] **Step 4: Implement bounded A*/uniform-cost search, Pareto retention, normalization, deterministic tie-breaking, and distinct termination statuses.**
- [x] **Step 5: Integrate the planner into Analyst so an LLM explains deterministic plans but cannot fabricate reachability/cost.**
- [x] **Step 6: Compare small searches with brute-force enumeration and store planner traces in integration evidence.**

### Task 6: M3 typed general BPMN mutation engine

**Files:**
- Create: `src/bpmn_adapt/bpmn/changes.py`
- Rewrite: `src/bpmn_adapt/bpmn/mutation.py`
- Create: `src/bpmn_adapt/bpmn/diff.py`
- Modify: `src/bpmn_adapt/bpmn/graph.py`
- Modify: `src/bpmn_adapt/agents/modeler.py`
- Create: `tests/unit/test_change_set.py`
- Create: `tests/unit/test_general_mutation.py`
- Create: `tests/integration/test_compound_adaptation.py`

**Interfaces:**
- Produces: `MutationEngine.apply(xml: str, changes: ChangeSet, runtime: RuntimeState) -> MutationResult`
- Produces: `BpmnDiffer.compare(source_xml: str, target_xml: str) -> StructuralDiff`
- `MutationResult` contains XML, inverse operations, diff, migration, diagnostics, and checksums.

- [x] **Step 1: Write failing tests for node/flow ADD, node MODIFY, gateway-type change, conditions/default flow, REMOVE, RE_ADD, compound transactions, namespace preservation, and rollback.**
- [x] **Step 2: Implement typed operation validation and stable ID allocation.**
- [x] **Step 3: Implement transactional XML graph mutation on a copy, reference repair, conservative BPMN-DI generation, and inverse metadata.**
- [x] **Step 4: Generalize token/scope/variable migration and reject unmappable active constructs with element-level diagnostics.**
- [x] **Step 5: Make Modeler parse LLM JSON into `ChangeSet`; reject unknown actions/fields before mutation.**
- [x] **Step 6: Run legacy plus new mutation/E2E tests and compare remove→re-add with the source oracle.**

### Task 7: M4 secure OMG XSD and semantic BPMN validation

**Files:**
- Create: `src/bpmn_adapt/bpmn/schemas/` with checksum manifest and OMG source notice
- Create: `src/bpmn_adapt/bpmn/xsd.py`
- Create: `src/bpmn_adapt/bpmn/semantics.py`
- Create: `src/bpmn_adapt/bpmn/validation.py`
- Create: `tests/fixtures/bpmn/valid/`
- Create: `tests/fixtures/bpmn/invalid/`
- Create: `tests/unit/test_bpmn_xsd.py`
- Create: `tests/unit/test_bpmn_semantics.py`

**Interfaces:**
- Produces: `BpmnValidator.validate(xml: str, executable_required: bool = True) -> ValidationReport`

- [x] **Step 1: Add tests for valid BPMN and invalid schema, XXE, duplicate IDs, broken references, illegal flow endpoints, gateway/default errors, boundary scope errors, unreachable nodes, and unsupported executable constructs.**
- [x] **Step 2: Vendor normative schema files with recorded URLs/checksums and load them without network access.**
- [x] **Step 3: Implement lxml schema validation with external entity/network resolution disabled.**
- [x] **Step 4: Implement semantic rules as separately versioned validators emitting PASS/FAIL/UNSUPPORTED diagnostics.**
- [x] **Step 5: Require validation before Modeler candidates reach Experimenter.**

### Task 8: M4 Petri conversion, PNML, WOFLAN, and checker adapter

**Files:**
- Create: `src/bpmn_adapt/formal/contracts.py`
- Create: `src/bpmn_adapt/formal/pm4py_adapter.py`
- Create: `src/bpmn_adapt/formal/pnml.py`
- Create: `src/bpmn_adapt/formal/external_checker.py`
- Create: `tests/fixtures/petri/`
- Create: `tests/unit/test_external_checker.py`
- Create: `tests/integration/test_formal_verification.py`

**Interfaces:**
- Produces: `FormalVerifier.verify(xml: str, output_dir: Path) -> FormalReport`
- Produces: `ExternalChecker.run(pnml: Path, timeout: float) -> CheckerReport`

- [x] **Step 1: Write known sound, deadlocking, livelocking, dead-transition, conversion-failure, checker-timeout, and malformed-output tests.**
- [x] **Step 2: Implement PM4Py BPMN conversion, workflow-net checks, WOFLAN invocation, and structured diagnostic mapping.**
- [x] **Step 3: Export deterministic PNML and checksum it.**
- [x] **Step 4: Implement argument-array subprocess invocation with no shell interpolation, timeout, output size bound, and version capture.**
- [x] **Step 5: Integrate formal results into Experimenter and block approval on failure/error/unsupported status.**

### Task 9: M5 neural embeddings and persistent hybrid vector retrieval

**Files:**
- Create: `src/bpmn_adapt/retrieval/contracts.py`
- Create: `src/bpmn_adapt/retrieval/dense.py`
- Create: `src/bpmn_adapt/retrieval/lexical.py`
- Create: `src/bpmn_adapt/retrieval/local_vector_store.py`
- Create: `src/bpmn_adapt/retrieval/pgvector_store.py`
- Create: `src/bpmn_adapt/retrieval/hybrid.py`
- Create: `src/bpmn_adapt/retrieval/governance.py`
- Replace compatibility implementation in `src/bpmn_adapt/retrieval/service.py`
- Create: `tests/contract/test_vector_store.py`
- Create: `tests/integration/test_dense_rag.py`

**Interfaces:**
- Produces: `EmbeddingEncoder.encode_documents(texts) -> ndarray`
- Produces: `EmbeddingEncoder.encode_queries(texts) -> ndarray`
- Produces: `VectorStore.upsert/search/revoke/rebuild/health`
- Produces: `HybridRetriever.retrieve(query, scope, mode, limit) -> RetrievalResult`

- [x] **Step 1: Write contract tests for persistence across restart, content/model cache keys, filters, revocation, exact/ANN comparison, interrupted rebuild, and score logs.**
- [x] **Step 2: Implement pinned SentenceTransformer loading with revision/device/batch metadata and deterministic evaluation settings.**
- [x] **Step 3: Implement atomic local index+manifest persistence and pgvector cosine/HNSW storage.**
- [x] **Step 4: Implement BM25/full-text retrieval and versioned fusion with complete candidate/ranking logs.**
- [x] **Step 5: Enforce approved-only success indexing and separate negative evidence labels.**
- [x] **Step 6: Run labeled retrieval tests and record recall@k, MRR, nDCG, and ANN recall; hash embeddings remain test-only.**

### Task 10: M6 workflow-engine and Camunda 8 integration

**Files:**
- Create: `src/bpmn_adapt/engine/contracts.py`
- Create: `src/bpmn_adapt/engine/dry_run.py`
- Create: `src/bpmn_adapt/engine/camunda8.py`
- Create: `src/bpmn_adapt/engine/http.py`
- Create: `tests/contract/test_engine_adapter.py`
- Create: `tests/integration/test_camunda8.py`
- Create: `tests/fixtures/engine/`

**Interfaces:**
- Produces: `WorkflowEngineAdapter.health/deploy/create_instance/inspect/validate_migration/migrate/cleanup`
- Camunda calls accept `idempotency_key` and return sanitized typed receipts.

- [x] **Step 1: Write recorded-protocol contract tests for success, auth failure, validation failure, timeout-after-deploy, duplicate retry, invalid mapping, and unrelated-resource cleanup protection.**
- [x] **Step 2: Implement dry-run adapter used by offline E2E tests.**
- [x] **Step 3: Implement authenticated Camunda REST transport with TLS verification, rate limiting, idempotency, bounded retry, and redaction.**
- [x] **Step 4: Implement deployment, definition lookup, instance creation/state inspection, migration validation/execution, post-state verification, and scoped cleanup.**
- [x] **Step 5: Add opt-in Docker E2E test that preserves deployment/migration receipts and engine screenshots/log references.**

### Task 11: M7 baselines, complete metrics, and statistics

**Files:**
- Create: `src/bpmn_adapt/evaluation/baselines.py`
- Create: `src/bpmn_adapt/evaluation/metrics.py`
- Create: `src/bpmn_adapt/evaluation/statistics.py`
- Create: `src/bpmn_adapt/evaluation/evidence.py`
- Rewrite: `src/bpmn_adapt/evaluation/runner.py`
- Create: `tests/unit/test_metrics.py`
- Create: `tests/unit/test_statistics.py`
- Create: `tests/integration/test_baselines.py`

**Interfaces:**
- Produces: `BaselineRunner.run(variant, scenario, context) -> Observation`
- Produces: `MetricSuite.evaluate(observation, ground_truth) -> MetricRecord`
- Produces: `StatisticalAnalyzer.compare(records, family_alpha) -> StatisticalReport`

- [x] **Step 1: Write tests for conversational, no-simulation, no-RAG, syntactic, semantic, hybrid, and hybrid-updated variants using identical manifests.**
- [x] **Step 2: Implement labeled node/edge graph-edit distance, restoration, schema/semantic/formal/engine pass, token/variable preservation, deadlock recovery, constraints, retrieval, latency, tokens, and cost metrics.**
- [x] **Step 3: Add explicit `NOT_EVALUABLE` handling for missing/contradictory ground truth and report denominators.**
- [x] **Step 4: Implement McNemar, Wilcoxon/permutation, assumption-gated paired t-test, bootstrap intervals, effect sizes, and Holm correction.**
- [x] **Step 5: Produce raw long-form CSV/JSON, publication tables, plots, and a regeneratable statistical manifest.**

### Task 12: M8 application service and CLI parity

**Files:**
- Refactor: `src/bpmn_adapt/application/service.py`
- Rewrite: `src/bpmn_adapt/cli.py`
- Create: `src/bpmn_adapt/application/dtos.py`
- Create: `tests/e2e/test_cli_commands.py`
- Create: `tests/e2e/test_replay_export.py`

**Interfaces:**
- Application use cases correspond one-to-one with CLI commands: ingest, index/revoke RAG, analyse, plan, adapt, validate, simulate, deploy, migrate, approve/reject, inspect, evaluate, baseline, batch, report, export, replay, and GUI.

- [x] **Step 1: Write parser/service tests for every command, JSON output, profile selection, dry-run, run ID, seed, and nonzero failure exit.**
- [x] **Step 2: Split the application facade into composable use cases while preserving old public methods as deprecated wrappers.**
- [x] **Step 3: Implement every command with typed JSON schemas and stable exit codes.**
- [x] **Step 4: Implement manifest replay and export bundles with checksum verification.**
- [x] **Step 5: Run CLI E2E workflows on representative Camunda, PMO, and Mangler folders.**

### Task 13: M8 tabbed GUI inspection workbench

**Files:**
- Rewrite: `src/bpmn_adapt/gui/app.py`
- Modify: `src/bpmn_adapt/gui/controller.py`
- Create: `src/bpmn_adapt/gui/workers.py`
- Create: `src/bpmn_adapt/gui/panels/project.py`
- Create: `src/bpmn_adapt/gui/panels/facts.py`
- Create: `src/bpmn_adapt/gui/panels/rag.py`
- Create: `src/bpmn_adapt/gui/panels/planning.py`
- Create: `src/bpmn_adapt/gui/panels/model.py`
- Create: `src/bpmn_adapt/gui/panels/validation.py`
- Create: `src/bpmn_adapt/gui/panels/evaluation.py`
- Create: `src/bpmn_adapt/gui/panels/provenance.py`
- Create: `src/bpmn_adapt/gui/panels/export.py`
- Create: `tests/unit/test_gui_controller.py`
- Create: `tests/e2e/test_gui_workbench.py`

**Interfaces:**
- Every panel consumes immutable application DTOs through `GuiController`; no panel queries persistence directly.
- `TaskWorker.submit/cancel` communicates through a thread-safe queue and invokes Tk updates only on the main thread.

- [x] **Step 1: Write headless controller parity tests and widget tests for each tab, selection, long-task progress/cancellation, error rendering, and exports.**
- [x] **Step 2: Implement the notebook shell and focused panels listed by the design.**
- [x] **Step 3: Implement background workers, progress events, cancellation, and deterministic shutdown.**
- [x] **Step 4: Implement BPMN structural diff, migration, trace, score, and statistical table renderers without hiding raw JSON.**
- [x] **Step 5: Add deterministic screenshot scenarios and a manual Windows acceptance checklist.**

### Task 14: M9 resumable full-dataset and live evidence runner

**Files:**
- Create: `scripts/run_full_dataset.py`
- Create: `src/bpmn_adapt/evaluation/datasets.py`
- Create: `src/bpmn_adapt/evaluation/manifest.py`
- Create: `tests/unit/test_dataset_manifest.py`
- Create: `tests/e2e/test_full_dataset_smoke.py`

**Interfaces:**
- CLI: `python scripts/run_full_dataset.py --profile <file> --resume <manifest> --variants <list> --json`
- Produces an append-only experiment manifest and per-scenario status/evidence links.

- [x] **Step 1: Write discovery tests for valid folders, duplicate names, invalid folders, resumed runs, checksum drift, and scenario enumeration.**
- [x] **Step 2: Implement content-addressed discovery and immutable experiment manifests.**
- [x] **Step 3: Implement resumable bounded parallel execution with per-scenario isolation and no loss of completed results after interruption.**
- [x] **Step 4: Run offline smoke fixtures, then the complete discovered dataset in mock+dense+SQLite mode.** *(The complete 82-folder run used the explicit hash-test encoder because SentenceTransformers is unavailable; the neural-dense execution is recorded as an external dependency gate.)*
- [x] **Step 5: When resources exist, run PostgreSQL/pgvector, Camunda, and declared live-LLM protocols; otherwise emit `BLOCKED_EXTERNAL` evidence with the failed capability probe.**

### Task 15: M9 evidence-driven documentation and compliance closure

**Files:**
- Modify: `docs/usage_guide.md`
- Modify: `docs/state_of_art_compliance.md`
- Modify: `docs/testing_status.md`
- Modify: `docs/test_scenarios.md`
- Modify: `docs/methodology.md`
- Modify: `docs/reproduction.md`
- Modify: `README.md`
- Create: `docs/defense_evidence_index.md`
- Create: `tests/test_documentation.py`

**Interfaces:**
- `docs/defense_evidence_index.md` maps every claim to source files, test node IDs, and evidence manifests.

- [x] **Step 1: Write documentation tests for command/help parity, configuration-variable coverage, valid local links, and compliance evidence links.**
- [x] **Step 2: Generate command/config reference sections from parser/settings metadata to prevent drift.**
- [x] **Step 3: Update methodology, scenarios, reproduction, usage, testing status, and README using actual verified results.**
- [x] **Step 4: Update each compliance row from evidence; leave live rows pending when capability probes are blocked.**
- [x] **Step 5: Run all unit, contract, integration, E2E, documentation, full-dataset, and available live profiles.**
- [x] **Step 6: Create the final checksum manifest, evidence index, GUI screenshots, run logs, statistical outputs, and defense report.**

---

## Execution order and milestone gates

| Milestone | Tasks | Gate |
|---|---|---|
| M0 | 1–3 | Dependencies/config/migrations/Compose/CI and offline probes pass; unavailable live services are `BLOCKED_EXTERNAL`. |
| M1 | 4 | DTO and repository contracts pass on SQLite; PostgreSQL runs when available. |
| M2 | 5 | Planner oracle, bounded-search, and Analyst integration tests pass. |
| M3 | 6 | All mutation types, transactions, and migration tests pass. |
| M4 | 7–8 | XSD, semantic, Petri, PNML, and formal-report suites pass. |
| M5 | 9 | Neural persistent retrieval, governance, and IR metrics pass; pgvector runs when available. |
| M6 | 10 | Dry-run engine contract passes; real Camunda gate remains pending until service exists. |
| M7 | 11 | All baselines/ablations/metrics/statistics regenerate from raw observations. |
| M8 | 12–13 | CLI/GUI parity, widget, export, replay, and screenshot tests pass. |
| M9 | 14–15 | Full offline dataset and documentation evidence pass; live rows reflect actual resource availability. |

## Final verification commands

```powershell
python -m pip check
python -m compileall -q src tests scripts
python -m pytest tests/unit -q
python -m pytest tests/contract -q
python -m pytest tests/integration -q -m "not live"
python -m pytest tests/e2e -q -m "not live"
python -m pytest -q
python scripts/run_full_dataset.py --profile config/offline.toml --variants all --json
python scripts/healthcheck.py --profile config/integration.toml --json
```

When external resources become available:

```powershell
docker compose up -d --wait
python -m pytest tests/integration -q -m "postgres or pgvector or camunda"
python -m pytest tests/e2e -q -m "camunda"
python scripts/run_full_dataset.py --profile config/integration.toml --variants all --json
python -m pytest tests/integration -q -m "live_llm"
```

The final report quotes command exit codes and result counts. A skipped or blocked live test is never described as passing.
