# State-of-the-Art compliance audit

Audit date: 2026-09-22. This audit uses three evidence states: **implemented and offline verified**, **implemented; live acceptance pending external resource**, and **not claimed/non-goal**. “Implemented” describes executable code and offline contracts; it never implies a live service was exercised.

## Component and workflow compliance

| Requirement | Status | Code, test, and evidence |
|---|---|---|
| Orchestrator Agent | **Implemented and offline verified** | `agents/orchestrator.py`; bounded sequence/retries, provenance, deterministic gates, final disposition, governed indexing; orchestrator/E2E tests; `experiments/evidence/m8/interfaces/task12-verification.json`. |
| Analyst Agent | **Implemented and offline verified** | `agents/analyst.py`; current DB facts, state, constraints and cited RAG evidence; temporal planning; Analyst integration tests; `experiments/evidence/m2/planning/task5-verification.json`. |
| Modeler Agent | **Implemented and offline verified** | `agents/modeler.py`; validates LLM JSON into typed operations and returns mutation/diff/migration; mutation tests; `experiments/evidence/m3/mutation/task6-verification.json`. |
| Experimenter Agent | **Implemented and offline verified** | `agents/experimenter.py`; scenarios, traces, validation/formal results, structured feedback; simulation/formal tests; `experiments/evidence/m4/formal/task8-verification.json`. |
| DB layer | **SQLite implemented and verified; PostgreSQL live pending** | Migrations and narrow core/RAG repositories; SQLite migration/parity tests pass. PostgreSQL adapter/Compose/live tests exist; service and driver unavailable. `experiments/evidence/m0/config/task2-verification.json`; architecture milestone M1 evidence is recorded under `experiments/evidence/m1/` by this audit mapping. |
| RAG layer | **Persistent/hybrid implementation offline verified; neural/pgvector live pending** | SentenceTransformer encoder, lexical scorer, fusion, atomic local store, pgvector store, governance and logs; fake-vector contracts pass. Actual model/pgvector gates skipped. `experiments/evidence/m5/rag/task9-verification.json`. |
| Provider-neutral LLM adapter | **Mock verified; live provider pending credential** | LLM protocol, deterministic mock and OpenAI-compatible HTTP adapter with timeout/retry/backoff/rate limiting/redaction. No live key was available. `experiments/evidence/m0/config/task1-verification.json`. |
| Per-agent versioned prompts | **Implemented and offline verified** | Four editable files in `prompts/`, loader/version provenance, prompt boundary tests; `experiments/evidence/m0/config/task1-verification.json`. |
| Folder/process agnosticism | **Implemented and full-dataset offline verified** | Content-addressed identity, isolated folder DB/output, generic discovery. 82 valid folders and 229 scenarios passed runner execution; `experiments/evidence/m9/full-dataset/task14-verification.json`. |
| GUI/CLI parity | **Implemented and offline verified** | Application service shared by 20 CLI commands and nine GUI tabs; controller parity/widget/export tests; screenshot and `experiments/evidence/m8/gui/task13-verification.json`. |

## Proposed Approach algorithms

