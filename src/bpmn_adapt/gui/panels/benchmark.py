"""Benchmark panel (Tab 12) for single-provider and multi-provider evaluation runs."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any

from bpmn_adapt.providers.manager import ProviderManager


INFO_BENCHMARK = """Tab 12: Benchmark Evaluation Suite

What this tab does:
Executes systematic single-provider or multi-provider evaluation campaigns across the 82 dataset processes, measuring accuracy, precision, recall, F1, latency, GED, and token preservation.

Inputs and Controls:
- Execution Mode: Single Provider (one model across suite) or Multi-Provider Comparison.
- Providers: Select which active models to run and compare.
- Dataset Root: Directory containing the 82 dataset folders.
- Request Types: Checkboxes for REMOVE, MODIFY, ADD, RE_ADD.
- Repetitions: Number of experimental trials per test case (1, 3, or 30).
- Screenshot Strategy: Automated UI capture profile (A Minimal, B Standard, C Full).
- Controls: ▶ Start, ⏸ Pause, ⏹ Stop, progress bar, and real-time telemetry stats.

Outputs produced:
- Complete metrics.json summary, tests.jsonl results, automated screenshot bundles, and comparative analysis tables.

Caveats:
Benchmarks execute real live LLM calls; ensure target providers have active quotas. Mid-run API keys can be updated in Tab 10.
"""


class BenchmarkPanel(ttk.Frame):
    """GUI Tab for configuring and launching benchmark runs with live progress tracking."""

    def __init__(self, parent, manager: ProviderManager | None = None, event_queue=None):
        super().__init__(parent, padding=8)
        self.manager = manager or ProviderManager()
        self.event_queue = event_queue
        self.is_running = False
        self.is_paused = False
        self._stop_requested = False

        self._build_ui()
        self._reload_providers()
        self.manager.subscribe(self._reload_providers)

    def display(self, payload: Any) -> None:
        """Display payload from task worker."""
        if isinstance(payload, dict):
            self._append_log(json.dumps(payload))

    def _build_ui(self) -> None:
        from bpmn_adapt.gui.info_helper import add_info_button
        add_info_button(self, "Benchmark", INFO_BENCHMARK)

        # Top Settings in a Paned or Scrollable container
        paned = ttk.PanedWindow(self, orient="vertical")
        paned.pack(fill="both", expand=True)

        config_frame = ttk.LabelFrame(paned, text="Benchmark Configuration", padding=8)
        paned.add(config_frame, weight=0)

        # Execution Mode
        m_frame = ttk.Frame(config_frame)
        m_frame.pack(fill="x", pady=2)
        ttk.Label(m_frame, text="Execution Mode:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 10))
        self.mode_var = tk.StringVar(value="single")
        ttk.Radiobutton(m_frame, text="Single Provider", variable=self.mode_var, value="single", command=self._toggle_mode).pack(side="left", padx=5)
        ttk.Radiobutton(m_frame, text="Multi-Provider Comparison", variable=self.mode_var, value="multi", command=self._toggle_mode).pack(side="left", padx=5)

        # Single Provider Section
        self.single_p_frame = ttk.Frame(config_frame)
        self.single_p_frame.pack(fill="x", pady=2)
        ttk.Label(self.single_p_frame, text="Provider:").pack(side="left", padx=(0, 4))
        self.single_p_var = tk.StringVar()
        self.single_p_cb = ttk.Combobox(self.single_p_frame, textvariable=self.single_p_var, state="readonly", width=35)
        self.single_p_cb.pack(side="left", padx=4)
        ttk.Button(self.single_p_frame, text="+", width=3, command=self._add_provider_inline).pack(side="left", padx=2)

        # Multi-Provider Section
        self.multi_p_frame = ttk.Frame(config_frame)
        ttk.Label(self.multi_p_frame, text="Providers to compare:").pack(anchor="w", pady=(2, 0))
        self.provider_checks_frame = ttk.Frame(self.multi_p_frame)
        self.provider_checks_frame.pack(fill="x", pady=2)
        self.multi_provider_vars: dict[str, tk.BooleanVar] = {}

        # Dataset Root
        d_frame = ttk.Frame(config_frame)
        d_frame.pack(fill="x", pady=2)
        ttk.Label(d_frame, text="Dataset Root:").pack(side="left", padx=(0, 4))
        self.dataset_root_var = tk.StringVar(value=r"E:\Implemention_dataset enriched")
        ttk.Entry(d_frame, textvariable=self.dataset_root_var, width=45).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(d_frame, text="Browse", command=self._browse_dataset_root).pack(side="left")

        # Request Types + Repetitions
        ops_rep_frame = ttk.Frame(config_frame)
        ops_rep_frame.pack(fill="x", pady=2)
        ttk.Label(ops_rep_frame, text="Request Types:").pack(side="left", padx=(0, 4))
        self.op_remove = tk.BooleanVar(value=True)
        self.op_modify = tk.BooleanVar(value=True)
        self.op_add = tk.BooleanVar(value=True)
        self.op_re_add = tk.BooleanVar(value=True)
        ttk.Checkbutton(ops_rep_frame, text="REMOVE", variable=self.op_remove).pack(side="left", padx=3)
        ttk.Checkbutton(ops_rep_frame, text="MODIFY", variable=self.op_modify).pack(side="left", padx=3)
        ttk.Checkbutton(ops_rep_frame, text="ADD", variable=self.op_add).pack(side="left", padx=3)
        ttk.Checkbutton(ops_rep_frame, text="RE_ADD", variable=self.op_re_add).pack(side="left", padx=3)

        ttk.Label(ops_rep_frame, text="Repetitions:").pack(side="left", padx=(15, 4))
        self.rep_var = tk.IntVar(value=3)
        self.rep_cb = ttk.Combobox(ops_rep_frame, textvariable=self.rep_var, values=(1, 3, 30), state="readonly", width=4)
        self.rep_cb.pack(side="left", padx=2)
        ttk.Label(ops_rep_frame, text="(1=dev, 3=standard, 30=full)", foreground="gray").pack(side="left", padx=4)

        # Screenshot Strategy
        shot_frame = ttk.Frame(config_frame)
        shot_frame.pack(fill="x", pady=2)
        ttk.Label(shot_frame, text="Screenshot Strategy:").pack(side="left", padx=(0, 4))
        self.strat_var = tk.StringVar(value="None (No Screenshots - Recommended)")
        ttk.Combobox(
            shot_frame, textvariable=self.strat_var,
            values=("None (No Screenshots - Recommended)", "A — Minimal", "B — Standard (~1,232)", "C — Full"),
            state="readonly", width=30
        ).pack(side="left", padx=4)
        self.shot_info_bar = tk.BooleanVar(value=True)
        self.shot_jpeg = tk.BooleanVar(value=False)
        self.shot_livelog = tk.BooleanVar(value=True)
        ttk.Checkbutton(shot_frame, text="Add info bar", variable=self.shot_info_bar).pack(side="left", padx=4)
        ttk.Checkbutton(shot_frame, text="Save as JPEG", variable=self.shot_jpeg).pack(side="left", padx=4)
        ttk.Checkbutton(shot_frame, text="Include Live Log", variable=self.shot_livelog).pack(side="left", padx=4)

        # Options: RAG Evidence & Failed Test Retry
        opt_frame = ttk.Frame(config_frame)
        opt_frame.pack(fill="x", pady=2)
        ttk.Label(opt_frame, text="Execution Options:").pack(side="left", padx=(0, 4))
        self.enable_rag_var = tk.BooleanVar(value=True)
        self.retry_failed_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_frame, text="✔ Enable RAG Context (Ablation Mode)", variable=self.enable_rag_var).pack(side="left", padx=4)
        ttk.Checkbutton(opt_frame, text="🔄 Retry Failed / Dropped Tests Only", variable=self.retry_failed_only_var).pack(side="left", padx=4)

        # Output Directory
        out_frame = ttk.Frame(config_frame)
        out_frame.pack(fill="x", pady=2)
        ttk.Label(out_frame, text="Output Directory:").pack(side="left", padx=(0, 4))
        self.out_dir_var = tk.StringVar(value="experiments/live_evaluation_v4")
        ttk.Entry(out_frame, textvariable=self.out_dir_var, width=45).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(out_frame, text="Browse", command=self._browse_out_dir).pack(side="left")

        # Controls & Status Frame
        run_control_frame = ttk.Frame(config_frame)
        run_control_frame.pack(fill="x", pady=(6, 2))
        self.btn_start = ttk.Button(run_control_frame, text="▶ Start", command=self._start_benchmark)
        self.btn_start.pack(side="left", padx=2)
        self.btn_retry_failed = ttk.Button(run_control_frame, text="🔄 Retry Failed Only", command=self._retry_failed_benchmark)
        self.btn_retry_failed.pack(side="left", padx=2)
        self.btn_pause = ttk.Button(run_control_frame, text="⏸ Pause", state="disabled", command=self._pause_benchmark)
        self.btn_pause.pack(side="left", padx=2)
        self.btn_stop = ttk.Button(run_control_frame, text="⏹ Stop", state="disabled", command=self._stop_benchmark)
        self.btn_stop.pack(side="left", padx=2)

        self.progress_bar = ttk.Progressbar(run_control_frame, orient="horizontal", mode="determinate")
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=8)
        self.lbl_progress = ttk.Label(run_control_frame, text="0/0 (0%)")
        self.lbl_progress.pack(side="left", padx=4)

        # Telemetry Stats row
        stats_frame = ttk.Frame(config_frame)
        stats_frame.pack(fill="x", pady=2)
        self.lbl_stats = ttk.Label(stats_frame, text="Stats: Completed: 0 | Errors: 0 | Fallbacks: 0", font=("Segoe UI", 9, "bold"))
        self.lbl_stats.pack(side="left")
        self.lbl_time = ttk.Label(stats_frame, text="Elapsed: 00:00:00 | ETA: --:--:--", foreground="gray")
        self.lbl_time.pack(side="right")

        # Bottom Paned Window: Live Log Tail
        log_frame = ttk.LabelFrame(paned, text="Live Log (tail)", padding=6)
        paned.add(log_frame, weight=1)

        self.txt_log = tk.Text(log_frame, height=9, wrap="word", bg="#0f172a", fg="#f8fafc", font=("Consolas", 9))
        self.txt_log.pack(fill="both", expand=True)

        # Footer Buttons
        footer = ttk.Frame(self)
        footer.pack(fill="x", pady=(4, 0))
        ttk.Button(footer, text="📊 View Live Metrics", command=self._switch_to_livelog).pack(side="left", padx=2)
        ttk.Button(footer, text="📁 Open Output Folder", command=self._open_output_folder).pack(side="left", padx=2)

        self._toggle_mode()

    def _toggle_mode(self) -> None:
        if self.mode_var.get() == "single":
            self.multi_p_frame.pack_forget()
            self.single_p_frame.pack(fill="x", pady=2)
        else:
            self.single_p_frame.pack_forget()
            self.multi_p_frame.pack(fill="x", pady=2)

    def _reload_providers(self) -> None:
        enabled = self.manager.enabled_providers()
        all_provs = self.manager.list()
        if enabled:
            single_vals = [f"{p['id']} ({p.get('name', p['id'])} - {p.get('model','')})" for p in enabled]
        else:
            single_vals = [f"{p['id']} ({p.get('name', p['id'])} - [Disabled/No Key])" for p in all_provs]

        self.single_p_cb.configure(values=single_vals)
        curr = self.single_p_var.get()
        if single_vals:
            if not curr or curr not in single_vals:
                self.single_p_var.set(single_vals[0])
        else:
            self.single_p_var.set("")

        for w in self.provider_checks_frame.winfo_children():
            w.destroy()

        self.multi_provider_vars.clear()
        for p in self.manager.list():
            pid = p["id"]
            var = tk.BooleanVar(value=bool(p.get("enabled") and str(p.get("api_key", "")).strip()))
            self.multi_provider_vars[pid] = var
            status_tag = "" if (p.get("enabled") and str(p.get("api_key", "")).strip()) else " [OFF/No Key]"
            chk = ttk.Checkbutton(self.provider_checks_frame, text=f"{p.get('name', pid)} ({p.get('model', '')}){status_tag}", variable=var)
            chk.pack(anchor="w", pady=1)

    def _browse_dataset_root(self) -> None:
        d = filedialog.askdirectory(initialdir=self.dataset_root_var.get())
        if d:
            self.dataset_root_var.set(d)

    def _browse_out_dir(self) -> None:
        d = filedialog.askdirectory(initialdir=self.out_dir_var.get())
        if d:
            self.out_dir_var.set(d)

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

    def _append_log(self, line: str) -> None:
        ts = time.strftime("[%H:%M:%S] ")
        self.txt_log.insert("end", ts + line + "\n")
        self.txt_log.see("end")

    def _switch_to_livelog(self) -> None:
        try:
            nb = self.winfo_toplevel().notebook
            for tab_id in nb.tabs():
                if "live log" in nb.tab(tab_id, "text").lower():
                    nb.select(tab_id)
                    return
        except Exception:
            pass

    def _open_output_folder(self) -> None:
        out_p = Path(self.out_dir_var.get()).resolve()
        out_p.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(out_p))
        else:
            subprocess.Popen(["xdg-open", str(out_p)])

    def _retry_failed_benchmark(self) -> None:
        self.retry_failed_only_var.set(True)
        self._append_log("Starting retry run for failed / socket dropped scenarios only...")
        self._start_benchmark(from_retry=True)

    def _start_benchmark(self, from_retry: bool = False) -> None:
        if not from_retry:
            self.retry_failed_only_var.set(False)
        self.is_running = True
        self.is_paused = False
        self._stop_requested = False
        self._stop_event = threading.Event()
        self.btn_start.configure(state="disabled")
        self.btn_retry_failed.configure(state="disabled")
        self.btn_pause.configure(state="normal", text="⏸ Pause")
        self.btn_stop.configure(state="normal")
        self._append_log("Starting benchmark execution run...")

        threading.Thread(target=self._run_benchmark_worker, daemon=True).start()

    def _pause_benchmark(self) -> None:
        if self.is_paused:
            self.is_paused = False
            self.btn_pause.configure(text="⏸ Pause")
            self._append_log("Benchmark resumed.")
        else:
            self.is_paused = True
            self.btn_pause.configure(text="▶ Resume")
            self._append_log("Benchmark paused.")

    def _stop_benchmark(self) -> None:
        self._stop_requested = True
        if hasattr(self, "_stop_event"):
            self._stop_event.set()
        self._append_log("Stop requested. Halting benchmark...")
        self.btn_stop.configure(state="disabled")
        self.btn_start.configure(state="normal")
        self.btn_retry_failed.configure(state="normal")
        self.is_running = False

    def _run_benchmark_worker(self) -> None:
        t_start = time.monotonic()
        from bpmn_adapt.evaluation.benchmark_runner import BenchmarkRunner

        # Gather UI parameters
        mode = self.mode_var.get()
        p_sel = self.single_p_var.get()
        selected_provider = p_sel.split()[0] if p_sel else "groq"
        compare_providers = [pid for pid, var in self.multi_provider_vars.items() if var.get()]

        req_types = []
        if self.op_remove.get(): req_types.append("REMOVE")
        if self.op_modify.get(): req_types.append("MODIFY")
        if self.op_add.get(): req_types.append("ADD")
        if self.op_re_add.get(): req_types.append("RE_ADD")
        if not req_types:
            req_types = ["REMOVE"]

        def on_prog(completed, total, msg, **kwargs):
            pct = int((completed / max(1, total)) * 100)
            elapsed = time.monotonic() - t_start
            eta = (elapsed / completed) * (total - completed) if completed > 0 else 0
            time_str = f"Elapsed: {time.strftime('%H:%M:%S', time.gmtime(elapsed))} | ETA: {time.strftime('%H:%M:%S', time.gmtime(eta))}"
            stats_str = f"Completed: {completed}/{total} ({pct}%)"

            res_dict = kwargs.get("result")
            ds_path = kwargs.get("dataset_path")
            app_svc = kwargs.get("app_service")
            b_def = kwargs.get("bundle_def")

            def update_ui():
                self.progress_bar["value"] = pct
                self.lbl_progress.configure(text=f"{completed}/{total} ({pct}%)")
                self.lbl_time.configure(text=time_str)
                self.lbl_stats.configure(text=stats_str)
                self._append_log(msg)
                if res_dict:
                    try:
                        top = self.winfo_toplevel()
                        if hasattr(top, "populate_inspection_tabs"):
                            top.populate_inspection_tabs(res_dict, dataset_path=ds_path, app_service=app_svc, bundle_def=b_def)
                    except Exception as e:
                        logger.debug("Live tab update error: %s", e)
            self.after(0, update_ui)

        # Sync Live Log panel to benchmark output directory
        out_path = Path(self.out_dir_var.get())
        try:
            top = self.winfo_toplevel()
            if hasattr(top, "panels") and "Live Log" in top.panels:
                top.panels["Live Log"].set_log_file(str(out_path / "llm_calls.jsonl"))
        except Exception:
            pass

        strat_str = self.strat_var.get().upper()
        if "NONE" in strat_str or "NO" in strat_str:
            shot_strat = "NONE"
        elif "A" in strat_str:
            shot_strat = "A"
        elif "B" in strat_str:
            shot_strat = "B"
        else:
            shot_strat = "C"

        try:
            runner = BenchmarkRunner(
                dataset_root=self.dataset_root_var.get(),
                mode=mode,
                provider=selected_provider,
                providers=compare_providers if mode == "multi" else [selected_provider],
                request_types=req_types,
                repetitions=self.rep_var.get(),
                output_dir=self.out_dir_var.get(),
                screenshot_strategy=shot_strat,
                allow_synthetic=False,
                resume=True,
                enable_rag=self.enable_rag_var.get(),
                retry_failed_only=self.retry_failed_only_var.get(),
                manager=self.manager,
                on_progress=on_prog,
                stop_event=self._stop_event,
            )
            res = runner.run()
            self.after(0, lambda: self._append_log(f"Benchmark finished successfully. Results: {len(res)} provider(s)"))

            # Update Comparison panel automatically with final results
            try:
                top = self.winfo_toplevel()
                if hasattr(top, "panels") and "Comparison" in top.panels:
                    top.panels["Comparison"].load_summary(res)
            except Exception:
                pass
        except Exception as exc:
            self.after(0, lambda: self._append_log(f"Benchmark run error: {exc}"))

        def finish_ui():
            self.is_running = False
            self.btn_start.configure(state="normal")
            self.btn_retry_failed.configure(state="normal")
            self.btn_pause.configure(state="disabled")
            self.btn_stop.configure(state="disabled")
            self._append_log("Benchmark execution finished.")
        self.after(0, finish_ui)
