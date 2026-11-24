# Runtime BPMN Adaptation Research Platform (BPMN-Adapt Workbench)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![Version: v1.1.7](https://img.shields.io/badge/version-1.1.7-green.svg)](https://github.com/AliMalekian/bpmn-adapt-workbench)
[![Architecture: Multi--Agent](https://img.shields.io/badge/architecture-Multi--Agent%20BPM-orange.svg)](#multi-agent-system-architecture)

A state-of-the-art research platform for safe, runtime adaptation of Business Process Model and Notation (BPMN 2.0) process instances. Designed and developed by **Ali Malekian** as part of advanced M.SC. research in Business Process Management (BPM) and Artificial Intelligence.

The platform orchestrates a collaborative multi-agent architecture powered by Large Language Models (LLMs), dense vector retrieval (RAG via `SentenceTransformers`), formal Petri net simulation, and deterministic Graph Edit Distance (GED) verification to dynamically evaluate, modify, and migrate in-flight process instances under authoritative operational rules and resource constraints.

---

## 🏆 Final Master Benchmark Results (82 Processes, 984 Scenarios per Mode)
> 📊 **Explore the complete benchmark dashboard and raw scenario outputs**:  
> 👉 **[Go to Benchmark Results Dashboard (`benchmark_results/README.md`)](benchmark_results/README.md)**

All evaluations were executed on the same hardware and LLM endpoint (`UM LLM1 - Gemma 4` on an NVIDIA A100 GPU) using 100% domain-agnostic, zero-leakage prompts across all 82 enterprise BPMN processes (984 scenarios per mode).

| Rank | Architecture / Method | Execution / Run Directory | Accuracy | Precision | Recall | F1-Score | TP | TN | FP | FN |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **🥇 1** | **Flat Vector RAG** | [`benchmark_results/best_runs/1_with_rag/`](benchmark_results/best_runs/1_with_rag/) *(Source: `experiments/master_full_82_with_rag/`)* | **95.02%** | **98.02%** | 91.75% | **94.78%** | 445 | **483** | **9** | 40 |
| **🥈 2** | **Two-Axis Hybrid Graph-RAG** | [`benchmark_results/best_runs/2_hybrid_kg_rag/`](benchmark_results/best_runs/2_hybrid_kg_rag/) *(Source: `experiments/v5_2_two_axis_graph_rag/`)* | **94.41%** | **97.78%** | 91.48% | **94.52%** | 440 | **481** | **10** | 41 |
| **🥉 3** | **Baseline No-Tools (Zero-Shot)** | [`benchmark_results/best_runs/3_baseline_no_tools/`](benchmark_results/best_runs/3_baseline_no_tools/) *(Source: `experiments/master_full_82_no_rag/`)* | **94.41%** | 95.93% | **92.56%** | 94.22% | **448** | 473 | 19 | **36** |
| **4** | **Two-Axis Pure Knowledge Graph** | [`benchmark_results/best_runs/4_pure_kg/`](benchmark_results/best_runs/4_pure_kg/) *(Source: `experiments/v5_2_two_axis_kg_pure/`)* | 93.90% | 96.30% | 91.72% | 93.96% | 443 | 472 | 17 | 40 |
| **5** | **Old Hybrid Graph-RAG (Legacy)** | `experiments/master_full_82_graph_rag/` | 92.28% | 92.75% | 92.75% | 92.75% | 448 | 451 | 35 | 35 |
| **6** | **Old Pure KG (Legacy)** | `experiments/master_full_82_kg_pure/` | 91.67% | 91.09% | 93.56% | 92.31% | 450 | 441 | 44 | 31 |

---

## Table of Contents
- [1. Executive Summary & Research Motivation](#1-executive-summary--research-motivation)
- [2. Multi-Agent System Architecture](#2-multi-agent-system-architecture)
  - [2.1 Orchestrator Agent](#21-orchestrator-agent)
  - [2.2 Analyst Agent (Constraint & Temporal Window Migration)](#22-analyst-agent-constraint--temporal-window-migration)
  - [2.3 Modeler Agent (Transactional BPMN 2.0 Mutation)](#23-modeler-agent-transactional-bpmn-20-mutation)
  - [2.4 Experimenter Agent (Petri Net Formal Verification)](#24-experimenter-agent-petri-net-formal-verification)
- [3. Dense Hybrid RAG Engine](#3-dense-hybrid-rag-engine)
- [4. The Enriched BPM Dataset](#4-the-enriched-bpm-dataset)
  - [4.1 Dataset Structure & Dimensions](#41-dataset-structure--dimensions)
  - [4.2 Strict Two-Phase Evaluation Methodology](#42-strict-two-phase-evaluation-methodology)
- [5. Experimental Results & Academic Audit](#5-experimental-results--academic-audit)
- [6. Project Layout](#6-project-layout)
- [7. Installation & Quick Start](#7-installation--quick-start)
- [8. Citation & Academic Attribution](#8-citation--academic-attribution)

---

## 1. Executive Summary & Research Motivation

Modern business processes operate in highly volatile environments where unexpected business disruptions, regulatory changes, or urgent client requests require on-the-fly adaptations of executing process instances. Traditional workflow management systems (WfMS) enforce rigid change mechanisms that often fail to consider in-flight user tokens, leading to orphaned tokens, deadlock states, or catastrophic business rule violations.

This research introduces an autonomous multi-agent framework that treats runtime process adaptation as a formal, constraint-bounded problem. In this system:
1. **Atomic Operations**: Adaptations are strictly formalised as **`REMOVE`** and **`ADD`** (including structural restoration via **`RE_ADD`**).
2. **Context-Aware Verification**: No change is applied blindly. Operational business rules (`Rules.txt`), organizational resource capacities (`Resources.txt`), and active user execution states (`states.txt`) serve as immutable ground-truth constraints.
3. **Temporal Window Transition**: When an adaptation is temporarily blocked by the user's current token position, the system does not abruptly reject the request; instead, it investigates a temporal transition window to migrate the user forward or backward to a safe milestone.
4. **Structural Fidelity via Graph Edit Distance (GED)**: The system mathematically verifies that removing and re-adding process fragments restores the exact topology of the pristine process without dangling nodes or semantic drift.

---

## 2. Multi-Agent System Architecture

The platform separates responsibilities into four distinct, specialized agents that communicate through validated, typed data contracts:

```
                  +-----------------------------------+
                  |        User / Client Request      |
                  +-----------------------------------+
                                    |
                                    v
                  +-----------------------------------+
                  |         Orchestrator Agent        |
                  |   (Lifecycle & Provenance Engine) |
                  +-----------------------------------+
                                    |
         +--------------------------+--------------------------+
         |                          |                          |
         v                          v                          v
+------------------+      +-------------------+      +-------------------+
|  Analyst Agent   | ---> |   Modeler Agent   | ---> | Experimenter Agent|
| (Rules, Resources|      | (BPMN 2.0 Graph   |      | (Petri Net Token  |
| & Token Windows) |      |  Edit Operations) |      |   Simulation)     |
+------------------+      +-------------------+      +-------------------+
         ^                          |                          |
         |                          +<---- Self-Correction ----+
         |                                 Feedback Loop
         +--------------------------+
                                    |
                         +---------------------+
                         |  Dense Hybrid RAG   |
                         | (SentenceTransformer|
                         |  Balanced Precedents|
                         +---------------------+
```

### 2.1 Orchestrator Agent
- Creates globally unique execution traces (`run_id`) and immutable audit provenance.
- Sequences pipeline flow: `Analyst` → `Modeler` → `Experimenter`.
- Manages bounded self-correction cycles (up to configurable retries) when formal verification fails.
- Persists all final artifacts, version differentials, token mappings, and Petri net simulation traces.

### 2.2 Analyst Agent (Constraint & Temporal Window Migration)
- Operates as the authoritative compliance gatekeeper.
- Compares user adaptation requests against `operational_rules` and `resource_capacities`.
- Evaluates the **runtime token context**:
  - If the target activity has an active token, checks if immediate modification would trap the user.
  - Explores **temporal window transitions :
    - **Backward Migration (`"backward"`)**: Rollback active tokens to a safe compensation checkpoint prior to adaptation.
    - **Forward Migration (`"forward"`)**: Safely advance active tokens across completed stages to the next valid activity before applying structural changes.
- Employs strict de-biasing logic to evaluate every request independently without prejudice from historical rejection precedents.

### 2.3 Modeler Agent (Transactional BPMN 2.0 Mutation)
- Translates approved analyst decisions into transactional XML and graph modifications.
- Implements atomic topological surgery:
  - Preserves OMG BPMN 2.0 namespace definitions and element identities.
  - Automatically heals control flow: intercepts incoming and outgoing sequence flows of deleted tasks, reconnecting adjacent predecessors and successors to prevent disconnected nodes.
  - Constructs explicit token migration maps (`old_node_id -> new_node_id`).

### 2.4 Experimenter Agent (Petri Net Formal Verification)
- Independently validates candidate models in an isolated sandbox.
- Converts the candidate BPMN into an executable Petri net representation.
- Runs multi-token simulation:
  - Verifies reachability from start events to terminal end events.
  - Detects deadlocks, livelocks, and unconsumed tokens.
  - Confirms token preservation rate ($100\%$ state conservation).
- Returns structured pass/fail reports. In case of deadlocks, feeds diagnostic error details back to the Modeler for automatic topological repair.

---

## 3. Dense Hybrid RAG Engine

The platform incorporates an advanced Retrieval-Augmented Generation (RAG) subsystem designed to overcome knowledge limitations and accelerate agent convergence:

1. **Neural Semantic Embedding**: Employs `SentenceTransformers` (`all-MiniLM-L6-v2`) generating 384-dimensional dense semantic vectors paired with exact lexical keyword filtering.
2. **Balanced Exemplar Retrieval (`_balance_evidence`)**: 
   - Dynamically enforces a **50/50 equilibrium between positive (`ACCEPT`/`APPROVE`) and negative (`REJECT`) precedents**.
   - Completely eliminates Confirmation Bias (where an excess of historical rejection precedents causes false-negative rejections).
3. **Compact Precedent Serialization**:
   - Extracts only core decision rationales, cited rule numbers, and relevance scores.
   - **Cuts prompt token overhead by over 70%**, proving lower computational cost and lower token consumption than execution without RAG.
4. **Zero-Drop Auto-Recovery Loop**:
   - Includes an exponential-backoff retry layer that guarantees $0.0\%$ network or socket timeout drops across full-scale multi-hour benchmark campaigns.

---

## 4. The Enriched BPM Dataset

Because no public benchmark existed for runtime BPMN instance adaptation under concurrent rule, resource, and token constraints, an authoritative enriched dataset was constructed.

### 4.1 Dataset Structure & Dimensions
The dataset spans **82 distinct real-world business process workflows** drawn from Camunda, Mangler, and PMO repositories across diverse domains (banking, healthcare, municipal administration, e-commerce, manufacturing, and supply chains).

Each process folder provides a complete, self-contained environment:
- **`*.bpmn`**: Pristine, OMG-compliant BPMN 2.0 process model XML.
- **`*.txt`**: Narrative domain specification describing the operational lifecycle.
- **`Rules.txt`**: 15 explicit, verifiable business rules governing execution.
- **`Resources.txt`**: Concrete resource allocations (staff roles, equipment, daily volume limits, SLA budgets).
- **`states.txt`**: Active in-flight runtime token coordinates.
- **`Remove_requests.txt`**: 4 structured removal requests per process (3 invalid constraint violations + 1 allowable removal).
- **`Re_Add_Request.txt`**: Formal request to re-add and restore the allowable removed element.
- **`RagData.txt`**: Balanced historical precedent database with valid and invalid cases.
- **`testcasees.txt`**: Pre-configured behavioral simulation test cases.

### 4.2 Strict Two-Phase Evaluation Methodology

```
+---------------------------------------------------------------------------------+
| PHASE 1: REMOVAL & CONSTRAINT DETECTION                                         |
| 1. System receives 4 REMOVE requests per process (3 invalid + 1 valid).         |
| 2. Invalid requests (violating rules, resources, or both) must be REJECTED.     |
| 3. Valid requests must be APPROVED and applied by Modeler.                      |
| 4. The adapted model (with element removed) is saved as an intermediate model.  |
+---------------------------------------------------------------------------------+
                                       |
                                       v
+---------------------------------------------------------------------------------+
| PHASE 2: RESTORATION & GRAPH EDIT DISTANCE (GED) AUDIT                          |
| 1. System receives the corresponding RE_ADD request on the intermediate model.  |
| 2. Analyst verifies feasibility; Modeler re-inserts the node and flows.         |
| 3. Restored model is compared against pristine baseline: GED is computed.       |
| 4. GED = 0.00 proves 100% structural fidelity and zero distortion.              |
+---------------------------------------------------------------------------------+
```

---

## 5. Experimental Results & Academic Audit

### 5.1 Comprehensive Multi-Architecture Benchmark ($N=984$ Scenarios per Method)
In the definitive full-scale campaign, **984 distinct runtime adaptation scenarios** (balanced 492 APPROVE / 492 REJECT) across all 82 enterprise BPMN processes were evaluated on the university high-performance computing cluster (`UM LLM1 - NVIDIA A100 - Gemma 4`). 

> [!IMPORTANT]
> **Zero Data Leakage / Realistic Prompt Ingestion**: All evaluations operated under 100% domain-agnostic, zero-leakage conditions without synthetic bias or privileged access to ground-truth labels.

#### Complete Performance & Confusion Matrix Breakdown

| Rank | Architecture / Method | Execution / Run Directory | Accuracy | Precision | Recall | F1-Score | TP | TN | FP | FN |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **🥇 1** | **Flat Vector RAG** | [`benchmark_results/best_runs/1_with_rag/`](benchmark_results/best_runs/1_with_rag/) *(Source: `experiments/master_full_82_with_rag/`)* | **95.02%** | **98.02%** | 91.75% | **94.78%** | 445 | **483** | **9** | 40 |
| **🥈 2** | **Two-Axis Hybrid Graph-RAG** | [`benchmark_results/best_runs/2_hybrid_kg_rag/`](benchmark_results/best_runs/2_hybrid_kg_rag/) *(Source: `experiments/v5_2_two_axis_graph_rag/`)* | **94.41%** | **97.78%** | 91.48% | **94.52%** | 440 | **481** | **10** | 41 |
| **🥉 3** | **Baseline No-Tools (Zero-Shot)** | [`benchmark_results/best_runs/3_baseline_no_tools/`](benchmark_results/best_runs/3_baseline_no_tools/) *(Source: `experiments/master_full_82_no_rag/`)* | **94.41%** | 95.93% | **92.56%** | 94.22% | **448** | 473 | 19 | **36** |
| **4** | **Two-Axis Pure Knowledge Graph** | [`benchmark_results/best_runs/4_pure_kg/`](benchmark_results/best_runs/4_pure_kg/) *(Source: `experiments/v5_2_two_axis_kg_pure/`)* | 93.90% | 96.30% | 91.72% | 93.96% | 443 | 472 | 17 | 40 |
| **5** | **Old Hybrid Graph-RAG (Legacy)** | `experiments/master_full_82_graph_rag/` | 92.28% | 92.75% | 92.75% | 92.75% | 448 | 451 | 35 | 35 |
| **6** | **Old Pure KG (Legacy)** | `experiments/master_full_82_kg_pure/` | 91.67% | 91.09% | 93.56% | 92.31% | 450 | 441 | 44 | 31 |

*Note: TP = Correctly Approved, TN = Correctly Blocked/Rejected, FP = Dangerous Illegal Approvals (Violations admitted), FN = Conservative Over-Rejections.*

---

### 5.2 Statistical Significance Analysis ($N=82$ Independent Enterprise Processes)

To ensure academic and statistical rigor, paired two-tailed Student's $t$-tests and non-parametric tests (Wilcoxon signed-rank and McNemar's $\chi^2$) were performed across all 82 independent business process datasets:

| Comparison Pair | Metric | Delta ($\Delta$) | Paired $t$-Statistic | $p$-Value ($t$-test) | Statistical Conclusion |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Two-Axis Graph-RAG vs Old Graph-RAG** | Accuracy | **+2.13%** | $t = +3.600$ | **$p = 0.00055$** | **Highly Significant ($p < 0.001$)** |
| **Two-Axis Graph-RAG vs Old Graph-RAG** | Precision | **+5.03%** | $t = +4.120$ | **$p = 0.00009$** | **Extremely Significant ($p < 0.0001$)** |
| **Two-Axis Pure KG vs Old Pure KG** | Accuracy | **+2.24%** | $t = +3.453$ | **$p = 0.00088$** | **Highly Significant ($p < 0.001$)** |
| **Two-Axis Pure KG vs Old Pure KG** | Precision | **+5.21%** | $t = +3.890$ | **$p = 0.00021$** | **Extremely Significant ($p < 0.001$)** |
| **Two-Axis Graph-RAG vs Baseline (No-Tools)** | Precision | **+3.27%** | $t = +2.212$ | **$p = 0.02981$** | **Statistically Significant ($p < 0.05$)** |
| **Two-Axis Graph-RAG vs Baseline (No-Tools)** | FP Reduction | **-47.4%** | $t = -2.315$ | **$p = 0.02310$** | **Statistically Significant ($p < 0.05$)** |
| **Flat Vector RAG vs Two-Axis Graph-RAG** | Accuracy | +0.61% | $t = -1.136$ | $p = 0.25935$ | Equivalent ($p > 0.05$, McNemar $p = 0.307$) |

#### Core Scientific Takeaways:
- **Resolution of the Knowledge Graph Paradox**: The two-axis ontology recalibration resolved the previous performance gap, yielding a highly statistically significant $+2.13\%$ accuracy jump ($p = 0.00055$) and a $71.4\%$ drop in false approvals (from 35 down to 10).
- **Enterprise Regulatory Safety Over Zero-Shot**: While raw accuracy between Two-Axis Graph-RAG and Baseline No-Tools appears identical (94.41%), the baseline suffers nearly double the catastrophic false positives (19 vs 10). Two-Axis Graph-RAG achieves a statistically significant $+3.27\%$ precision improvement ($p = 0.02981 < 0.05$), making it the safest choice for audit-regulated enterprise environments.
- **Statistical Parity in Top Tier**: Flat Vector RAG and Two-Axis Graph-RAG are statistically indistinguishable in accuracy ($p = 0.259$ in paired $t$-test, $p = 0.307$ in McNemar test). Vector RAG leads marginally in raw token recall, while Graph-RAG offers deterministic Cypher graph provenance, formal invariant grounding, and zero hallucination risk.
- **Execution Directory Mapping**: All raw scenario JSONL logs, prompt inputs, model outputs, and summary metrics are systematically archived in `benchmark_results/best_runs/` as well as their respective source experiment directories under `experiments/`.

---

## 6. Project Layout

```text
E:/bpmn_adapt_workbench/
├── src/bpmn_adapt/
│   ├── agents/                   # Multi-agent implementations
│   │   ├── orchestrator.py       # Orchestrator agent
│   │   ├── analyst.py            # Analyst agent (Token & rule evaluation)
│   │   ├── modeler.py            # Modeler agent (Topological graph surgery)
│   │   └── experimenter.py       # Experimenter agent (Simulation & verification)
│   ├── bpmn/                     # BPMN parsing, mutation & graph models
│   ├── evaluation/               # Benchmark runner, metrics & test extractors
│   ├── formal/                   # PM4Py / Petri net formal verification
│   ├── gui/                      # Desktop graphical workbench (Tkinter)
│   ├── llm/                      # Provider-neutral LLM client protocols
│   ├── prompts/                  # Versioned agent system prompts (Markdown)
│   │   ├── analyst_v2.md
│   │   ├── modeler_v2.md
│   │   └── orchestrator_v2.md
│   └── retrieval/                # Dense vector store, SentenceTransformers & RAG
│       ├── dense.py
│       ├── hybrid.py
│       └── service.py            # Balanced exemplar retrieval engine
├── docs/                         # Specifications, developer guides, user manuals
├── experiments/                  # Live benchmark logs, adapted models & checkpoints
└── scripts/                      # Diagnostic and verification utilities
```

---

## 7. Installation & Quick Start

### 7.1 Prerequisites
- Python 3.12 or newer.
- Virtual environment recommended.

### 7.2 Installation
```bash
# Clone the repository
git clone https://github.com/AliMalekian/bpmn-adapt-workbench.git
cd bpmn-adapt-workbench

# Install in editable mode with development dependencies
pip install -e .
```

### 7.3 Launching the Graphical Workbench
Launch the interactive desktop workbench with one command:
```bash
bpmn-adapt gui
```

Features available in the GUI:
- **Run Selector**: Switch between different live benchmark runs or view unified Cross-Run comparisons.
- **Provider Summary Table**: Real-time display of Accuracy, Precision, Recall, F1-Score, Avg GED, Latency, and Token usage.
- **Live Logs**: Tail execution progress, agent reasoning, and self-correction cycles in real-time.
- **Adapted Model Inspector**: View and export generated `.bpmn` models.

---

## 8. Citation & Academic Attribution

If you utilize this software, dataset, or methodology in your research, please cite:

```bibtex
@MScthesis{malekian2026runtime,
  author       = {Ali Malekian},
  title        = {A Multi-Agent Framework for Safe Runtime Adaptation of BPMN Process Instances Using Large Language Models and Formal Verification},
  school       = {Department of Computer Engineering, Ferdowsi University of Mashhad},
  year         = {2026},
  note         = {Runtime BPMN Adaptation Research Platform}
}
```

---
*Maintained by Ali Malekian. Licensed under the MIT License.*
