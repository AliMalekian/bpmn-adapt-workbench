# Defense-Ready BPMN Adaptation Platform — Completion Design

**Date:** 2026-09-22  
**Status:** Proposed for user review  
**Supersedes:** The incomplete/optional portions of `2026-09-21-runtime-bpmn-adaptation-design.md`  
**Source of truth:** `Malekian_State_Of_The_Art.docx` plus the user's confirmed M0–M9 scope

## 1. Objective

Complete the existing BPMN adaptation research platform so every implementation claim in the State-of-the-Art proposal is backed by:

1. an explicit production component and stable interface;
2. deterministic validation independent of LLM assertions;
3. automated unit, integration, and end-to-end tests;
4. full-workspace dataset execution;
5. live PostgreSQL/pgvector, Camunda, and OpenAI-compatible LLM evidence where the claim concerns those systems;
6. immutable run manifests, logs, checksums, and reproducibility instructions.

An audit item may be marked **fully satisfied** only when its acceptance criterion has passed and the compliance document links to the relevant code, test, and evidence artefact. The implementation must never change an audit status merely to make the table appear complete.

## 2. Confirmed reference stack

- Python 3.11 and 3.12 compatibility.
- SQLite as the offline/default authoritative database.
- PostgreSQL plus pgvector as the live/integration authoritative and vector database.
- A durable local vector index for SQLite/offline use.
- SentenceTransformers neural dense embeddings.
- Camunda 8 Self-Managed as the reference execution engine.
- OMG BPMN 2.0.2 XSD validation plus project semantic validation.
- PM4Py BPMN-to-Petri conversion, PNML export, and WOFLAN soundness analysis.
- An optional external Petri-checker command adapter.
- NetworkX for graph metrics, SciPy/statsmodels for inference, and pandas for experiment tables.
- Tkinter/ttk desktop workbench with background execution.
- OpenAI-compatible live LLM adapter plus deterministic mock adapter.

Exact third-party versions and container digests will be pinned during M0 after compatibility tests. The evidence manifest records them rather than relying on mutable `latest` tags.

## 3. System boundaries

### 3.1 In scope

- Folder-based ingestion for every supported process folder in the workspace.
- Structured and natural-language adaptations.
- REMOVE, RE_ADD, ADD, MODIFY, flow edits, gateway edits, and compound changes.
- Runtime token and process-variable migration planning.
- Current, backward, and forward temporal feasibility planning.
- Time/budget/risk multi-objective optimization.
- BPMN schema, semantic, simulation, formal, and engine validation.
- Approval-gated persistent hybrid RAG.
- Deployment and migration of isolated Camunda test instances.
- Baselines, ablations, metrics, statistical tests, and publication artefacts.
- Equivalent GUI and CLI use cases.

### 3.2 Safety boundary

The reference engine integration targets an isolated research namespace. It must not deploy to or migrate instances in an unapproved production engine. Destructive engine calls require an explicit configured test tenant/namespace and a dry-run result before execution.

### 3.3 Meaning of “full BPMN 2.0 conformance”

The platform will provide complete XML conformance checking against the normative OMG BPMN 2.0.2 schemas and explicit semantic checks for the executable process subset handled by mutation, simulation, Petri conversion, and Camunda. It will preserve unknown extension elements. A valid BPMN choreography or conversation is schema-conformant but is not silently represented as an executable process. Unsupported executable semantics are reported as a typed validation failure and cannot be approved.

This definition avoids the scientifically invalid claim that one simulator executes every BPMN collaboration, choreography, vendor extension, and engine-specific behavior.

## 4. Target package structure

```text
src/bpmn_adapt/
  agents/
    orchestrator.py
    analyst.py
    modeler.py
    experimenter.py
  planning/
    state.py
    transitions.py
    constraints.py
    cost.py
    temporal.py
  bpmn/
    graph.py
    changes.py
    mutation.py
    diff.py
    xsd.py
    semantics.py
    namespaces.py
  formal/
    contracts.py
    pm4py_adapter.py
    pnml.py
    external_checker.py
  retrieval/
    contracts.py
    hybrid.py
    lexical.py
    dense.py
    local_vector_store.py
    pgvector_store.py
    governance.py
  persistence/
    contracts.py
    migrations/
    sqlite.py
    postgres.py
    repositories/
  engine/
    contracts.py
    camunda8.py
    dry_run.py
  evaluation/
    datasets.py
    baselines.py
    metrics.py
    statistics.py
    runner.py
    evidence.py
  gui/
    app.py
    controller.py
    workers.py
    panels/
  cli.py
  config.py
  prompts/
  application/
```

