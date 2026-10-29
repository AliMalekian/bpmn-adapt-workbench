# Reproduction guide

## Offline evidence environment

Use Python 3.11 or 3.12 from the repository root:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-dev.txt -c constraints.txt
python -m pip install -e .
Copy-Item .env.example .env
```

For a dependency-free compatibility run, do not set live secrets and use `config/offline.toml`. It selects mock LLM, SQLite, `hash_test`, local compatibility retrieval, and dry-run engine.

```powershell
python scripts/healthcheck.py --profile config/offline.toml --json
python -m compileall -q src tests scripts
python -m unittest discover -s tests -v
python scripts/run_full_dataset.py --root . --profile config/offline.toml --resume experiments/evidence/reproduction/manifest.jsonl --variants hybrid --workers 4 --json
python scripts/run_full_dataset.py --root . --profile config/offline.toml --resume experiments/evidence/reproduction/manifest.jsonl --variants hybrid --workers 4 --json
```

The second dataset command must report every prior event as skipped. Record Python/OS versions, dependency lock, command exit codes, manifest checksum, folder count, event count, and skips. Regenerate drift-controlled documentation with:

```powershell
python scripts/generate_reference.py
python -m unittest tests.test_documentation -v
```

## Neural local-vector gate

Install/cache the pinned SentenceTransformer model and use `config/default.toml`. Run the dense integration test, index persistence contracts, and the full manifest with all variants:

```powershell
python -m unittest tests.integration.test_dense_rag tests.contract.test_vector_store -v
python scripts/run_full_dataset.py --root . --profile config/default.toml --resume experiments/evidence/neural/manifest.jsonl --variants conversational,no_simulation,none,syntactic,semantic,hybrid,hybrid_updated --workers 4 --json
```

Preserve model name, revision, model-key/dimensions, local vector manifest checksum, retrieval logs and IR metrics. Do not substitute `hash_test` evidence for this gate.

## PostgreSQL/pgvector and Camunda gates

Set non-default database/engine credentials in `.env`, then:

```powershell
docker compose config
docker compose up -d --wait
python scripts/healthcheck.py --profile config/integration.toml --json
python -m unittest tests.integration.test_postgres_migrations tests.integration.test_pgvector_store -v
python -m unittest tests.integration.test_camunda8 -v
```

Preserve Compose image digests, health output, database/extension versions, migration ledger, Camunda deployment and migration receipts, post-migration state, scoped cleanup result, and screenshots. Never run broad cleanup against unrelated resources.

## Live LLM gate

Set `ADAPT_LLM_API_KEY`, exact provider/model/base URL and a restricted rate limit. Keep prompts/version and seed fixed:

```powershell
python scripts/healthcheck.py --profile config/integration.toml --json
python -m bpmn_adapt.cli --config config/integration.toml --run-id live-case-001 adapt "Pmo-3D printer" "remove Receive status" --operation REMOVE --target "Receive status" --state STATE-02
```

Run approved/rejected/unsupported scenarios and retain redacted request/response metadata, parsed DTOs, retries, usage and costs. Never retain the key or authorization header.

## Formal gate

With PM4Py/WOFLAN installed:

```powershell
python -m unittest tests.integration.test_formal_verification -v
```

If using an external checker, set the argument-array command and timeout in the profile. Preserve checker path/version, PNML checksum, bounded stdout/stderr and result mapping.

## Publication regeneration

Freeze the content-addressed scenario manifest before comparison. Run all seven variants with the declared repetitions and seed. Archive `observations.json`, `observations.csv`, `ablation_summary.csv`, `publication_table.csv`, `statistics.json`, `accuracy.svg`, and checksum manifest. Verify that NOT_EVALUABLE observations have transparent denominators and are excluded from inference.

The verified offline reference manifest is `../experiments/evidence/m9/full-dataset/manifest-v3.jsonl`, with SHA-256 `7568966e704cc66f73b7b556061b630c5cd57d7b98694dbfbd759ac8e1ca3823` at audit time. Its resume key includes configuration fingerprint and runner version. See [testing status](testing_status.md) before interpreting any result.
