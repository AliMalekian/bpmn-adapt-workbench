"""Manual Test panel (Tab 11) for interactive single-test execution and result inspection."""
from __future__ import annotations
import json
from pathlib import Path
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any

from bpmn_adapt.domain.models import AdaptationRequest, OperationType
from bpmn_adapt.gui.screenshot import AutomatedScreenshot
from bpmn_adapt.providers.manager import ProviderManager


INFO_MANUAL = """Tab 11: Interactive Manual Adaptation Test

What this tab does:
Allows interactive testing of single adaptation requests across any selected dataset folder and provider model, visualizing decision outcomes, rule triggers, resource assignments, and timing.

Inputs and Controls:
- Provider: Selects the active LLM provider (must be enabled in Provider Config).
- Dataset: Choose a dataset from the 82 available processes or browse for one.
- Operation: Action type (REMOVE, MODIFY, ADD, RE_ADD).
- Target Element: BPMN element name to adapt.
- Request Text: Natural language user instruction.
- State ID: Current process execution state / active token marking.
- ▶ Run Adaptation: Executes the adaptation pipeline through the multi-agent system.
- 💾 Save Result / 📷 Save Screenshot / 🔍 View Raw Payload: Export results and visuals.

Outputs produced:
- Decision (APPROVE, REJECT, ALTERNATIVE_PROPOSED), Rejection Category, Triggered Rules, Resource Constraints, Proposed Timing, Reason explanation, and Latency.

Caveats:
A valid enabled provider with an active API key is required for live reasoning.
"""


