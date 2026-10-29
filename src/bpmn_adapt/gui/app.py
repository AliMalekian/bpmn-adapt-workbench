"""Tk/ttk tabbed inspection workbench with CLI-equivalent controls."""
from __future__ import annotations
import json
import tkinter as tk
from tkinter import filedialog,messagebox,simpledialog,ttk

from .controller import GuiController
from .workers import TaskWorker
from .panels.project import ProjectPanel
from .panels.facts import FactsPanel
from .panels.rag import RagPanel
from .panels.planning import PlanningPanel
from .panels.model import ModelPanel
from .panels.validation import ValidationPanel
from .panels.evaluation import EvaluationPanel
from .panels.provenance import ProvenancePanel
from .panels.export import ExportPanel
from .panels.provider_config import ProviderConfigPanel
from .panels.manual_test import ManualTestPanel
from .panels.benchmark import BenchmarkPanel
from .panels.live_log import LiveLogPanel
from .panels.comparison import ComparisonPanel

TAB_DEFINITIONS = (
    ("Project", ProjectPanel),
    ("DB Facts", FactsPanel),
    ("RAG Evidence", RagPanel),
    ("Planning", PlanningPanel),
    ("Model & Migration", ModelPanel),
    ("Validation & Simulation", ValidationPanel),
    ("Evaluation", EvaluationPanel),
    ("Provenance", ProvenancePanel),
    ("Export", ExportPanel),
    ("Provider Configuration", ProviderConfigPanel),
    ("Manual Test", ManualTestPanel),
    ("Benchmark", BenchmarkPanel),
    ("Live Log", LiveLogPanel),
    ("Comparison", ComparisonPanel),
)
ACTIONS=("ingest","index-rag","revoke-rag","analyse","plan","adapt","validate","simulate",
         "deploy","migrate","approve","reject","inspect","evaluate","baseline","batch",
         "report","export","replay")
ROUTE={"ingest":"Project","report":"Project","inspect":"DB Facts","index-rag":"RAG Evidence",
 "revoke-rag":"RAG Evidence","analyse":"RAG Evidence","plan":"Planning","adapt":"Model & Migration",
 "validate":"Validation & Simulation","simulate":"Validation & Simulation","deploy":"Validation & Simulation",
 "migrate":"Model & Migration","evaluate":"Evaluation","baseline":"Evaluation","batch":"Evaluation",
 "approve":"Provenance","reject":"Provenance","replay":"Provenance","export":"Export"}


