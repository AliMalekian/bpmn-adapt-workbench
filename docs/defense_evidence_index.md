# Defense evidence index

This index maps defense claims to executable source, acceptance tests, and preserved evidence. “Live pending” is an explicit result, not a pass.

| Claim | Source | Acceptance tests | Evidence |
|---|---|---|---|
| Layered config, redaction, dependencies | `src/bpmn_adapt/config.py` | `tests/unit/test_config_profiles.py` | [Task 1](../experiments/evidence/m0/config/task1-verification.json) |
| Migrations and repository bootstrapping | `persistence/migrator.py`, migrations | `tests/contract/test_repository_migrations.py` | [Task 2](../experiments/evidence/m0/config/task2-verification.json) |
| Compose/readiness/CI | `compose.yaml`, `scripts/healthcheck.py` | `tests/unit/test_healthcheck.py`, service health | [Task 3](../experiments/evidence/m0/config/task3-verification.json) |
| Domain contracts and identity isolation | `domain/`, `persistence/repositories/` | domain/repository parity tests | [Task 4](../experiments/evidence/m0/config/task4-verification.json) |
| Temporal planning and optimization | `planning/` | temporal oracle and Analyst integration | [Task 5](../experiments/evidence/m2/planning/task5-verification.json) |
| General transactional mutation/migration | `bpmn/changes.py`, `mutation.py`, `diff.py` | change/general/compound tests | [Task 6](../experiments/evidence/m3/mutation/task6-verification.json) |
| XSD and semantic conformance | `bpmn/xsd.py`, `semantics.py`, schemas | XSD/semantic fixtures | [Task 7](../experiments/evidence/m4/validation/task7-verification.json) |
| Petri/PNML/WOFLAN/external checker | `formal/` | external-checker/formal tests | [Task 8](../experiments/evidence/m4/formal/task8-verification.json) |
| Neural/persistent hybrid RAG | `retrieval/` | vector contract, dense and governance tests | [Task 9](../experiments/evidence/m5/rag/task9-verification.json) |
| Camunda/dry-run engine adapters | `engine/` | engine contracts, recordings, live-gated test | [Task 10](../experiments/evidence/m6/engine/task10-verification.json) |
| Baselines, metrics, statistics | `evaluation/` | metric/statistics/baseline tests | [Task 11](../experiments/evidence/m7/evaluation/task11-verification.json) |
| CLI/application/export/replay | `application/`, `cli.py` | CLI and replay E2E | [Task 12](../experiments/evidence/m8/interfaces/task12-verification.json) |
| Nine-tab GUI/workers | `gui/` | controller/workbench tests | [Task 13](../experiments/evidence/m8/gui/task13-verification.json), [workbench](../experiments/evidence/m8/gui/workbench.png), [DB facts](../experiments/evidence/m8/gui/panel-db-facts.png), [RAG](../experiments/evidence/m8/gui/panel-rag-evidence.png), [planning](../experiments/evidence/m8/gui/panel-planning.png), [model/migration](../experiments/evidence/m8/gui/panel-model---migration.png), [validation/simulation](../experiments/evidence/m8/gui/panel-validation---simulation.png), [evaluation](../experiments/evidence/m8/gui/panel-evaluation.png), [provenance](../experiments/evidence/m8/gui/panel-provenance.png), [export](../experiments/evidence/m8/gui/panel-export.png) |
| Full-dataset/resume | `evaluation/datasets.py`, `manifest.py`, runner script | manifest and full-dataset smoke | [Task 14](../experiments/evidence/m9/full-dataset/task14-verification.json), [manifest](../experiments/evidence/m9/full-dataset/manifest-v3.jsonl) |
| Documentation and final verification | `docs/`, `roadmap.md` | `tests/test_documentation.py` | [Defense report](defense_report.md), [checksum manifest](../experiments/evidence/final/checksums.json) |

## External-gate evidence expectations

PostgreSQL/pgvector must add server/extension version, migration/parity output and vector-query evidence. Neural retrieval must add model/revision/cache checksum and IR/full-dataset results. Camunda must add deployment/migration receipts, post-state, scoped cleanup and screenshots. Live LLM must add redacted endpoint/model/usage and validated agent outputs. Formal live execution must add PM4Py/WOFLAN/checker versions and PNML/report checksums.

The detailed status and exact commands are in [testing status](testing_status.md) and [reproduction](reproduction.md).