class ManualTestPanel(ttk.Frame):
    """GUI Tab for executing and visualizing a single BPMN adaptation request."""

    def __init__(self, parent, manager: ProviderManager | None = None, dataset_root: str = "E:/Implemention_dataset enriched"):
        super().__init__(parent, padding=8)
        self.manager = manager or ProviderManager()
        self.dataset_root = Path(dataset_root)
        self.last_result: dict[str, Any] | None = None

        self._build_ui()
        self._populate_providers()
        self._populate_datasets()
        self.manager.subscribe(self._populate_providers)

    def display(self, payload: Any) -> None:
        """Display result payload passed from controller or worker."""
        if isinstance(payload, dict):
            self._render_result(payload)

    def _build_ui(self) -> None:
        from bpmn_adapt.gui.info_helper import add_info_button
        add_info_button(self, "Manual Test", INFO_MANUAL)

        # Form Container
        form_frame = ttk.LabelFrame(self, text="Manual Test Execution Parameters", padding=8)
        form_frame.pack(fill="x", pady=(0, 6))

        # Row 0: Provider + Add button
        ttk.Label(form_frame, text="Provider:").grid(row=0, column=0, sticky="w", pady=2)
        p_row = ttk.Frame(form_frame)
        p_row.grid(row=0, column=1, sticky="ew", pady=2)
        self.var_provider = tk.StringVar()
        self.cb_provider = ttk.Combobox(p_row, textvariable=self.var_provider, state="readonly", width=36)
        self.cb_provider.pack(side="left", fill="x", expand=True)
        ttk.Button(p_row, text="+", width=3, command=self._add_provider_inline).pack(side="left", padx=3)

        # Row 1: Dataset + Browse button
        ttk.Label(form_frame, text="Dataset:").grid(row=1, column=0, sticky="w", pady=2)
        d_row = ttk.Frame(form_frame)
        d_row.grid(row=1, column=1, sticky="ew", pady=2)
        self.var_dataset = tk.StringVar()
        self.cb_dataset = ttk.Combobox(d_row, textvariable=self.var_dataset, width=36)
        self.cb_dataset.pack(side="left", fill="x", expand=True)
        ttk.Button(d_row, text="Browse", width=7, command=self._browse_dataset).pack(side="left", padx=3)

        # Row 2: Operation
        ttk.Label(form_frame, text="Operation:").grid(row=2, column=0, sticky="w", pady=2)
        self.var_op = tk.StringVar(value="REMOVE")
        self.cb_op = ttk.Combobox(form_frame, textvariable=self.var_op, values=("REMOVE", "MODIFY", "ADD", "RE_ADD"), state="readonly", width=15)
        self.cb_op.grid(row=2, column=1, sticky="w", pady=2)

        # Row 3: Target Element
        ttk.Label(form_frame, text="Target Element:").grid(row=3, column=0, sticky="w", pady=2)
        self.var_target = tk.StringVar(value="Package goods")
        ttk.Entry(form_frame, textvariable=self.var_target, width=42).grid(row=3, column=1, sticky="ew", pady=2)

        # Row 4: Raw Request Text
        ttk.Label(form_frame, text="Request Text:").grid(row=4, column=0, sticky="w", pady=2)
        self.var_req = tk.StringVar(value="Remove the task")
        ttk.Entry(form_frame, textvariable=self.var_req, width=42).grid(row=4, column=1, sticky="ew", pady=2)

        # Row 5: State ID and Action Selector
        row5 = ttk.Frame(form_frame)
        row5.grid(row=5, column=0, columnspan=2, sticky="ew", pady=2)
        ttk.Label(row5, text="State ID:").pack(side="left")
        self.var_state = tk.StringVar(value="state_1")
        ttk.Entry(row5, textvariable=self.var_state, width=12).pack(side="left", padx=(4, 16))

        ttk.Label(row5, text="Action:").pack(side="left")
        self.var_action = tk.StringVar(value="adapt (Full Adaptation)")
        self.cb_action = ttk.Combobox(row5, textvariable=self.var_action, values=(
            "adapt (Full Adaptation)",
            "plan (Planning Only)",
            "inspect (DB Facts)",
            "validate (Validation Only)",
            "simulate (Simulation Only)",
            "ingest (Dataset Ingestion)"
        ), state="readonly", width=25)
        self.cb_action.pack(side="left", padx=4)

        form_frame.columnconfigure(1, weight=1)

        # Execution Button Bar
        run_bar = ttk.Frame(self)
        run_bar.pack(fill="x", pady=6)
        self.btn_run = ttk.Button(run_bar, text="▶ Run Adaptation", style="Primary.TButton", command=self._run_adaptation)
        self.btn_run.pack(side="left", padx=2)
        self.lbl_exec_status = ttk.Label(run_bar, text="", font=("Segoe UI", 9, "bold"), foreground="#2563EB")
        self.lbl_exec_status.pack(side="left", padx=8)

        # Result Panel
        res_frame = ttk.LabelFrame(self, text="Execution Result", padding=8)
        res_frame.pack(fill="both", expand=True, pady=4)

        meta_grid = ttk.Frame(res_frame)
        meta_grid.pack(fill="x", pady=(0, 6))

        ttk.Label(meta_grid, text="Decision:", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w")
        self.lbl_decision = ttk.Label(meta_grid, text="—", font=("Segoe UI", 11, "bold"))
        self.lbl_decision.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(meta_grid, text="Category:", font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w", padx=(12, 0))
        self.lbl_category = ttk.Label(meta_grid, text="—")
        self.lbl_category.grid(row=0, column=3, sticky="w", padx=6)

        ttk.Label(meta_grid, text="Timing:", font=("Segoe UI", 9, "bold")).grid(row=0, column=4, sticky="w", padx=(12, 0))
        self.lbl_timing = ttk.Label(meta_grid, text="—")
        self.lbl_timing.grid(row=0, column=5, sticky="w", padx=6)

        ttk.Label(meta_grid, text="Rule IDs:", font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w", pady=3)
        self.lbl_rules = ttk.Label(meta_grid, text="[]")
        self.lbl_rules.grid(row=1, column=1, sticky="w", padx=6, pady=3)

        ttk.Label(meta_grid, text="Resource IDs:", font=("Segoe UI", 9, "bold")).grid(row=1, column=2, sticky="w", padx=(12, 0), pady=3)
        self.lbl_resources = ttk.Label(meta_grid, text="[]")
        self.lbl_resources.grid(row=1, column=3, sticky="w", padx=6, pady=3)

        ttk.Label(meta_grid, text="Provider:", font=("Segoe UI", 9, "bold")).grid(row=2, column=0, sticky="w")
        self.lbl_provider = ttk.Label(meta_grid, text="—")
        self.lbl_provider.grid(row=2, column=1, columnspan=2, sticky="w", padx=6)

        ttk.Label(meta_grid, text="Latency:", font=("Segoe UI", 9, "bold")).grid(row=2, column=3, sticky="w", padx=(12, 0))
        self.lbl_latency = ttk.Label(meta_grid, text="—")
        self.lbl_latency.grid(row=2, column=4, sticky="w", padx=6)

        # Reason & Details Text
        ttk.Label(res_frame, text="Justification & Diagnostic Trace:", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(4, 2))
        self.txt_reason = tk.Text(res_frame, height=7, wrap="word")
        self.txt_reason.pack(fill="both", expand=True)

        # Action Buttons below Results
        res_actions = ttk.Frame(self)
        res_actions.pack(fill="x", pady=4)
        ttk.Button(res_actions, text="💾 Save Result", command=self._save_result).pack(side="left", padx=2)
        ttk.Button(res_actions, text="📷 Save Screenshot", command=self._save_screenshot).pack(side="left", padx=2)
        ttk.Button(res_actions, text="🔍 View Raw Payload", command=self._view_raw).pack(side="left", padx=2)

    def _populate_providers(self) -> None:
        enabled = self.manager.enabled_providers()
        all_provs = self.manager.list()
        # Prefer enabled providers; if none enabled, show all with status note so user knows what is available
        if enabled:
            vals = [f"{p['id']} ({p.get('name', p['id'])} - {p.get('model','')})" for p in enabled]
        else:
            vals = [f"{p['id']} ({p.get('name', p['id'])} - [Disabled/No Key])" for p in all_provs]

        self.cb_provider.configure(values=vals)
        curr = self.var_provider.get()
        if vals:
            if not curr or curr not in vals:
                self.var_provider.set(vals[0])
        else:
            self.var_provider.set("")

    def _populate_datasets(self) -> None:
        if not self.dataset_root.is_dir():
            return
        folders = [d.name for d in self.dataset_root.iterdir() if d.is_dir()]
        self.cb_dataset.configure(values=sorted(folders))
        if folders and not self.var_dataset.get():
            self.var_dataset.set(folders[0])

    def _browse_dataset(self) -> None:
        d = filedialog.askdirectory(initialdir=str(self.dataset_root))
        if d:
            self.var_dataset.set(Path(d).name)

    def _add_provider_inline(self) -> None:
        """Opens Provider Configuration tab so user can configure endpoints, keys, and enable them properly."""
        try:
            nb = self.winfo_toplevel().notebook
            for tab_id in nb.tabs():
                if "provider configuration" in nb.tab(tab_id, "text").lower():
                    nb.select(tab_id)
                    return
        except Exception:
            pass
        messagebox.showinfo("Provider Configuration", "Please configure and enable your providers in the 'Provider Configuration' tab.", parent=self)

    def _run_adaptation(self) -> None:
        prov_selection = self.var_provider.get()
        if not prov_selection:
            messagebox.showwarning("Warning", "Please select a provider.")
            return
        prov_id = prov_selection.split()[0]
        dataset_name = self.var_dataset.get().strip()
        if not dataset_name:
            messagebox.showwarning("Warning", "Please select a dataset folder.")
            return

        dataset_path = self.dataset_root / dataset_name
        if not dataset_path.is_dir():
            messagebox.showerror("Error", f"Dataset folder not found: {dataset_path}")
            return

        self.btn_run.configure(state="disabled")
        self.lbl_exec_status.configure(text="Running adaptation...", foreground="blue")

        def run_thread():
            t0 = time.monotonic()
            try:
                from bpmn_adapt.config import Settings
                from bpmn_adapt.application.service import RuntimeAdaptationApplication

                # Build client for this specific provider
                client = self.manager.build_client(prov_id)
                settings = Settings.load(overrides={"llm_mode": "live"})
                app_service = RuntimeAdaptationApplication.from_settings(settings)
                app_service.llm = client
                app_service.orchestrator.llm = client
                app_service.orchestrator.analyst.llm = client
                app_service.orchestrator.modeler.llm = client
                app_service.orchestrator.experimenter.llm = client

                action_choice = self.var_action.get()

                if "ingest" in action_choice:
                    bundle = app_service.ingest(dataset_path)
                    latency = time.monotonic() - t0
                    def done_ingest():
                        self.lbl_exec_status.configure(text=f"Ingested ({latency:.2f}s)", foreground="green")
                        self.btn_run.configure(state="normal")
                        try:
                            top = self.winfo_toplevel()
                            if hasattr(top, "panels") and "Project" in top.panels:
                                top.panels["Project"].display(bundle.definition.to_dict())
                                top.select_tab("Project")
                        except Exception:
                            pass
                    self.after(0, done_ingest)
                    return

                if "inspect" in action_choice:
                    facts = app_service.inspect(dataset_path)
                    latency = time.monotonic() - t0
                    def done_inspect():
                        self.lbl_exec_status.configure(text=f"Inspected ({latency:.2f}s)", foreground="green")
                        self.btn_run.configure(state="normal")
                        try:
                            top = self.winfo_toplevel()
                            if hasattr(top, "panels") and "DB Facts" in top.panels:
                                top.panels["DB Facts"].display(facts)
                                top.select_tab("DB Facts")
                        except Exception:
                            pass
                    self.after(0, done_inspect)
                    return

                if "validate" in action_choice:
                    val = app_service.validate_folder(dataset_path)
                    latency = time.monotonic() - t0
                    def done_val():
                        self.lbl_exec_status.configure(text=f"Validated ({latency:.2f}s)", foreground="green")
                        self.btn_run.configure(state="normal")
                        try:
                            top = self.winfo_toplevel()
                            if hasattr(top, "panels") and "Validation & Simulation" in top.panels:
                                top.panels["Validation & Simulation"].display({"validation": val, "traces": []})
                                top.select_tab("Validation & Simulation")
                        except Exception:
                            pass
                    self.after(0, done_val)
                    return

                if "plan" in action_choice:
                    plan_res = app_service.plan_folder(
                        dataset_path,
                        self.var_req.get(),
                        target=self.var_target.get(),
                        state_id=self.var_state.get(),
                    )
                    latency = time.monotonic() - t0
                    def done_plan():
                        self.lbl_exec_status.configure(text=f"Planned ({latency:.2f}s)", foreground="green")
                        self.btn_run.configure(state="normal")
                        try:
                            top = self.winfo_toplevel()
                            if hasattr(top, "panels") and "Planning" in top.panels:
                                top.panels["Planning"].display(plan_res if isinstance(plan_res, dict) else plan_res.to_dict())
                                top.select_tab("Planning")
                        except Exception:
                            pass
                    self.after(0, done_plan)
                    return

                # Execute adaptation via adapt_folder
                result = app_service.adapt_folder(
                    dataset_path,
                    self.var_req.get(),
                    target=self.var_target.get(),
                    operation=self.var_op.get(),
                    state_id=self.var_state.get(),
                )
                latency = time.monotonic() - t0

                res_dict = {
                    "status": "SUCCESS",
                    "decision": result.decision.status.value,
                    "rejection_category": result.decision.rejection_category,
                    "rule_ids": list(result.decision.rule_ids),
                    "resource_ids": list(result.decision.resource_ids),
                    "proposed_timing": getattr(result.decision, "proposed_timing", "current"),
                    "reason": result.decision.reason,
                    "provider": prov_selection,
                    "latency": latency,
                    "result_status": result.status,
                }

                def done_ui():
                    self._render_result(res_dict)
                    self.lbl_exec_status.configure(text=f"Done ({latency:.2f}s)", foreground="green")
                    self.btn_run.configure(state="normal")
                    try:
                        top = self.winfo_toplevel()
                        if hasattr(top, "populate_inspection_tabs"):
                            top.populate_inspection_tabs(
                                result=result.to_dict(),
                                dataset_path=str(dataset_path),
                                app_service=app_service
                            )
                    except Exception:
                        pass
                self.after(0, done_ui)

            except Exception as exc:
                latency = time.monotonic() - t0
                err_dict = {
                    "status": "ERROR",
                    "decision": "ERROR",
                    "rejection_category": "EXECUTION_EXCEPTION",
                    "rule_ids": [],
                    "resource_ids": [],
                    "proposed_timing": "none",
                    "reason": str(exc),
                    "provider": prov_selection,
                    "latency": latency,
                }
                def err_ui():
                    self._render_result(err_dict)
                    self.lbl_exec_status.configure(text="Failed", foreground="red")
                    self.btn_run.configure(state="normal")
                self.after(0, err_ui)

        threading.Thread(target=run_thread, daemon=True).start()

    def _render_result(self, res: dict[str, Any]) -> None:
        self.last_result = res
        decision = res.get("decision", "—")
        self.lbl_decision.configure(text=decision)
        if decision == "APPROVE":
            self.lbl_decision.configure(foreground="green")
        elif decision == "REJECT":
            self.lbl_decision.configure(foreground="red")
        else:
            self.lbl_decision.configure(foreground="#d97706")  # amber

        self.lbl_category.configure(text=res.get("rejection_category") or "(none)")
        self.lbl_timing.configure(text=res.get("proposed_timing") or "current")
        self.lbl_rules.configure(text=str(res.get("rule_ids", [])))
        self.lbl_resources.configure(text=str(res.get("resource_ids", [])))
        self.lbl_provider.configure(text=res.get("provider", "—"))
        self.lbl_latency.configure(text=f"{res.get('latency', 0.0):.2f}s")

        self.txt_reason.delete("1.0", "end")
        self.txt_reason.insert("1.0", res.get("reason", ""))

    def _save_result(self) -> None:
        if not self.last_result:
            messagebox.showwarning("Warning", "No result to save.")
            return
        dest = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if dest:
            Path(dest).write_text(json.dumps(self.last_result, indent=2, ensure_ascii=False), encoding="utf-8")
            messagebox.showinfo("Saved", f"Result saved to {dest}")

    def _save_screenshot(self) -> None:
        if not self.last_result:
            messagebox.showwarning("Warning", "No result to capture.")
            return
        desktop_root = self.winfo_toplevel()
        shot = AutomatedScreenshot(desktop_root, output_root="screenshots")
        path = shot.capture_single_tab(
            tab_name="Manual Test",
            test_id="manual",
            dataset_name=self.var_dataset.get().strip() or "manual_dataset",
            operation=self.var_op.get(),
            target=self.var_target.get(),
            decision=self.last_result.get("decision", "UNKNOWN"),
            provider=self.var_provider.get().split()[0] if self.var_provider.get() else "unknown",
            model="model",
            latency=self.last_result.get("latency", 0.0),
        )
        if path:
            messagebox.showinfo("Screenshot Captured", f"Screenshot saved to:\n{path}")

    def _view_raw(self) -> None:
        if not self.last_result:
            messagebox.showwarning("Warning", "No result available.")
            return
        top = tk.Toplevel(self)
        top.title("Raw Execution Result")
        top.geometry("600x450")
        txt = tk.Text(top, wrap="none")
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", json.dumps(self.last_result, indent=2, ensure_ascii=False))