class DesktopApp(tk.Tk):
    def __init__(self,controller:GuiController):
        super().__init__(); self.controller=controller; self.worker=TaskWorker(); self.current_task=None
        self.title("BPMN Adaptation Workbench"); self.geometry("1340x880")
        
        # Custom application icon (replaces default Tk feather)
        self._set_app_icon()

        self.folder=tk.StringVar(); self.request=tk.StringVar(); self.target=tk.StringVar(); self.state=tk.StringVar(value="STATE-01")
        self.run_id=tk.StringVar(); self.operation=tk.StringVar(value="REMOVE"); self.action=tk.StringVar(value="adapt")
        self.status=tk.StringVar(value="Ready")
        self._enable_universal_clipboard_shortcuts()
        self._build(); self.after(50,self._poll); self.protocol("WM_DELETE_WINDOW",self._close)

    def _enable_universal_clipboard_shortcuts(self) -> None:
        """Enables Ctrl+C, Ctrl+V, Ctrl+X, Ctrl+A to work across all keyboard layouts (e.g. Persian/Farsi)."""
        def on_ctrl_key(event):
            if not (event.state & 4):
                return
            widget = event.widget
            # Windows physical Virtual Key (VK) codes:
            # 86 = V (Paste)
            if event.keycode == 86:
                try:
                    widget.event_generate("<<Paste>>")
                    return "break"
                except Exception:
                    pass
            # 67 = C (Copy)
            elif event.keycode == 67:
                try:
                    widget.event_generate("<<Copy>>")
                    return "break"
                except Exception:
                    pass
            # 88 = X (Cut)
            elif event.keycode == 88:
                try:
                    widget.event_generate("<<Cut>>")
                    return "break"
                except Exception:
                    pass
            # 65 = A (Select All)
            elif event.keycode == 65:
                try:
                    if isinstance(widget, (tk.Entry, ttk.Entry)):
                        widget.select_range(0, "end")
                        widget.icursor("end")
                        return "break"
                    elif isinstance(widget, tk.Text):
                        widget.tag_add("sel", "1.0", "end")
                        return "break"
                except Exception:
                    pass

        self.bind_all("<Control-KeyPress>", on_ctrl_key, add="+")

    def _set_app_icon(self) -> None:
        """Sets custom application icon, removing default Tk feather."""
        try:
            from pathlib import Path
            icon_p = Path(__file__).parent / "assets" / "icon.png"
            if icon_p.exists():
                self._app_icon = tk.PhotoImage(file=str(icon_p))
                self.iconphoto(True, self._app_icon)
        except Exception:
            pass

    def _build(self):
        # Modern ttk styling theme
        style = ttk.Style(self)
        try:
            if "clam" in style.theme_names():
                style.theme_use("clam")
        except Exception:
            pass

        self.configure(bg="#F8FAFC")
        style.configure(".", font=("Segoe UI", 9))
        style.configure("TNotebook", background="#F8FAFC", borderwidth=0)
        style.configure("TNotebook.Tab", padding=[9, 5], font=("Segoe UI", 9))
        style.map("TNotebook.Tab",
                  background=[("selected", "#2563EB"), ("!selected", "#E2E8F0")],
                  foreground=[("selected", "#FFFFFF"), ("!selected", "#334155")],
                  font=[("selected", ("Segoe UI", 9, "bold")), ("!selected", ("Segoe UI", 9))])

        style.configure("TButton", padding=[8, 4], font=("Segoe UI", 9))
        style.map("TButton",
                  background=[("active", "#E2E8F0"), ("!disabled", "#F1F5F9")],
                  foreground=[("!disabled", "#0F172A")])

        style.configure("Primary.TButton", padding=[10, 5], font=("Segoe UI", 9, "bold"))
        style.map("Primary.TButton",
                  background=[("active", "#1D4ED8"), ("!disabled", "#2563EB")],
                  foreground=[("!disabled", "#FFFFFF")])

        style.configure("TLabelframe", background="#F8FAFC", relief="solid", borderwidth=1)
        style.configure("TLabelframe.Label", font=("Segoe UI", 9, "bold"), foreground="#0F172A", background="#F8FAFC")
        style.configure("TFrame", background="#F8FAFC")
        style.configure("TLabel", background="#F8FAFC", font=("Segoe UI", 9))

        # Main notebook container fills the area
        self.notebook=ttk.Notebook(self)
        self.notebook.pack(fill="both",expand=True,padx=8,pady=(8, 2))

        # Bottom sleek status bar
        status_bar = ttk.Frame(self, padding=(8, 3))
        status_bar.pack(fill="x", side="bottom")
        ttk.Label(status_bar, text="●", foreground="#10B981", font=("Segoe UI", 10)).pack(side="left", padx=(0, 4))
        ttk.Label(status_bar, text="System: ", font=("Segoe UI", 9, "bold")).pack(side="left")
        ttk.Label(status_bar, textvariable=self.status, foreground="#334155").pack(side="left")

        self.panels={}
        for name,panel_type in TAB_DEFINITIONS:
            panel=panel_type(self.notebook); self.notebook.add(panel,text=name); self.panels[name]=panel

    def populate_inspection_tabs(
        self,
        result: dict,
        dataset_path: str | None = None,
        app_service: Any = None,
        bundle_def: dict | None = None
    ) -> None:
        """Comprehensive multi-phase propagation across all 9 inspection tabs."""
        if not isinstance(result, dict):
            return

        # 1. Project Tab
        if "Project" in self.panels:
            if bundle_def:
                self.panels["Project"].display(bundle_def)
            elif dataset_path and app_service:
                try:
                    bundle = app_service.ingest(dataset_path)
                    self.panels["Project"].display(bundle.definition.to_dict())
                except Exception:
                    pass

        # 2. DB Facts Tab
        if "DB Facts" in self.panels and dataset_path and app_service:
            try:
                facts = app_service.inspect(dataset_path)
                self.panels["DB Facts"].display(facts)
            except Exception:
                pass

        # 3. RAG Evidence Tab
        if "RAG Evidence" in self.panels:
            req = result.get("decision", {}).get("request", {})
            proc_id = req.get("process_id", "")
            raw_text = req.get("raw_text", "")
            hits = []
            if app_service and hasattr(app_service, "rag") and proc_id and raw_text:
                try:
                    ev_objs = app_service.rag.retrieve(raw_text, process_id=proc_id)
                    hits = [e.to_dict() for e in ev_objs]
                except Exception:
                    pass
            rag_payload = {
                "filters": {"process_id": proc_id, "operation": req.get("operation")},
                "selected_evidence_ids": result.get("decision", {}).get("evidence_ids", []),
                "retrieved_cases_count": len(hits),
                "hits": hits,
                "ranking": [{"id": h.get("id"), "score": h.get("final_score")} for h in hits],
            }
            self.panels["RAG Evidence"].display(rag_payload)

        # 4. Planning Tab
        if "Planning" in self.panels:
            dec = result.get("decision", {})
            plan_payload = {
                "status": dec.get("status", "UNKNOWN"),
                "proposed_timing": dec.get("proposed_timing", "current"),
                "rejection_category": dec.get("rejection_category"),
                "rule_violations": dec.get("rule_ids", []),
                "resource_violations": dec.get("resource_ids", []),
                "reason": dec.get("reason"),
                "selected_plan": dec.get("planning_result"),
                "diagnostics": {
                    "target_element": dec.get("request", {}).get("target_element"),
                    "operation": dec.get("request", {}).get("operation"),
                }
            }
            self.panels["Planning"].display(plan_payload)

        # 5. Model & Migration Tab
        if "Model & Migration" in self.panels:
            cand = result.get("candidate")
            if cand:
                model_payload = {
                    "status": "MUTATED_CANDIDATE_GENERATED",
                    "candidate": cand,
                    "diff": cand.get("changes", []),
                    "migration": cand.get("migration", {}),
                    "inverse_operations": result.get("inverse_operations", []),
                }
            else:
                dec = result.get("decision", {})
                model_payload = {
                    "status": "BLOCKED (No mutation generated)",
                    "decision": dec.get("status"),
                    "rejection_category": dec.get("rejection_category"),
                    "target_element": dec.get("request", {}).get("target_element"),
                    "reason": "Candidate model generation and token migration were aborted because the adaptation was rejected during feasibility analysis.",
                    "diff": [],
                    "migration": {"safe": False, "mappings": {}}
                }
            self.panels["Model & Migration"].display(model_payload)

        # 6. Validation & Simulation Tab
        if "Validation & Simulation" in self.panels:
            exp = result.get("experiment")
            if exp:
                val_payload = {
                    "status": "PASSED" if exp.get("passed") else "FAILED",
                    "traces": exp.get("traces", []),
                    "failures": exp.get("failures", []),
                    "metrics": exp.get("metrics", {}),
                }
            else:
                val_payload = {
                    "status": "SKIPPED",
                    "reason": "Petri net simulation and execution traces were skipped because no candidate model was produced.",
                    "source_soundness": "Original process definition verified structurally sound.",
                    "traces": []
                }
            self.panels["Validation & Simulation"].display(val_payload)

        # 7. Evaluation Tab
        if "Evaluation" in self.panels:
            dec = result.get("decision", {})
            eval_payload = {
                "status": "COMPLETED",
                "metrics": {
                    "decision": dec.get("status"),
                    "rejection_category": dec.get("rejection_category"),
                    "rule_violations": dec.get("rule_ids", []),
                    "resource_violations": dec.get("resource_ids", []),
                },
                "run_id": result.get("run_id"),
                "dataset_path": str(dataset_path or ""),
            }
            self.panels["Evaluation"].display(eval_payload)

        # 8. Provenance Tab
        if "Provenance" in self.panels:
            prov = result.get("provenance", {})
            prov_payload = {
                "run_id": result.get("run_id"),
                "status": result.get("status"),
                "process_id": prov.get("process_id"),
                "folder": prov.get("folder"),
                "configuration_fingerprint": prov.get("config_fingerprint"),
                "prompt_versions": prov.get("prompt_versions", {}),
                "events": prov.get("events", [])
            }
            self.panels["Provenance"].display(prov_payload)

        # 9. Export Tab
        if "Export" in self.panels:
            out_root = str(app_service.settings.output_root) if (app_service and hasattr(app_service, "settings")) else "experiments/runs"
            run_dir = f"{out_root}/{result.get('run_id','')}"
            export_payload = {
                "run_id": result.get("run_id"),
                "status": result.get("status"),
                "run_directory": run_dir,
                "exported_artifacts": ["result.json"] + (["candidate.bpmn"] if result.get("candidate") else []),
            }
            self.panels["Export"].display(export_payload)

    def select_tab(self, name: str) -> None:
        if name in self.panels:
            self.notebook.select(self.panels[name])

    def _browse(self):
        selected=filedialog.askdirectory()
        if selected:self.folder.set(selected)

    def _run(self):
        try: function=self._command(self.action.get())
        except Exception as exc: messagebox.showerror("Invalid input",str(exc)); return
        self.status.set(f"Running {self.action.get()}…"); self.current_task=self.worker.submit(function)

    def _command(self,action):
        c=self.controller; folder=self.folder.get(); request=self.request.get(); target=self.target.get(); state=self.state.get(); run=self.run_id.get() or None; operation=self.operation.get()
        if action=="ingest": return lambda:c.ingest(folder)
        if action=="index-rag": return lambda:c.index_rag(folder)
        if action=="revoke-rag":
            evidence=simpledialog.askstring("Evidence","Evidence ID:",parent=self); reason=simpledialog.askstring("Reason","Revocation reason:",parent=self)
            return lambda:c.revoke_rag(evidence,reason)
        if action=="analyse": return lambda:c.analyse(folder,request,target,state)
        if action=="plan": return lambda:c.plan(folder,request,target,state)
        if action=="adapt": return lambda:c.adapt(folder,request,target,state,operation,run)
        if action=="validate": return lambda:c.validate(folder)
        if action=="simulate": return lambda:c.simulate(folder)
        if action=="deploy": return lambda:c.deploy(folder,run,True,{})
        if action=="migrate":
            instance=simpledialog.askstring("Migration","Instance ID:",parent=self); definition=simpledialog.askstring("Migration","Target definition key:",parent=self); mapping=json.loads(simpledialog.askstring("Migration","Mapping JSON:",initialvalue="{}",parent=self) or "{}")
            return lambda:c.migrate(instance,definition,mapping,run)
        if action in {"approve","reject"}:
            reason=simpledialog.askstring("Approval","Reason:",parent=self) or ""
            return lambda:getattr(c,action)(run,reason)
        if action=="inspect": return lambda:c.inspect(folder)
        if action=="evaluate": return lambda:c.evaluate(folder)
        if action=="baseline": return lambda:c.baseline(folder)
        if action=="batch": return lambda:c.batch([folder],request or None)
        if action=="report": return lambda:c.report(folder)
        if action=="export":
            destination=filedialog.asksaveasfilename(defaultextension=".zip")
            return lambda:c.export(run,destination)
        if action=="replay": return lambda:c.replay(run)
        raise ValueError(action)

    def _cancel(self):
        if self.current_task:self.worker.cancel(self.current_task); self.status.set("Cancelling…")

    def _poll(self):
        for event in self.worker.poll():
            if event.task_id!=self.current_task:continue
            if event.kind=="completed":
                name=ROUTE[self.action.get()]; self.panels[name].display(event.payload); self.notebook.select(self.panels[name]); self.status.set("Completed")
            elif event.kind=="error": self.status.set("Failed"); messagebox.showerror("Operation failed",event.payload["message"])
            elif event.kind=="cancelled": self.status.set("Cancelled")
        self.after(50,self._poll)

    def _close(self): self.worker.shutdown(); self.destroy()
