# Runtime BPMN Adaptation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a folder-agnostic Python application that safely adapts BPMN process instances through explicit multi-agent orchestration, authoritative DB validation, hybrid RAG evidence, simulation, GUI, and CLI.

**Architecture:** The application separates immutable dataset ingestion, authoritative relational persistence, advisory hybrid RAG, provider-neutral LLM services, four independent agents, and shared application services. `OrchestratorAgent` coordinates the other agents and is the only final approval authority; GUI and CLI call the same application services for any selected valid process folder.

**Tech Stack:** Python 3.11+, `pydantic`, `SQLAlchemy`, SQLite/PostgreSQL drivers, `lxml`/`xml.etree`, `networkx`, `typer`, `textual` or `PySide6`, `pytest`, `hypothesis`, local sentence-transformer embeddings, optional OpenAI-compatible HTTP client.

**Spec:** `docs/superpowers/specs/2026-09-21-runtime-bpmn-adaptation-design.md`

## Global Constraints

- Preserve all source dataset files; place generated models, logs, indexes, and reports in run-scoped output directories.
- Operate on any valid folder without hard-coded process names, BPMN IDs, rules, or resources.
- DB facts are authoritative; RAG is advisory and cannot bypass current DB validation.
- Store requests/candidates in the DB first; index only final, approved, validated adaptations with complete lineage.
- Use SQLite by default and PostgreSQL through identical repository interfaces.
- Keep API keys out of source control and logs; configure through typed settings and `.env.example`.
- Keep each agent’s editable, versioned system prompt in `src/bpmn_adapt/prompts/`.
- Default automated tests and reproducible runs to deterministic mock LLM and embedding fixtures.

## Review Focus

1. A RAG item from a different folder or superseded BPMN version must never be retrieved as compatible evidence.
2. A model change that parses as XML but leaves an active token without a legal migration must fail final approval.
3. A live-provider timeout/rate-limit event must leave a complete redacted provenance record and must not create an approved adaptation.
4. Parallel gateway and loop paths must not be treated as a linear route by simulation or migration logic.
5. GUI and CLI executions of the same folder/request/configuration must produce the same typed result and provenance schema.

---

## Locked component structure

```text
src/bpmn_adapt/
├── domain/                 # Pydantic domain contracts
├── ingestion/              # folder discovery and source parsing
├── bpmn/                   # XML, graph, mutation, version-diff
├── persistence/            # DB models, repositories, migrations
├── retrieval/              # index, filters, hybrid ranking, lineage
├── llm/                    # LLMClient protocol, providers, mock client
├── prompts/                # versioned agent system prompts
├── agents/                 # OrchestratorAgent, AnalystAgent, ModelerAgent, ExperimenterAgent
├── simulation/             # state-space execution and trace validation
├── evaluation/             # ground truth, metrics, ablations, statistics
├── application/            # folder-scoped use cases shared by interfaces
├── cli.py                  # Typer commands
└── gui/                    # desktop screens/view models
```

## Phase 1 — Reproducible foundation, contracts, and configuration

### Task 1: Establish the package and reproducibility boundary

**Files:** Create `pyproject.toml`, `.gitignore`, `.env.example`, `src/bpmn_adapt/config.py`, `src/bpmn_adapt/domain/models.py`, `tests/unit/test_config.py`.

**Produces:** `Settings`, `RunConfigFingerprint`, and Pydantic contracts used by all later tasks.

- [ ] Write failing tests proving mock mode is the default, missing live API keys are rejected, and configuration fingerprints exclude secrets.
- [ ] Implement typed settings for provider, model, base URL, API key, timeout, retries, rate limit, embedding setup, DB URL, RAG mode, prompts, and output root.
- [ ] Define immutable models: `ProcessDefinition`, `ProcessVersion`, `RuntimeState`, `AdaptationRequest`, `RetrievedEvidence`, `FeasibilityDecision`, `AtomicChange`, `MigrationPlan`, `CandidateModel`, `ExperimentReport`, and `RunProvenance`.
- [ ] Run `pytest tests/unit/test_config.py -v` and `python -m compileall src`.

## Phase 2 — Folder-agnostic ingestion and BPMN core

### Task 2: Implement valid-folder ingestion

**Files:** Create `src/bpmn_adapt/ingestion/discovery.py`, `src/bpmn_adapt/ingestion/parsers.py`, `tests/unit/test_discovery.py`, `tests/fixtures/minimal_process/`.

