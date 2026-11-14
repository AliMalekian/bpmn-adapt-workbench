# Version 4 Benchmark Campaign: Full 82-Process Paired Evaluation & Epistemological Audit Report

**Date of Completion:** November 12–14, 2026  
**Execution Environment:** `UM LLM1` cluster (NVIDIA A100-SXM4-80GB, Model: `Gemma 4`)  
**Evaluation Scope:** 82 Real-World Enterprise Business Processes (Camunda, Mangler, PMO Industry Suites)  
**Total Executed Scenarios:** 1,968 runs (984 With-RAG + 984 No-RAG paired evaluations)  
**Methodology:** Full Closed-Loop Continual Learning with Verification Guardrails (Zero Synthetic Data)

---

## 1. Executive Summary & Core Statistical Findings

The Version 4 benchmark campaign was executed to rigorously evaluate the effect of adding historical case-based retrieval (RAG) to foundation large language models performing automated BPMN process adaptation. 

The primary finding is that **Passive Context Injection (Vanilla RAG) completely fails to produce a statistically significant advantage over a strong foundation LLM** ($p = 1.00000$ on McNemar's paired test).

| Metric | Version 4 With-RAG | Version 4 No-RAG | Delta |
| :--- | :---: | :---: | :---: |
| **Total Scenarios Evaluated** | 984 | 984 | — |
| **Overall Accuracy** | **95.43%** (939 / 984) | **95.53%** (940 / 984) | **-0.10%** |
| **Precision** | 98.69% | 98.70% | -0.01% |
| **Recall** | 92.07% | 92.28% | -0.21% |
| **F1-Score** | 95.27% | 95.38% | -0.11% |
| **False Positives (FP)** | **6** | **6** | 0 |
| **False Negatives (FN)** | 39 | 38 | +1 |
| **Milestone / Boundary Accuracy (`REMOVE_4`)** | 54.88% (45 / 82) | 54.88% (45 / 82) | 0.00% |

---

## 2. Statistical Significance Analysis (McNemar's Paired Test)

To determine whether the presence of RAG produces a statistically distinguishable decision distribution from No-RAG, an exact two-sided McNemar test was performed on the paired outcomes across all 984 scenarios.

### 2.1 Full Contingency Table ($N = 984$)

```
                        No-RAG Correct    No-RAG Incorrect
With-RAG Correct              939                0    (b)
With-RAG Incorrect              1  (c)          44
```

- **Both Correct:** 939 scenarios (95.43%)
- **Both Incorrect:** 44 scenarios (4.47%)
- **Discordant Pairs ($b + c$):** Exactly 1 scenario (0.10%)
  - With-RAG Correct / No-RAG Incorrect ($b$): 0
  - No-RAG Correct / With-RAG Incorrect ($c$): 1 (`Pmo-Online ordering platform_REMOVE_6`)
- **Identical Decisions:** 983 / 984 scenarios (**99.90% concordance**)
- **McNemar Exact $p$-Value:** **$p = 1.00000$**

**Conclusion:** The null hypothesis ($H_0$: Passive RAG and No-RAG have identical performance) cannot be rejected. Passive RAG is statistically indistinguishable from zero RAG.

---

## 3. Granular Category Breakdown

| Scenario Type | Total | With-RAG Correct | With-RAG Acc | No-RAG Correct | No-RAG Acc | Delta |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **ADD_1** (Standard Tasks) | 82 | 82 | 100.0% | 82 | 100.0% | +0.0% |
| **ADD_2** (Parallel Branches) | 82 | 82 | 100.0% | 82 | 100.0% | +0.0% |
| **ADD_3** (Event Handlers) | 82 | 82 | 100.0% | 82 | 100.0% | +0.0% |
| **ADD_4** (Multi-Instance Tasks) | 82 | 82 | 100.0% | 82 | 100.0% | +0.0% |
| **ADD_5** (Resource-Constrained) | 82 | 81 | 98.8% | 81 | 98.8% | +0.0% |
| **ADD_6** (Audit/Compliance Logging) | 82 | 82 | 100.0% | 82 | 100.0% | +0.0% |
| **REMOVE_1** (Direct Rule Violations) | 82 | 82 | 100.0% | 82 | 100.0% | +0.0% |
| **REMOVE_2** (Resource Capacity Bottlenecks) | 82 | 77 | 93.9% | 77 | 93.9% | +0.0% |
| **REMOVE_3** (Interface & Transmission Steps) | 82 | 81 | 98.8% | 81 | 98.8% | +0.0% |
| **REMOVE_4** (Administrative Milestones) | 82 | 45 | **54.9%** | 45 | **54.9%** | +0.0% |
| **REMOVE_5** (Optional Post-Completion Steps)| 82 | 82 | 100.0% | 82 | 100.0% | +0.0% |
| **REMOVE_6** (Organizational Audits & Surveys)| 82 | 81 | 98.8% | 82 | **100.0%** | **-1.2%** |

---

## 4. Root Cause Analysis (RCA): Why Passive RAG Failed

Forensic inspection of the 2,817 individual LLM call traces (`llm_calls.jsonl`) revealed three decisive architectural bottlenecks:

### 4.1 The Passive Context Injection Flaw (Zero Attention Allocation)
In Version 4, historical precedents were retrieved and appended to the prompt under the `historical_rag_evidence` JSON key. However, the schema and prompt never forced the LLM to process or cite this key. Because Gemma 4 had access to first-order primary evidence (the exact operational rules in `Rules.txt` and the process graph), it solved 99.9% of scenarios using primary rules alone, bypassing the historical precedents entirely.

### 4.2 Ceiling Effect on Explicit Rules
In categories `ADD_1` through `ADD_6` and `REMOVE_1`, `REMOVE_3`, `REMOVE_5`, the rules are deterministic and unambiguous. An A100-class foundation LLM achieves 98.8% to 100% accuracy on these without external memory. Adding RAG to explicit rule categories produces a mathematically hard ceiling where $\Delta \approx 0$.

### 4.3 Over-Conservatism on Ambiguous Nodes
In the single scenario where With-RAG diverged (`Pmo-Online ordering platform_REMOVE_6`), the task was an optional secondary satisfaction survey. The No-RAG model recognized that optional tasks do not breach mandatory rules and correctly approved it. The With-RAG model, lacking structured analogical grounding, misattributed general customer feedback rules to this optional step and falsely rejected it.

### 4.4 Disconnect in Query Preprocessing
In `analyst.py`, the RAG retriever was called with raw user text prior to regex cleaning, while the LLM received the cleaned text. This meant vector search operated on noisy uncleaned strings, introducing spurious semantic alignments.

---

## 5. Architectural Mandate for Version 5

To break the ceiling effect and achieve a statistically significant 2% to 5% overall performance delta ($p < 0.01$):
1. **Analogical Chain-of-Thought (ACoT):** The output schema must mandate an explicit `precedent_analogical_reasoning` field where the agent explicitly contrasts positive vs negative precedents before issuing a verdict.
2. **Precedent Authorization Engine:** When a rule is ambiguous (e.g., in `REMOVE_4` milestone tasks), the presence of a validated historical precedent must act as formal organizational authorization.
3. **Graph-Anchored RAG Queries:** Queries must be formed using structural graph tokens (`[Op] + [Target] + [Role] + [Context]`), eliminating semantic dilution.
4. **Epistemic Invariant Decoupling:** Keep formal graph connectivity strictly independent of precedents to prevent precedent-driven hallucinations while empowering policy flexibility.
