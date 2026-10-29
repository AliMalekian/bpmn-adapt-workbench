"""Live Log panel (Tab 13) with event stream, live accuracy curve, provider telemetry, and error counters."""
from __future__ import annotations
import json
import queue
import time
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Any


INFO_LIVELOG = """Tab 13: Live Log & Telemetry Streaming

What this tab does:
Provides real-time event streaming, live accuracy progress curves, provider call frequency distributions, and error/retry counters.

Inputs and Controls:
- ⏸ Pause / ▶ Stream: Toggles real-time polling of events.
- Clear: Clears event history and resets visual chart buffers.
- Export Events: Exports collected telemetry stream to a JSONL file.
- Provider Filter: Filters displayed events by target provider model.
- Status Filter: Filters events by outcome (SUCCESS, FAILED, REJECT, APPROVE).

Outputs produced:
- Live streaming log output with timestamps, running average accuracy chart, provider bar breakdown, and error load gauge.

Caveats:
Listens both to in-memory events and incrementally follows active llm_calls.jsonl logs.
"""


class LiveLogPanel(ttk.Frame):
    """GUI Tab displaying real-time streaming evaluation telemetry and visual analytics."""

    def __init__(self, parent, event_queue: queue.Queue | None = None, log_file: str | None = None):
        super().__init__(parent, padding=8)
        self.event_queue = event_queue or queue.Queue()
        self.log_file = log_file or self._find_best_log_file()
        self._file_offset = 0
        self.is_streaming = True
        self.events_history: list[dict[str, Any]] = []
        self.accuracy_history: list[float] = []
        self.provider_counts: dict[str, int] = {}
        self.error_counts = {"total": 0, "retries": 0, "fatal": 0}
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.total_tokens: int = 0

        self._build_ui()
        self._init_file_watcher()
        self._start_polling()

    @staticmethod
    def _find_best_log_file() -> str:
        from pathlib import Path
        import glob
        base_dirs = [Path.cwd(), Path(__file__).resolve().parents[4]]
        candidates = []
        for b in base_dirs:
            candidates.extend([
                b / "experiments" / "live_evaluation_v4" / "llm_calls.jsonl",
                b / "experiments" / "live_evaluation_v3" / "llm_calls.jsonl",
                b / "live_evaluation_v3" / "llm_calls.jsonl",
            ])
            for m in glob.glob(str(b / "experiments" / "*" / "llm_calls.jsonl")):
                p_m = Path(m)
                if p_m.is_file() and p_m not in candidates:
                    candidates.append(p_m)
        for c in candidates:
            if c.is_file():
                pass
        existing = [c for c in candidates if c.is_file()]
        if existing:
            existing.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            return str(existing[0])
        return str(base_dirs[0] / "experiments" / "live_evaluation_v4" / "llm_calls.jsonl")

    def _init_file_watcher(self) -> None:
        """Sets up file position for live log reading and reads existing entries from start."""
        from pathlib import Path
        p = Path(self.log_file)
        if p.is_file():
            self._file_offset = 0
            if hasattr(self, "lbl_logfile"):
                self.lbl_logfile.configure(text=f"File: {p.name}")
        else:
            if hasattr(self, "txt_events"):
                self.txt_events.insert("end", f"[System] Waiting for logs ({self.log_file})...\n")

    def display(self, payload: Any) -> None:
        """Standard panel interface method."""
        if isinstance(payload, dict):
            self.add_event(payload)

    def add_event(self, event: dict[str, Any]) -> None:
        """Thread-safe submission of a telemetry event."""
        self.event_queue.put(event)

    def set_log_file(self, path: str) -> None:
        """Dynamically switch log file being followed."""
        from pathlib import Path
        self.log_file = str(path)
        self._file_offset = 0
        if hasattr(self, "lbl_logfile"):
            self.lbl_logfile.configure(text=f"File: {Path(path).name}")
        self._init_file_watcher()

    def _browse_log_file(self) -> None:
        chosen = filedialog.askopenfilename(
            title="Select Log File",
            filetypes=[("JSONL Log Files", "*.jsonl"), ("All Files", "*.*")],
            initialdir="experiments",
        )
        if chosen:
            self._clear_all()
            self.set_log_file(chosen)

    def _build_ui(self) -> None:
        from bpmn_adapt.gui.info_helper import add_info_button
        add_info_button(self, "Live Log", INFO_LIVELOG)

        # Top Toolbar: Controls + Filters
        top_bar = ttk.Frame(self)
        top_bar.pack(fill="x", pady=(0, 6))

        self.btn_toggle_stream = ttk.Button(top_bar, text="⏸ Pause", command=self._toggle_stream)
        self.btn_toggle_stream.pack(side="left", padx=2)
        ttk.Button(top_bar, text="Clear", command=self._clear_all).pack(side="left", padx=2)
        ttk.Button(top_bar, text="Export Events", command=self._export_events).pack(side="left", padx=2)
        ttk.Button(top_bar, text="📂 Select Log File", command=self._browse_log_file).pack(side="left", padx=2)
        self.lbl_logfile = ttk.Label(top_bar, text="", foreground="#64748b", font=("Segoe UI", 8))
        self.lbl_logfile.pack(side="left", padx=6)

        filter_frame = ttk.Frame(top_bar)
        filter_frame.pack(side="right")

        ttk.Label(filter_frame, text="Filter:").pack(side="left", padx=2)
        self.var_filter_prov = tk.StringVar(value="All providers")
        self.cb_prov = ttk.Combobox(filter_frame, textvariable=self.var_filter_prov, values=["All providers"], state="readonly", width=14)
        self.cb_prov.pack(side="left", padx=2)

        self.var_filter_status = tk.StringVar(value="All status")
        cb_stat = ttk.Combobox(filter_frame, textvariable=self.var_filter_status, values=["All status", "SUCCESS", "FAILED", "REJECT", "APPROVE"], state="readonly", width=11)
        cb_stat.pack(side="left", padx=2)

        # 4-Quadrant Grid (2x2)
        quad_frame = ttk.Frame(self)
        quad_frame.pack(fill="both", expand=True)
        quad_frame.rowconfigure(0, weight=1)
        quad_frame.rowconfigure(1, weight=1)
        quad_frame.columnconfigure(0, weight=1)
        quad_frame.columnconfigure(1, weight=1)

        # Quadrant 1 (Top-Left): Streaming Events
        q1 = ttk.LabelFrame(quad_frame, text="Streaming Events", padding=4)
        q1.grid(row=0, column=0, sticky="nsew", padx=3, pady=3)
        self.txt_events = tk.Text(q1, wrap="word", bg="#0f172a", fg="#f8fafc", font=("Consolas", 9))
        self.txt_events.pack(fill="both", expand=True)

        # Quadrant 2 (Top-Right): Live Accuracy Chart
        q2 = ttk.LabelFrame(quad_frame, text="Live Accuracy Chart", padding=4)
        q2.grid(row=0, column=1, sticky="nsew", padx=3, pady=3)
        self.canvas_acc = tk.Canvas(q2, bg="#ffffff", highlightthickness=0)
        self.canvas_acc.pack(fill="both", expand=True)
        self.canvas_acc.bind("<Configure>", lambda e: self._redraw_accuracy_chart())

        # Quadrant 3 (Bottom-Left): Provider Usage
        q3 = ttk.LabelFrame(quad_frame, text="Provider Usage", padding=4)
        q3.grid(row=1, column=0, sticky="nsew", padx=3, pady=3)
        self.canvas_providers = tk.Canvas(q3, bg="#ffffff", highlightthickness=0)
        self.canvas_providers.pack(fill="both", expand=True)
        self.canvas_providers.bind("<Configure>", lambda e: self._redraw_provider_chart())

        # Quadrant 4 (Bottom-Right): Errors and Retries
        q4 = ttk.LabelFrame(quad_frame, text="Errors and Retries", padding=4)
        q4.grid(row=1, column=1, sticky="nsew", padx=3, pady=3)
        self.canvas_errors = tk.Canvas(q4, bg="#ffffff", highlightthickness=0)
        self.canvas_errors.pack(fill="both", expand=True)
        self.canvas_errors.bind("<Configure>", lambda e: self._redraw_error_chart())

        # Bottom Bar: Progress & ETA
        bottom_bar = ttk.Frame(self)
        bottom_bar.pack(fill="x", pady=(4, 0))
        self.lbl_progress = ttk.Label(bottom_bar, text="Events received: 0")
        self.lbl_progress.pack(side="left")
        self.lbl_time = ttk.Label(bottom_bar, text="Stream active (polling 500ms)", foreground="green")
        self.lbl_time.pack(side="right")

    def _start_polling(self) -> None:
        self._poll_events()

    def _poll_events(self) -> None:
        if self.is_streaming:
            processed = 0
            # 1. Drain in-memory queue
            while not self.event_queue.empty() and processed < 50:
                try:
                    ev = self.event_queue.get_nowait()
                    self._process_single_event(ev)
                    processed += 1
                except queue.Empty:
                    break

            # 2. Incrementally read new lines from log file
            from pathlib import Path
            p = Path(self.log_file)
            if p.is_file():
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        f.seek(self._file_offset)
                        new_lines = f.readlines()
                        self._file_offset = f.tell()

                    for line in new_lines:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            p_tok = data.get("prompt_tokens")
                            c_tok = data.get("completion_tokens")
                            if not p_tok:
                                p_tok = max(1, len(data.get("system_prompt", "") + data.get("user_payload", "")) // 4)
                            if not c_tok:
                                c_tok = max(1, len(str(data.get("response", "") or data.get("raw_response", ""))) // 4)
                            t_tok = data.get("total_tokens") or (p_tok + c_tok)

                            ev = {
                                "provider": data.get("model") or data.get("provider", "LLM"),
                                "status": data.get("status", "SUCCESS"),
                                "latency": data.get("latency_seconds") or data.get("latency", 0.0),
                                "prompt_tokens": p_tok,
                                "completion_tokens": c_tok,
                                "total_tokens": t_tok,
                                "message": f"[{data.get('status', 'OK')}] {data.get('schema_name', '')} ({data.get('model', '')}) {data.get('latency_seconds', 0.0)}s | tokens: {t_tok:,}",
                            }
                            self._process_single_event(ev)
                            processed += 1
                        except Exception:
                            self.txt_events.insert("end", f"{line}\n")
                            self.txt_events.see("end")
                            processed += 1
                except Exception:
                    pass

            if processed > 0:
                self._redraw_accuracy_chart()
                self._redraw_provider_chart()
                self._redraw_error_chart()
                self.lbl_progress.configure(
                    text=f"Events: {len(self.events_history)} | In Tokens: {self.total_prompt_tokens:,} | Out Tokens: {self.total_completion_tokens:,} | Total: {self.total_tokens:,}"
                )

        self.after(500, self._poll_events)

    def _process_single_event(self, ev: dict[str, Any]) -> None:
        self.events_history.append(ev)
        prov = ev.get("provider", "unknown")
        status = ev.get("status", "SUCCESS")
        text = ev.get("message", json.dumps(ev))

        # Accumulate token metrics
        p_tok = ev.get("prompt_tokens", 0)
        c_tok = ev.get("completion_tokens", 0)
        t_tok = ev.get("total_tokens", 0) or (p_tok + c_tok)
        self.total_prompt_tokens += p_tok
        self.total_completion_tokens += c_tok
        self.total_tokens += t_tok

        # Update provider stats
        self.provider_counts[prov] = self.provider_counts.get(prov, 0) + 1
        curr_provs = sorted(self.provider_counts.keys())
        self.cb_prov.configure(values=["All providers"] + curr_provs)

        # Update accuracy history if present
        if "accuracy" in ev:
            self.accuracy_history.append(float(ev["accuracy"]))
        elif "correct" in ev:
            # Running average
            is_corr = 1.0 if ev["correct"] else 0.0
            if self.accuracy_history:
                prev_acc = self.accuracy_history[-1]
                n = len(self.accuracy_history)
                new_acc = (prev_acc * n + is_corr) / (n + 1)
                self.accuracy_history.append(new_acc)
            else:
                self.accuracy_history.append(is_corr)

        # Update error counts
        if status in ("FAILED", "ERROR"):
            self.error_counts["total"] += 1
            if ev.get("is_fatal", False):
                self.error_counts["fatal"] += 1
            else:
                self.error_counts["retries"] += 1

        # Append to event log text
        ts = time.strftime("[%H:%M:%S] ")
        self.txt_events.insert("end", f"{ts}{text}\n")
        self.txt_events.see("end")

    def _redraw_accuracy_chart(self) -> None:
        c = self.canvas_acc
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 50 or h < 50:
            return

        # Grid lines
        c.create_rectangle(40, 20, w - 20, h - 30, outline="#e2e8f0", fill="#f8fafc")
        c.create_text(25, 25, text="100%", fill="#64748b", font=("Segoe UI", 8))
        c.create_text(25, (h - 10) / 2, text="50%", fill="#64748b", font=("Segoe UI", 8))
        c.create_text(25, h - 35, text="0%", fill="#64748b", font=("Segoe UI", 8))

        if not self.accuracy_history:
            c.create_text(w / 2, h / 2, text="No accuracy data yet", fill="#94a3b8")
            return

        points = []
        n = len(self.accuracy_history)
        chart_w = w - 60
        chart_h = h - 50

        for i, acc in enumerate(self.accuracy_history):
            x = 40 + (i / max(1, n - 1)) * chart_w
            y = 20 + (1.0 - max(0.0, min(1.0, acc))) * chart_h
            points.append(x)
            points.append(y)

        if len(points) >= 4:
            c.create_line(points, fill="#2563eb", width=2, smooth=True)
            # Dot on latest point
            lx, ly = points[-2], points[-1]
            c.create_oval(lx - 4, ly - 4, lx + 4, ly + 4, fill="#1d4ed8", outline="#ffffff", width=1)
            c.create_text(lx, ly - 10, text=f"{self.accuracy_history[-1]*100:.1f}%", fill="#1e293b", font=("Segoe UI", 8, "bold"))

    def _redraw_provider_chart(self) -> None:
        c = self.canvas_providers
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 50 or h < 50:
            return

        if not self.provider_counts:
            c.create_text(w / 2, h / 2, text="No provider calls logged yet", fill="#94a3b8")
            return

        total_calls = sum(self.provider_counts.values())
        y_pos = 20
        bar_height = 18
        colors = ["#3b82f6", "#10b981", "#8b5cf6", "#f59e0b", "#ec4899"]

        for idx, (prov, count) in enumerate(self.provider_counts.items()):
            color = colors[idx % len(colors)]
            pct = (count / max(1, total_calls))
            bar_w = (w - 140) * pct

            c.create_text(10, y_pos + 9, anchor="w", text=f"{prov[:12]}:", font=("Segoe UI", 8, "bold"), fill="#1e293b")
            c.create_rectangle(85, y_pos, 85 + bar_w, y_pos + bar_height, fill=color, outline="")
            c.create_text(95 + bar_w, y_pos + 9, anchor="w", text=f"{count} ({pct*100:.0f}%)", font=("Segoe UI", 8), fill="#475569")
            y_pos += bar_height + 8
            if y_pos > h - 20:
                break

    def _redraw_error_chart(self) -> None:
        c = self.canvas_errors
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 50 or h < 50:
            return

        c.create_text(20, 25, anchor="w", text=f"Total Errors: {self.error_counts['total']}", font=("Segoe UI", 10, "bold"), fill="#dc2626")
        c.create_text(20, 50, anchor="w", text=f"Recovered Retries: {self.error_counts['retries']}", font=("Segoe UI", 9), fill="#d97706")
        c.create_text(20, 75, anchor="w", text=f"Fatal Aborts: {self.error_counts['fatal']}", font=("Segoe UI", 9), fill="#991b1b")

        # Visual indicator bar
        bar_y = 110
        c.create_rectangle(20, bar_y, w - 20, bar_y + 20, fill="#f1f5f9", outline="#e2e8f0")
        if self.error_counts["total"] > 0:
            err_w = min(w - 40, (self.error_counts["total"] / 20.0) * (w - 40))
            c.create_rectangle(20, bar_y, 20 + err_w, bar_y + 20, fill="#ef4444", outline="")
            c.create_text(w / 2, bar_y + 10, text=f"Error Load: {self.error_counts['total']} incident(s)", fill="#ffffff", font=("Segoe UI", 8, "bold"))
        else:
            c.create_text(w / 2, bar_y + 10, text="Clean Run (0 errors)", fill="#16a34a", font=("Segoe UI", 8, "bold"))

    def _toggle_stream(self) -> None:
        self.is_streaming = not self.is_streaming
        self.btn_toggle_stream.configure(text="▶ Stream" if not self.is_streaming else "⏸ Pause")
        self.lbl_time.configure(
            text="Stream paused" if not self.is_streaming else "Stream active (polling 500ms)",
            foreground="orange" if not self.is_streaming else "green",
        )

    def _clear_all(self) -> None:
        self.events_history.clear()
        self.accuracy_history.clear()
        self.provider_counts.clear()
        self.error_counts = {"total": 0, "retries": 0, "fatal": 0}
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.txt_events.delete("1.0", "end")
        self._redraw_accuracy_chart()
        self._redraw_provider_chart()
        self._redraw_error_chart()
        self.lbl_progress.configure(text="Events received: 0")

    def _export_events(self) -> None:
        dest = filedialog.asksaveasfilename(defaultextension=".jsonl", filetypes=[("JSONL files", "*.jsonl")])
        if dest:
            with open(dest, "w", encoding="utf-8") as f:
                for ev in self.events_history:
                    f.write(json.dumps(ev, ensure_ascii=False) + "\n")
