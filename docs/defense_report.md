# Final defense package report

This report is finalized from fresh verification output at the end of Task 15.

## Delivered scope

The repository contains the complete M0–M9 code architecture: six explicit components, provider-neutral LLMs and prompts, temporal planning/optimization, transactional general BPMN mutation, conformance/formal adapters, persistent hybrid retrieval, engine adapters, evaluation/statistics, GUI/CLI parity, resumable full-dataset execution, configuration/services/CI, documentation and evidence.

## Verification result

Fresh Python 3.12 verification: **151 passed, 7 skipped, 0 failed (158 total)**. `compileall` passed. Documentation contracts passed. The offline CLI report succeeded on a real dataset folder. `pip check` correctly reported missing live/full-stack dependencies (`httpx`, PM4Py, SentenceTransformers, statsmodels) and an older lxml; these are recorded external/dependency gates rather than passes.

The final-code offline dataset evidence contains 82 valid folders and 229 completed runner events with zero runner failures. An immediate resume skipped all 229 using folder checksum + scenario + variant + configuration fingerprint + runner version. The v3 manifest SHA-256 is `7568966e704cc66f73b7b556061b630c5cd57d7b98694dbfbd759ac8e1ca3823`.

## Honest external boundary

Live PostgreSQL/pgvector, SentenceTransformers model execution, PM4Py/WOFLAN, Camunda 8 and OpenAI-compatible LLM acceptance remain pending because their dependencies/services/credential were unavailable. Their adapters, profiles, Compose definitions and opt-in tests are delivered. No live pass is claimed.

## Artefacts

Use [the evidence index](defense_evidence_index.md), [testing status](testing_status.md), [compliance audit](state_of_art_compliance.md), [reproduction guide](reproduction.md), and [continuation roadmap](../roadmap.md). The checksum inventory is generated at `../experiments/evidence/final/checksums.json`.
