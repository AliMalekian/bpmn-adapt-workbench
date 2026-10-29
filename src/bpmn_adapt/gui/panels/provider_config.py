"""Provider Configuration panel (Tab 10) for managing LLM providers, credentials, and fallback policy."""
from __future__ import annotations
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any

from bpmn_adapt.providers.manager import ProviderManager


INFO_PROVIDER = """Tab 10: Provider Configuration

What this tab does:
Manages multi-provider LLM endpoints, credentials, priority orders, and fallback policies for adaptation reasoning.

Inputs and Controls:
- [+] Add Provider: Opens a dialog to configure new OpenAI-compatible or local model endpoints.
- Test Selected: Executes an immediate live ping canary against the selected provider row.
- Test All: Concurrently verifies connectivity across all enabled providers.
- Save Policy: Persists the active fallback policy settings (429 handling, 5xx retries, backoff).
- Save Provider / Change API Key: Updates credentials and configuration in providers.json.
- Delete: Removes the selected provider from the configuration table.

Outputs produced:
- Canary latency, status indicator (✔ ON, ⚠ NO KEY, ✖ OFF), and updated providers.json configuration.

Caveats:
Providers marked Enabled without an API Key will show '⚠ NO KEY' and will be skipped in automatic chains.
"""


class ProviderConfigPanel(ttk.Frame):
    """GUI Tab for viewing, editing, adding, and canary testing all LLM providers."""

    def __init__(self, parent, manager: ProviderManager | None = None):
        super().__init__(parent, padding=8)
        self.manager = manager or ProviderManager()
        self._selected_id: str | None = None
        self._show_key = False

        self._build_ui()
        self._reload_tree()
        self.manager.subscribe(self._reload_tree)

    def display(self, payload: Any) -> None:
        """Standard panel interface method."""
        self._reload_tree()

    def _build_ui(self) -> None:
        from bpmn_adapt.gui.info_helper import add_info_button
        add_info_button(self, "Provider Configuration", INFO_PROVIDER)

        # Top Action Bar
        btn_bar = ttk.Frame(self)
        btn_bar.pack(fill="x", pady=(0, 6))

        ttk.Button(btn_bar, text="[+] Add Provider", command=self._add_provider_dialog).pack(side="left", padx=3)
        ttk.Button(btn_bar, text="Test Selected", command=self._test_selected).pack(side="left", padx=3)
        ttk.Button(btn_bar, text="Test All", command=self._test_all).pack(side="left", padx=3)
        ttk.Button(btn_bar, text="Save Policy", command=self._save_policy).pack(side="left", padx=3)

        self.status_lbl = ttk.Label(btn_bar, text="Ready", foreground="gray")
        self.status_lbl.pack(side="right", padx=6)

        # Main Paned Window: Top is table, Bottom is Detail + Fallback Policy
        paned = ttk.PanedWindow(self, orient="vertical")
        paned.pack(fill="both", expand=True)

        # Table frame
        tree_frame = ttk.LabelFrame(paned, text="Configured Providers (Priority Order)", padding=6)
        paned.add(tree_frame, weight=1)

        cols = ("id", "name", "type", "model", "priority", "status")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=7, selectmode="browse")
        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="Name")
        self.tree.heading("type", text="Type")
        self.tree.heading("model", text="Model")
        self.tree.heading("priority", text="Priority")
        self.tree.heading("status", text="Status")

        self.tree.column("id", width=120)
        self.tree.column("name", width=160)
        self.tree.column("type", width=130)
        self.tree.column("model", width=180)
        self.tree.column("priority", width=70, anchor="center")
        self.tree.column("status", width=90, anchor="center")

        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Priority Reordering Bar under tree
        prio_bar = ttk.Frame(tree_frame)
        prio_bar.pack(side="bottom", fill="x", pady=(4, 0))
        ttk.Button(prio_bar, text="▲ Move Up (Higher Priority)", command=self._move_up).pack(side="left", padx=2)
        ttk.Button(prio_bar, text="▼ Move Down (Lower Priority)", command=self._move_down).pack(side="left", padx=2)

        # Bottom Frame: Detail Editor + Fallback Policy Frame
        bottom_frame = ttk.Frame(paned)
        paned.add(bottom_frame, weight=1)

        # Detail Editor
        self.edit_frame = ttk.LabelFrame(bottom_frame, text="Provider Details", padding=8)
        self.edit_frame.pack(side="left", fill="both", expand=True, padx=(0, 4), pady=4)

        self.var_id = tk.StringVar()
        self.var_name = tk.StringVar()
        self.var_type = tk.StringVar(value="openai_compatible")
        self.var_base_url = tk.StringVar()
        self.var_model = tk.StringVar()
        self.var_api_key = tk.StringVar()
        self.var_server_id = tk.IntVar(value=1)
        self.var_priority = tk.IntVar(value=1)
        self.var_enabled = tk.BooleanVar(value=False)
        self.var_delay = tk.DoubleVar(value=2.0)

        f_grid = ttk.Frame(self.edit_frame)
        f_grid.pack(fill="both", expand=True)

        ttk.Label(f_grid, text="Provider ID:").grid(row=0, column=0, sticky="w", pady=2)
        self.entry_id = ttk.Entry(f_grid, textvariable=self.var_id, state="readonly", width=22)
        self.entry_id.grid(row=0, column=1, sticky="w", pady=2)

        ttk.Label(f_grid, text="Priority:").grid(row=0, column=2, sticky="w", padx=(10, 2), pady=2)
        self.spin_priority = ttk.Spinbox(f_grid, textvariable=self.var_priority, from_=1, to=20, width=5)
        self.spin_priority.grid(row=0, column=3, sticky="w", pady=2)

        ttk.Checkbutton(f_grid, text="Enabled", variable=self.var_enabled).grid(row=0, column=4, sticky="w", padx=10, pady=2)

        ttk.Label(f_grid, text="Name:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(f_grid, textvariable=self.var_name, width=28).grid(row=1, column=1, columnspan=2, sticky="ew", pady=2)

        ttk.Label(f_grid, text="Type:").grid(row=1, column=3, sticky="w", padx=(10, 2), pady=2)
        type_cb = ttk.Combobox(f_grid, textvariable=self.var_type, values=("openai_compatible", "um_llm"), state="readonly", width=16)
        type_cb.grid(row=1, column=4, sticky="w", pady=2)
        type_cb.bind("<<ComboboxSelected>>", self._on_type_change)

        ttk.Label(f_grid, text="Base URL:").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Entry(f_grid, textvariable=self.var_base_url, width=42).grid(row=2, column=1, columnspan=4, sticky="ew", pady=2)

        ttk.Label(f_grid, text="Model:").grid(row=3, column=0, sticky="w", pady=2)
        self.cb_model = ttk.Combobox(f_grid, textvariable=self.var_model, width=28)
        self.cb_model.grid(row=3, column=1, sticky="ew", pady=2)

        self.btn_fetch_models = ttk.Button(f_grid, text="⚡ Fetch Models", width=14, command=self._fetch_models_async)
        self.btn_fetch_models.grid(row=3, column=2, sticky="w", padx=4, pady=2)

        self.lbl_server = ttk.Label(f_grid, text="Server ID:")
        self.entry_server = ttk.Combobox(f_grid, textvariable=self.var_server_id, values=(1, 2, 3), state="readonly", width=6)

        ttk.Label(f_grid, text="API Key:").grid(row=4, column=0, sticky="w", pady=2)
        self.key_entry = ttk.Entry(f_grid, textvariable=self.var_api_key, show="*", width=28)
        self.key_entry.grid(row=4, column=1, columnspan=2, sticky="ew", pady=2)

        self.btn_show_key = ttk.Button(f_grid, text="Show", width=6, command=self._toggle_show_key)
        self.btn_show_key.grid(row=4, column=3, sticky="w", padx=4, pady=2)

        ttk.Label(f_grid, text="Request Delay (s):").grid(row=5, column=0, sticky="w", pady=2)
        self.spin_delay = ttk.Spinbox(f_grid, textvariable=self.var_delay, from_=0.0, to=30.0, increment=0.5, width=8)
        self.spin_delay.grid(row=5, column=1, sticky="w", pady=2)
        ttk.Label(f_grid, text="(Rate limit spacing between requests)", foreground="gray").grid(row=5, column=2, columnspan=3, sticky="w", pady=2)

        # Action buttons in detail frame
        detail_btns = ttk.Frame(self.edit_frame)
        detail_btns.pack(fill="x", pady=(6, 0))

        ttk.Button(detail_btns, text="Test Connection", command=self._test_single).pack(side="left", padx=2)
        ttk.Button(detail_btns, text="Save Provider", command=self._save_selected).pack(side="left", padx=4)
        ttk.Button(detail_btns, text="Change API Key", command=self._change_api_key_runtime).pack(side="left", padx=2)
        ttk.Button(detail_btns, text="Delete", command=self._delete_selected).pack(side="left", padx=2)

        # Connection Diagnostics Box (full-width, multi-line, word-wrapped)
        diag_frame = ttk.LabelFrame(self.edit_frame, text="Connection Diagnostics & Error Details", padding=6)
        diag_frame.pack(fill="both", expand=True, pady=(6, 0))

        diag_top = ttk.Frame(diag_frame)
        diag_top.pack(fill="x")
        self.test_status_badge = ttk.Label(diag_top, text="Status: Ready", font=("Segoe UI", 9, "bold"), foreground="gray")
        self.test_status_badge.pack(side="left")
        self.btn_copy_err = ttk.Button(diag_top, text="📋 Copy Full Diagnostic", command=self._copy_error_details)
        self.btn_copy_err.pack(side="right")

        self.test_result_txt = tk.Text(diag_frame, height=3, wrap="word", font=("Segoe UI", 8), bg="#f8f9fa", relief="solid", bd=1)
        self.test_result_txt.pack(fill="both", expand=True, pady=(4, 0))
        self.test_result_txt.insert("1.0", "Select a provider and click 'Test Connection' to verify network reachability and credentials.")
        self.test_result_txt.configure(state="disabled")

        # Fallback Policy Frame
        policy_frame = ttk.LabelFrame(bottom_frame, text="Fallback Policy", padding=8)
        policy_frame.pack(side="right", fill="both", padx=(4, 0), pady=4)

        self.on_429 = tk.BooleanVar(value=True)
        self.on_5xx = tk.BooleanVar(value=True)
        self.on_timeout = tk.BooleanVar(value=True)
        self.fail_fast_4xx = tk.BooleanVar(value=True)
        self.max_retries = tk.IntVar(value=3)
        self.backoff_mult = tk.DoubleVar(value=2.0)

        policy = self.manager.get_fallback_policy()
        self.on_429.set(policy.get("on_429", True))
        self.on_5xx.set(policy.get("on_5xx", True))
        self.on_timeout.set(policy.get("on_timeout", True))
        self.fail_fast_4xx.set(policy.get("fail_fast_4xx", True))
        self.max_retries.set(policy.get("max_retries_per_provider", 3))
        self.backoff_mult.set(policy.get("backoff_multiplier", 2.0))

        ttk.Checkbutton(policy_frame, text="Fallback on 429 (Rate Limit)", variable=self.on_429).pack(anchor="w", pady=1)
        ttk.Checkbutton(policy_frame, text="Fallback on 5xx (Server Error)", variable=self.on_5xx).pack(anchor="w", pady=1)
        ttk.Checkbutton(policy_frame, text="Fallback on Timeout", variable=self.on_timeout).pack(anchor="w", pady=1)
        ttk.Checkbutton(policy_frame, text="Fail fast on non-429 4xx", variable=self.fail_fast_4xx).pack(anchor="w", pady=1)

        ret_f = ttk.Frame(policy_frame)
        ret_f.pack(fill="x", pady=4)
        ttk.Label(ret_f, text="Max retries/provider:").pack(side="left")
        ttk.Entry(ret_f, textvariable=self.max_retries, width=5).pack(side="left", padx=4)

        back_f = ttk.Frame(policy_frame)
        back_f.pack(fill="x", pady=4)
        ttk.Label(back_f, text="Backoff multiplier:").pack(side="left")
        ttk.Entry(back_f, textvariable=self.backoff_mult, width=5).pack(side="left", padx=4)

        self._on_type_change()

    def _on_type_change(self, event=None) -> None:
        if self.var_type.get() == "um_llm":
            self.lbl_server.grid(row=3, column=3, sticky="w", padx=(10, 2), pady=2)
            self.entry_server.grid(row=3, column=4, sticky="w", pady=2)
        else:
            self.lbl_server.grid_remove()
            self.entry_server.grid_remove()

    def _toggle_show_key(self) -> None:
        self._show_key = not self._show_key
        self.key_entry.configure(show="" if self._show_key else "*")
        self.btn_show_key.configure(text="Hide" if self._show_key else "Show")

    def _reload_tree(self) -> None:
        sel = self._selected_id
        for row in self.tree.get_children():
            self.tree.delete(row)

        for p in self.manager.list():
            pid = p.get("id", "")
            has_key = bool(str(p.get("api_key", "")).strip())
            enabled = p.get("enabled", False)
            status_text = "✔ ON" if (enabled and has_key) else ("⚠ NO KEY" if enabled else "✖ OFF")
            self.tree.insert("", "end", iid=pid, values=(
                pid,
                p.get("name", pid),
                p.get("type", "openai_compatible"),
                p.get("model", ""),
                p.get("priority", 99),
                status_text,
            ))

        total = len(self.manager.list())
        if hasattr(self, "spin_priority"):
            self.spin_priority.configure(to=max(total, 1))

        if sel and sel in self.tree.get_children():
            self.tree.selection_set(sel)
            self._load_provider_detail(sel)
        elif self.tree.get_children():
            first = self.tree.get_children()[0]
            self.tree.selection_set(first)
            self._load_provider_detail(first)

    def _move_up(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        pid = sel[0]
        p = self.manager.get(pid)
        if not p:
            return
        current_prio = int(p.get("priority", 1))
        if current_prio > 1:
            self.manager.reorder_priority(pid, current_prio - 1)
            self._selected_id = pid
            self._reload_tree()

    def _move_down(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        pid = sel[0]
        p = self.manager.get(pid)
        if not p:
            return
        current_prio = int(p.get("priority", 1))
        total = len(self.manager.list())
        if current_prio < total:
            self.manager.reorder_priority(pid, current_prio + 1)
            self._selected_id = pid
            self._reload_tree()

    def _on_select(self, event=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        pid = sel[0]
        self._selected_id = pid
        self._load_provider_detail(pid)

    def _load_provider_detail(self, pid: str) -> None:
        p = self.manager.get(pid)
        if not p:
            return
        self.var_id.set(p.get("id", ""))
        self.var_name.set(p.get("name", ""))
        self.var_type.set(p.get("type", "openai_compatible"))
        self.var_base_url.set(p.get("base_url", ""))
        self.var_model.set(p.get("model", ""))
        self.var_api_key.set(p.get("api_key", ""))
        self.var_priority.set(p.get("priority", 1))
        self.var_enabled.set(p.get("enabled", False))
        self.var_delay.set(float(p.get("request_delay_seconds", 2.0)))
        if p.get("type") == "um_llm":
            self.var_server_id.set(p.get("server_id", 1))
        self._on_type_change()
        if hasattr(self, "test_status_badge"):
            self.test_status_badge.configure(text="Status: Ready", foreground="gray")
        if hasattr(self, "test_result_txt"):
            self.test_result_txt.configure(state="normal")
            self.test_result_txt.delete("1.0", "end")
            self.test_result_txt.insert("1.0", f"Ready to test provider '{pid}'. Click 'Test Connection'.")
            self.test_result_txt.configure(state="disabled")

    def _save_selected(self) -> None:
        pid = self.var_id.get().strip()
        if not pid:
            messagebox.showwarning("Warning", "No provider selected.")
            return

        updates = {
            "name": self.var_name.get().strip(),
            "type": self.var_type.get(),
            "base_url": self.var_base_url.get().strip(),
            "model": self.var_model.get().strip(),
            "api_key": self.var_api_key.get().strip(),
            "priority": self.var_priority.get(),
            "enabled": self.var_enabled.get(),
            "request_delay_seconds": float(self.var_delay.get()),
        }
        if self.var_type.get() == "um_llm":
            updates["server_id"] = self.var_server_id.get()

        try:
            self.manager.update(pid, updates)
            self.status_lbl.configure(text=f"Saved {pid}", foreground="green")
            self._reload_tree()
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to save provider: {exc}")

    def _delete_selected(self) -> None:
        pid = self.var_id.get().strip()
        if not pid:
            return
        if messagebox.askyesno("Confirm Delete", f"Delete provider '{pid}'?"):
            self.manager.delete(pid)
            self._selected_id = None
            self._reload_tree()

    def _add_provider_dialog(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Add New Custom Provider")
        dialog.geometry("480x380")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        var_id = tk.StringVar()
        var_name = tk.StringVar()
        var_type = tk.StringVar(value="openai_compatible")
        var_base_url = tk.StringVar(value="https://api.openai.com/v1")
        var_model = tk.StringVar(value="gpt-4o")
        var_api_key = tk.StringVar()
        var_priority = tk.IntVar(value=len(self.manager.list()) + 1)
        var_enabled = tk.BooleanVar(value=True)

        frm = ttk.Frame(dialog, padding=12)
        frm.pack(fill="both", expand=True)

        fields = [
            ("Provider ID:", var_id),
            ("Name:", var_name),
            ("Base URL:", var_base_url),
            ("Model:", var_model),
            ("API Key:", var_api_key),
            ("Priority:", var_priority),
        ]

        for idx, (lbl, var) in enumerate(fields):
            ttk.Label(frm, text=lbl).grid(row=idx, column=0, sticky="w", pady=3)
            show_char = "*" if lbl == "API Key:" else ""
            ttk.Entry(frm, textvariable=var, show=show_char, width=32).grid(row=idx, column=1, sticky="ew", pady=3, padx=(6, 0))

        ttk.Label(frm, text="Type:").grid(row=len(fields), column=0, sticky="w", pady=3)
        cb_type = ttk.Combobox(frm, textvariable=var_type, values=("openai_compatible", "um_llm"), state="readonly", width=30)
        cb_type.grid(row=len(fields), column=1, sticky="ew", pady=3, padx=(6, 0))

        ttk.Checkbutton(frm, text="Enabled Immediately", variable=var_enabled).grid(row=len(fields) + 1, column=1, sticky="w", pady=4, padx=(6, 0))

        def on_save():
            pid = var_id.get().strip().lower()
            if not pid:
                messagebox.showwarning("Validation Error", "Provider ID cannot be empty.", parent=dialog)
                return
            new_prov = {
                "id": pid,
                "name": var_name.get().strip() or pid.title(),
                "type": var_type.get(),
                "base_url": var_base_url.get().strip(),
                "model": var_model.get().strip(),
                "api_key": var_api_key.get().strip(),
                "priority": var_priority.get(),
                "enabled": var_enabled.get(),
            }
            try:
                self.manager.add(new_prov)
                self._selected_id = pid
                self._reload_tree()
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("Error", f"Failed to add provider: {exc}", parent=dialog)

        btn_box = ttk.Frame(frm)
        btn_box.grid(row=len(fields) + 2, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(btn_box, text="Save Provider", command=on_save).pack(side="left", padx=6)
        ttk.Button(btn_box, text="Cancel", command=dialog.destroy).pack(side="left", padx=6)

    def _copy_error_details(self) -> None:
        text_to_copy = getattr(self, "_last_error_details", "")
        if not text_to_copy and hasattr(self, "test_result_txt"):
            text_to_copy = self.test_result_txt.get("1.0", "end").strip()
        if text_to_copy:
            self.clipboard_clear()
            self.clipboard_append(text_to_copy)
            messagebox.showinfo("Copied to Clipboard", "Connection diagnostic / error details copied to clipboard.")

    def _fetch_models_async(self) -> None:
        pid = self.var_id.get().strip()
        if not pid:
            messagebox.showwarning("Warning", "Select or save a provider first.")
            return
        self._save_selected()
        self.test_status_badge.configure(text="Status: Fetching available models...", foreground="blue")
        self.btn_fetch_models.configure(state="disabled")

        def run_fetch():
            try:
                models = self.manager.fetch_models(pid)
                def on_success():
                    self.cb_model.configure(values=models)
                    self.btn_fetch_models.configure(state="normal")
                    self.test_status_badge.configure(text=f"Status: Fetched {len(models)} models", foreground="green")
                    self.test_result_txt.configure(state="normal")
                    self.test_result_txt.delete("1.0", "end")
                    self.test_result_txt.insert("1.0", f"Successfully fetched {len(models)} models from provider endpoint.\nAvailable models have been populated into the Model dropdown above.")
                    self.test_result_txt.configure(state="disabled")
                    messagebox.showinfo("Models Fetched", f"Found {len(models)} models for provider '{pid}'.\nClick the Model dropdown to select.")
                self.after(0, on_success)
            except Exception as exc:
                def on_error():
                    self.btn_fetch_models.configure(state="normal")
                    self.test_status_badge.configure(text="Status: Failed to fetch models", foreground="red")
                    self.test_result_txt.configure(state="normal")
                    self.test_result_txt.delete("1.0", "end")
                    self.test_result_txt.insert("1.0", f"Error fetching models: {exc}")
                    self.test_result_txt.configure(state="disabled")
                self.after(0, on_error)

        threading.Thread(target=run_fetch, daemon=True).start()

    def _test_single(self) -> None:
        pid = self.var_id.get().strip()
        if not pid:
            return
        # Save before testing so memory reflects inputs
        self._save_selected()
        self.test_status_badge.configure(text="Status: Testing...", foreground="blue")
        self.test_result_txt.configure(state="normal")
        self.test_result_txt.delete("1.0", "end")
        self.test_result_txt.insert("1.0", f"Sending test canary ping to '{pid}'...")
        self.test_result_txt.configure(state="disabled")

        def run_test():
            res = self.manager.test(pid)
            stat = res.get("status", "FAIL")
            lat = res.get("latency", 0.0)
            err = res.get("error", "")

            def update_ui():
                self.test_result_txt.configure(state="normal")
                self.test_result_txt.delete("1.0", "end")
                if stat in ("PASS", "OK"):
                    self.test_status_badge.configure(text=f"Status: ✔ PASS (Latency: {lat:.2f}s)", foreground="green")
                    self.test_result_txt.insert("1.0", f"Provider '{pid}' is reachable, authorized, and passed canary check successfully.")
                    self._last_error_details = ""
                else:
                    error_msg = str(err) if err is not None else "Unknown error"
                    self._last_error_details = error_msg
                    self.test_status_badge.configure(text=f"Status: ✖ FAIL (Latency: {lat:.2f}s)", foreground="red")
                    self.test_result_txt.insert("1.0", f"{error_msg}")
                self.test_result_txt.configure(state="disabled")
            self.after(0, update_ui)

        threading.Thread(target=run_test, daemon=True).start()

    def _change_api_key_runtime(self) -> None:
        pid = self.var_id.get().strip() or self._selected_id
        if not pid:
            messagebox.showwarning("Warning", "Select a provider first.")
            return
        new_key = simpledialog.askstring("Change API Key Mid-Run", f"Enter new API key for provider '{pid}':", show="*")
        if new_key is not None and new_key.strip():
            self.manager.update_api_key_runtime(pid, new_key.strip())
            self.var_api_key.set(new_key.strip())
            self.status_lbl.configure(text=f"API key updated for {pid}", foreground="green")
            self._reload_tree()
            messagebox.showinfo("API Key Updated", f"API key for '{pid}' updated successfully. Running processes will immediately use this key.")

    def _test_selected(self) -> None:
        self._test_single()

    def _test_all(self) -> None:
        self.status_lbl.configure(text="Testing all enabled providers...", foreground="blue")

        def run_all():
            results_dict = self.manager.test_all()
            results = list(results_dict.values()) if isinstance(results_dict, dict) else list(results_dict)
            pass_count = sum(1 for r in results if isinstance(r, dict) and r.get("status") in ("PASS", "OK"))
            msg = f"Tested {len(results)} enabled: {pass_count} passed, {len(results)-pass_count} failed."

            def update_ui():
                self.status_lbl.configure(text=msg, foreground="black")
                messagebox.showinfo("Canary Test Results", "\n".join(
                    f"[{r.get('status')}] {r.get('provider_id')} ({r.get('latency', 0.0):.2f}s) - {r.get('error') or 'OK'}"
                    for r in results if isinstance(r, dict)
                ))
                self._reload_tree()
            self.after(0, update_ui)

        threading.Thread(target=run_all, daemon=True).start()

    def _save_policy(self) -> None:
        policy = {
            "on_429": self.on_429.get(),
            "on_5xx": self.on_5xx.get(),
            "on_timeout": self.on_timeout.get(),
            "fail_fast_4xx": self.fail_fast_4xx.get(),
            "max_retries_per_provider": self.max_retries.get(),
            "backoff_multiplier": self.backoff_mult.get(),
        }
        self.manager.set_fallback_policy(policy)
        self.status_lbl.configure(text="Fallback policy saved", foreground="green")
