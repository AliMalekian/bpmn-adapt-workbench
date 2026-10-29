from __future__ import annotations
import copy
import json
from tkinter import ttk
import tkinter as tk
from bpmn_adapt.gui.info_helper import add_info_button


class InspectionPanel(ttk.Frame):
    def __init__(self, parent, renderer=None, title: str | None = None, info_text: str | None = None):
        super().__init__(parent, padding=8)
        self.renderer = renderer or (lambda p: json.dumps(p, ensure_ascii=False, indent=2))
        self.title = title
        self.info_text = info_text
        self._build_ui()

    def _build_ui(self) -> None:
        """Creates the panel widgets with info button and scrollable text display."""
        if self.title and self.info_text:
            add_info_button(self, self.title, self.info_text)
        
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

        banner = [
            f"=== {self.title or 'Inspection Panel'} ===",
            "",
            "Status: Awaiting execution.",
            "No execution data or dataset has been loaded for this stage yet.",
            "",
            "To populate this tab with live data:",
            "  1. Go to the 'Manual Test' tab.",
            "  2. Choose a dataset folder and an enabled LLM provider.",
            "  3. Click '▶ Run Adaptation' (or execute an action such as ingest, inspect, plan, validate).",
            "  4. The complete architectural breakdown for this stage will be displayed here automatically.",
            "",
            "=" * 70,
            "Tab Reference & Scope:",
            (self.info_text or "").strip()
        ]
        self.text.insert("1.0", "\n".join(banner))

    def display(self, payload):
        immutable = copy.deepcopy(payload)
        self.text.delete("1.0", "end")
        self.text.insert("1.0", self.renderer(immutable))
