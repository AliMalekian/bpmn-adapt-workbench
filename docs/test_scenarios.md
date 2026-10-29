# Test scenarios

This catalogue is both a manual acceptance script and the rationale for automated fixtures. Every scenario records folder checksum, request, target/state, variant, expected layered outcome, seed, configuration fingerprint and evidence links.

## A. Configuration and persistence

1. Profile < environment < CLI precedence; secret redaction and secret-independent fingerprint.
2. Invalid mode, weights, timeout, provider or missing live key fails before a run.
3. `.env` parsing handles comments/quotes and does not override explicit environment.
4. Upgrade an old SQLite schema twice; preserve process/run data and migration ledger.
5. Two canonical folders with the same terminal name receive distinct IDs and DB namespaces.
6. PostgreSQL migrations and repository parity on a real server (pending external gate).

## B. Temporal planning

1. Immediate requested transition is selected.
2. Backward reversible transition enables a later adaptation.
3. Forward wait/resource-release makes a blocked request feasible.
4. Multiple alternatives produce a correct Pareto set.
5. Weight changes select expected time/budget/risk alternative with deterministic tie-break.
6. Absent target is INFEASIBLE; unreachable target, state limit, depth limit and timeout remain distinct.
7. Small planner result equals brute-force oracle.

## C. Mutation and migration

1. ADD node and reconnect flows; ADD standalone flow.
2. MODIFY name/attributes; change gateway type.
3. Add/modify condition and assign/remove gateway default flow.
4. REMOVE ordinary activity with reference repair; active token maps safely.
5. RE_ADD restores original element/flows and matches source oracle.
6. Compound transaction succeeds atomically; invalid later operation rolls all changes back.
7. Namespace/extension preservation and conservative BPMN-DI generation.
8. Active subprocess, boundary, event or gateway without safe map returns element-level blocking diagnostic.

## D. BPMN conformance and formal assurance

1. Valid BPMN 2.0 passes vendored XSD and semantic checks.
2. Malformed XML, XXE/DTD, schema mismatch, duplicate IDs and broken references fail.
3. Illegal endpoints, invalid/default gateway flow, boundary scope and unreachable nodes fail.
4. Unsupported executable construct returns UNSUPPORTED and blocks approval.
5. Known sound workflow converts to PNML and passes expected formal report.
6. Deadlock, livelock and dead-transition fixtures map to structured diagnostics.
7. Conversion error, checker timeout and malformed/oversized output are bounded failures.
8. Actual PM4Py/WOFLAN execution is the pending dependency gate.

## E. RAG governance and retrieval

1. Persist vectors, restart store and retrieve identical scoped result.
2. Cache identity changes with content/model revision; filtering excludes wrong process/operation/version.
3. Revocation survives restart and removes case from normal results without deleting lineage.
4. Interrupted rebuild leaves previous index readable until atomic swap.
5. `none`, syntactic, semantic and hybrid log filters/candidates/component scores/order/version.
6. Approved validated case indexes as positive; unapproved candidate is rejected; negative label remains separate.
7. Favorable RAG evidence cannot override a current DB blocker.
8. Real SentenceTransformer recall/MRR/nDCG/ANN recall and pgvector comparison are pending external gates.

## F. Multi-agent workflow

1. Feasible REMOVE: Analyst approves, Modeler changes, Experimenter passes, Orchestrator approves/indexes.
2. Rule/resource conflict: Analyst rejects before mutation and cites authoritative IDs.
3. Invalid LLM JSON/unknown fields/actions: Modeler rejects as untrusted input.
4. Candidate validation/simulation failure returns structured feedback and bounded retry.
5. Retry exhaustion rejects and preserves every attempt/provenance event.
6. RE_ADD uses original BPMN as structural oracle.
7. Approval/rejection command records actor/reason and controls RAG eligibility.

## G. Workflow engine

1. Dry-run health/deploy/create/inspect/validate/migrate/cleanup contract.
2. Recorded Camunda success, auth failure, validation failure and invalid mapping.
3. Timeout after deploy/migration reconciles remote state before retry; repeated idempotency key returns same receipt.
4. Cleanup refuses unrelated deployment/resource.
5. Real Camunda deploy/create/migrate/post-state/cleanup is pending a running service.

## H. Evaluation and statistics

1. Conversational, no-simulation, no-RAG, syntactic, semantic, hybrid and hybrid-updated share the same scenario manifest.
2. Labeled node/edge graph distance and remove/re-add restoration match hand oracle.
3. Token/variable preservation aggregates exact numerators/denominators.
4. Missing/contradictory ground truth is NOT_EVALUABLE and excluded.
5. Exact McNemar, assumption-gated paired t, Wilcoxon/permutation fallback, bootstrap CI, effect size and Holm match small known examples.
6. Raw JSON/CSV, publication table, SVG, statistics and checksums regenerate deterministically.

## I. Interfaces and reproducibility

1. Every CLI command parses, calls its matching service use case, emits JSON, and uses stable exit codes.
2. Export archive verifies checksums; tampering makes replay fail.
3. GUI has nine tabs, controller parity, raw JSON, background completion/error/cancel and clean shutdown.
4. Full-dataset interruption/resume loses no completed event; checksum drift creates a new key.
5. Duplicate names remain isolated; invalid folders are listed, not silently skipped.
6. Source folder timestamps/checksums remain unchanged after execution.

## J. Verified full-dataset scenario distribution

The 2026-09-22 offline manifest covered 82 `inspect`, 82 `evaluate`, 11 `remove-1`, 11 `remove-2`, 12 `remove-3`, 12 `remove-4`, and 19 `re-add` events: 229 total across 82 valid folders, zero invalid folders, zero runner failures. Structured business rejections remain inside successful runner payloads.

## K. Manual GUI defense demonstration

1. Open workbench using offline profile and `Pmo-3D printer`.
2. Ingest, inspect DB facts and select `STATE-02`.
3. Index examples and display filters, scores and citations.
4. Analyse/plan “remove Receive status”; explain selected temporal alternative and costs.
5. Adapt and display diff/migration, validation traces, approval/provenance.
6. Run evaluation and display table/statistics/raw JSON.
7. Export, verify archive and replay.
8. Repeat a rejected constraint case and show that RAG cannot override DB facts.

See [usage](usage_guide.md), [methodology](methodology.md), and [testing status](testing_status.md).