Each directory exposes contracts independently from concrete adapters. Agents may not reach into concrete DB, vector-store, or engine internals.

## 5. Core data contracts

### 5.1 Runtime planning state

`PlanningState` contains:

- process version and instance identity;
- BPMN/Petri marking;
- active and completed elements;
- process variables and data-object references;
- resource inventory and future availability events;
- logical time and deadline state;
- accumulated monetary/resource budget;
- accumulated risk vector;
- path history and reversible-transition metadata.

It has a canonical serialization and hash so search deduplicates equivalent states and evidence can cite exact state IDs.

### 5.2 Temporal plan

`TemporalPlan` contains:

- strategy: `CURRENT`, `BACKWARD`, or `FORWARD`;
- ordered transitions;
- start/final state IDs;
- satisfied and failed constraints;
- time, budget, and risk components;
- normalized weighted cost;
- Pareto-front membership;
- explanation and rejected alternatives;
- search limits and completeness status.

### 5.3 General mutation representation

`ChangeSet` is a transaction containing typed operations:

- `AddNode`, `RemoveNode`, `UpdateNode`;
- `AddFlow`, `RemoveFlow`, `UpdateFlow`;
- `AddGateway`, `RemoveGateway`, `ChangeGatewayType`;
- `UpdateCondition`, `SetDefaultFlow`;
- `AddEvent`, `UpdateEvent`, `RemoveEvent`;
- `UpdateExtensionElement` under an explicit allow-list;
- `RestoreFromVersion`.

Every operation has preconditions, affected IDs, inverse/rollback metadata, and source-request provenance.

### 5.4 Migration plan

`MigrationPlan` maps:

- source activity IDs to target activity IDs;
- every active token/element instance;
- scope and subprocess IDs;
- global and local variables;
- incidents/jobs/subscriptions where the engine exposes them;
- unmappable state with an explicit reason.

A plan is safe only if deterministic validators and the engine dry run agree.

### 5.5 Validation result

Every validator emits the same envelope:

- validator ID/version;
- pass/fail/error status;
- diagnostics with severity, element IDs, and citations;
- input and output checksums;
- runtime and tool version;
- reproducibility command.

## 6. Temporal planning and optimization

### 6.1 Search model

The planner uses a bounded A*/uniform-cost framework over `PlanningState`.

- Current analysis evaluates the requested transition in the present state.
- Forward analysis applies valid process transitions and explicit wait/resource-release actions.
- Backward analysis traverses recorded/reversible predecessors and proposes compensation or parameter changes without pretending completed irreversible work can be undone.
- Transitions are generated from BPMN/Petri structure, resources, rules, and runtime state—not invented solely by an LLM.

The LLM may translate user intent or explain a plan, but cannot declare a state reachable or constraint-satisfying without planner evidence.

### 6.2 Objective

For each feasible state, the planner records raw cost components. Selection uses:

```text
score = w_time * normalized_time
      + w_budget * normalized_budget
      + w_risk * normalized_risk
```

Weights, normalization bounds, maximum states, maximum depth, and timeout are versioned configuration. The planner retains the Pareto frontier and applies deterministic tie-breaking by risk, time, budget, transition count, then canonical plan ID.

### 6.3 Failure behavior

Search exhaustion, timeout, missing data, and proven infeasibility are distinct statuses. A timeout must never be described as proof that no plan exists.

## 7. BPMN transformation and validation pipeline

The Modeler pipeline is:

1. parse current BPMN while preserving namespaces/extensions;
2. translate approved intent into a typed `ChangeSet`;
3. validate operation preconditions;
4. apply changes transactionally to an in-memory copy;
5. update references and BPMN-DI;
6. generate migration instructions;
7. serialize canonically;
8. run XSD and semantic validation;
9. pass the candidate to formal, simulation, and engine validators.

The source document is never overwritten. A failed operation returns diagnostics and the unchanged source checksum.

### 7.1 XML conformance

The XSD validator uses vendored, checksum-verified OMG BPMN 2.0.2 schemas. Network access is not required during validation. XML external entity resolution is disabled.

### 7.2 Semantic conformance

Semantic rules include ID/reference integrity, flow-node legality, start/end constraints, gateway directions/defaults, event definitions, boundary attachments, scope consistency, reachability, well-formed split/join structures, and executable-process requirements.

### 7.3 Engine conformance

An approved test deployment is the final syntax/engine compatibility check. Engine rejection is a validation failure and feeds structured diagnostics to the Modeler.

