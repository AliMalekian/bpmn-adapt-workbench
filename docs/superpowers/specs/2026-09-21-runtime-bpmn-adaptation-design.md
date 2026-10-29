# Runtime BPMN Adaptation Research Platform — Design Specification

## 1. Purpose and scope

This specification defines a thesis-grade Python research platform for safe runtime adaptation of BPMN process instances. It implements the Proposed Approach from *Malekian_State_Of_The_Art* as six explicit, independently testable components: **Orchestrator Agent**, **Analyst Agent**, **Modeler Agent**, **Experimenter Agent**, **Database layer**, and **RAG layer**.

The platform consumes the enriched process folders already present in the workspace. A folder provides BPMN XML, narrative text, rules, resources, runtime states, RAG examples, and test cases. The platform shall preserve source data and write all generated artefacts to a separate experiment-output directory.

The system supports both a graphical desktop interface and a command-line interface. It is designed for controlled experiments, auditability, and repeatable thesis/paper evaluation; it is not an uncontrolled autonomous production deployment.

## 2. Research questions operationalised

The system shall measure whether a multi-agent, evidence-grounded approach can safely adapt a running BPMN instance while preserving control-flow validity, constraints, and executable token state.

Primary outcomes:

1. BPMN XML and graph validity after adaptation.
2. Simulation success, deadlock detection, and trace validity.
3. Token-migration preservation.
4. Rule/resource constraint-violation rate.
5. Recovery rate when current-state execution is infeasible but a bounded backward or forward alternative exists.
6. Structural similarity to the known original/re-added process when an oracle is available.
7. End-to-end latency, agent retries, and evidence provenance.

## 3. Explicit components and responsibilities

### 3.1 Orchestrator Agent (`OrchestratorAgent`)

The Orchestrator Agent is the only component allowed to coordinate an adaptation run. It is a named class, not a utility function.

Responsibilities:

- create a unique run identifier and immutable provenance record;
- sequence Analyst → Modeler → Experimenter;
- enforce configurable retry and self-correction limits;
- pass only typed, validated contracts between agents;
- approve final deployment only when all required checks pass;
- persist every decision, retry, evidence set, model version, simulation result, and final status;
- expose a deterministic mock execution path for tests.

The Orchestrator never directly edits BPMN XML, makes feasibility decisions, or fabricates simulation results.

### 3.2 Analyst Agent (`AnalystAgent`)

The Analyst Agent performs the context-aware feasibility analysis before structural modification.

Responsibilities:

- parse and normalise a user request into a typed candidate operation;
- obtain the current instance state and BPMN version from the DB layer;
- obtain applicable rules and resource availability from the DB layer;
- request RAG evidence from the RAG layer;
- check target existence, current token feasibility, rules, resources, and process-local evidence;
- evaluate the current state first, then bounded backward and forward alternatives when necessary;
- return an explicit feasibility decision: `APPROVE`, `REJECT`, or `ALTERNATIVE_PROPOSED`, with cited evidence and reasons.

The Analyst may use an LLM for controlled language understanding and explanation, but the final feasibility result must be checked by deterministic validators.

### 3.3 Modeler Agent (`ModelerAgent`)

The Modeler Agent converts an approved, atomic change specification into a candidate BPMN version and token-migration plan.

Responsibilities:

- decompose a request into atomic graph edits;
- apply only approved remove/re-add edits to a copy of BPMN XML;
- preserve BPMN 2.0 identifiers and record every edit in a version diff;
- reconnect incoming/outgoing sequence flows when a removal is accepted;
- preserve gateway and parallel-branch semantics;
- construct a typed token-migration mapping from old to candidate model;
- return a candidate model, XML, version diff, migration instructions, and any assumptions.

The Modeler must not approve its own candidate. It receives only approved analyst output, and an Experimenter failure may trigger a bounded correction cycle through the Orchestrator.

### 3.4 Experimenter Agent (`ExperimenterAgent`)

The Experimenter Agent independently validates a candidate model in an isolated simulation environment.

Responsibilities:

- generate or load test scenarios from `testcasees.txt` and current state;
- validate BPMN XML, graph reachability, gateway consistency, and token migration;
- simulate candidate execution traces, including branch, loop, and end-event coverage where applicable;
- detect deadlock, unreachable required activities, invalid migration, and constraint violations;
- return a structured `ExperimentReport` with pass/fail status, traces, metrics, and failure payloads;
- feed failures to the Modeler through the Orchestrator; it must not mutate BPMN itself.