| Claim | Status | Evidence |
|---|---|---|
| Backward/current/forward temporal state-space planning | **Implemented and offline verified** | Canonical states, reversible and future-release transitions, bounded A*/uniform-cost search, Pareto alternatives, distinct termination; oracle/brute-force tests; `experiments/evidence/m2/planning/task5-verification.json`. |
| Time/budget/risk optimization | **Implemented and offline verified** | Normalized weighted cost, reproducible tie breaks and configurable limits/weights in planning package; Task 5 evidence. |
| General ADD/MODIFY/REMOVE/RE_ADD/gateway/flow changes | **Implemented and offline verified at typed engine boundary** | Transactional ChangeSet supports node/flow addition, attribute/name changes, gateway type, conditions/defaults, removal/restoration, compounds and rollback; `experiments/evidence/m3/mutation/task6-verification.json`. Natural-language CLI intent parsing is intentionally minimal; structured/LLM ChangeSet is the precise interface. |
| Token/scope/variable migration | **Implemented and offline verified for supported executable constructs** | Generalized mappings and conservative blocking of unmappable active constructs; mutation and compound tests; Task 6 evidence. Unsupported scopes are rejected, never claimed migrated. |
| OMG BPMN 2.0.2 XSD validation | **Implemented and offline verified** | Vendored schemas/checksums/source notice, network/entity-disabled lxml loader, schema diagnostics; `experiments/evidence/m4/validation/task7-verification.json`. |
| BPMN semantic validation | **Implemented and offline verified** | Duplicate/reference/endpoint/gateway/default/boundary/reachability/executable-support rules with PASS/FAIL/UNSUPPORTED; Task 7 evidence. |
| Petri-net conversion, PNML, WOFLAN | **Implemented; adapter tests pass, PM4Py live dependency pending** | PM4Py adapter, deterministic PNML/checksum, WOFLAN report mapping, safe external subprocess; known-net/checker tests; `experiments/evidence/m4/formal/task8-verification.json`. Actual PM4Py/WOFLAN execution skipped because dependency absent. |
| Camunda deployment and instance migration | **Implemented; recorded/dry-run verified, live Camunda pending** | Camunda 8 REST transport/adapter, OAuth/TLS, idempotency, timeout reconciliation, validation, migration, post-check and scoped cleanup; `experiments/evidence/m6/engine/task10-verification.json`. |

## DB/RAG authority and governance

| Requirement | Status | Evidence |
|---|---|---|
| DB authoritative; RAG advisory | **Implemented and offline verified** | Separate repository protocols and Analyst deterministic blocker tests prove favorable evidence cannot override current rules/resources. |
| Hybrid semantic + syntactic retrieval | **Implemented** | BM25/lexical candidates, neural normalized dense encoder, weighted fusion, `none`/`syntactic`/`semantic`/`hybrid` modes. Neural model execution remains pending; hash is explicitly `hash_test`. |
| Persistent vector index | **Implemented and fake-vector verified** | Atomic local data/manifest swap, restart persistence, content/model cache keys, revocation, interrupted rebuild; pgvector cosine/HNSW schema. |
| Reproducible retrieval logging | **Implemented and offline verified** | Query hash, scope filters, every candidate’s component/final scores, selected order, model/fusion/index versions. |
| Compatible evidence by folder/family, operation and version | **Implemented and offline verified** | Vector/DB scopes filter process identity, operation, source version and active flag. |
| Approval-gated update and lineage | **Implemented and offline verified** | Core run/approval precedes positive indexing; evidence records run/process/version/operation/validation lineage. Negative evidence is separately labeled. |
| Revocation | **Implemented and offline verified** | DB and vector record become inactive with reason; no silent deletion. CLI and GUI expose the operation. |
| Data-poisoning boundary | **Implemented within research scope** | Untrusted LLM/RAG cannot bypass typed parsing, DB constraints, validation, simulation or approval. Authentication/signatures are declared future production hardening, not silently claimed. |

## Evaluation protocol

| Requirement | Status | Evidence |
|---|---|---|
| Conversational and no-simulation baselines | **Implemented and offline verified** | Same manifest contract as `none`, syntactic, semantic, hybrid, hybrid-updated; `experiments/evidence/m7/evaluation/task11-verification.json`. |
| Multi-layer ground truth | **Implemented and offline verified** | Decision, constraint, structure, restoration, migration, executability, retrieval, performance and cost fields; missing/contradictory truth becomes NOT_EVALUABLE with denominator 0. |
| Graph-edit/restoration metrics | **Implemented and offline verified** | Labeled node/edge distance and normalized restoration similarity. |
| Aggregate token/variable preservation | **Implemented and offline verified** | Per-observation and aggregate preservation fields with explicit denominators. |
| Retrieval metrics and ablations | **Implemented and offline verified with deterministic encoder** | Recall@k, MRR, nDCG, ANN recall and all required modes; actual neural comparison pending model. |
| Statistical significance | **Implemented and offline verified** | Exact McNemar, assumption-gated paired t, Wilcoxon/permutation fallback, bootstrap intervals, effect sizes and Holm correction. |
| Reproducible outputs | **Implemented and offline verified** | Raw JSON/CSV, publication CSV, SVG, statistics and checksum manifests. |
| Remove/re-add oracle | **Implemented and offline verified** | Original BPMN supplied for restoration and structural comparison. |
| Claim that RAG automatically improves | **Not claimed** | Improvement must be demonstrated by controlled before/after ablations; code intentionally does not assume it. |