## 8. Formal verification

The formal pipeline:

1. load validated BPMN through PM4Py;
2. convert it to an accepting Petri net;
3. export canonical PNML;
4. run workflow-net and WOFLAN soundness checks;
5. record dead transitions, improper completion, deadlocks/livelocks, and reachability diagnostics;
6. optionally invoke a configured external checker through a timeout-limited command adapter;
7. compare and retain all checker results.

Tool failure and unsupported conversion are not equivalent to a sound model. They block final approval unless the configured research protocol explicitly declares the relevant construct out of scope before the experiment begins.

## 9. Dense hybrid RAG

### 9.1 Embeddings

The default semantic encoder is a pinned SentenceTransformer suitable for English process text. Model name, revision, dimensions, pooling, normalization, device, package version, and model-file checksum are logged.

Documents and queries use the encoder's appropriate document/query methods when supported. Batch encoding is deterministic in evaluation mode.

### 9.2 Persistence

- PostgreSQL mode stores embeddings in pgvector with a cosine HNSW index and exact-search audit path.
- SQLite mode uses a durable local vector-index directory with a manifest and atomic rebuild/swap.
- Each vector row includes evidence ID, content checksum, embedding model version, active flag, process ID, source-version compatibility, operation, and lineage.

The service reuses a stored vector when both content checksum and encoder identity match. Restart tests must prove that embeddings are loaded rather than recomputed.

### 9.3 Hybrid retrieval

Lexical BM25/full-text and dense cosine candidates are fused with a configured, versioned strategy. Compatibility filters are applied before final selection. Logs contain candidate pools, raw scores, normalization, fusion, filters, final ranking, model/index versions, and evidence citations.

### 9.4 Authority and poisoning controls

- DB facts remain authoritative.
- RAG evidence is advisory.
- Only approved, fully validated runs may enter the successful-case index.
- Rejected cases may be retained as explicitly labeled negative evidence, never as approved precedent.
- Revocation is soft, versioned, attributed, and immediately excluded from retrieval.
- RAG and authoritative repositories use distinct interfaces and PostgreSQL schemas/roles.
- Live tests assert that malicious or favorable RAG text cannot override blocking current facts.

## 10. Workflow engine integration

`WorkflowEngineAdapter` defines health, deploy, create instance, inspect state, validate migration, migrate, inspect post-state, and cleanup operations.

The Camunda 8 adapter must:

- use configured authentication and TLS settings;
- operate only in an allowed tenant/research namespace;
- attach run IDs to deployments;
- retrieve active elements and variables;
- translate `MigrationPlan` mappings to Camunda instructions;
- execute dry-run validation before migration;
- verify definition version, active elements, variables, jobs, and incidents after migration;
- record sanitized requests/responses;
- support idempotency and bounded retries;
- never delete unrelated deployments or instances.

Integration fixtures will deploy models containing controllable wait/user-task points so an instance remains active during adaptation.

## 11. Agent responsibilities after completion

### 11.1 Orchestrator Agent

- owns stage sequencing and retry budgets;
- obtains one immutable run context;
- prevents Modeler execution without Analyst approval/alternative plan;
- requires all configured validators before final approval;
- coordinates engine deployment/migration only in authorized mode;
- writes ordered provenance and final status;
- indexes RAG only after approval;
- supports replay from a manifest.

### 11.2 Analyst Agent

- gathers runtime state, DB facts, rules, resources, temporal events, and RAG evidence;
- invokes deterministic constraint and temporal planners;
- uses the LLM for intent interpretation and explanation;
- returns feasibility status, selected plan, alternatives, costs, and citations;
- cannot modify BPMN.

### 11.3 Modeler Agent

- converts approved intent/plan to a typed `ChangeSet`;
- applies general mutations;
- produces BPMN and token/data/engine migration instructions;
- consumes structured Experimenter feedback on retry;
- cannot approve its own candidate.

### 11.4 Experimenter Agent

- derives tests from rules, runtime states, BPMN paths, and fault scenarios;
- runs schema, semantic, Petri, bounded simulation, and optional engine tests;
- reports structured failures and coverage;
- cannot silently waive a failed validator.

## 12. Baselines and evaluation protocol

Every scenario is executed under a common manifest against:

1. conversational single-LLM baseline;
2. multi-agent baseline without Experimenter/self-correction;
3. complete system without RAG;
4. syntactic-only RAG;
5. semantic-only RAG;
6. hybrid RAG;
7. hybrid RAG after approval-gated updates.