**Consumes:** folder path. **Produces:** a `ProcessDefinition` with explicit source-file provenance or a typed validation error.

- [ ] Write tests for valid PMO/Camunda/Mangler-style filenames, missing required inputs, UTF-8 text, and no modification of source files.
- [ ] Implement discovery for BPMN, narrative, rules, resources, states, RAG examples, requests, and test cases without process-specific assumptions.
- [ ] Run ingestion over every immediate valid workspace folder and emit a read-only compatibility report.
- [ ] Run `pytest tests/unit/test_discovery.py -v`.

### Task 3: Implement BPMN graph, mutation, and token contracts

**Files:** Create `src/bpmn_adapt/bpmn/parser.py`, `graph.py`, `mutation.py`, `migration.py`, `tests/unit/test_bpmn_mutation.py`.

**Produces:** `BpmnGraph`, XML-preserving version diffs, and `MigrationPlan`.

- [ ] Write failing tests for remove/re-add reconnection, invalid target rejection, gateway preservation, and an active token with no legal target.
- [ ] Parse BPMN 2.0 XML into a directed typed graph while retaining original IDs and namespaces.
- [ ] Implement atomic remove/re-add edits only on copied model versions; record incoming/outgoing reconnections and exact diffs.
- [ ] Implement token mapping checks requiring a legal successor/predecessor relationship and preserving join requirements.
- [ ] Run `pytest tests/unit/test_bpmn_mutation.py -v`.

## Phase 3 — Authoritative database layer

### Task 4: Implement DB models and repository interfaces

**Files:** Create `src/bpmn_adapt/persistence/models.py`, `repositories.py`, `sqlite.py`, `postgres.py`, `tests/integration/test_repositories.py`.

**Produces:** `ProcessRepository`, `InstanceRepository`, `ConstraintRepository`, `RequestRepository`, `DecisionRepository`, `SimulationRepository`, `ProvenanceRepository`, `RetrievalLogRepository`.

- [ ] Write integration tests that execute the same repository contract on SQLite and PostgreSQL when `TEST_POSTGRES_URL` is supplied; skip PostgreSQL only when absent.
- [ ] Persist process/version lineage, instances/token states, rules/resources, requests, decisions, candidates, reports, retrieval logs, and provenance.
- [ ] Enforce foreign keys and transaction boundaries so a failed run cannot create an approved version or RAG entry.
- [ ] Run SQLite integration tests and, when configured, PostgreSQL conformance tests.

## Phase 4 — LLM/API and prompt governance

### Task 5: Implement provider-neutral LLM services and versioned prompts

**Files:** Create `src/bpmn_adapt/llm/client.py`, `mock.py`, `openai_compatible.py`, `rate_limit.py`, `src/bpmn_adapt/prompts/{orchestrator,analyst,modeler,experimenter}_v1.md`, `loader.py`, `tests/unit/test_llm_and_prompts.py`.

**Produces:** injected `LLMClient` and `EmbeddingClient` interfaces; independently versioned prompt resources.

- [ ] Write failing tests for mock determinism, structured response validation, timeout/retry behavior, prompt-version loading, and secret redaction.
- [ ] Implement `LLMClient.complete()` and `EmbeddingClient.embed()` protocols; implement deterministic mock and OpenAI-compatible adapters.
- [ ] Implement bounded exponential retry and token-bucket rate limiting keyed by configured provider/model without logging keys.
- [ ] Write each agent prompt with explicit role boundary, required JSON schema, citations, refusal conditions, and a prompt ID/version header.
- [ ] Run `pytest tests/unit/test_llm_and_prompts.py -v`.

## Phase 5 — Explicit hybrid RAG layer

### Task 6: Implement `HybridRAGService` and update governance

**Files:** Create `src/bpmn_adapt/retrieval/index.py`, `filters.py`, `ranking.py`, `service.py`, `governance.py`, `tests/integration/test_hybrid_rag.py`.

**Consumes:** process-local RAG records and DB lineage. **Produces:** ranked `RetrievedEvidence` plus complete retrieval log.

