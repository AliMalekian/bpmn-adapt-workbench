# Project roadmap and continuation handoff

## Purpose and thesis objective

The platform tests whether a governed multi-agent architecture can safely adapt an executing BPMN process from a folder-local description, constraints, resources, runtime states, examples, and test cases. Its central research rule is that current structured database facts are authoritative while RAG evidence is advisory and historical. An LLM may interpret, propose, and explain; deterministic planners, schemas, constraints, migration rules, formal checks, and simulations decide whether the proposal may advance.

The operational objective is a process-agnostic program: select any valid dataset folder, enter a request, and run the same end-to-end sequence through GUI or CLI without source edits. The evaluation objective is multi-layered: decision correctness, constraint reasoning, structural restoration/edit quality, token and variable preservation, executability, retrieval usefulness, latency, token use, cost, and paired statistical significance.

## Current technical state

All M0–M9 implementation areas exist in code:

1. Layered TOML/`.env`/environment/CLI configuration, secret redaction, migrations, Compose, health checks, and CI.
2. Collision-safe identities and separate core/RAG repository contracts.
3. Bounded backward/current/forward temporal planning with time, budget, and risk objectives.
4. Transactional ADD, MODIFY, REMOVE, RE_ADD, node, flow, gateway, condition, and default-flow operations with inverse metadata and migration maps.
5. Offline-vendored OMG BPMN 2.0.2 XSD validation plus semantic diagnostics.
6. PM4Py conversion, deterministic PNML, WOFLAN mapping, and a bounded external-checker adapter.
7. SentenceTransformer encoding, atomic local vector persistence, pgvector storage, lexical retrieval, hybrid fusion, lineage, approval gates, and revocation. `hash_test` remains an explicit dependency-free test profile only.
8. Dry-run and Camunda 8 deployment/instance/migration adapters with idempotency and reconciliation.
9. Seven evaluation variants, graph-edit/token metrics, NOT_EVALUABLE handling, paired tests, effect sizes, Holm correction, and publication artefacts.
10. Full CLI use-case coverage, export/replay, a nine-tab Tk workbench, resumable full-dataset execution, and evidence documentation.

Available offline verification completed 229 scenarios across 82 folders. External live acceptance is still required for PostgreSQL/pgvector, the neural model artefact, Camunda 8, and an OpenAI-compatible LLM. This is an environmental verification gap, not permission to describe those integrations as live-tested.

## How the language model fits the system

The LLM is accessed only through the provider-neutral client protocol. `MockLLMClient` makes tests deterministic; `OpenAICompatibleClient` uses configurable model, base URL, key, timeout, retry, backoff, and rate limits. Each agent loads its own versioned prompt from `src/bpmn_adapt/prompts/`.

The LLM is not the source of truth. Analyst explanations must cite facts and retrieved evidence; Modeler output is parsed into a typed `ChangeSet`; Experimenter results come from executable checks; Orchestrator approval is bounded by deterministic gates. Treat all model output as untrusted structured input. A future model change requires prompt-version provenance, schema tests, a frozen scenario manifest, baseline comparison, and regression thresholds—not merely a subjective demo.

To develop the LLM portion further:

1. Freeze a labeled train/development/test split by process family to prevent example leakage.
2. Add provider/model versions as experimental factors while holding retrieval and seeds fixed.
3. Validate JSON and citations before any change reaches the mutation engine.
4. Measure decision calibration, unsupported-claim rate, constraint citation precision/recall, edit exactness, and retry yield.
5. Red-team prompt injection in narratives and RAG documents; retrieved text never gains instruction authority.
6. Consider fine-tuning only after error taxonomy and baseline evidence show prompt/retrieval changes are insufficient.
7. Never train or index rejected/unvalidated outputs as positive evidence; retain lineage and revocation.

## Step-by-step execution process