Common inputs, model parameters, retry policy, seeds, timeouts, and scoring code are shared. Baselines may disable named components only as defined; they may not receive extra information unavailable to competitors.

### 12.1 Ground-truth layers

- request/feasibility decision;
- constraint reasoning and cited facts;
- temporal-plan validity and optimality;
- structural adaptation;
- BPMN conformance;
- token/data migration;
- Petri soundness;
- simulation/engine executability;
- RAG relevance/usefulness.

### 12.2 Metrics

- decision accuracy, precision, recall, F1, and confusion matrix;
- constraint citation precision/recall and violation rate;
- node/edge-labeled graph-edit distance;
- exact/oracle restoration rate;
- schema, semantic, Petri, simulation, and engine pass rates;
- token and variable preservation rates;
- deadlock-recovery rate;
- temporal-plan success, regret, and cost components;
- retrieval recall@k, precision@k, MRR, nDCG, and approximate-index recall;
- latency, retries, LLM tokens, and estimated cost.

### 12.3 Statistics

The evaluation uses paired tests because every system variant receives the same scenario:

- McNemar's test for paired binary outcomes;
- paired permutation or Wilcoxon signed-rank tests for non-normal continuous differences;
- paired t-test only when documented assumptions hold;
- bootstrap confidence intervals;
- effect sizes appropriate to each test;
- Holm correction for multiple comparisons.

Raw observations remain available so every table can be regenerated.

## 13. GUI/CLI parity

### 13.1 GUI

The desktop application uses a `ttk.Notebook` with panels for:

- project/folder/process/instance selection;
- request editor and structured change builder;
- DB facts and versions;
- RAG evidence, filters, scores, lineage, approval, and revocation;
- temporal plans, alternatives, and costs;
- Analyst decision;
- mutation list, XML/graph diff, and migration map;
- schema/semantic/Petri validation;
- simulation and engine traces/failures;
- approvals and provenance;
- evaluation tables/plots;
- export and replay.

Long operations run in cancellable workers and marshal updates back to the Tk event loop. Every panel is backed by application-service DTOs, not direct DB access.

### 13.2 CLI

The CLI exposes equivalent use cases, including:

- `ingest`, `index-rag`, `revoke-rag`;
- `analyse`, `plan`, `adapt`, `validate`, `simulate`;
- `deploy`, `migrate`, `engine-status`;
- `approve`, `reject`, `inspect`;
- `evaluate`, `baseline`, `batch`, `report`;
- `export`, `replay`, `gui`.

Commands support JSON output, named configuration files, dry-run, run IDs, deterministic seeds, and nonzero exit codes for failure.

## 14. Configuration and secrets

Configuration precedence is:

1. CLI overrides;
2. environment variables;
3. selected versioned TOML/YAML profile;
4. documented defaults.

`.env` loading is supported for local development, with `.env.example` containing no secrets. Secret values are represented by secret references/redacted wrappers and are excluded from logs, exports, exception strings, and fingerprints.

Configuration includes LLM provider/model/base URL/key reference/timeout/retry/rate limits, embedding model/revision/device/batch size, DB/vector URLs, engine endpoint/auth/tenant, validator paths, planner weights/bounds, evaluation seeds/repetitions, and output paths.

## 15. Error handling and approval policy

- Boundary failures use typed exceptions and structured diagnostics.
- Transient LLM/engine/DB failures use bounded retry with jitter and rate limiting.
- Validation failure is not retried blindly; diagnostics must change the next candidate.
- Unknown runtime state, target ambiguity, unsupported construct, and incomplete ground truth require explicit user-visible status.
- Final automated approval requires Analyst feasibility plus schema, semantic, migration, formal, simulation, and configured engine passes.
- Human approval is a separate signed/attributed state required before live migration when enabled.
- A failed or interrupted run is never indexed as approved RAG evidence.

## 16. Reproducibility and evidence package

Each run directory contains, as applicable:

```text
manifest.json
config.redacted.json
request.json
source.bpmn
source.checksum
retrieval.json
analysis.json
temporal-plan.json
changes.json
candidate.bpmn
candidate.checksum
migration.json
validation/
  xsd.json
  semantic.json
  petri.json
  simulation.json
  engine.json
formal/model.pnml
engine/deployment.json
engine/migration.json
provenance.jsonl
metrics.json
environment.json
```

Evaluation directories additionally contain raw observations, baseline manifests, CSV tables, plots, statistical results, and a Markdown summary. A checksum manifest detects later modification.

