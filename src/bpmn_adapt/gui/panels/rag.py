"""RAG Evidence panel (Tab 3) with interactive RAG status and flush memory controls."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from .base import InspectionPanel
from . import render_rag
from bpmn_adapt.gui.info_helper import add_info_button
from bpmn_adapt.retrieval.rag_admin import flush_rag, get_rag_status

INFO_RAG = """Tab 3: RAG Evidence & Knowledge Retrieval

What this tab does:
Displays indexed historical adaptation cases, semantic similarity ranking, component scores, and retrieved contextual evidence used by the Analyst and Modeler agents.

Controls:
- RAG Status: Displays current memory statistics (total cases, approved, rejected, vector indexes).
- Flush RAG: Clears all historical RAG cases from the runtime database and vector index, resetting the system to a clean Cold-Start state (0 records) for unassisted learning curve evaluations.
- Refresh: Updates memory counts in real time.

Outputs produced:
- Retrieval query filters, semantic hit list with similarity scores, ranking components (lexical vs semantic), rule links, and full evidence records.
"""


class RagPanel(InspectionPanel):
    def __init__(self, parent):
        super().__init__(parent, render_rag, title="RAG Evidence", info_text=INFO_RAG)

    def _build_ui(self) -> None:
        """Builds inspection panel with top RAG management toolbar."""
        if self.title and self.info_text:
            add_info_button(self, self.title, self.info_text)

        # Top RAG Management Toolbar
        tb = ttk.Frame(self, padding=(0, 0, 0, 6))
        tb.pack(fill="x")

        ttk.Label(tb, text="RAG Memory Management:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        
        self.lbl_rag_status = ttk.Label(tb, text="Loading status...", font=("Segoe UI", 9), foreground="#2563eb")
        self.lbl_rag_status.pack(side="left", padx=(0, 10))

        ttk.Button(tb, text="🗑️ Flush RAG", command=self._on_flush_rag).pack(side="right", padx=3)
        ttk.Button(tb, text="📊 RAG Status", command=self._on_show_status).pack(side="right", padx=3)
        ttk.Button(tb, text="🔄 Refresh", command=self._update_status).pack(side="right", padx=3)

        # Inspection Text Container
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        self.text = tk.Text(container, wrap="none", font=("Consolas", 9))
        scroll_y = ttk.Scrollbar(container, orient="vertical", command=self.text.yview)
        scroll_x = ttk.Scrollbar(container, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.text.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        self._update_status()

    def _update_status(self) -> None:
        """Fetches live RAG database status and updates label."""
        try:
            status = get_rag_status()
            tot = status.get("total_cases", 0)
            app = status.get("approved_cases", 0)
            rej = status.get("rejected_cases", 0)
            vecs = status.get("vector_files_count", 0)
            if tot == 0:
                self.lbl_rag_status.configure(text="Empty (0 records - Cold Start Ready)", foreground="#16a34a")
            else:
                self.lbl_rag_status.configure(
                    text=f"{tot} cases ({app} Approved, {rej} Rejected | {vecs} vectors)",
                    foreground="#1d4ed8"
                )
        except Exception as e:
            self.lbl_rag_status.configure(text=f"Error checking status: {e}", foreground="#dc2626")

    def _on_show_status(self) -> None:
        """Displays detailed RAG memory status popup."""
        status = get_rag_status()
        tot = status.get("total_cases", 0)
        app = status.get("approved_cases", 0)
        rej = status.get("rejected_cases", 0)
        vecs = status.get("vector_files_count", 0)
        db_p = status.get("database_path", "")
        msg = (
            f"Active RAG Cases: {tot}\n"
            f"  • Approved Cases: {app}\n"
            f"  • Rejected Cases: {rej}\n"
            f"Vector Index Files: {vecs}\n\n"
            f"Database: {db_p}\n\n"
            f"State: {'Cold Start Ready (0 cases)' if tot == 0 else 'Populated with historical precedents'}"
        )
        messagebox.showinfo("RAG Memory Status", msg)

    def _on_flush_rag(self) -> None:
        """Prompts for user confirmation and flushes RAG memory."""
        confirm = messagebox.askyesno(
            "Flush RAG Memory",
            "Are you sure you want to flush all RAG memory?\n\n"
            "This will delete all historical cases from the database and vector index, "
            "resetting RAG to a completely clean Cold-Start state (0 cases).\n\n"
            "Proceed with flush?"
        )
        if not confirm:
            return

        res = flush_rag()
        self._update_status()
        messagebox.showinfo("RAG Flushed", res.get("message", "RAG memory flushed successfully."))