1. Create a Python 3.11/3.12 environment and install declared requirements.
2. Copy `.env.example` to `.env`; choose `config/offline.toml`, `config/default.toml`, or `config/integration.toml`.
3. Run `python scripts/healthcheck.py --profile <profile> --json`; resolve every capability required for the planned claim.
4. Run `ingest` and `inspect` on a process folder. Verify BPMN, narrative, rules, resources, states, examples, and tests.
5. Run `index-rag`; verify scope, model key, vector manifest, active status, and lineage.
6. Run `analyse` and `plan`; inspect authoritative blockers, citations, alternatives, costs, and termination status.
7. Run `adapt`; inspect the change set, BPMN diff, inverse operations, migration map, validation, simulation, and provenance.
8. Use `approve` or `reject` when human disposition is required. Only approved validated outcomes become positive RAG cases.
9. Run `validate`, `simulate`, and configured formal checks independently.
10. In dry-run mode, exercise `deploy` and `migrate`; in live mode, capture Camunda receipts and post-migration state.
11. Run `evaluate`/`baseline` for a folder and `scripts/run_full_dataset.py` for the dataset manifest.
12. Export a run, replay it with checksum verification, regenerate references, and execute all tests.
13. Update a compliance row only when code, an acceptance test, and an evidence artefact all exist.

## Exact continuation checklist

- Install the full locked environment and rerun `python -m pip check`.
- Cache `sentence-transformers/all-MiniLM-L6-v2` at the configured revision, run dense retrieval tests, then run the 82-folder manifest with `config/default.toml`.
- Start `compose.yaml`, run PostgreSQL migration/repository and pgvector contract suites, and preserve service/version logs.
- Start Camunda 8, run deployment, instance creation, migration validation/execution, state verification, and scoped cleanup; capture receipts and screenshots.
- Supply a restricted live LLM key, run provider contract and full agent workflows, and record model/version/token/cost data with secrets redacted.
- Execute all seven variants over the frozen full manifest with sufficient repetitions; regenerate statistics and plots.
- Review GUI tabs using [the GUI checklist](docs/gui_manual_acceptance.md) in offline and live profiles.
- Only then change pending live rows in [the compliance audit](docs/state_of_art_compliance.md) and [testing status](docs/testing_status.md).

## Practical safety and operating rules

- Never modify dataset folders; write only to configured output roots.
- Never commit `.env`, keys, OAuth secrets, database passwords, raw authorization headers, or secret-bearing logs.
- Never let RAG override current DB facts.
- Never index a candidate as positive before validation and approval.
- Revoke evidence by marking it inactive; do not erase lineage.
- Keep planner depth/state/time, retries, simulations, subprocess output, and HTTP calls bounded.
- Use idempotency keys for deployment and migration; reconcile after ambiguous timeouts.
- Treat unsupported BPMN as a typed blocking result, not success.
- Preserve old vector manifests until atomic replacement succeeds.
- A skipped live test is pending, never passing.

## Suggested future improvements

After the specified live gates pass, valuable extensions are authenticated multi-user approval, signed provenance, BPMN collaboration/choreography coverage, model-specific Camunda extension validation, additional engines, scalable ANN backends, process-family cross-validation, causal analysis of RAG updates, multilingual prompt/evidence evaluation, accessibility testing for the GUI, and a web/API front end. A Git repository with protected CI and signed releases should be established before public distribution; this workspace was intentionally not initialized as Git.

## Navigation for the next agent

Start with [the approved plan](docs/superpowers/plans/2026-09-22-defense-ready-completion.md), [the design](docs/superpowers/specs/2026-09-22-defense-ready-completion-design.md), [the evidence index](docs/defense_evidence_index.md), and [testing status](docs/testing_status.md). The execution ledger is `.superpowers/sdd/2026-09-22-defense-ready-completion/progress.md`. The authoritative full-dataset manifest is `experiments/evidence/m9/full-dataset/manifest-v3.jsonl`; its recorded SHA-256 is `7568966e704cc66f73b7b556061b630c5cd57d7b98694dbfbd759ac8e1ca3823`. Its resume identity includes folder checksum, scenario, variant, configuration fingerprint, and runner version.
