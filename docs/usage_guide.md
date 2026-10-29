# Complete usage guide

This guide is designed for a first-time user. All commands assume the repository root is the current directory.

## 1. Install and configure

Use 64-bit Python 3.11 or 3.12. Tkinter is included in standard Windows Python; Linux distributions may require their `python3-tk` package.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt -c constraints.txt
python -m pip install -e .
```

If you do not install the project, set `$env:PYTHONPATH='src'` before module commands. Copy `.env.example` to `.env`. The loader applies this precedence: CLI overrides, environment variables, `.env`, selected TOML profile, built-in defaults. Secrets are redacted from fingerprints and diagnostics; never commit `.env`.

Profiles:

- `config/offline.toml`: mock LLM, SQLite, explicit `hash_test` compatibility encoder, local execution, dry-run engine. No credentials or downloaded model required.
- `config/default.toml`: mock LLM, SQLite, real SentenceTransformers encoder, persistent local vectors. The model must be installed/cached.
- `config/integration.toml`: live OpenAI-compatible LLM, PostgreSQL/pgvector, SentenceTransformers, Camunda 8.

Important variables include LLM provider/model/base URL/key/timeout/retry/backoff/rate limit; embedding provider/model/revision/device/batch; vector backend/path; DB URL; RAG mode/weights; output root; planning weights/bounds; engine OAuth and retry fields; formal checker mode/command/timeout; and evaluation seed/repetitions. The exhaustive generated table is in [the generated reference](generated_reference.md).

Check readiness before a run:

```powershell
python scripts/healthcheck.py --profile config/offline.toml --json
python scripts/healthcheck.py --profile config/integration.toml --json
```

A nonzero integration result is expected until every requested service/dependency is available. `MISSING_DEPENDENCY`, `REFUSED`, `UNAUTHORIZED`, and `BLOCKED_EXTERNAL` are not successful verification.

## 2. What makes a valid process folder

Point the platform at the folder itself. Discovery looks for BPMN XML plus the folder-associated narrative, rules, resources, runtime state, RAG examples, and test cases used by this dataset. Ingestion computes a collision-safe identity from the canonical folder and content, parses available files, and writes only to the configured DB/output directory. It never edits the source folder.

Folder names and process content are not hardcoded. A second folder with the same terminal name receives a different identity. Invalid or unsupported content returns structured diagnostics.

## 3. GUI walkthrough

Launch the workbench:

```powershell
python -m bpmn_adapt.cli --config config/offline.toml gui
```

The command is also named `gui` in the CLI reference. At the top, choose the profile, browse to a process folder, enter the request, optional target, operation, state/instance, run ID, and relevant JSON parameters. Select an action and run it. Long work runs in a background worker; progress/error/cancellation events return through the UI queue, while Tk widgets remain on the main thread.

Use the tabs in this order:

1. **Project** — select the folder/dataset; run ingestion; choose a stored state or workflow instance; submit structured `ADD`, `MODIFY`, `REMOVE`, or `RE_ADD`, or natural language such as “remove Receive status”.
2. **DB Facts** — inspect the authoritative process/version record, rules, resources, runtime states, and current instance facts. These facts override conflicting RAG evidence.
3. **RAG Evidence** — inspect evidence IDs, active/revoked status, process/operation/version filters, semantic, syntactic, and fused scores, ranking, citations, model/index version, and lineage.
4. **Planning** — inspect Analyst feasibility, cited constraints, current/backward/forward alternatives, selected plan, time/budget/risk breakdown, Pareto alternatives, and bounded-search termination.
5. **Model & Migration** — inspect typed operations, candidate BPMN XML, structural diff, inverse operations, and token/variable migration map. Save/copy raw JSON when auditing exact fields.
6. **Validation & Simulation** — inspect XSD/semantic/formal diagnostics, generated traces, failures, and Experimenter feedback. An unsupported or failed gate blocks approval.
7. **Evaluation** — run/compare conversational, no-simulation, no-RAG, syntactic, semantic, hybrid, and hybrid-updated variants; inspect metrics, denominators, statistical tests, confidence intervals, corrections, and plot/report paths.
8. **Provenance** — inspect run ID, configuration fingerprint, prompts, model/index versions, request/decision chain, retry attempts, approval status, and engine receipts.
9. **Export** — select a run, create a ZIP bundle with checksums, or replay an existing run after checksum validation.

The action chooser exposes the same application use cases as CLI: ingestion, indexing/revocation, analysis/planning/adaptation, validation/simulation, deployment/migration, approval/rejection, inspection, evaluation/baselines, batch/report, export/replay. Panels show a specialized view and retain raw JSON. For screenshot acceptance, follow [the GUI manual checklist](gui_manual_acceptance.md).

## 4. CLI conventions

Command inventory: `ingest`, `index-rag`, `validate`, `simulate`, `evaluate`, `report`, `baseline`, `deploy`, `analyse`, `plan`, `adapt`, `revoke-rag`, `migrate`, `approve`, `reject`, `inspect`, `batch`, `export`, `replay`, and `gui`.

Global options precede the command:

```text
bpmn-adapt [--config FILE] [--json] [--seed N] [--run-id ID] [--offline | --live] COMMAND ...
```

`--json` emits compact machine-readable output. `--config` selects a TOML profile. `--seed` fixes evaluation randomness. `--run-id` gives supported operations a reproducible identity. `--offline` forces mock LLM/dry-run/local vectors; `--live` enables the live LLM mode and therefore requires a key.

Exit codes are 0 success, 2 input/configuration error, 3 structured rejection/failure, 4 external connection/timeout failure, and 5 unexpected internal error.

### Folder preparation and inspection

- `ingest FOLDER`: parse and upsert folder data.
- `index-rag FOLDER`: ingest folder examples and index them under governance rules.
- `inspect [FOLDER] [--instance ID]`: show DB facts for a folder or live/dry-run instance state.
- `report FOLDER`: compact process/configuration summary.
- `revoke-rag EVIDENCE_ID REASON`: mark evidence inactive in DB and vector store; lineage remains.

```powershell
bpmn-adapt --config config/offline.toml --json ingest "Pmo-3D printer"
bpmn-adapt --config config/offline.toml inspect "Pmo-3D printer"
bpmn-adapt --config config/offline.toml revoke-rag source-id "superseded by policy version 4"
```

### Analysis, planning, and adaptation

- `analyse FOLDER REQUEST [--target NAME_OR_ID] [--state ID] [--operation ADD|MODIFY|REMOVE|RE_ADD]`: facts/evidence/feasibility without mutation.
- `plan FOLDER REQUEST [--target ...] [--state ...]`: deterministic temporal search and cost selection.
- `adapt FOLDER REQUEST [--target ...] [--state ...] [--operation ...]`: complete orchestrated workflow.
- `approve RUN_ID REASON [--actor NAME]` and `reject RUN_ID REASON [--actor NAME]`: record disposition.

```powershell
bpmn-adapt --config config/offline.toml analyse "Pmo-3D printer" "remove Receive status" --operation REMOVE --target "Receive status" --state STATE-02
bpmn-adapt --config config/offline.toml plan "Pmo-3D printer" "Receive status" --target "Receive status" --state STATE-02
bpmn-adapt --config config/offline.toml --run-id thesis-case-001 adapt "Pmo-3D printer" "remove Receive status" --operation REMOVE --target "Receive status" --state STATE-02
bpmn-adapt approve thesis-case-001 "reviewed against oracle" --actor researcher
```

Natural language is supported at the request boundary, but explicit operation/target/state is preferable for controlled experiments. `RE_ADD` receives the original BPMN as a restoration oracle. General ADD/MODIFY/gateway/flow operations are represented in the typed mutation layer; for precise complex changes, use structured modeler output rather than relying on the minimal command-line intent heuristic.

### Independent assurance

- `validate FOLDER`: secure XSD plus semantic validation.
- `simulate FOLDER`: bounded execution traces and structured failures.
- `deploy FOLDER [--create-instance] [--variables JSON]`: deploy through dry-run or Camunda adapter.
- `migrate INSTANCE_ID TARGET_DEFINITION_KEY [--mapping JSON]`: validate and execute migration.

```powershell
bpmn-adapt --config config/offline.toml validate "Pmo-3D printer"
bpmn-adapt --config config/offline.toml simulate "Pmo-3D printer"
bpmn-adapt --config config/offline.toml deploy "Pmo-3D printer" --create-instance --variables '{"caseId":"demo-1"}'
bpmn-adapt --config config/offline.toml migrate instance-1 target-definition --mapping '{"oldTask":"newTask"}'
```

In Camunda mode, deployment and migration use idempotency keys, bounded retry, state reconciliation, validation, and post-state verification. A dry-run receipt proves application behavior, not Camunda interoperability.

### Evaluation and batch execution

- `evaluate FOLDER`: all configured ablations and artefacts.
- `baseline FOLDER [--variant NAME]`: one variant or all baseline results.
- `batch FOLDER... [--request TEXT]`: reports or adaptations across named folders.

```powershell
bpmn-adapt --config config/offline.toml evaluate "Pmo-3D printer"
bpmn-adapt --config config/offline.toml baseline "Pmo-3D printer" --variant no_simulation
bpmn-adapt --config config/offline.toml batch "Pmo-3D printer" "Mangler-Car Service"
```

Full folder-agnostic execution is resumable:

```powershell
python scripts/run_full_dataset.py --root . --profile config/offline.toml --resume experiments/evidence/my-run/manifest.jsonl --variants hybrid --workers 4 --json
```

Repeat exactly the same command to skip completed content-addressed scenarios. Change of folder content changes its checksum and creates new manifest events. For all ablations, pass `--variants conversational,no_simulation,none,syntactic,semantic,hybrid,hybrid_updated`; for selected work use `--scenario-kinds inspect,evaluate,adapt`.

### Export and replay

- `export RUN_ID DESTINATION`: create a checksum-bearing ZIP bundle.
- `replay RUN_ID`: verify recorded inputs/checksums and rerun with the stored identity.

```powershell
bpmn-adapt --config config/offline.toml export thesis-case-001 experiments/exports
bpmn-adapt --config config/offline.toml replay thesis-case-001
```

Replay fails when a referenced artefact has drifted. Preserve the profile, `.env`-free redacted configuration, model/revision, prompt versions, source checksums, seed, run ID, and manifest for academic reproduction.

## 5. Database and RAG lifecycle

`validation.db` files in dataset material are input/ground-truth assets when present; they are not silently treated as the mutable runtime repository. `runtime_bpmn.db` (or the configured SQLite URL) stores authoritative definitions/versions, instances/states, rules/resources, requests/decisions, planner records, candidates, validations, simulations, approvals, engine receipts, observations, and provenance. Migrations are idempotent.

Core and RAG repositories are separated by interface and authority. RAG contains advisory examples and vector records. Retrieval defaults to active, same-process, same-operation, compatible-version evidence and logs filters, candidates, component scores, final ordering, fusion/index/model versions, and selected citations.

Incoming requests and candidates are stored in core first. Only a validated approved adaptation is indexed as positive evidence. Negative labels are separate. Revocation sets active=false with reason; it never silently deletes history. Full-dataset execution uses one content-addressed folder namespace, isolated SQLite DB, and output directory per folder, plus an append-only run manifest.

## 6. Live profiles

For neural local vectors, use `config/default.toml`, pre-download/cache the exact model revision, and check the model key in evidence. For PostgreSQL/pgvector and Camunda, start the pinned services in `compose.yaml`, provide non-default credentials through environment variables, and run the integration profile health check. For a live LLM set `ADAPT_LLM_API_KEY`, provider, model, and base URL; use a restricted research credential.

```powershell
docker compose up -d --wait
$env:ADAPT_LLM_API_KEY='...'
python scripts/healthcheck.py --profile config/integration.toml --json
python -m unittest discover -s tests -v
```

Run the service-gated integration tests described in [reproduction](reproduction.md). Do not infer live success from adapter unit/recording tests.

## 7. Troubleshooting

- **`No module named bpmn_adapt`**: install editable package or set `PYTHONPATH=src`.
- **Missing SentenceTransformers/model**: use `config/offline.toml` for compatibility testing, or install/cache the pinned model for a neural claim.
- **Live mode says key required/unauthorized**: set a valid key and confirm base URL/model; health diagnostics redact it.
- **PostgreSQL/pgvector missing/refused**: install `psycopg`/`pgvector`, start Compose, verify URL/role/extension.
- **Camunda refused**: wait for health, verify REST/OAuth endpoints, tenant, credentials, and TLS.
- **BPMN FAIL/UNSUPPORTED**: inspect element-level schema/semantic/formal diagnostics. Unsupported is intentionally blocking.
- **Adaptation rejected**: inspect DB constraints first, then RAG citations and planner termination; RAG cannot override a blocker.
- **Token migration rejected**: active scope/element lacks a safe mapping; provide an explicit mapping or redesign the change.
- **No retrieval hits**: verify process ID, operation, source-version compatibility, active status, indexing, and RAG mode.
- **Resume reruns work**: source checksum, scenario, or variant changed; inspect manifest keys.
- **GUI freezes/does not open**: verify Tk installation and use the worker-backed action path; run CLI to isolate display issues.
- **Formal test skipped**: PM4Py/WOFLAN or the external checker is unavailable. A skip is not a pass.

For exact syntax, see [the generated CLI reference](generated_reference.md). For evidence and honest verification boundaries, see [testing status](testing_status.md) and [the defense index](defense_evidence_index.md).
