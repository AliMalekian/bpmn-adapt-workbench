# Methodology

## Research question and unit of analysis

The system evaluates whether governed multi-agent reasoning plus deterministic BPMN assurance can produce feasible, structurally correct, executable, provenance-rich runtime adaptations. The unit is a `(folder checksum, scenario ID, variant, seed, configuration fingerprint)` observation. Process-family separation should be used for confirmatory train/development/test splits.

## Architecture and authority

The Orchestrator sequences Analyst → Modeler → Experimenter with bounded retries and final gates. The authoritative DB stores current definitions/versions, state, rules, resources, requests, decisions, candidates, validation/simulation, approvals and provenance. RAG stores advisory historical cases and retrieval/index records. A retrieved case can motivate or explain a proposal but cannot override current DB constraints.

The Analyst combines current facts, compatible evidence, and temporal search. The planner explores current, reversible backward, and future/resource-release transitions under state/depth/time bounds. Alternatives retain time, budget and risk components, Pareto status and deterministic weighted selection. The Modeler converts approved intent to a typed transactional ChangeSet. The Experimenter aggregates XSD, semantic, formal and simulation outcomes and returns structured failures for bounded repair.

## RAG methods

The production semantic method uses normalized SentenceTransformer dense embeddings with pinned model/revision/device metadata. The durable local store atomically swaps data/manifest; pgvector provides the live SQL backend. The syntactic channel uses lexical/BM25-style scoring. Fusion logs scope filters, all candidates, semantic/syntactic/final scores, order, model key and fusion version. `hash_test` exists only for dependency-free deterministic tests and is never relabeled neural.

Positive cases require successful validation and approval; incoming/candidate data stays in core first. Negative evidence is labeled separately. Revocation marks records inactive. Compatible retrieval filters process identity/family, operation, source version and active status.

## Adaptation assurance

Mutations operate on a copy and commit only when the full ChangeSet succeeds. Supported typed edits cover nodes, flows, attributes/names, gateway types, conditions/default flow, remove/re-add and compounds. Results include source/candidate checksums, inverse operations, structural diff, and token/scope/variable migration instructions. Unmappable active constructs are blocking diagnostics.

Validation order is secure XML parsing and OMG XSD, semantic validators, formal conversion/soundness when enabled, then bounded trace simulation and optional engine checks. Unsupported constructs produce `UNSUPPORTED`, never an optimistic pass.

## Baselines and ablations

Every evaluated scenario uses the same immutable manifest for: conversational; no-simulation; no-RAG (`none`); syntactic-only; semantic-only; hybrid; and hybrid after approved updates. Remove/re-add uses the original BPMN as a strong restoration oracle. Any before/after RAG improvement is a hypothesis to test, not an assumption.

## Ground truth and metrics

Ground truth is layered:

1. request-level decision and feasibility;
2. cited constraint/rule/resource reasoning;
3. node/edge structural edit and restoration;
4. token, scope and variable preservation;
5. XSD/semantic/formal/engine executability and deadlock recovery;
6. evidence relevance and ranking;
7. latency, LLM token usage and monetary cost.

Missing or contradictory labels are `NOT_EVALUABLE` and excluded with visible denominators. Metrics include decision accuracy, constraint precision/recall where labeled, labeled node/edge graph distance, normalized restoration, aggregate token/variable preservation, pass rates, recall@k, MRR, nDCG, ANN recall, latency, tokens and cost.

## Statistical analysis

Paired binary outcomes use exact McNemar. Continuous paired differences are checked for assumptions; eligible data use paired t, otherwise Wilcoxon or a seeded permutation fallback. Reports include bootstrap confidence intervals, effect sizes, sample/denominator counts and Holm family-wise correction. Statistical output is regenerated from raw long-form JSON/CSV, never hand-edited.

## Reproducibility and threat controls

Source folders are immutable. Identities and manifests are content-addressed. Runs store prompt/model/index versions, redacted configuration fingerprint, seed, checksums, decisions and receipts. Search, retries, subprocesses and calls are bounded. External timeout after side effect uses idempotency and reconciliation. Duplicate folder names cannot collide. Interrupted vector rebuild preserves the last readable index. Missing truth, unsupported BPMN and unavailable services remain explicit statuses.

Threats include dataset leakage across similar process families, synthetic/templated test cases, LLM nondeterminism, model/version drift, imperfect BPMN-to-Petri semantics, vendor-extension differences, and limited live-engine diversity. Report these with every thesis result.