GUI evidence consists of deterministic seeded screenshot scenarios with sensitive fields redacted.

## 17. Testing strategy

### 17.1 Unit tests

Every planner transition, cost calculation, mutation, validator rule, vector-store operation, metric, statistic, DTO, parser, and adapter mapping receives isolated tests.

### 17.2 Contract tests

The same repository suite runs against SQLite and PostgreSQL. The same vector-store suite runs against local persistence and pgvector. Engine and LLM adapters use recorded protocol fixtures plus live opt-in profiles.

### 17.3 Integration tests

Docker-backed tests exercise PostgreSQL/pgvector and Camunda. Dense-model tests use the pinned model and verify persistence/retrieval. PM4Py tests verify conversion and known sound/unsound nets.

### 17.4 End-to-end tests

Representative Camunda, PMO, and Mangler folders cover every operation and planning mode. A real active Camunda instance is deployed, adapted, migrated, and verified.

### 17.5 Full-dataset tests

The dataset runner discovers folders rather than using a fixed list, records exclusions as failures unless predeclared, and executes:

- ingestion and conformance;
- generated and supplied scenarios;
- mock/offline full pipeline;
- dense retrieval;
- PostgreSQL/pgvector profile;
- agreed live-LLM profile;
- baselines and ablations.

Live API cost and sample counts must be declared before execution. “Full dataset” means every discovered valid folder and every experiment scenario selected by the registered protocol, not merely one request per folder.

## 18. Milestones and quality gates

### M0 — Reproducible infrastructure

Dependencies, lock files, configuration profiles, Docker Compose, migrations, health probes, evidence layout, and CI profiles. Gate: clean environment starts and PostgreSQL/pgvector, Camunda, model-load, and configuration probes pass.

### M1 — Domain and persistence

Collision-safe identities, instances, temporal facts, general changes, validation/evidence schema, and repository contracts. Gate: SQLite/PostgreSQL parity and safe migration from current DB.

### M2 — Temporal planner

Backward/forward/current search and cost optimization. Gate: oracle small-state optimality and infeasible/timeout distinctions.

### M3 — General modeler

ADD/MODIFY/gateway/flow/event mutations and generalized migration. Gate: transactional mutation and compound-edit corpus.

### M4 — Conformance/formal verification

OMG XSD, semantic validator, Petri conversion, PNML, WOFLAN, and checker adapter. Gate: valid/invalid and sound/unsound reference corpora.

### M5 — Dense persistent RAG

SentenceTransformers, local persistence, pgvector, lexical retrieval, fusion, governance, and recall benchmarks. Gate: restart persistence, relevance, exact/ANN comparison, authority tests.

### M6 — Camunda integration

Deployment, state inspection, migration, verification, and safe cleanup. Gate: real active-instance migration with variables and negative mapping test.

### M7 — Evaluation/statistics

Baselines, ablations, complete metrics, repeated trials, and statistical analysis. Gate: regenerate every table from raw observations.

### M8 — GUI/CLI parity

Inspection workbench, workers, export/replay, administrative commands, and interface contract tests. Gate: widget tests, screenshot smoke tests, and manual Windows checklist.

### M9 — Defense verification

Full tests/dataset/live runs, evidence bundle, documentation, and final audit. Gate: every “fully satisfied” row links to passing evidence; otherwise it truthfully retains a non-full status.

## 19. Effort estimate and dependencies

Expected sequential effort is 73–114 engineering days, or approximately 15–23 full-time weeks for one engineer. External service startup, model downloads, live API rate limits/cost, and dataset defects can extend calendar time.

Implementation can begin with offline milestones while credentials are pending. M6 and M9 live gates require:

- a running Docker daemon;
- pulled/pinned PostgreSQL/pgvector and Camunda images;
- an OpenAI-compatible endpoint, model, API key, and approved budget;
- permission to store redacted live logs and screenshots.

## 20. Definition of defense-ready completion

The project is defense-ready only when:

1. M0–M9 gates pass on a clean reproducible environment;
2. all supported operations and planning modes have unit/integration/E2E evidence;
3. the complete discovered dataset protocol finishes with a published manifest;
4. PostgreSQL/pgvector, dense embeddings, Camunda migration, and live LLM evidence exist;
5. baseline/ablation statistics and raw results are included;
6. GUI screenshots and parity tests are included;
7. all documentation matches actual commands and results;
8. `docs/state_of_art_compliance.md` links each full claim to code, tests, and evidence;
9. any remaining failure is reported honestly and prevents a false “fully satisfied” claim.
