"""Comparison panel (Tab 14) for multi-provider statistical comparison, charts, and report generation."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Any


INFO_COMPARISON = """Tab 14: Multi-Provider Statistical Comparison

What this tab does:
Aggregates, ranks, and statistically validates multi-provider benchmark campaigns, rendering comparison tables, pairwise McNemar contingency tests, and visual comparative charts.

Inputs and Controls:
- Export Comparison Report: Exports the statistical comparison matrix and Markdown synthesis.
- Open Output Folder: Opens the local report directory containing charts and summaries.

Outputs produced:
- Comparison summary table (Accuracy, Precision, Recall, F1, Latency, Error Rate).
- Statistical Significance: Pairwise McNemar test p-values and odds ratios.
- Visual Charts: Accuracy comparison bar chart and latency distribution chart.
- Winner Banner: Identifies statistically dominant model based on accuracy and F1 score.

Caveats:
Populated automatically upon completion of a Multi-Provider Comparison benchmark run.
"""


class ComparisonPanel(ttk.Frame):
    """GUI Tab displaying comparative benchmarks, statistical significance, and visual charts."""

    def __init__(self, parent, report_dir: str = "experiments/comparison"):
        super().__init__(parent, padding=8)
        self.report_dir = Path(report_dir)
        self.summary_data: dict[str, Any] = {}

        self._build_ui()
        self._auto_load_recent()

    def display(self, payload: Any) -> None:
        """Display summary comparison data."""
        if isinstance(payload, dict):
            self.load_summary(payload)

    def load_summary(self, data: dict[str, Any]) -> None:
        self.summary_data = data
        self._render_table()
        self._render_stats()
        self._render_charts()

    def _build_ui(self) -> None:
        from bpmn_adapt.gui.info_helper import add_info_button
        add_info_button(self, "Comparison", INFO_COMPARISON)

        # Header + Action buttons
        hdr = ttk.Frame(self)
        hdr.pack(fill="x", pady=(0, 6))

        ttk.Label(hdr, text="Benchmark Results & Provider Analytics", font=("Segoe UI", 12, "bold")).pack(side="left")
        ttk.Button(hdr, text="Export Comparison Report", command=self._export_report).pack(side="right", padx=3)
        ttk.Button(hdr, text="Open Output Folder", command=self._open_folder).pack(side="right", padx=3)
        ttk.Button(hdr, text="🔄 Load / Refresh", command=self._auto_load_recent).pack(side="right", padx=3)

        # Winner Banner
        self.winner_banner = ttk.Label(self, text="Status: Ready to load benchmark results", font=("Segoe UI", 10, "bold"), foreground="#2563eb")
        self.winner_banner.pack(anchor="w", pady=(0, 6))

        # Main Paned Window
        paned = ttk.PanedWindow(self, orient="vertical")
        paned.pack(fill="both", expand=True)

        # Top: Table + Statistical Significance
        top_split = ttk.Frame(paned)
        paned.add(top_split, weight=1)

        # Provider Summary Table
        tbl_frame = ttk.LabelFrame(top_split, text="Provider Summary Table", padding=6)
        tbl_frame.pack(side="left", fill="both", expand=True, padx=(0, 4))

        cols = ("provider", "acc", "f1", "lat", "err", "in_tok", "out_tok", "tot_tok")
        self.tree = ttk.Treeview(tbl_frame, columns=cols, show="headings", height=5)
        self.tree.heading("provider", text="Provider")
        self.tree.heading("acc", text="Acc (%)")
        self.tree.heading("f1", text="F1 (%)")
        self.tree.heading("lat", text="Lat (s)")
        self.tree.heading("err", text="Err (%)")
        self.tree.heading("in_tok", text="In Tokens")
        self.tree.heading("out_tok", text="Out Tokens")
        self.tree.heading("tot_tok", text="Total Tokens")

        self.tree.column("provider", width=130)
        self.tree.column("acc", width=60, anchor="center")
        self.tree.column("f1", width=60, anchor="center")
        self.tree.column("lat", width=60, anchor="center")
        self.tree.column("err", width=60, anchor="center")
        self.tree.column("in_tok", width=75, anchor="center")
        self.tree.column("out_tok", width=75, anchor="center")
        self.tree.column("tot_tok", width=80, anchor="center")
        self.tree.pack(fill="both", expand=True)

        # Statistical Tests Box
        stats_frame = ttk.LabelFrame(top_split, text="Statistical Hypothesis Tests (McNemar)", padding=6)
        stats_frame.pack(side="right", fill="both", expand=True, padx=(4, 0))

        self.txt_stats = tk.Text(stats_frame, width=38, height=5, wrap="word", bg="#f8fafc", font=("Consolas", 9))
        self.txt_stats.pack(fill="both", expand=True)

        # Bottom: Canvas for Charts (Accuracy, Grouped Bar, Latency)
        chart_frame = ttk.LabelFrame(paned, text="Comparative Visual Analytics", padding=6)
        paned.add(chart_frame, weight=2)

        self.chart_canvas = tk.Canvas(chart_frame, bg="#ffffff", highlightthickness=0)
        self.chart_canvas.pack(fill="both", expand=True)
        self.chart_canvas.bind("<Configure>", lambda e: self._render_charts())

    def _extract_tokens_from_folder(self, folder: Path) -> dict[str, Any]:
        """Reads llm_calls.jsonl if present to extract or estimate token usage."""
        llm_calls_f = folder / "llm_calls.jsonl"
        in_tok, out_tok = 0, 0
        if llm_calls_f.is_file():
            try:
                for line in llm_calls_f.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if not line.strip():
                        continue
                    c = json.loads(line)
                    p = c.get("prompt_tokens")
                    o = c.get("completion_tokens")
                    if not p:
                        p = max(1, len(c.get("system_prompt", "") + c.get("user_payload", "")) // 4)
                    if not o:
                        o = max(1, len(str(c.get("response", "") or c.get("raw_response", ""))) // 4)
                    in_tok += p
                    out_tok += o
            except Exception:
                pass
        tot = in_tok + out_tok
        return {
            "total_prompt_tokens": in_tok,
            "total_completion_tokens": out_tok,
            "total_tokens": tot,
            "estimated_cost_flash_usd": round((in_tok * 0.15 + out_tok * 0.60) / 1_000_000, 4),
            "estimated_cost_flagship_usd": round((in_tok * 3.00 + out_tok * 15.00) / 1_000_000, 4),
        }

    def _auto_load_recent(self) -> None:
        """Auto-detects and loads metrics from recent benchmark runs (supports both single & multi provider)."""
        import glob
        base_dirs = [
            Path.cwd(),
            Path(__file__).resolve().parents[4],
        ]
        candidates = []
        for b in base_dirs:
            candidates.extend([
                b / "experiments" / "live_evaluation_v4",
                b / "experiments" / "live_evaluation_v3",
                b / self.report_dir,
            ])
            for match in glob.glob(str(b / "experiments" / "*")):
                p_match = Path(match)
                if p_match.is_dir() and p_match not in candidates:
                    candidates.append(p_match)

        loaded = False
        for folder in candidates:
            if not folder.exists():
                continue
            metrics_f = folder / "metrics.json"
            summary_f = folder / "comparison_summary.json"
            tests_f = folder / "tests.jsonl"
            folder_tokens = self._extract_tokens_from_folder(folder)

            # Prioritize tests.jsonl if it contains fresher or more complete runs than metrics.json
            use_tests_jsonl = False
            tests_parsed = []
            if tests_f.is_file():
                try:
                    for line in tests_f.read_text(encoding="utf-8").splitlines():
                        if line.strip():
                            tests_parsed.append(json.loads(line))
                    if tests_parsed:
                        if not metrics_f.is_file():
                            use_tests_jsonl = True
                        else:
                            # Compare mtime or test counts
                            m_data = {}
                            try:
                                m_data = json.loads(metrics_f.read_text(encoding="utf-8"))
                            except Exception:
                                pass
                            m_total = m_data.get("total_tests", 0) if isinstance(m_data, dict) else 0
                            if len(tests_parsed) >= m_total or tests_f.stat().st_mtime > metrics_f.stat().st_mtime:
                                use_tests_jsonl = True
                except Exception:
                    pass

            if use_tests_jsonl and tests_parsed:
                try:
                    p_name = tests_parsed[0].get("provider", "LLM Provider")
                    model = tests_parsed[0].get("model", "")
                    correct = sum(1 for t in tests_parsed if t.get("matched_ground_truth"))
                    total = len(tests_parsed)
                    acc = round((correct / max(1, total)) * 100, 1)
                    lats = [t.get("latency_s", 0.0) for t in tests_parsed if t.get("latency_s") is not None]
                    avg_lat = round(sum(lats) / max(1, len(lats)), 2)
                    in_tok = folder_tokens.get("total_prompt_tokens", 0) or sum(t.get("prompt_tokens", 0) for t in tests_parsed)
                    out_tok = folder_tokens.get("total_completion_tokens", 0) or sum(t.get("completion_tokens", 0) for t in tests_parsed)
                    tot_tok = folder_tokens.get("total_tokens", 0) or (in_tok + out_tok)
                    synth = {
                        p_name: {
                            "provider_id": p_name,
                            "name": p_name,
                            "model": model,
                            "accuracy": acc,
                            "precision": acc,
                            "recall": acc,
                            "f1": acc,
                            "avg_latency_s": avg_lat,
                            "error_rate": round(sum(1 for t in tests_parsed if t.get("decision") == "ERROR") / max(1, total) * 100, 1),
                            "total_tests": total,
                            "prompt_tokens": in_tok,
                            "completion_tokens": out_tok,
                            "total_tokens": tot_tok,
                            "token_metrics": folder_tokens,
                            "xsd_pass_rate": round(sum(1 for t in tests_parsed if t.get("xsd_valid")) / max(1, total), 2),
                            "simulation_success_rate": round(sum(1 for t in tests_parsed if t.get("simulation_success")) / max(1, total), 2),
                            "avg_token_preservation": round(sum(t.get("token_preservation_rate", 1.0) for t in tests_parsed) / max(1, total), 2),
                        }
                    }
                    self.load_summary(synth)
                    loaded = True
                    break
                except Exception:
                    pass

            if summary_f.is_file():
                try:
                    data = json.loads(summary_f.read_text(encoding="utf-8"))
                    self.load_summary(data)
                    loaded = True
                    break
                except Exception:
                    pass

            if metrics_f.is_file():
                try:
                    data = json.loads(metrics_f.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        if not data.get("prompt_tokens") and folder_tokens.get("total_prompt_tokens"):
                            data["prompt_tokens"] = folder_tokens["total_prompt_tokens"]
                            data["completion_tokens"] = folder_tokens["total_completion_tokens"]
                            data["total_tokens"] = folder_tokens["total_tokens"]
                            data["token_metrics"] = folder_tokens
                    self.load_summary(data)
                    loaded = True
                    break
                except Exception:
                    pass

        if not loaded:
            self.winner_banner.configure(text="No recent benchmark metrics found to load.", foreground="#dc2626")

    def _get_provider_items(self) -> list[dict[str, Any]]:
        results = self.summary_data.get("results", {})
        if results and isinstance(results, dict):
            return list(results.values())
        raw_provs = self.summary_data.get("providers", [])
        if raw_provs:
            items = []
            for p in raw_provs:
                if isinstance(p, dict):
                    items.append(p)
                elif isinstance(p, str) and p in results:
                    items.append(results[p])
                else:
                    items.append({"name": str(p), "id": str(p)})
            return items
        # Check if summary_data is directly a dictionary of provider metrics
        if isinstance(self.summary_data, dict):
            items = []
            for k, v in self.summary_data.items():
                if isinstance(v, dict) and ("accuracy" in v or "total_tests" in v or "provider_id" in v):
                    items.append(v)
            if items:
                return items
            # Or if it's a single metrics.json dictionary
            if "accuracy" in self.summary_data:
                return [self.summary_data]
        return []

    def _render_table(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        providers = self._get_provider_items()
        for p in providers:
            in_tok = p.get("prompt_tokens") or p.get("token_metrics", {}).get("total_prompt_tokens", 0)
            out_tok = p.get("completion_tokens") or p.get("token_metrics", {}).get("total_completion_tokens", 0)
            tot_tok = p.get("total_tokens") or p.get("token_metrics", {}).get("total_tokens", 0)

            in_str = f"{in_tok:,}" if in_tok else "-"
            out_str = f"{out_tok:,}" if out_tok else "-"
            tot_str = f"{tot_tok:,}" if tot_tok else "-"

            self.tree.insert("", "end", values=(
                p.get("name", p.get("provider_id", "Unknown")),
                f"{p.get('accuracy', 0.0):.1f}%",
                f"{p.get('f1', p.get('accuracy', 0.0)):.1f}%",
                f"{p.get('avg_latency_s', p.get('latency', 0.0)):.2f}s",
                f"{p.get('error_rate', 0.0):.1f}%",
                in_str,
                out_str,
                tot_str,
            ))

        winner = self.summary_data.get("winner")
        if winner:
            self.winner_banner.configure(
                text=f"🏆 Winner: {winner.get('name', 'N/A')} (Accuracy: {winner.get('accuracy', 0.0):.1f}%)",
                foreground="#16a34a",
            )
        elif len(providers) == 1:
            p = providers[0]
            self.winner_banner.configure(
                text=f"📊 Evaluated Provider: {p.get('name', p.get('provider_id', 'N/A'))} | Accuracy: {p.get('accuracy', 0.0):.1f}% | Avg Latency: {p.get('avg_latency_s', p.get('latency', 0.0)):.2f}s | Total Tests: {p.get('total_tests', 0)}",
                foreground="#2563eb",
            )

    def _render_stats(self) -> None:
        self.txt_stats.delete("1.0", "end")
        providers = self._get_provider_items()

        if len(providers) == 1:
            p = providers[0]
            tok_metrics = p.get("token_metrics", {})
            in_tok = p.get("prompt_tokens") or tok_metrics.get("total_prompt_tokens", 0)
            out_tok = p.get("completion_tokens") or tok_metrics.get("total_completion_tokens", 0)
            tot_tok = p.get("total_tokens") or tok_metrics.get("total_tokens", 0)
            tests_cnt = max(1, p.get("total_tests", 1))
            avg_tok = tot_tok // tests_cnt if tot_tok else 0

            cost_flash = tok_metrics.get("estimated_cost_flash_usd") or round((in_tok * 0.15 + out_tok * 0.60) / 1_000_000, 4)
            cost_flagship = tok_metrics.get("estimated_cost_flagship_usd") or round((in_tok * 3.00 + out_tok * 15.00) / 1_000_000, 4)

            lines = [
                "Single-Provider Benchmark Summary:\n",
                f"• Provider: {p.get('name', p.get('provider_id', 'N/A'))}\n",
                f"• Model: {p.get('model', 'N/A')}\n",
                f"• Completed Scenarios: {p.get('total_tests', 0)}\n",
                f"• Accuracy: {p.get('accuracy', 0.0):.1f}%\n",
                f"• Average Latency: {p.get('avg_latency_s', p.get('latency', 0.0)):.2f}s\n",
                f"• XSD Validation Rate: {p.get('xsd_pass_rate', 1.0)*100:.1f}%\n",
                f"• Simulation Success Rate: {p.get('simulation_success_rate', 1.0)*100:.1f}%\n",
                f"• Avg Token Preservation: {p.get('avg_token_preservation', 1.0)*100:.1f}%\n\n",
                "Token Usage & Commercial Cost Projection:\n",
                f"• Prompt Tokens (In): {in_tok:,}\n",
                f"• Completion Tokens (Out): {out_tok:,}\n",
                f"• Total Billable Tokens: {tot_tok:,}\n",
                f"• Avg Tokens / Scenario: {avg_tok:,}\n",
                f"• Projected Cost (Gemini Flash / GPT-4o-mini): ~${cost_flash:.4f} USD\n",
                f"• Projected Cost (Claude 3.5 Sonnet / GPT-4o): ~${cost_flagship:.4f} USD\n\n",
                "Note: Pairwise McNemar hypothesis testing requires >= 2 providers.",
            ]
            self.txt_stats.insert("end", "".join(lines))
            return

        mcnemar = self.summary_data.get("pairwise_mcnemar", self.summary_data.get("mcnemar_tests", []))
        lines = []
        if mcnemar:
            lines.append("Pairwise McNemar Tests (α = 0.05):\n")
            for test in mcnemar:
                pair = test.get("comparison", f"{test.get('a')} vs {test.get('b')}")
                p_val = test.get("p_value", 1.0)
                sig = "significant" if p_val < 0.05 else "not significant"
                lines.append(f"• {pair}: p={p_val:.4f} ({sig})\n")
            lines.append("\n")

        # Multi-provider token usage summary
        lines.append("Token Usage Comparison:\n")
        for p in providers:
            tok_metrics = p.get("token_metrics", {})
            in_tok = p.get("prompt_tokens") or tok_metrics.get("total_prompt_tokens", 0)
            out_tok = p.get("completion_tokens") or tok_metrics.get("total_completion_tokens", 0)
            tot_tok = p.get("total_tokens") or tok_metrics.get("total_tokens", 0)
            p_name = p.get("name", p.get("provider_id", "LLM"))
            lines.append(f"• {p_name}: {tot_tok:,} total tokens (In: {in_tok:,}, Out: {out_tok:,})\n")

        self.txt_stats.insert("end", "".join(lines))

    def _render_charts(self) -> None:
        c = self.chart_canvas
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 100 or h < 100:
            return

        providers = self._get_provider_items()
        if not providers:
            c.create_text(w / 2, h / 2, text="No comparison data loaded yet.", fill="#94a3b8", font=("Segoe UI", 10))
            return

        # Split width: Left half Accuracy & F1 bars, Right half Latency bars
        half_w = (w - 40) / 2
        colors = ["#2563eb", "#10b981", "#8b5cf6", "#f59e0b", "#ec4899"]
        label_margin = 175  # Generous offset so provider labels never collide with bars

        # Left: Accuracy bars
        c.create_text(20, 15, anchor="w", text="Accuracy by Provider", font=("Segoe UI", 9, "bold"), fill="#1e293b")
        y = 35
        bar_h = 22
        usable_bw = max(50.0, half_w - label_margin - 80)
        for idx, p in enumerate(providers):
            name = p.get("name", p.get("id", f"P{idx}"))[:22]
            acc = p.get("accuracy", 0.0) / 100.0
            color = colors[idx % len(colors)]
            bw = usable_bw * max(0.0, min(1.0, acc))

            c.create_text(20, y + 11, anchor="w", text=f"{name}:", font=("Segoe UI", 8), fill="#334155")
            bar_start = 20 + label_margin
            c.create_rectangle(bar_start, y, bar_start + bw, y + bar_h, fill=color, outline="")
            c.create_text(bar_start + bw + 8, y + 11, anchor="w", text=f"{acc*100:.1f}%", font=("Segoe UI", 8, "bold"), fill="#0f172a")
            y += bar_h + 8

        # Right: Latency bars
        rx = 20 + half_w + 20
        c.create_text(rx, 15, anchor="w", text="Average Latency (seconds)", font=("Segoe UI", 9, "bold"), fill="#1e293b")
        y = 35
        max_lat = max([p.get("avg_latency_s", p.get("latency", 1.0)) for p in providers] + [5.0])
        for idx, p in enumerate(providers):
            name = p.get("name", p.get("provider_id", p.get("id", f"P{idx}")))[:22]
            lat = p.get("avg_latency_s", p.get("latency", 0.0))
            bw = usable_bw * (lat / max(1.0, max_lat))

            c.create_text(rx, y + 11, anchor="w", text=f"{name}:", font=("Segoe UI", 8), fill="#334155")
            bar_start = rx + label_margin
            c.create_rectangle(bar_start, y, bar_start + bw, y + bar_h, fill="#f59e0b", outline="")
            c.create_text(bar_start + bw + 8, y + 11, anchor="w", text=f"{lat:.2f}s", font=("Segoe UI", 8, "bold"), fill="#0f172a")
            y += bar_h + 8

    def _export_report(self) -> None:
        dest = filedialog.asksaveasfilename(defaultextension=".md", filetypes=[("Markdown files", "*.md")])
        if dest:
            content = f"# BPMN Adaptation Multi-Provider Comparison Report\n\n"
            content += f"## Winner\n{self.winner_banner['text']}\n\n"
            content += "## Summary Table\n\n| Provider | Accuracy | Precision | Recall | F1 | Latency (s) | Error Rate |\n"
            content += "|---|---|---|---|---|---|---|\n"
            for p in self.summary_data.get("providers", []):
                content += f"| {p.get('name')} | {p.get('accuracy'):.1f}% | {p.get('precision'):.1f}% | {p.get('recall'):.1f}% | {p.get('f1'):.1f}% | {p.get('latency'):.2f}s | {p.get('error_rate'):.1f}% |\n"
            Path(dest).write_text(content, encoding="utf-8")

    def _open_folder(self) -> None:
        out_p = self.report_dir.resolve()
        out_p.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(out_p))
        else:
            subprocess.Popen(["xdg-open", str(out_p)])
