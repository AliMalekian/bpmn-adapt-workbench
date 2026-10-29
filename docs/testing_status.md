# Testing status

Status date: 2026-09-22. “Offline verified” means executed locally with SQLite, mock LLM, explicit `hash_test` compatibility embeddings, and dry-run/recorded external adapters. It does not mean a live integration passed.

## Latest verified executions

| Scope | Result | Evidence |
|---|---:|---|
| Complete Python test discovery | **151 passed, 7 skipped, 0 failed (158 total)** | `py -3.12 -m unittest discover -s tests -q` |
| Task 14 focused discovery/resume test | 11 passed | `experiments/evidence/m9/full-dataset/task14-verification.json` |
| Complete dataset, fresh offline run | 229 completed, 0 runner failures; 82/82 valid folders | Same Task 14 evidence and `manifest-v3.jsonl` |
| Complete dataset, immediate resume | 0 completed, 229 skipped | Same Task 14 evidence |
| GUI screenshot acceptance | Captured | `experiments/evidence/m8/gui/workbench.png` |

## Component coverage matrix

| Component/requirement | Unit tests | Integration tests | E2E tests | Dataset scope | Live status |
|---|---|---|---|---|---|
| Configuration/redaction/profiles | Yes | Health composition | CLI profile options | Representative + full runner profile | Live secrets absent |
| Migration runner/core repository | Yes | SQLite contracts | Ingest/adapt flows | All 82 folders use isolated SQLite | PostgreSQL pending |
| Orchestrator Agent | Yes | Agent chain | Folder-to-result, CLI/replay | Adapt cases in full manifest | Live LLM/engine pending |
| Analyst Agent | Yes | Planner + facts/RAG | Analyse/adapt CLI/GUI | Full inspect/evaluate; available adapt cases | Live LLM pending |
| Modeler Agent/mutation | Yes, all typed operations | Compound adaptation | Remove/re-add and CLI | Dataset test cases exercised | Engine import pending |
| Experimenter/simulator | Yes | Formal/validation composition | Simulate/adapt | Per-folder evaluation | Live engine pending |
| Temporal planner/optimizer | Oracle/brute-force unit suite | Analyst planning | `plan` command | Representative requests | No external dependency |
| XSD/semantic validation | Valid/invalid/XXE/unsupported | Modeler gate | `validate`/adapt | Dataset candidates | lxml available in evidence interpreter; vendor-extension breadth bounded |
| Petri/PNML/external checker | Checker/PNML tests | Formal gate test | Through Experimenter when enabled | Subset fixtures | PM4Py/WOFLAN pending dependency |
| Lexical/hybrid/local vectors | Yes, restart/filter/revoke/rebuild | Fake dense ranking | Retrieval through agent | Hash-test full run | Real SentenceTransformer pending |
| pgvector | SQL/contract construction | Opt-in live test exists | Through integration profile | Not run | PostgreSQL/pgvector pending |
| LLM adapter/prompts | Mock/protocol/prompt tests | Agent chain in mock | Full workflow in mock | Full offline run | Actual provider pending key |
| Dry-run engine | Contract tests | Adapter chain | Deploy/migrate CLI | Representative | Verified offline |
| Camunda 8 adapter | Recorded transport/edge cases | Opt-in live test exists | Deploy/migrate path | Not run | Running service pending |
| Baselines/metrics/statistics | Yes | Seven variants | Evaluate/baseline CLI | Evaluate event for all 82 folders in selected hybrid run | All-variant neural/full repetitions pending resources |
| CLI | Parser/exit/service tests | Representative folders | Every command class/export/replay | Full runner uses application boundary | Live commands pending services |
| GUI | Controller/worker tests | Headless workbench test | Screenshot/manual checklist | Representative | Live profile UI pending services |
| Full-dataset runner | Discovery/manifest tests | Isolated executor | Resume smoke | 82 folders, 229 scenarios | Neural/live profiles pending |
| Documentation | Parser/config/link contracts | N/A | Reproduction commands manually checked | Whole repository | N/A |

## Requirement-level assurance

- DB-as-authoritative/RAG-as-advisory: automated tests cover authoritative blockers and separate repository write surfaces; verified in mock mode, not with live Postgres/LLM.
- Approval-gated update/revocation: automated unit/contract tests cover approval requirements, lineage, inactive filtering, and durable revocation.
- Folder/process agnosticism: duplicate-terminal-name identity test, arbitrary fixture ingestion, and 82-folder full run.
- General BPMN edits: isolated and compound automated tests cover add/modify/remove/re-add, nodes/flows/gateways/conditions/defaults, rollback, namespaces, diff, and migrations.
- Conformance/security: automated schema, semantic, broken-reference, gateway, reachability, unsupported, DTD/entity tests.
- Formal verification: safe subprocess and result parsing are tested; actual PM4Py/WOFLAN is not.
- Evaluation: unit/integration tests cover metrics, NOT_EVALUABLE, all baselines, paired tests, effect sizes, Holm, and artefact generation. Scientific conclusions still require the final frozen all-variant neural/live experiment.
- Reproducibility: config fingerprints, checksums, seeded evaluation, immutable manifests, export/replay and resume are automated.

## Explicitly skipped/pending external resources

| Gate | Why pending | Test entry point | What constitutes completion |
|---|---|---|---|
| PostgreSQL | No running server/driver in evidence environment | `tests/integration/test_postgres_migrations.py` | Real migrations, parity, rollback and health pass |
| pgvector | No server/extension/driver | `tests/integration/test_pgvector_store.py` | Upsert/search/filter/revoke/restart and index plan pass |
| SentenceTransformers | Package/model unavailable | `tests/integration/test_dense_rag.py` | Pinned model loads; neural retrieval metrics and full dataset run finish |
| PM4Py/WOFLAN | Package unavailable | `tests/integration/test_formal_verification.py` | Known sound/unsound fixtures return expected formal status |
| Camunda 8 | Docker/service unavailable | `tests/integration/test_camunda8.py` | Deploy/create/inspect/migrate/verify/cleanup pass with receipts |
| Live LLM | API key absent | live profile/provider contract and agent E2E | Authenticated structured responses complete with redacted evidence |

The integration health probe with a non-secret probe value reported database/vector/embedding `MISSING_DEPENDENCY`, LLM `UNAUTHORIZED`, and engine `REFUSED`. These results are blockers, not passes.

## Interpretation limits

The 229 PASS events mean the runner completed and preserved a structured application result. A business-level rejection or safety-gated candidate is valid experimental output and is stored inside the payload; it is not an infrastructure failure. The Task 14 full run used only the `hybrid` variant and the `hash_test` encoder. It therefore demonstrates folder coverage and pipeline robustness, not neural retrieval quality or statistical superiority.

See [reproduction](reproduction.md), [test scenarios](test_scenarios.md), and [compliance](state_of_art_compliance.md).
