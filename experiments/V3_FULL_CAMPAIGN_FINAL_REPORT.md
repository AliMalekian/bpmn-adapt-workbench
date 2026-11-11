# Version 3 Final Benchmark Campaign Report: Closed-Loop Adversarial + Structural RAG

**Date:** 2026-11-11  
**Cluster:** University of Marburg LLM1 Cluster (`UM LLM1 - NVIDIA A100 - Gemma 4`)  
**Scope:** Full 82 Standard BPMN Processes across 984 Scenarios (Phase 2: With-RAG, Phase 3: Without-RAG)  
**Total Tests Evaluated:** 1,968 scenario runs  

---

## 1. Executive Summary & Full Results

| Metric | V3 With-RAG | V3 No-RAG | V2 Baseline With-RAG (`3b420f0`) | V2 Baseline No-RAG (`3b420f0`) |
| :--- | :---: | :---: | :---: | :---: |
| **Total Scenarios** | 984 | 984 | 984 | 984 |
| **Overall Accuracy** | **94.8171%** (933 / 984) | **95.0203%** (935 / 984) | 94.5122% (930 / 984) | 93.8008% (923 / 984) |
| **Precision** | **99.3289%** | **99.5516%** | 98.0306% | 96.1538% |
| **Recall** | 90.7975% | 90.8163% | 91.2424% | 91.8367% |
| **F1-Score** | **94.8718%** | **94.9786%** | 94.5148% | 93.9457% |
| **True Positives (TP)** | 444 | 445 | 448 | 450 |
| **False Positives (FP)** | **3** | **2** | 9 | 18 |
| **True Negatives (TN)** | 489 | 490 | 482 | 473 |
| **False Negatives (FN)** | 45 | 45 | 43 | 40 |
| **ADD Accuracy** | **99.5935%** (490 / 492) | **99.7967%** (491 / 492) | 97.3577% | 95.7317% |
| **REMOVE Accuracy** | **90.0407%** (443 / 492) | **90.2439%** (444 / 492) | 91.6667% | 91.8699% |
| **Average Latency** | 32.46s | 33.12s | 30.32s | 28.54s |

---

## 2. Analysis of Errors in Version 3

### 2.1 The Remaining False Positives (FP)
Across all 984 scenarios, catastrophic Type-I errors dropped from 18 to only 2-3:
1. `#39` (`Camunda-Self-service-restaurant_REMOVE_3`): Target `Inform chef` (Only failed in With-RAG due to cross-process precedent; No-RAG correctly rejected it!).
2. `#278` (`Mangler-Robotic Burger Seller_REMOVE_2`): Target `Enthusiastic status updates every 30 seconds while the burger is prepared` (Humorous notification step).
3. `#854` (`Pmo-job application_REMOVE_2`): Target `Send rejection Email task`.

### 2.2 The False Negatives (FN) - The Key Discovery
An exhaustive audit revealed that **43 of the 45 FNs (95.6%)** belong strictly to the single scenario index: `REMOVE_4`.
- `REMOVE_1`, `REMOVE_2`, `REMOVE_3`: 98.8% accuracy.
- `REMOVE_5`: 100% accuracy (82 / 82).
- `REMOVE_6`: 97.6% accuracy (80 / 82).
- `REMOVE_4`: Failed in 43 processes because:
  1. Target element parsing regex produced `Target: 'The'` instead of the actual activity name in 15 PMO datasets.
  2. The LLM conflated timing/milestone preconditions (e.g., *"Process closes only after final report is distributed"*) with mandatory task requirements.
  3. Preceding sequence bias in RAG: Requests 1, 2, 3 were rejected and indexed into RAG memory immediately before Request 4 was evaluated, poisoning Request 4 with fresh intra-process rejections.

---

## 3. Transition to Version 4 (Master Blueprint)

Version 4 will implement:
1. **Target Parser Regex Fix:** Resolving `The "..."` pattern and populating complete `target_node_context`.
2. **Deterministic Request Pre-processing:** Isolating operational request from user rationalization and pre-enriching graph context.
3. **Legal/Process Mandate Disambiguation Invariant:** Distinguishing timing milestones from mandatory task requirements in `analyst_v2.md`.
4. **Balanced Contrastive RAG Pairs (1:1):** Guaranteeing 1 positive exemplar and 1 negative exemplar with 70% semantic / 30% syntactic weighting.
5. **Symmetric Structural Alignment Filtering:** Rejecting precedents with `LOW` structural alignment for both APPROVE and REJECT.
