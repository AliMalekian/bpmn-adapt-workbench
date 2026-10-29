# GUI manual acceptance checklist

- Launch `bpmn-adapt gui` and confirm all nine workbench tabs are visible.
- Select a Camunda, PMO, and Mangler folder in separate runs.
- Run ingest, inspect, analyse, plan, adapt, validate, simulate, evaluate, and export.
- Confirm long operations leave the window responsive and Cancel changes the status.
- Confirm DB facts, RAG component scores, planning alternatives, BPMN diff,
  migration map, traces/failures, statistics, provenance, and raw JSON remain visible.
- Confirm an invalid input is rendered as an error dialog without closing the workbench.
- Export a run, replay its ZIP, and compare the displayed checksum/provenance data.
- For a configured live profile, deploy and migrate only disposable test instances,
  then verify run-scoped cleanup does not affect unrelated resources.