- [ ] Write failing tests for same-folder/source-version filtering, inactive-case exclusion, semantic paraphrase retrieval, syntactic-only mode, and ranking log completeness.
- [ ] Implement DB-backed RAG metadata, semantic embedding store, structured filters, deterministic tie-breaking, and semantic/syntactic/hybrid modes.
- [ ] Implement approval-gated indexing: require final analyst/modeler/experimenter/orchestrator evidence; mark revoked items inactive rather than deleting them.
- [ ] Persist query hash, filters, evidence IDs, models, scores, rank, index version, and configuration fingerprint.
- [ ] Run `pytest tests/integration/test_hybrid_rag.py -v`.

## Phase 6 — Four independent agents and full workflow

### Task 7: Implement `AnalystAgent`

**Files:** Create `src/bpmn_adapt/agents/analyst.py`, `tests/unit/test_analyst_agent.py`.

- [ ] Test DB-over-RAG authority, concrete rule/resource citations, current-state feasibility, backward/forward alternatives, and rejected requests.
- [ ] Implement retrieval of runtime facts and compatible evidence; normalise structured/natural-language requests through the injected LLM client.
- [ ] Apply deterministic target/rule/resource/token checks and return `APPROVE`, `REJECT`, or `ALTERNATIVE_PROPOSED` with evidence.
- [ ] Run `pytest tests/unit/test_analyst_agent.py -v`.

### Task 8: Implement `ModelerAgent` and `ExperimenterAgent`

**Files:** Create `src/bpmn_adapt/agents/modeler.py`, `experimenter.py`, `src/bpmn_adapt/simulation/engine.py`, `tests/integration/test_modeler_experimenter.py`.

- [ ] Test that Modeler cannot run without Analyst approval; test safe re-add restoration and failed migration rejection.
- [ ] Implement Modeler delegation to BPMN mutation/migration services and version-diff persistence.
- [ ] Implement Experimenter scenario loading, graph/state-space simulation, trace validation, deadlock detection, and structured failure reports.
- [ ] Run `pytest tests/integration/test_modeler_experimenter.py -v`.

### Task 9: Implement `OrchestratorAgent`

**Files:** Create `src/bpmn_adapt/agents/orchestrator.py`, `src/bpmn_adapt/application/adapt_process.py`, `tests/integration/test_orchestrator.py`.

- [ ] Test sequencing, retry exhaustion, final approval only after Experimenter pass, full provenance, and no RAG update on failure.
- [ ] Implement run creation, dependency injection, Analyst → Modeler → Experimenter sequencing, bounded correction loop, final approval, and approved-case RAG indexing.
- [ ] Ensure every selected folder receives isolated DB/index/output namespaces and identical typed results.
- [ ] Run `pytest tests/integration/test_orchestrator.py -v`.

## Phase 7 — GUI, CLI, evaluation, and publication outputs

### Task 10: Implement interfaces and experiment protocol

**Files:** Create `src/bpmn_adapt/cli.py`, `src/bpmn_adapt/gui/app.py`, `src/bpmn_adapt/evaluation/{ground_truth,metrics,runner,reports}.py`, `tests/e2e/test_cli_gui_parity.py`.

- [ ] Test a selected folder plus request through CLI and GUI application service yields the same result schema and provenance fields.
- [ ] Implement CLI commands: `ingest`, `index-rag`, `analyse`, `adapt`, `simulate`, `evaluate`, `report`, and `gui`.
- [ ] Implement GUI screens for folder/state selection, request entry, DB facts, evidence scores, proposed model diff, migration, simulation report, and export.
- [ ] Implement multi-layer ground truth: decision, constraints, structure, token mapping, executability, and RAG usefulness; use original BPMN as remove/re-add restoration oracle.
- [ ] Implement ablations: no RAG, syntactic-only, semantic-only, hybrid, and hybrid before/after approved updates; export CSV/JSON/HTML figures with seed/configuration/prompt/model metadata.
- [ ] Run end-to-end tests on representative PMO, Camunda, and Mangler folders and then the complete dataset suite.

## Final verification gate

- [ ] Run unit, integration, and end-to-end suites in mock/offline mode.
- [ ] Run dataset-wide folder discovery and one end-to-end workflow per valid folder.
- [ ] Confirm no source dataset file changed; verify every output has folder/run provenance.
- [ ] Produce `docs/methodology.md`, `docs/reproduction.md`, and an evaluation manifest that records code revision, seed, models, prompts, configuration fingerprint, and dataset inventory.
- [ ] Review the publication tables for correct denominator, confidence intervals where applicable, and explicit separation of simulator-based evidence from formal proof.