The initial formal-validation implementation will use deterministic graph/state-space checks. A Petri-net export/checker adapter is an explicit optional evaluation extension, not an unsupported claim of universal formal completeness.

### 3.5 Database layer (`DatabaseLayer` and repositories)

The Database layer is an independent persistence boundary, rather than direct file access from agents. SQLite is the default implementation for local research use. PostgreSQL is supported through the same repository interfaces for multi-user or larger experiment deployments.

It shall persist:

- process definitions and BPMN version lineage;
- process instances and runtime/token states;
- rules and resources, including source references;
- user requests and normalised operations;
- analyst decisions and cited evidence;
- candidate model diffs and migration plans;
- simulation inputs, traces, reports, metrics, and failures;
- RAG retrieval logs and embedding metadata;
- orchestration runs, retries, timestamps, configuration fingerprint, and audit provenance.

Repository interfaces include `ProcessRepository`, `InstanceRepository`, `ConstraintRepository`, `RequestRepository`, `DecisionRepository`, `SimulationRepository`, `ProvenanceRepository`, and `RetrievalLogRepository`. ORM details remain behind these interfaces.

### 3.6 RAG layer (`HybridRAGService`)

The RAG layer is explicit and independent. It indexes process-local `RagData.txt` examples and associated metadata. It uses **hybrid semantic + syntactic retrieval**:

- **Syntactic/structured filtering:** process folder, operation type, target BPMN element or aliases, rule identifiers, resource identifiers, decision category, and decision status.
- **Semantic ranking:** dense text embeddings with cosine similarity over request and evidence text.
- **Hybrid ranking:** configurable weighted combination of structured eligibility and semantic score, with deterministic tie-breaking.

Each retrieval response shall log: query text hash, evidence IDs, metadata filters, embedding-model identifier, semantic score, lexical/structured score, final rank, ranking configuration, and index version. The platform shall support semantic-only, syntactic-only, and hybrid modes to enable ablation studies.

Purely lexical retrieval is not the default because it misses paraphrases. Purely dense retrieval is not sufficient because it can retrieve an incompatible process or operation. Hybrid retrieval is the default research configuration.

#### Authority, update, and revocation policy

The DB and RAG remain strictly separated by authority. The DB is authoritative, structured, and current; it is the sole source of truth for BPMN versions, runtime state, rules, resources, requests, decisions, and simulation facts. RAG is advisory, semantic, and historical. An agent may use RAG to propose or explain an action, but must validate it against current DB facts before approval.

Incoming requests and candidate outputs are stored in the DB first. A case is added to the RAG index only after Analyst approval, Modeler output, Experimenter validation, and final Orchestrator approval. Every indexed case carries lineage: folder/process identifier, source and target BPMN versions, request/decision/simulation IDs, active status, timestamp, configuration fingerprint, LLM/embedding model, and prompt versions. If a case becomes obsolete or invalid, it is marked inactive and excluded from default retrieval; it is never silently deleted. Default retrieval is restricted to compatible evidence: same process family/folder, operation type, and valid source-version range.

## 4. LLM integration and prompt governance

### 4.1 Provider-neutral adapter

All LLM access occurs through a named `LLMClient` protocol and provider-neutral adapter. Agents receive the interface by dependency injection; they never call a vendor SDK directly.

Required adapter capabilities:

- chat/completion request with system prompt, user payload, schema contract, timeout, retry policy, and request identifier;
- optional embeddings request for RAG;
- typed response parsing and validation;
- provider error normalisation, rate-limit handling, retry backoff, and redacted logging;
- mock/offline implementation with deterministic fixtures for tests and reproducible evaluation.

Initial providers may include OpenAI-compatible HTTP endpoints and a generic local endpoint. Provider-specific code must be isolated in adapters, allowing future additions without changing agents.

### 4.2 Configuration and secrets

Configuration uses environment variables and a typed settings class. A committed `.env.example` documents every variable without containing a secret. `.env` is excluded by `.gitignore`; keys are never logged or written to the DB.

Minimum configuration fields:

```dotenv
ADAPT_LLM_MODE=mock                 # mock | live
ADAPT_LLM_PROVIDER=openai_compatible
ADAPT_LLM_MODEL=example-model
ADAPT_LLM_BASE_URL=https://example.invalid/v1
ADAPT_LLM_API_KEY=
ADAPT_LLM_TIMEOUT_SECONDS=60
ADAPT_LLM_MAX_RETRIES=2
ADAPT_LLM_RETRY_BACKOFF_SECONDS=1.0
ADAPT_LLM_RATE_LIMIT_REQUESTS_PER_MINUTE=30
ADAPT_EMBEDDING_PROVIDER=local
ADAPT_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
ADAPT_DATABASE_URL=sqlite:///experiments/runtime_bpmn.db
ADAPT_RAG_MODE=hybrid               # hybrid | semantic | syntactic
```

The mock mode is the default in automated tests and may use deterministic, versioned response fixtures. Live mode requires explicit configuration.

### 4.3 Versioned agent prompts

Every agent has a distinct, editable, versioned system prompt. Prompts are stored as package resources, never hidden inline in agent logic:

```text
src/bpmn_adapt/prompts/
├── __init__.py
├── orchestrator_v1.md
├── analyst_v1.md
├── modeler_v1.md
└── experimenter_v1.md
```

Each prompt contains a declared prompt ID/version, role boundaries, allowed inputs, required JSON schema, refusal conditions, and citation/provenance requirements. The configuration stores the selected prompt version, and the DB records prompt ID/version for every LLM interaction.

## 5. Data compatibility and canonical domain contracts

The ingestion layer must map the present folder layout without rewriting source files:

- BPMN XML (`.bpmn`, `.bpmn2`, `.bpmn2.xml`, or XML);
- narrative description;
- `Rules.txt` and `Resources.txt`;
- `Remove_requests.txt` and `Re_Add_Request.txt`;
- `states.txt`, `RagData.txt`, and `testcasees.txt`.

Typed contracts shall include `ProcessDefinition`, `ProcessVersion`, `RuntimeState`, `TokenState`, `ResourceFact`, `Rule`, `AdaptationRequest`, `RetrievedEvidence`, `FeasibilityDecision`, `AtomicChange`, `MigrationPlan`, `CandidateModel`, `ExperimentScenario`, `ExperimentReport`, and `RunProvenance`.

Source data is immutable input. Candidate BPMN models, generated traces, retrieved evidence, and reports are versioned outputs outside the source folders.

### 5.1 Folder-agnostic, process-agnostic execution requirement

The final system shall operate on **each valid process/dataset folder independently**. It must contain no process-specific code, hard-coded BPMN element names, fixed rule/resource values, or manually altered pipeline logic for an individual folder.

For any selected folder, a user shall be able to supply only the folder path and a user request (natural-language or structured). The system shall then execute the complete Proposed Approach end-to-end for that folder:

1. ingest and validate the folder's BPMN, narrative, rules, resources, runtime states, RAG examples, and test cases;
2. initialise or select the folder-scoped DB records and RAG index;
3. load the configured, versioned prompts and LLM/API adapter;
4. invoke the Orchestrator Agent, Analyst Agent, Modeler Agent, and Experimenter Agent in the defined sequence;
5. perform evidence retrieval, feasibility validation, temporal planning, BPMN mutation, token migration, simulation, evaluation, and final approval/rejection;
6. persist a folder-scoped provenance record, model-version lineage, retrieval log, traces, metrics, and reproducible report artefacts;
7. expose the identical workflow through both the GUI and CLI.

The GUI shall provide a folder selector and the CLI shall accept a folder-path argument. Both shall call the same application service and produce the same typed result schema. Each run shall isolate its DB namespace/index namespace and output directory by stable folder identifier plus run identifier, preventing evidence or state from one process folder from being silently applied to another.

## 6. End-to-end workflow

1. GUI or CLI submits a request for a selected process instance/state.
2. Orchestrator creates a run and records the exact configuration and prompt versions.
3. Analyst gathers DB facts and hybrid-RAG evidence, applies deterministic constraints, and returns a decision.
4. If rejected, the Orchestrator returns cited reasons and stores the result.
5. If approved, Modeler produces the candidate BPMN version and migration plan.
6. Experimenter validates and simulates the candidate.
7. If the report fails and retry budget remains, the Orchestrator sends the structured failure to Modeler for correction.
8. If the report passes, the Orchestrator grants final approval, stores the version/provenance, and makes the candidate available for export or deployment.
9. The completed case and its evidence may be indexed as a new RAG record only after approval, with lineage preserved.

