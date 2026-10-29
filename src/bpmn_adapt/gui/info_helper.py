"""Shared helper for tab information popups."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk


def add_info_button(parent, title: str, content: str) -> ttk.Frame:
    """Creates a top banner with an info (ℹ) button that displays tab documentation in a popup dialog."""
    bar = ttk.Frame(parent)
    bar.pack(fill="x", side="top", pady=(0, 4))

    def show_popup():
        dialog = tk.Toplevel(parent)
        dialog.title(f"Tab Information — {title}")
        dialog.geometry("620x420")
        try:
            dialog.transient(parent.winfo_toplevel())
        except Exception:
            pass

        txt_frame = ttk.Frame(dialog, padding=8)
        txt_frame.pack(fill="both", expand=True)

        txt = tk.Text(txt_frame, wrap="word", font=("Segoe UI", 9), padx=8, pady=8)
        scroll = ttk.Scrollbar(txt_frame, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=scroll.set)
        txt.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        txt.insert("1.0", content.strip())
        txt.configure(state="disabled")

        btn_box = ttk.Frame(dialog, padding=4)
        btn_box.pack(fill="x")
        ttk.Button(btn_box, text="Close", command=dialog.destroy).pack(side="right", padx=6, pady=4)

    btn = ttk.Button(bar, text="ℹ Info", width=8, command=show_popup)
    btn.pack(side="right", padx=2)
    return bar
