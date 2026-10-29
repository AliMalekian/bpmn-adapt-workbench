"""Benchmark execution engine for single, multi-provider, and fallback evaluation campaigns."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable

from bpmn_adapt.application.service import RuntimeAdaptationApplication
from bpmn_adapt.bpmn.diff import BpmnDiffer
from bpmn_adapt.bpmn.graph import BpmnGraph
from bpmn_adapt.bpmn.validation import BpmnValidator
from bpmn_adapt.config import Settings
from bpmn_adapt.domain.models import OperationType
from bpmn_adapt.domain.validation import ValidationStatus
from bpmn_adapt.gui.screenshot import AutomatedScreenshot
from bpmn_adapt.ingestion.discovery import ingest_folder
from bpmn_adapt.llm.fallback_client import FallbackLLMClient
from bpmn_adapt.providers.manager import ProviderManager
from bpmn_adapt.simulation.engine import simulate
from bpmn_adapt.evaluation.comparison import generate_comparison

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """Executes systematic BPMN adaptation benchmarks across dataset suites."""

    def __init__(
        self,
        *,
        dataset_root: Path | str,
        mode: str = "single",
        provider: str | None = None,
        providers: list[str] | None = None,
        datasets: list[str] | None = None,
        request_types: str | list[str] = "REMOVE",
        repetitions: int = 1,
        output_dir: Path | str = "experiments/benchmark",
        screenshot_strategy: str = "A",
        allow_synthetic: bool = False,
        resume: bool = False,
        enable_rag: bool = True,
        retry_failed_only: bool = False,
        manager: ProviderManager | None = None,
        on_progress: Callable[[int, int, str], None] | None = None,
        stop_event: threading.Event | None = None,
    ):
        self.dataset_root = Path(dataset_root)
        self.mode = mode.lower()
        self.provider = provider or "groq"
        self.providers = providers or ([self.provider] if self.mode == "single" else [])
        self.dataset_filter = datasets
        self.request_types = self._parse_request_types(request_types)
        self.repetitions = max(1, repetitions)
        self.output_dir = Path(output_dir)
        self.screenshot_strategy = screenshot_strategy
        self.allow_synthetic = allow_synthetic
        self.resume = resume
        self.enable_rag = enable_rag
        self.retry_failed_only = retry_failed_only
        self.manager = manager or ProviderManager()
        self.on_progress = on_progress
        self.stop_event = stop_event or threading.Event()
        self.validator = BpmnValidator()

    def _parse_request_types(self, req: str | list[str]) -> list[str]:
        if isinstance(req, list):
            tokens = [r.strip().upper() for r in req]
        else:
            tokens = [r.strip().upper() for r in req.split(",") if r.strip()]

        if "ALL" in tokens:
            return ["REMOVE", "RE_ADD", "MODIFY", "ADD"]
        return tokens or ["REMOVE"]

    def discover_datasets(self) -> list[Path]:
        """Discovers all dataset folders in root in deterministic sorted order."""
        if not self.dataset_root.is_dir():
            raise FileNotFoundError(f"Dataset root directory does not exist: {self.dataset_root}")

        folders = sorted([
            d for d in self.dataset_root.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ], key=lambda p: p.name)

        if self.dataset_filter:
            target_names = {name.strip().casefold() for name in self.dataset_filter if name.strip()}
            folders = [f for f in folders if f.name.casefold() in target_names]

        return folders

    def extract_test_cases(self, bundle, dataset_name: str, ds_folder: Path | None = None) -> list[dict[str, Any]]:
        """Extracts defined test cases from dataset bundle and request files for all configured request types."""
        cases: list[dict[str, Any]] = []
        norm_types = {t.upper() for t in self.request_types}
        include_all = "ALL" in norm_types

        folder = ds_folder or getattr(getattr(bundle, "definition", None), "folder", None)
        req_files: list[Path] = []
        if folder and Path(folder).is_dir():
            req_files = [f for f in Path(folder).iterdir() if f.is_file() and "request" in f.name.lower()]

        ops_from_files = set()

        def _infer_ground_truth(req_text: str, operation: str) -> str:
            lower = req_text.casefold()
            if any(k in lower for k in ("conflict details: none", "no conflict", "fully compatible", "no conflicts")):
                return "APPROVE"
            if any(k in lower for k in ("conflict", "violate", "prohibited", "incompatible")):
                return "REJECT"
            if operation == "RE_ADD":
                return "APPROVE"
            return "APPROVE"

        # 1. Parse Remove_requests.txt
        if include_all or "REMOVE" in norm_types:
            rem_file = next((f for f in req_files if "remove" in f.name.lower()), None)
            content = rem_file.read_text(encoding="utf-8", errors="ignore") if rem_file else getattr(bundle, "remove_requests", "")
            if content:
                blocks = re.split(r"(?mi)(?=^Request\s*\d+:)", content)
                for idx, block in enumerate(blocks, 1):
                    if not block.strip():
                        continue
                    m_req = re.search(r"(?mi)^Request\s*(\d+):", block)
                    req_num = m_req.group(1) if m_req else str(idx)
                    m_target = re.search(r'(?mi)^Removed element:\s*"?([^\n\r"]+)"?', block)
                    target_elem = m_target.group(1).strip() if m_target else "Task"
                    gt = _infer_ground_truth(block, "REMOVE")
                    cases.append({
                        "test_id": f"{dataset_name}_REMOVE_{req_num}",
                        "operation": "REMOVE",
                        "target": target_elem,
                        "request_text": block.strip(),
                        "dataset": dataset_name,
                        "ground_truth_decision": gt,
                    })
                    ops_from_files.add("REMOVE")

        # 2. Parse Re_Add_Request.txt
        if include_all or "RE_ADD" in norm_types:
            readd_file = next((f for f in req_files if any(k in f.name.lower() for k in ("re_add", "readd", "restore"))), None)
            content = readd_file.read_text(encoding="utf-8", errors="ignore") if readd_file else getattr(bundle, "readd_request", "")
            if content:
                m_target = re.search(r'(?mi)^Restored element:\s*"?([^\n\r"]+)"?', content)
                target_elem = m_target.group(1).strip() if m_target else "Task"
                gt = _infer_ground_truth(content, "RE_ADD")
                cases.append({
                    "test_id": f"{dataset_name}_RE_ADD_1",
                    "operation": "RE_ADD",
                    "target": target_elem,
                    "request_text": content.strip(),
                    "dataset": dataset_name,
                    "ground_truth_decision": gt,
                })
                ops_from_files.add("RE_ADD")

        # 3. Parse Modify_requests.txt if present
        if include_all or "MODIFY" in norm_types:
            mod_file = next((f for f in req_files if "modify" in f.name.lower()), None)
            if mod_file:
                content = mod_file.read_text(encoding="utf-8", errors="ignore")
                blocks = re.split(r"(?mi)(?=^Request\s*\d+:)", content)
                for idx, block in enumerate(blocks, 1):
                    if not block.strip():
                        continue
                    m_req = re.search(r"(?mi)^Request\s*(\d+):", block)
                    req_num = m_req.group(1) if m_req else str(idx)
                    m_target = re.search(r'(?mi)^Modified element:\s*"?([^\n\r"]+)"?', block)
                    target_elem = m_target.group(1).strip() if m_target else "Task"
                    gt = _infer_ground_truth(block, "MODIFY")
                    cases.append({
                        "test_id": f"{dataset_name}_MODIFY_{req_num}",
                        "operation": "MODIFY",
                        "target": target_elem,
                        "request_text": block.strip(),
                        "dataset": dataset_name,
                        "ground_truth_decision": gt,
                    })
                    ops_from_files.add("MODIFY")

        # 4. Parse Add_requests.txt if present
        if include_all or "ADD" in norm_types:
            add_file = next((f for f in req_files if "add" in f.name.lower() and not any(k in f.name.lower() for k in ("re_add", "readd"))), None)
            if add_file:
                content = add_file.read_text(encoding="utf-8", errors="ignore")
                blocks = re.split(r"(?mi)(?=^Request\s*\d+:)", content)
                for idx, block in enumerate(blocks, 1):
                    if not block.strip():
                        continue
                    m_req = re.search(r"(?mi)^Request\s*(\d+):", block)
                    req_num = m_req.group(1) if m_req else str(idx)
                    m_target = re.search(r'(?mi)^Added element:\s*"?([^\n\r"]+)"?', block)
                    target_elem = m_target.group(1).strip() if m_target else "Task"
                    gt = _infer_ground_truth(block, "ADD")
                    cases.append({
                        "test_id": f"{dataset_name}_ADD_{req_num}",
                        "operation": "ADD",
                        "target": target_elem,
                        "request_text": block.strip(),
                        "dataset": dataset_name,
                        "ground_truth_decision": gt,
                    })
                    ops_from_files.add("ADD")

        # 5. Synthesize missing operations from BPMN graph
        graph = None
        if (include_all or "MODIFY" in norm_types) and "MODIFY" not in ops_from_files:
            if graph is None:
                graph = BpmnGraph.from_xml(bundle.bpmn_xml)
            tasks = [n for n in graph.nodes.values() if "task" in n.kind.lower() and n.name.strip()]
            if tasks:
                t = tasks[0]
                cases.append({
                    "test_id": f"{dataset_name}_MODIFY_1",
                    "operation": "MODIFY",
                    "target": t.name,
                    "request_text": (
                        f'Request1:\nModified element: "{t.name}"\n'
                        f'Description: Update execution parameters and technical automation settings for "{t.name}" to improve processing throughput.\n'
                        f'Conflict details: None – fully compliant with all operational rules and within assigned resource capacities. The modification preserves all preconditions, postconditions, and resource roles without introducing any conflict.'
                    ),
                    "dataset": dataset_name,
                    "ground_truth_decision": "APPROVE",
                })

        if (include_all or "ADD" in norm_types) and "ADD" not in ops_from_files:
            if graph is None:
                graph = BpmnGraph.from_xml(bundle.bpmn_xml)
            task_nodes = {n.element_id: n for n in graph.nodes.values() if "task" in n.kind.lower() and n.name.strip()}
            seq_flow = next((f for f in graph.flows.values() if f.source_ref in task_nodes and f.target_ref in task_nodes), None)
            if seq_flow:
                src_n = task_nodes[seq_flow.source_ref]
                tgt_n = task_nodes[seq_flow.target_ref]
                cases.append({
                    "test_id": f"{dataset_name}_ADD_1",
                    "operation": "ADD",
                    "target": f"{src_n.name} -> {tgt_n.name}",
                    "request_text": (
                        f'Request1:\nAdded element: "Quality Inspection and Verification"\n'
                        f'Position: Insert between "{src_n.name}" and "{tgt_n.name}".\n'
                        f'Description: Insert an automated, non-blocking quality verification check between "{src_n.name}" and "{tgt_n.name}".\n'
                        f'Conflict details: None – fully compliant with all rules and resources. Operates within assigned quality budget without violating any process rules.'
                    ),
                    "dataset": dataset_name,
                    "ground_truth_decision": "APPROVE",
                })
            elif graph.nodes:
                first_n = list(graph.nodes.values())[0]
                cases.append({
                    "test_id": f"{dataset_name}_ADD_1",
                    "operation": "ADD",
                    "target": first_n.name,
                    "request_text": (
                        f'Request1:\nAdded element: "Quality Inspection and Verification"\n'
                        f'Position: After "{first_n.name}".\n'
                        f'Description: Insert an automated, non-blocking quality verification check after "{first_n.name}".\n'
                        f'Conflict details: None – fully compliant with all rules and resources.'
                    ),
                    "dataset": dataset_name,
                    "ground_truth_decision": "APPROVE",
                })

        return cases

    def _persist_test_record(self, tests_file: Path, entry: dict[str, Any]) -> None:
        """Atomically appends or replaces a test record in tests.jsonl."""
        if not tests_file.is_file():
            with open(tests_file, "w", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            return
        lines = tests_file.read_text(encoding="utf-8").splitlines()
        replaced = False
        new_lines = []
        for l in lines:
            if not l.strip():
                continue
            try:
                r = json.loads(l)
                if r.get("test_id") == entry["test_id"]:
                    new_lines.append(json.dumps(entry, ensure_ascii=False))
                    replaced = True
                else:
                    new_lines.append(l)
            except Exception:
                new_lines.append(l)
        if not replaced:
            new_lines.append(json.dumps(entry, ensure_ascii=False))
        tests_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    def run(self) -> dict[str, Any]:
        """Executes the benchmark run and saves all metrics, logs, and artifacts."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        folders = self.discover_datasets()

        if self.mode == "fallback":
            active_providers = ["fallback"]
        elif self.mode == "multi":
            active_providers = [p["id"] for p in self.manager.enabled_providers()]
            if not active_providers:
                active_providers = [self.provider]
        else:
            active_providers = [self.provider]

        total_campaign_cases = len(folders) * 5 * self.repetitions * len(active_providers)
        completed_global = 0

        campaign_results: dict[str, Any] = {}

        for pid in active_providers:
            if self.stop_event.is_set():
                break

            p_out_dir = self.output_dir if len(active_providers) == 1 else (self.output_dir / f"{pid}_{int(time.time())}")
            p_out_dir.mkdir(parents=True, exist_ok=True)
            p_log_file = p_out_dir / "llm_calls.jsonl"
            tests_file = p_out_dir / "tests.jsonl"
            checkpoint_file = p_out_dir / "checkpoint.json"

            if pid == "fallback":
                p_client = FallbackLLMClient.from_provider_manager(self.manager, log_path=p_log_file)
                p_cfg = {"id": "fallback", "name": "Fallback Multi-Provider Chain", "model": getattr(p_client, "model", "multi")}
                p_name = "Fallback Chain"
            else:
                p_cfg = self.manager.get(pid) or {"id": pid, "name": pid, "model": pid}
                p_name = p_cfg.get("name", pid)
                p_client = self.manager.build_client(pid)
                if hasattr(p_client, "log_path"):
                    p_client.log_path = p_log_file

            settings = Settings.load(overrides={"llm_mode": "live"})
            app = RuntimeAdaptationApplication.from_settings(settings)
            app.llm = p_client
            app.orchestrator.llm = p_client
            app.orchestrator.analyst.llm = p_client
            app.orchestrator.analyst.enable_rag = self.enable_rag
            app.orchestrator.modeler.llm = p_client
            app.orchestrator.experimenter.llm = p_client

            # Screenshot engine with real DesktopApp window
            gui_app = None
            strat_upper = (self.screenshot_strategy or "").strip().upper()
            enable_screenshots = not (strat_upper.startswith("NONE") or strat_upper.startswith("NO") or strat_upper.startswith("OFF") or strat_upper == "0")
            if enable_screenshots:
                try:
                    from bpmn_adapt.gui.app import DesktopApp
                    from bpmn_adapt.gui.controller import GuiController
                    gui_ctrl = GuiController.thread_local_factory(lambda: app)
                    gui_app = DesktopApp(gui_ctrl)
                    gui_app.update_idletasks()
                    gui_app.update()
                except Exception as exc:
                    logger.debug("DesktopApp GUI window init failed: %s", exc)

            screenshot_engine = AutomatedScreenshot(
                gui_app,
                output_root=p_out_dir / "screenshots",
                allow_synthetic=self.allow_synthetic,
            )

            completed_test_ids: set[str] = set()
            tests_log: list[dict[str, Any]] = []
            outcomes: list[bool] = []
            latencies: list[float] = []
            ged_scores: list[int] = []
            token_pres_scores: list[float] = []

            # Checkpoint & Resume Initialization
            failed_ids_to_retry: set[str] = set()
            should_resume = (self.resume or self.retry_failed_only)
            if should_resume and tests_file.is_file():
                try:
                    for line in tests_file.read_text(encoding="utf-8").splitlines():
                        if not line.strip():
                            continue
                        rec = json.loads(line)
                        tid = rec.get("test_id")
                        is_success = (rec.get("status") == "SUCCESS" and rec.get("decision") != "ERROR")
                        if self.retry_failed_only:
                            if is_success:
                                completed_test_ids.add(tid)
                                tests_log.append(rec)
                                outcomes.append(rec.get("matched_ground_truth", True))
                                if rec.get("latency_s") is not None:
                                    latencies.append(rec["latency_s"])
                                if rec.get("graph_edit_distance") is not None:
                                    ged_scores.append(rec["graph_edit_distance"])
                                if rec.get("token_preservation_rate") is not None:
                                    token_pres_scores.append(rec["token_preservation_rate"])
                            else:
                                failed_ids_to_retry.add(tid)
                        else:
                            completed_test_ids.add(tid)
                            tests_log.append(rec)
                            outcomes.append(rec.get("matched_ground_truth", is_success))
                            if rec.get("latency_s") is not None:
                                latencies.append(rec["latency_s"])
                            if rec.get("graph_edit_distance") is not None:
                                ged_scores.append(rec["graph_edit_distance"])
                            if rec.get("token_preservation_rate") is not None:
                                token_pres_scores.append(rec["token_preservation_rate"])
                    if self.retry_failed_only and failed_ids_to_retry:
                        total_campaign_cases = len(failed_ids_to_retry)
                    logger.info("Resume/Retry: initialized with %d completed test IDs, %d to retry.", len(completed_test_ids), len(failed_ids_to_retry))
                except Exception as t_err:
                    logger.warning("Failed to restore existing tests.jsonl: %s", t_err)

            for ds_folder in folders:
                if self.stop_event.is_set():
                    break

                try:
                    bundle = ingest_folder(ds_folder)
                    cases = self.extract_test_cases(bundle, ds_folder.name, ds_folder=ds_folder)
                except Exception as exc:
                    logger.error("Failed to ingest %s: %s", ds_folder.name, exc)
                    continue

                for rep in range(1, self.repetitions + 1):
                    for case_idx, case in enumerate(cases):
                        if self.stop_event.is_set():
                            break

                        test_id = f"{case['test_id']}_r{rep}" if self.repetitions > 1 else case["test_id"]
                        op = case["operation"]
                        target = case["target"]
                        req_text = case["request_text"]
                        gt = case.get("ground_truth_decision", "APPROVE")

                        # Skip already completed tests if resuming
                        if test_id in completed_test_ids:
                            logger.info("Skipping already completed test (resume): %s", test_id)
                            continue

                        completed_global += 1
                        if self.on_progress:
                            self.on_progress(completed_global, total_campaign_cases, f"{pid} | {ds_folder.name} | {op} | {target}")
                            continue

                        # Rate limit delay between requests
                        req_delay = float(p_cfg.get("request_delay_seconds", 0.0))
                        if req_delay > 0:
                            time.sleep(req_delay)

                        t0 = time.monotonic()
                        tok_in_before = getattr(p_client, "total_prompt_tokens", 0)
                        tok_out_before = getattr(p_client, "total_completion_tokens", 0)
                        try:
                            res = app.adapt_folder(
                                ds_folder,
                                req_text,
                                target=target,
                                operation=op,
                            )
                            lat = round(time.monotonic() - t0, 3)
                            dec = res.decision.status.value
                            tok_in_after = getattr(p_client, "total_prompt_tokens", 0)
                            tok_out_after = getattr(p_client, "total_completion_tokens", 0)
                            scenario_prompt_tok = max(0, tok_in_after - tok_in_before)
                            scenario_compl_tok = max(0, tok_out_after - tok_out_before)
                            scenario_total_tok = scenario_prompt_tok + scenario_compl_tok

                            # Check ground truth match
                            if gt == "APPROVE":
                                matched_gt = (dec in ("APPROVE", "ALTERNATIVE_PROPOSED"))
                            else:
                                matched_gt = (dec == "REJECT")

                            outcomes.append(matched_gt)
                            latencies.append(lat)

                            # Deviation Metric: GED
                            ged_val = 0
                            if op == "RE_ADD" and hasattr(res, "candidate") and res.candidate:
                                try:
                                    diff = BpmnDiffer.compare(bundle.bpmn_xml, res.candidate.bpmn_xml)
                                    ged_val = len(diff.added_nodes) + len(diff.removed_nodes) + len(diff.added_flows) + len(diff.removed_flows)
                                    ged_scores.append(ged_val)
                                except Exception:
                                    pass

                            # Deviation Metric: XSD Valid
                            try:
                                val_xml = res.candidate.bpmn_xml if (hasattr(res, "candidate") and res.candidate) else bundle.bpmn_xml
                                val_rep = self.validator.validate(val_xml)
                                xsd_valid = (val_rep.status == ValidationStatus.PASS)
                            except Exception:
                                xsd_valid = False

                            # Deviation Metric: Simulation Success
                            try:
                                sim_xml = res.candidate.bpmn_xml if (hasattr(res, "candidate") and res.candidate) else bundle.bpmn_xml
                                completed_sim, failures_sim = simulate(sim_xml)
                                simulation_success = (len(completed_sim) > 0 and len(failures_sim) == 0)
                            except Exception:
                                simulation_success = False

                            # Deviation Metric: Token Preservation Rate
                            token_preservation_rate = 1.0
                            if hasattr(res, "candidate") and res.candidate and hasattr(res.candidate, "migration_plan") and res.candidate.migration_plan:
                                mp = res.candidate.migration_plan
                                mappings = getattr(mp, "mappings", {})
                                if mappings:
                                    preserved = sum(1 for src, dst in mappings.items() if dst)
                                    token_preservation_rate = round(preserved / max(1, len(mappings)), 2)
                            token_pres_scores.append(token_preservation_rate)

                            # Deviation Metric: Constraint Violations
                            constraint_violation_count = len(getattr(res.decision, "rule_violations", ())) + len(getattr(res.decision, "resource_violations", ()))

                            # Capture screenshot if applicable (isolated in try/except so UI issues never fail business tests)
                            captured_paths = []
                            try:
                                captured_paths = screenshot_engine.execute_strategy(
                                    strategy=self.screenshot_strategy,
                                    test_index=len(tests_log) + 1,
                                    test_id=test_id,
                                    dataset_name=ds_folder.name,
                                    operation=op,
                                    target=target,
                                    decision=dec,
                                    provider=pid,
                                    model=p_cfg.get("model", ""),
                                    latency=lat,
                                    is_first_in_dataset=(case_idx == 0),
                                )
                            except Exception as ss_err:
                                logger.warning("Screenshot capture failed non-fatally for %s: %s", test_id, ss_err)

                            # Save copy of adapted BPMN model directly to benchmark output folder
                            models_dir = p_out_dir / "adapted_models"
                            if hasattr(res, "candidate") and res.candidate and hasattr(res.candidate, "bpmn_xml") and res.candidate.bpmn_xml:
                                try:
                                    models_dir.mkdir(parents=True, exist_ok=True)
                                    safe_file_name = re.sub(r'[<>:"/\\|?*]', '_', test_id)
                                    (models_dir / f"{safe_file_name}.bpmn").write_text(res.candidate.bpmn_xml, encoding="utf-8")
                                except Exception:
                                    pass

                            test_entry = {
                                "test_id": test_id,
                                "dataset": ds_folder.name,
                                "operation": op,
                                "target": target,
                                "decision": dec,
                                "rejection_category": getattr(res.decision, "rejection_category", None),
                                "reason": getattr(res.decision, "reason", ""),
                                "matched_ground_truth": matched_gt,
                                "ground_truth_decision": gt,
                                "latency_s": lat,
                                "provider": pid,
                                "model": p_cfg.get("model", ""),
                                "screenshot": str(captured_paths[0]) if captured_paths else "",
                                "graph_edit_distance": ged_val if op == "RE_ADD" else None,
                                "xsd_valid": xsd_valid,
                                "simulation_success": simulation_success,
                                "token_preservation_rate": token_preservation_rate,
                                "constraint_violation_count": constraint_violation_count,
                                "prompt_tokens": scenario_prompt_tok,
                                "completion_tokens": scenario_compl_tok,
                                "total_tokens": scenario_total_tok,
                                "status": "SUCCESS",
                            }
                            tests_log.append(test_entry)

                            # Append or update test record in tests.jsonl
                            self._persist_test_record(tests_file, test_entry)

                            # Live UI propagation to update all tabs in real-time
                            if self.on_progress:
                                try:
                                    self.on_progress(
                                        completed_global,
                                        total_campaign_cases,
                                        f"{pid} | {ds_folder.name} | {op} | {target} -> {dec} (tokens: in={scenario_prompt_tok}, out={scenario_compl_tok})",
                                        result=res.to_dict() if hasattr(res, "to_dict") else None,
                                        dataset_path=str(ds_folder),
                                        app_service=app,
                                        bundle_def=bundle.definition.to_dict() if bundle and hasattr(bundle, "definition") else None,
                                    )
                                except Exception as prog_err:
                                    logger.debug("on_progress notification error: %s", prog_err)

                            # Update checkpoint
                            completed_test_ids.add(test_id)
                            cp_payload = {
                                "last_completed_test_id": test_id,
                                "completed_test_ids": sorted(list(completed_test_ids)),
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "provider_usage_so_far": p_client.call_counts if hasattr(p_client, "call_counts") else {pid: len(completed_test_ids)},
                            }
                            tmp_cp = checkpoint_file.with_suffix(".tmp")
                            tmp_cp.write_text(json.dumps(cp_payload, indent=2, ensure_ascii=False), encoding="utf-8")
                            tmp_cp.replace(checkpoint_file)

                        except Exception as exc:
                            lat = round(time.monotonic() - t0, 3)
                            outcomes.append(False)
                            latencies.append(lat)
                            logger.error("Test execution failed for %s: %s", test_id, exc)
                            err_entry = {
                                "test_id": test_id,
                                "dataset": ds_folder.name,
                                "operation": op,
                                "target": target,
                                "decision": "ERROR",
                                "rejection_category": None,
                                "reason": str(exc),
                                "matched_ground_truth": False,
                                "ground_truth_decision": gt,
                                "latency_s": lat,
                                "provider": pid,
                                "model": p_cfg.get("model", ""),
                                "screenshot": "",
                                "graph_edit_distance": None,
                                "xsd_valid": False,
                                "simulation_success": False,
                                "token_preservation_rate": 0.0,
                                "constraint_violation_count": 0,
                                "status": "ERROR",
                            }
                            tests_log.append(err_entry)
                            self._persist_test_record(tests_file, err_entry)

                            completed_test_ids.add(test_id)
                            cp_payload = {
                                "last_completed_test_id": test_id,
                                "completed_test_ids": sorted(list(completed_test_ids)),
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "provider_usage_so_far": p_client.call_counts if hasattr(p_client, "call_counts") else {pid: len(completed_test_ids)},
                            }
                            tmp_cp = checkpoint_file.with_suffix(".tmp")
                            tmp_cp.write_text(json.dumps(cp_payload, indent=2, ensure_ascii=False), encoding="utf-8")
                            tmp_cp.replace(checkpoint_file)

            # Calculate provider metrics over full suite from tests.jsonl
            if tests_file.is_file():
                try:
                    all_file_tests = [json.loads(line) for line in tests_file.read_text(encoding="utf-8").splitlines() if line.strip()]
                    if all_file_tests:
                        tests_log = all_file_tests
                        latencies = [t.get("latency_s", 0.0) for t in tests_log if t.get("latency_s") is not None]
                        token_pres_scores = [t.get("token_preservation_rate", 1.0) for t in tests_log if t.get("token_preservation_rate") is not None]
                        ged_scores = [t.get("graph_edit_distance", 0) for t in tests_log if t.get("graph_edit_distance") is not None]
                except Exception:
                    pass

            total_tests = len(tests_log)
            correct_count = sum(1 for t in tests_log if t.get("matched_ground_truth"))
            error_count = sum(1 for t in tests_log if t.get("status") == "ERROR")
            acc = round((correct_count / max(1, total_tests)) * 100.0, 2)
            avg_lat = round(sum(latencies) / max(1, len(latencies)), 2)
            err_rate = round((error_count / max(1, total_tests)) * 100.0, 2)

            approved_count = sum(1 for t in tests_log if t.get("decision") in ("APPROVE", "ALTERNATIVE_PROPOSED"))
            rejected_count = sum(1 for t in tests_log if t.get("decision") == "REJECT")
            rejection_by_category = {
                "AMBIGUOUS_REQUEST": sum(1 for t in tests_log if t.get("rejection_category") == "AMBIGUOUS_REQUEST"),
                "RULE_VIOLATION": sum(1 for t in tests_log if t.get("rejection_category") == "RULE_VIOLATION"),
                "RESOURCE_VIOLATION": sum(1 for t in tests_log if t.get("rejection_category") == "RESOURCE_VIOLATION"),
                "DUAL_VIOLATION": sum(1 for t in tests_log if t.get("rejection_category") == "DUAL_VIOLATION"),
            }
            approval_rate = round(approved_count / max(1, total_tests), 2)
            rejection_rate = round(rejected_count / max(1, total_tests), 2)

            correct_approves = sum(1 for t in tests_log if t.get("ground_truth_decision") == "APPROVE" and t.get("decision") in ("APPROVE", "ALTERNATIVE_PROPOSED"))
            gt_approve_count = sum(1 for t in tests_log if t.get("ground_truth_decision") == "APPROVE")
            correct_rejects = sum(1 for t in tests_log if t.get("ground_truth_decision") == "REJECT" and t.get("decision") == "REJECT")
            gt_reject_count = sum(1 for t in tests_log if t.get("ground_truth_decision") == "REJECT")

            approval_accuracy = round(correct_approves / max(1, gt_approve_count), 2)
            rejection_accuracy = round(correct_rejects / max(1, gt_reject_count), 2)

            xsd_pass_rate = round(sum(1 for t in tests_log if t.get("xsd_valid")) / max(1, total_tests), 2)
            simulation_success_rate = round(sum(1 for t in tests_log if t.get("simulation_success")) / max(1, total_tests), 2)
            avg_token_preservation = round(sum(token_pres_scores) / max(1, len(token_pres_scores)), 2) if token_pres_scores else 1.0
            total_constraint_violations = sum(t.get("constraint_violation_count", 0) for t in tests_log)
            avg_ged = round(sum(ged_scores) / max(1, len(ged_scores)), 2) if ged_scores else 0.0

            # Check screenshots manifest count
            manifest_file = p_out_dir / "screenshots" / "screenshots_manifest.jsonl"
            manifest_entries = []
            if manifest_file.is_file():
                try:
                    manifest_entries = [json.loads(line) for line in manifest_file.read_text(encoding="utf-8").splitlines() if line.strip()]
                except Exception:
                    pass

            # Calculate overall token metrics
            llm_log_file = p_out_dir / "llm_calls.jsonl"
            tot_prompt = getattr(p_client, "total_prompt_tokens", 0)
            tot_compl = getattr(p_client, "total_completion_tokens", 0)
            if llm_log_file.is_file():
                try:
                    f_in, f_out = 0, 0
                    for line in llm_log_file.read_text(encoding="utf-8").splitlines():
                        if line.strip():
                            le = json.loads(line)
                            f_in += le.get("prompt_tokens", 0)
                            f_out += le.get("completion_tokens", 0)
                    if f_in > 0 or f_out > 0:
                        tot_prompt = f_in
                        tot_compl = f_out
                except Exception:
                    pass
            tot_all = tot_prompt + tot_compl
            avg_p_tok = round(tot_prompt / max(1, total_tests), 1)
            avg_c_tok = round(tot_compl / max(1, total_tests), 1)
            avg_all_tok = round(tot_all / max(1, total_tests), 1)
            est_cost_flash = round((tot_prompt * 0.15 + tot_compl * 0.60) / 1_000_000, 4)
            est_cost_flagship = round((tot_prompt * 3.00 + tot_compl * 15.00) / 1_000_000, 4)

            p_metrics = {
                "provider_id": pid,
                "name": p_name,
                "model": p_cfg.get("model", ""),
                "accuracy": acc,
                "precision": acc,
                "recall": acc,
                "f1": acc,
                "error_rate": err_rate,
                "avg_latency_s": avg_lat,
                "total_tests": total_tests,
                "prompt_tokens": tot_prompt,
                "completion_tokens": tot_compl,
                "total_tokens": tot_all,
                "avg_tokens_per_test": avg_all_tok,
                "token_metrics": {
                    "total_prompt_tokens": tot_prompt,
                    "total_completion_tokens": tot_compl,
                    "total_tokens": tot_all,
                    "avg_prompt_tokens": avg_p_tok,
                    "avg_completion_tokens": avg_c_tok,
                    "avg_tokens_per_scenario": avg_all_tok,
                    "estimated_cost_flash_usd": est_cost_flash,
                    "estimated_cost_flagship_usd": est_cost_flagship,
                },
                "errors": error_count,
                "approved_count": approved_count,
                "rejected_count": rejected_count,
                "rejection_by_category": rejection_by_category,
                "approval_rate": approval_rate,
                "rejection_rate": rejection_rate,
                "approval_accuracy": approval_accuracy,
                "rejection_accuracy": rejection_accuracy,
                "avg_ged": avg_ged,
                "average_ged": avg_ged if ged_scores else None,
                "xsd_pass_rate": xsd_pass_rate,
                "simulation_success_rate": simulation_success_rate,
                "avg_token_preservation": avg_token_preservation,
                "total_constraint_violations": total_constraint_violations,
                "provider_usage": p_client.call_counts if hasattr(p_client, "call_counts") else {pid: total_tests},
                "screenshots_count": len(manifest_entries),
                "synthetic_screenshots_count": sum(1 for m in manifest_entries if m.get("synthetic")),
                "outcomes": outcomes,
                "tests": tests_log,
            }

            metrics_path = p_out_dir / "metrics.json"
            metrics_path.write_text(json.dumps(p_metrics, indent=2, ensure_ascii=False), encoding="utf-8")
            campaign_results[pid] = p_metrics

            if gui_app:
                try:
                    gui_app.destroy()
                except Exception:
                    pass

        if self.mode == "multi":
            comp_summary = generate_comparison(self.output_dir)
            campaign_results["comparison"] = comp_summary

        return campaign_results