## 7. Interfaces

### CLI

The CLI shall expose equivalent research functions: `ingest`, `index-rag`, `analyse`, `adapt`, `simulate`, `evaluate`, `report`, and `gui`. It shall support JSON output and configuration selection for automated runs.

### GUI

The GUI shall support dataset/process/state selection; request entry; DB facts; RAG evidence and scores; analyst decision; candidate BPMN diff; migration map; simulation traces/failures; approval status; configuration visibility; and export of reports. The GUI is a presentation layer and must call the same application services as the CLI.

## 8. Evaluation protocol

The experiment runner shall execute the proposed complete system and these ablations/baselines:

1. Complete multi-agent hybrid-RAG system.
2. No-simulation/self-correction baseline.
3. No-RAG baseline.
4. Syntactic-only RAG, semantic-only RAG, and hybrid RAG.
5. Mock/offline versus configured live-LLM runs, reported separately.

Ground truth is multi-layered rather than a single undifferentiated accuracy value: expected request decision; rule/resource conflict reasoning; structural adaptation; token migration; executability; and RAG-evidence usefulness. For remove/re-add scenarios, the original BPMN is the restoration oracle, enabling exact restoration, graph-edit-distance, and post-re-add trace comparisons. RAG must not be assumed to improve accuracy merely because it grows; the ablations test that claim.

Metrics include XML validity, graph validity, simulation-success rate, token-preservation rate, deadlock-recovery rate, constraint-violation rate, structural distance where an oracle exists, evidence quality, retries, latency, and error classes. All results must identify dataset split, random seed, configuration fingerprint, prompt version, LLM/embedding model, and code version.

## 9. Implementation plan and to-do list

### Phase 1 — Foundation and reproducibility

- [ ] Create the package layout, typed configuration, `.env.example`, `.gitignore`, dependency policy, and test tooling.
- [ ] Define all canonical domain contracts and repository interfaces.
- [ ] Implement SQLite repositories and PostgreSQL conformance tests against the same interfaces.
- [ ] Implement run/provenance recording and immutable experiment-output directories.

### Phase 2 — Dataset and BPMN core

- [ ] Implement folder discovery and strict parsers for all present source files.
- [ ] Implement BPMN XML parser, control-flow graph, versioning, diff, and safe exporter.
- [ ] Implement runtime-state/token model and deterministic rule/resource validators.

### Phase 3 — Independent knowledge and LLM services

- [ ] Implement `LLMClient`, provider adapters, typed settings, rate limiting, retries, and deterministic mock client.
- [ ] Create versioned prompt files and prompt-loading/recording service.
- [ ] Implement RAG indexing, syntactic filters, semantic embeddings, hybrid ranking, and retrieval logging.
- [ ] Add RAG ablation modes and deterministic retrieval tests.

### Phase 4 — Four independent agents

- [ ] Implement `AnalystAgent` with feasibility/temporal-alternative decisions.
- [ ] Implement `ModelerAgent` with atomic edits and migration plans.
- [ ] Implement `ExperimenterAgent` with simulation and structured failures.
- [ ] Implement `OrchestratorAgent` with sequencing, retry budget, provenance, and final approval.

### Phase 5 — Interfaces and reporting

- [ ] Implement the CLI application services and JSON/CSV report exports.
- [ ] Implement the GUI using the same application services, without duplicating domain logic.
- [ ] Implement result tables, trace views, audit exports, and thesis-ready figures.

### Phase 6 — Validation and experiments

- [ ] Add unit tests for each component and prompt/schema contract tests.
- [ ] Add integration tests for complete successful, rejected, migration-failure, and retry-exhaustion flows.
- [ ] Run dataset-wide experiments and all ablations.
- [ ] Produce a reproduction guide, methodology appendix, and dataset/limitations statement.

## 10. Non-goals and safety boundaries

- The first version will not directly connect to or alter a live production process engine.
- An LLM cannot bypass deterministic rule/resource checks or final Experimenter validation.
- Secrets are not committed, displayed, or persisted in provenance records.
- A successful simulation is reported as empirical validation within the configured simulator, not as an unqualified proof of correctness.