## Reproducibility, interfaces, and safety

| Requirement | Status | Evidence |
|---|---|---|
| Configuration/profile/secret safety | **Implemented and offline verified** | Layered loader, `.env.example`, fingerprinting/redaction, validation and generated reference; `experiments/evidence/m0/config/task1-verification.json`. |
| Schema migration/repository bootstrapping | **Implemented and SQLite verified** | Idempotent ledger/data-preservation tests; `experiments/evidence/m0/config/task2-verification.json`. |
| Compose, health probes and CI | **Implemented; live readiness pending** | Pinned service definitions, probes, Python 3.11/3.12 workflow; `experiments/evidence/m0/config/task3-verification.json`. |
| CLI full use-case surface | **Implemented and offline verified** | Ingest/index/revoke/analyse/plan/adapt/validate/simulate/deploy/migrate/approve/reject/inspect/evaluate/baseline/batch/report/export/replay/gui; `experiments/evidence/m8/interfaces/task12-verification.json`. |
| GUI inspection/export parity | **Implemented and offline verified** | Nine panels, raw JSON, workers/cancel, export/replay; screenshot and Task 13 evidence. |
| Full dataset | **Implemented and offline verified** | Append-only/resumable runner; 82 folders, 229 PASS runner events, zero FAIL, resume skipped 229; `experiments/evidence/m9/full-dataset/task14-verification.json`. |
| Source immutability and namespace isolation | **Implemented and offline verified** | Content-addressed process/folder IDs, per-folder DB/output, no source writes. |
| Bounded execution and typed unsupported results | **Implemented and offline verified** | Bounded planning/retries/simulation/HTTP/subprocess; unsupported constructs block rather than crash/pass. |

## External acceptance gates still pending

The code paths are complete, but the following cannot honestly be labeled live-verified in this environment:

1. PostgreSQL repository migrations/contracts and pgvector similarity/HNSW against a real server.
2. SentenceTransformers model loading and neural full-dataset execution.
3. Camunda 8 deployment, active instance migration, post-state verification, and cleanup against a running cluster.
4. Live OpenAI-compatible responses with an actual API key/model.
5. PM4Py/WOFLAN execution with the unavailable dependency.

These are listed as **implemented; live acceptance pending external resource**, not “partially implemented.” Exact commands are in [reproduction](reproduction.md) and coverage is in [testing status](testing_status.md).

## Safety boundaries and non-goals

This is a research platform, not an authorization, identity, or production change-management system. It does not claim universal semantic support for every vendor extension, choreography/conversation construct, arbitrary in-flight engine scope, or unsafe automatic deployment. Unsupported semantics block approval. A human remains accountable for live approval, credentials, backup/rollback, access control, and organizational policy. The platform does not claim that RAG, LLM use, or adaptation improves outcomes until the specified experiment demonstrates it.

## Evidence paths by milestone

- M0: `experiments/evidence/m0/`
- M1: `experiments/evidence/m1/` (mapping to Task 4 architecture; executable evidence is stored at M0 Task 4)
- M2: `experiments/evidence/m2/`
- M3: `experiments/evidence/m3/`
- M4: `experiments/evidence/m4/`
- M5: `experiments/evidence/m5/`
- M6: `experiments/evidence/m6/`
- M7: `experiments/evidence/m7/`
- M8: `experiments/evidence/m8/`
- M9: `experiments/evidence/m9/`
