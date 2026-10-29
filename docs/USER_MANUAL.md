# BPMN Adapt Workbench — User Manual

## Overview
This workbench evaluates runtime adaptation of BPMN processes using a 4-agent pipeline (Orchestrator → Analyst → Modeler → Experimenter) with live LLM calls.

## Prerequisites
- Python 3.11 or 3.12 (3.14 also works with PYTHONPATH)
- Windows 10/11
- Internet connection (VPN required for AI Studio and Groq from Iran)
- API keys for at least one provider

## Installation
Clone the repository:
```bash
git clone <repo-url>
cd bpmn_adapt_workbench
```

Activate the environment:
```powershell
. .\scripts\setup_env.ps1
```

Install dependencies:
```bash
pip install -e .
```
(or install packages directly if version check fails).

## Top Form: "Process and request" Controls
The top form provides direct access to the core CLI command pipeline:
- **Process folder**: Full path to the target dataset folder containing BPMN diagrams, rules, resources, and state fixtures.
- **User request**: Natural language instruction describing the adaptation change (e.g., `Remove the task`, `Insert verification step`).
- **Target element**: Name or element ID of the BPMN node/activity targeted for adaptation (e.g., `Package goods`).
- **Runtime state**: Active execution marking or state fixture identifier (e.g., `STATE-01`, `state_1`).
- **Run ID**: Unique run identifier for provenance inspection, audit replay, or approval/rejection operations.
- **Operation**: BPMN mutation operator (`REMOVE`, `MODIFY`, `ADD`, `RE_ADD`).
- **Action**: Command pipeline to run (`ingest`, `inspect`, `index-rag`, `plan`, `adapt`, `validate`, `simulate`, `evaluate`, `approve`, `export`, `replay`).
- **Help Buttons (`?`)**: Every field has an inline `?` button that displays detailed contextual guidance.
- **Tab Info Buttons (`ℹ Info`)**: Every tab (1–14) features an info button in the top right opening a modal guide explaining inputs, outputs, widgets, and caveats.
1. Launch the GUI:
   ```bash
   bpmn-adapt gui
   ```
2. Go to the "Provider Configuration" tab.
3. For each provider you want to use:
   - Select the provider in the table.
   - Enter your API key in the "API Key" field.
   - Check the "Enabled" box.
   - Click "Test Connection" to verify.
   - Click "Save Provider".
4. To add a new custom provider:
   - Click "[+] Add Provider".
   - Fill in the fields.
   - Click "Save Provider".

## Configuring Providers (CLI)
```bash
# Set API key
bpmn-adapt providers set-key groq YOUR_GROQ_KEY

# Enable a provider
bpmn-adapt providers enable groq

# Test a provider
bpmn-adapt providers test groq

# List all providers
bpmn-adapt providers list
```

## Running a Manual Test
1. Go to the "Manual Test" tab.
2. Select a Provider.
3. Select a Dataset.
4. Choose an Operation (`REMOVE`, `MODIFY`, `ADD`, `RE_ADD`).
5. Enter a Target Element.
6. Click "Run Adaptation".
7. View the result in the Result panel.

## Running an Automated Benchmark
1. Go to the "Benchmark" tab.
2. Select Execution Mode (Single / Fallback Chain / Multi-Provider).
3. Choose one or more Providers.
4. Select the Dataset Root (`E:\Implemention_dataset enriched`).
5. Check the Request Types you want to test (`REMOVE`, `MODIFY`, `ADD`, `RE_ADD`).
6. Set Repetitions (1 for quick dev, 3 for standard, 30 for full).
7. Choose a Screenshot Strategy:
   - `A` — Minimal: 1 screenshot per test
   - `B` — Standard: 1 per test + all 11 every 5th test
   - `C` — Full: all 11 tabs per test
8. Choose an Output directory.
9. Click "Start Benchmark".
10. Monitor progress in the Live Log panel.
11. Use "Pause" and "Stop" as needed.

## Benchmark Output
After a benchmark completes, look in the output directory:
```
experiments/<run_id>/
  metrics.json                 — accuracy, precision, recall, F1, GED, etc.
  tests.jsonl                  — per-test results
  llm_calls.jsonl              — every LLM call
  screenshots_manifest.jsonl   — screenshot index
  screenshots/                 — all screenshots
  plots/                       — all charts
  FINAL_REPORT.md              — narrative report
  checkpoint.json              — for resume
```

## Resuming a Benchmark
If a benchmark stops (e.g., rate limit, network issue):
1. Change the API key if needed:
   ```bash
   bpmn-adapt providers set-key groq NEW_KEY
   ```
2. Resume from where it stopped:
   ```bash
   bpmn-adapt run-benchmark --output experiments/<run_id> --resume
   ```

## Multi-Provider Comparison
Run the benchmark in "Multi-Provider Comparison" mode:
1. Select all providers to compare.
2. Start the benchmark.
3. After each provider finishes, the comparison is generated in:
   ```
   experiments/<run_id>/comparison/
     comparison_summary.json
     COMPARISON_REPORT.md
     accuracy_comparison.png/.pdf
     etc.
   ```

## Accessing the Live Log
1. Go to the "Live Log" tab.
2. View streaming events in real-time.
3. See rolling accuracy chart and provider usage.
4. Filter by provider, schema, or status.

## Viewing Comparison Results
After a multi-provider benchmark:
1. Go to the "Comparison" tab.
2. See the provider summary table.
3. View charts (accuracy, latency, error rate).
4. See McNemar p-values.

## Common Issues
- **Groq rate limit (429)**: Wait 1 hour, or change API key via GUI/CLI.
- **Gemini timeout**: Ensure VPN is active.
- **UM LLM 2s rate limit**: Inherent; the pipeline handles it automatically.
- **Screenshot capture fails**: Ensure the GUI window is not minimized.

## Contact
For issues with this workbench, contact the author.
