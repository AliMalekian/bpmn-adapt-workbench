"""Automated screenshot capture with metadata banner and manifest tracking."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageGrab

logger = logging.getLogger(__name__)

# Tab mapping: friendly name -> notebook tab name/index
DEFAULT_TABS = [
    ("01_project", "Project"),
    ("02_dbfacts", "DB Facts"),
    ("03_rag", "RAG Evidence"),
    ("04_planning", "Planning"),
    ("05_model", "Model & Migration"),
    ("06_validation", "Validation & Simulation"),
    ("07_evaluation", "Evaluation"),
    ("08_provenance", "Provenance"),
    ("09_export", "Export"),
    ("10_livelog", "Live Log"),
    ("11_decision", "Manual Test"),
]


class AutomatedScreenshot:
    """Captures application tabs with metadata info bar and maintains screenshot manifest."""

    def __init__(self, desktop_app, output_root: Path | str = "screenshots", allow_synthetic: bool = False):
        self.app = desktop_app
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.output_root / "screenshots_manifest.jsonl"
        self.allow_synthetic = allow_synthetic
        self._font = None
        try:
            self._font = ImageFont.truetype("arial.ttf", 14)
        except Exception:
            try:
                self._font = ImageFont.load_default()
            except Exception:
                self._font = None

    def capture_all_tabs(
        self,
        test_id: str,
        dataset_name: str,
        operation: str,
        target: str,
        decision: str,
        provider: str,
        model: str,
        latency: float,
        *,
        tab_list: list[tuple[str, str]] | None = None,
        as_jpeg: bool = False,
        include_banner: bool = True,
    ) -> list[Path]:
        """Switches to each specified tab, captures window with banner, saves and manifests."""
        captured_paths: list[Path] = []
        tabs_to_capture = tab_list or DEFAULT_TABS
        clean_target = re.sub(r'[<>:"/\\|?*]', '_', target)
        clean_test_id = re.sub(r'[<>:"/\\|?*]', '_', test_id)
        subfolder = self.output_root / dataset_name / f"{clean_test_id}_{operation}_{clean_target}"
        subfolder.mkdir(parents=True, exist_ok=True)

        ext = ".jpg" if as_jpeg else ".png"

        for label, tab_name in tabs_to_capture:
            out_file = subfolder / f"{label}{ext}"
            try:
                # Switch to tab if possible
                self._select_tab(tab_name)
                time.sleep(0.08)
                self.app.update_idletasks()
                self.app.update()

                img, is_synthetic = self._capture_window()
                if img is None:
                    continue

                if include_banner:
                    img = self._add_info_bar(
                        img,
                        test_id=test_id,
                        dataset=dataset_name,
                        operation=operation,
                        target=target,
                        decision=decision,
                        provider=provider,
                        model=model,
                        latency=latency,
                    )

                if as_jpeg:
                    img = img.convert("RGB")
                    img.save(out_file, "JPEG", quality=85)
                else:
                    img.save(out_file, "PNG", optimize=True)

                captured_paths.append(out_file)
                self._record_manifest(
                    test_id=test_id,
                    dataset=dataset_name,
                    tab=label,
                    path=out_file,
                    decision=decision,
                    provider=provider,
                    latency=latency,
                    synthetic=is_synthetic,
                )
            except Exception as exc:
                logger.warning("Failed to capture tab %s for test %s: %s", tab_name, test_id, exc)

        return captured_paths

    def capture_single_tab(
        self,
        tab_name: str,
        test_id: str,
        dataset_name: str,
        operation: str,
        target: str,
        decision: str,
        provider: str,
        model: str,
        latency: float,
        *,
        as_jpeg: bool = False,
        include_banner: bool = True,
    ) -> Path | None:
        """Captures a single specific tab."""
        tab_label = f"11_{tab_name.lower().replace(' ', '_')}"
        res = self.capture_all_tabs(
            test_id=test_id,
            dataset_name=dataset_name,
            operation=operation,
            target=target,
            decision=decision,
            provider=provider,
            model=model,
            latency=latency,
            tab_list=[(tab_label, tab_name)],
            as_jpeg=as_jpeg,
            include_banner=include_banner,
        )
        return res[0] if res else None

    def execute_strategy(
        self,
        strategy: str,
        test_index: int,
        test_id: str,
        dataset_name: str,
        operation: str,
        target: str,
        decision: str,
        provider: str,
        model: str,
        latency: float,
        *,
        as_jpeg: bool = False,
        include_banner: bool = True,
        is_first_in_dataset: bool = False,
    ) -> list[Path]:
        """Executes screenshot strategy A, B, C, or NONE (disabled)."""
        strat = (strategy or "").strip().upper()
        if not strat or strat.startswith("NONE") or strat.startswith("NO") or strat.startswith("OFF") or strat == "0":
            return []
        if strat.startswith("A") or strat == "MINIMAL":
            # 1 per test (decision tab only)
            return self.capture_all_tabs(
                test_id=test_id,
                dataset_name=dataset_name,
                operation=operation,
                target=target,
                decision=decision,
                provider=provider,
                model=model,
                latency=latency,
                tab_list=[("11_decision", "Manual Test")],
                as_jpeg=as_jpeg,
                include_banner=include_banner,
            )
        elif strat.startswith("B") or strat == "STANDARD":
            # 1 per test for decision, all 11 every 5th test, 1 per dataset for livelog
            tabs = [("11_decision", "Manual Test")]
            if is_first_in_dataset:
                tabs.append(("10_livelog", "Live Log"))
            if test_index % 5 == 0:
                tabs = DEFAULT_TABS

            return self.capture_all_tabs(
                test_id=test_id,
                dataset_name=dataset_name,
                operation=operation,
                target=target,
                decision=decision,
                provider=provider,
                model=model,
                latency=latency,
                tab_list=tabs,
                as_jpeg=as_jpeg,
                include_banner=include_banner,
            )
        elif strat.startswith("C") or strat == "FULL":
            # All 11 tabs per test
            return self.capture_all_tabs(
                test_id=test_id,
                dataset_name=dataset_name,
                operation=operation,
                target=target,
                decision=decision,
                provider=provider,
                model=model,
                latency=latency,
                tab_list=DEFAULT_TABS,
                as_jpeg=as_jpeg,
                include_banner=include_banner,
            )
        else:
            # Custom / Fallback to decision tab
            return self.capture_all_tabs(
                test_id=test_id,
                dataset_name=dataset_name,
                operation=operation,
                target=target,
                decision=decision,
                provider=provider,
                model=model,
                latency=latency,
                tab_list=[("11_decision", "Manual Test")],
                as_jpeg=as_jpeg,
                include_banner=include_banner,
            )

    def _select_tab(self, tab_name: str) -> None:
        try:
            if hasattr(self.app, "notebook"):
                nb = self.app.notebook
                for tab_id in nb.tabs():
                    if nb.tab(tab_id, "text").strip().lower() == tab_name.strip().lower():
                        nb.select(tab_id)
                        return
                if hasattr(self.app, "panels") and tab_name in self.app.panels:
                    nb.select(self.app.panels[tab_name])
        except Exception as exc:
            logger.debug("Failed to select tab %s: %s", tab_name, exc)

    def _capture_window(self) -> tuple[Image.Image | None, bool]:
        if not self.app:
            return None, False

        # Attempt 1: Standard ImageGrab desktop capture
        try:
            x = self.app.winfo_rootx()
            y = self.app.winfo_rooty()
            w = self.app.winfo_width()
            h = self.app.winfo_height()
            if w > 0 and h > 0:
                bbox = (x, y, x + w, y + h)
                img = ImageGrab.grab(bbox=bbox)
                if img is not None:
                    return img, False
        except Exception as exc:
            logger.debug("ImageGrab screen capture failed: %s", exc)

        # Attempt 2: Direct Win32 PrintWindow window DC capture (captures real GUI widgets even in background/session 0)
        try:
            img = self._capture_win32_window()
            if img is not None:
                return img, False
        except Exception as exc:
            logger.debug("Win32 PrintWindow capture failed: %s", exc)

        # Attempt 3: Only if explicitly allowed
        if self.allow_synthetic:
            logger.error("Falling back to synthetic UI rendering (--allow-synthetic-screenshots enabled).")
            return self._render_synthetic_ui(), True

        logger.warning("Screen capture unavailable; skipping screenshot to prevent synthetic evidence substitution.")
        return None, False

    def _capture_win32_window(self) -> Image.Image | None:
        """Captures real window surface directly via Win32 GDI PrintWindow."""
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        client_hwnd = self.app.winfo_id()
        parent_hwnd = user32.GetParent(client_hwnd) or client_hwnd
        hwnd = parent_hwnd

        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        if w <= 0 or h <= 0:
            w = self.app.winfo_width()
            h = self.app.winfo_height()
        if w <= 0 or h <= 0:
            return None

        hdc_win = user32.GetWindowDC(hwnd)
        if not hdc_win:
            return None
        hdc_mem = gdi32.CreateCompatibleDC(hdc_win)
        hbitmap = gdi32.CreateCompatibleBitmap(hdc_win, w, h)
        gdi32.SelectObject(hdc_mem, hbitmap)
        res = user32.PrintWindow(hwnd, hdc_mem, 2)
        if not res:
            res = user32.PrintWindow(client_hwnd, hdc_mem, 2)

        if not res:
            gdi32.DeleteObject(hbitmap)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(hwnd, hdc_win)
            return None

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ('biSize', wintypes.DWORD),
                ('biWidth', wintypes.LONG),
                ('biHeight', wintypes.LONG),
                ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD),
                ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD),
                ('biXPelsPerMeter', wintypes.LONG),
                ('biYPelsPerMeter', wintypes.LONG),
                ('biClrUsed', wintypes.DWORD),
                ('biClrImportant', wintypes.DWORD),
            ]

        class BITMAPINFO(ctypes.Structure):
            _fields_ = [
                ('bmiHeader', BITMAPINFOHEADER),
                ('bmiColors', wintypes.DWORD * 3),
            ]

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0

        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(hdc_mem, hbitmap, 0, h, buf, ctypes.byref(bmi), 0)

        im = Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1)
        im = im.convert('RGB')

        gdi32.DeleteObject(hbitmap)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(hwnd, hdc_win)
        return im

    def _render_synthetic_ui(self) -> Image.Image:
        """
        WARNING: This method is for development and automated testing ONLY.
        Never enable it in production, evaluation, or publication runs.
        Synthetic screenshots cannot be used as scientific evidence.
        Always keep allow_synthetic=False in real benchmarks.
        """
        w, h = 1280, 820
        img = Image.new("RGB", (w, h), color=(241, 245, 249))  # slate-100
        draw = ImageDraw.Draw(img)

        # Title bar
        draw.rectangle([(0, 0), (w, 32)], fill=(30, 41, 59))
        draw.text((12, 8), "Defense-Ready BPMN Adaptation Workbench", fill=(255, 255, 255), font=self._font)

        # Top request form
        draw.rectangle([(10, 40), (w - 10, 150)], fill=(255, 255, 255), outline=(203, 213, 225))
        draw.text((20, 48), "Process and request", fill=(71, 85, 105), font=self._font)

        labels = ["Process folder: E:/Implemention_dataset enriched/Pmo-3D printer", "User request: Remove the task", "Target element: Package goods", "Operation: REMOVE   |   Action: adapt"]
        for idx, lbl in enumerate(labels):
            draw.text((30, 70 + idx * 18), lbl, fill=(51, 65, 85), font=self._font)

        # Notebook tabs bar
        tabs = [
            "Project", "DB Facts", "RAG Evidence", "Planning", "Model & Migration",
            "Validation & Simulation", "Evaluation", "Provenance", "Export",
            "Provider Configuration", "Manual Test", "Benchmark", "Live Log", "Comparison"
        ]

        active_tab_name = "Manual Test"
        if hasattr(self.app, "notebook"):
            try:
                sel = self.app.notebook.select()
                active_tab_name = self.app.notebook.tab(sel, "text")
            except Exception:
                pass

        tab_x = 10
        tab_y = 160
        for tname in tabs:
            is_active = (tname.lower() == active_tab_name.lower())
            tab_w = max(70, len(tname) * 7 + 16)
            bg = (255, 255, 255) if is_active else (226, 232, 240)
            fg = (37, 99, 235) if is_active else (100, 116, 139)
            draw.rectangle([(tab_x, tab_y), (tab_x + tab_w, tab_y + 26)], fill=bg, outline=(203, 213, 225))
            draw.text((tab_x + 8, tab_y + 6), tname, fill=fg, font=self._font)
            tab_x += tab_w + 3

        # Active tab content panel
        panel_rect = [(10, tab_y + 26), (w - 10, h - 15)]
        draw.rectangle(panel_rect, fill=(255, 255, 255), outline=(203, 213, 225))

        # Render custom content depending on active tab
        content_y = tab_y + 40
        draw.text((30, content_y), f"Tab View: [{active_tab_name}]", fill=(15, 23, 42), font=self._font)

        if "provider" in active_tab_name.lower():
            draw.text((30, content_y + 30), "Configured Providers Table (Priority Order):", fill=(71, 85, 105), font=self._font)
            draw.rectangle([(30, content_y + 55), (w - 30, content_y + 240)], fill=(248, 250, 252), outline=(226, 232, 240))
            rows = [
                "ID                  Name                         Type                 Model                   Status",
                "-------------------------------------------------------------------------------------------------------",
                "groq                Groq Cloud                   openai_compatible    openai/gpt-oss-120b     ✔ ON",
                "gemini              Google AI Studio             openai_compatible    gemini-3.8-flash        ✔ ON",
                "um-llm1-gemma4      UM LLM1 (A100)               um_llm               gemma4 (server 1)       ✖ OFF",
                "um-llm2-gemma3      UM LLM2 (V100)               um_llm               gemma3 (server 2)       ✖ OFF",
                "um-llm3-gemma3      UM LLM3 (4090)               um_llm               gemma3 (server 3)       ✖ OFF",
            ]
            for r_idx, r in enumerate(rows):
                draw.text((45, content_y + 65 + r_idx * 20), r, fill=(30, 41, 59), font=self._font)

            draw.rectangle([(30, content_y + 260), (w - 30, content_y + 390)], fill=(248, 250, 252), outline=(226, 232, 240))
            draw.text((45, content_y + 275), "Fallback Policy Configuration:", fill=(71, 85, 105), font=self._font)
            draw.text((45, content_y + 305), "[✔] Fallback on 429 (Rate Limit)     [✔] Fallback on 5xx (Server Error)     [✔] Fallback on Timeout", fill=(15, 23, 42), font=self._font)
            draw.text((45, content_y + 335), "[✔] Fail fast on non-429 4xx          Max retries/provider: 3                Backoff multiplier: 2.0", fill=(15, 23, 42), font=self._font)

        elif "manual" in active_tab_name.lower():
            draw.rectangle([(30, content_y + 30), (w - 30, content_y + 160)], fill=(248, 250, 252), outline=(226, 232, 240))
            draw.text((45, content_y + 40), "Execution Parameters: Dataset: Pmo-3D printer | Operation: REMOVE | Target: Package goods", fill=(51, 65, 85), font=self._font)
            draw.text((45, content_y + 70), "Provider: groq (Groq Cloud - openai/gpt-oss-120b)", fill=(51, 65, 85), font=self._font)
            draw.rectangle([(45, content_y + 105), (190, content_y + 140)], fill=(37, 99, 235))
            draw.text((65, content_y + 115), "▶ Run Adaptation", fill=(255, 255, 255), font=self._font)

            draw.rectangle([(30, content_y + 180), (w - 30, content_y + 390)], fill=(248, 250, 252), outline=(226, 232, 240))
            draw.text((45, content_y + 195), "Execution Result:  Decision: APPROVE   |   Category: (none)   |   Timing: current   |   Latency: 30.47s", fill=(22, 101, 52), font=self._font)
            draw.text((45, content_y + 225), "Rule IDs: []   |   Resource IDs: []", fill=(71, 85, 105), font=self._font)
            draw.text((45, content_y + 255), "Reason: No operational rule mandates the 'Package goods' task and no resource capacity references it.", fill=(30, 41, 59), font=self._font)
            draw.text((45, content_y + 285), "Runtime token context shows no active token on the target, allowing immediate removal.", fill=(30, 41, 59), font=self._font)

        elif "benchmark" in active_tab_name.lower():
            draw.rectangle([(30, content_y + 30), (w - 30, content_y + 200)], fill=(248, 250, 252), outline=(226, 232, 240))
            draw.text((45, content_y + 45), "Execution Mode: (•) Single Provider    ( ) Multi-Provider Comparison", fill=(51, 65, 85), font=self._font)
            draw.text((45, content_y + 75), "Dataset Root: E:/Implemention_dataset enriched   |   Repetitions: 3   |   Strategy: B — Standard", fill=(51, 65, 85), font=self._font)
            draw.text((45, content_y + 105), "Request Types: [✔] REMOVE   [✔] MODIFY   [✔] ADD   [✔] RE_ADD", fill=(51, 65, 85), font=self._font)
            draw.rectangle([(45, content_y + 140), (w - 45, content_y + 165)], fill=(226, 232, 240))
            draw.rectangle([(45, content_y + 140), (45 + 380, content_y + 165)], fill=(16, 185, 129))
            draw.text((55, content_y + 145), "Progress: 120/410 (29%)   |   Stats: Completed: 120 | Errors: 2 | Elapsed: 00:42:18", fill=(255, 255, 255), font=self._font)

            draw.rectangle([(30, content_y + 220), (w - 30, content_y + 410)], fill=(15, 23, 42))
            draw.text((45, content_y + 235), "[19:45:03] Test 121/410 • Mangler-Chainsaw • REMOVE • Target: Cut Wood", fill=(248, 250, 252), font=self._font)
            draw.text((45, content_y + 265), "[19:45:05]   Analyst -> Groq (openai/gpt-oss-120b)", fill=(148, 163, 184), font=self._font)
            draw.text((45, content_y + 295), "[19:45:08]   Analyst -> REJECT (RULE_VIOLATION)", fill=(248, 113, 113), font=self._font)
            draw.text((45, content_y + 325), "[19:45:08]   GT: REJECT | Match: ✔   |   Screenshot saved: 11_decision.png", fill=(74, 222, 128), font=self._font)

        elif "live" in active_tab_name.lower():
            draw.rectangle([(30, content_y + 30), (w/2 - 10, content_y + 220)], fill=(15, 23, 42))
            draw.text((45, content_y + 45), "Streaming Telemetry Console:", fill=(248, 250, 252), font=self._font)
            draw.text((45, content_y + 75), "[19:45:03] Test 121/410 started", fill=(148, 163, 184), font=self._font)
            draw.text((45, content_y + 105), "[19:45:05] Analyst -> Groq Cloud (HTTP 200)", fill=(148, 163, 184), font=self._font)
            draw.text((45, content_y + 135), "[19:45:08] Decision: REJECT (RULE_VIOLATION)", fill=(248, 113, 113), font=self._font)
            draw.text((45, content_y + 165), "[19:45:08] Live screenshot captured: B — Standard", fill=(74, 222, 128), font=self._font)

            draw.rectangle([(w/2 + 10, content_y + 30), (w - 30, content_y + 220)], fill=(248, 250, 252), outline=(226, 232, 240))
            draw.text((w/2 + 25, content_y + 45), "Live Accuracy Curve (Rolling Window): 91.3%", fill=(37, 99, 235), font=self._font)
            pts = [(w/2 + 30, content_y + 160), (w/2 + 120, content_y + 140), (w/2 + 240, content_y + 90), (w/2 + 360, content_y + 80), (w/2 + 480, content_y + 70)]
            for p_i in range(len(pts) - 1):
                draw.line([pts[p_i], pts[p_i + 1]], fill=(37, 99, 235), width=3)

            draw.rectangle([(30, content_y + 240), (w/2 - 10, content_y + 420)], fill=(248, 250, 252), outline=(226, 232, 240))
            draw.text((45, content_y + 255), "Provider Usage Breakdown: Total Calls: 934", fill=(71, 85, 105), font=self._font)
            draw.text((45, content_y + 285), "• Groq Cloud: 892 calls (95.5%)", fill=(37, 99, 235), font=self._font)
            draw.text((45, content_y + 315), "• Google AI Studio: 42 calls (4.5%)", fill=(16, 185, 129), font=self._font)

            draw.rectangle([(w/2 + 10, content_y + 240), (w - 30, content_y + 420)], fill=(248, 250, 252), outline=(226, 232, 240))
            draw.text((w/2 + 25, content_y + 255), "Error & Recovery Counters:", fill=(71, 85, 105), font=self._font)
            draw.text((w/2 + 25, content_y + 285), "• Total Errors: 12 (HTTP 429 rate limit backoffs)", fill=(234, 88, 12), font=self._font)
            draw.text((w/2 + 25, content_y + 315), "• Recovered Retries: 10   |   Fatal Aborts: 2", fill=(22, 101, 52), font=self._font)

        elif "comparison" in active_tab_name.lower():
            draw.rectangle([(30, content_y + 30), (w - 30, content_y + 160)], fill=(248, 250, 252), outline=(226, 232, 240))
            draw.text((45, content_y + 40), "🏆 Winner: Google AI Studio (Accuracy: 91.3%, Latency: 3.2s, Error Rate: 0.5%)", fill=(22, 101, 52), font=self._font)
            draw.text((45, content_y + 70), "Provider Summary Table:", fill=(71, 85, 105), font=self._font)
            draw.text((45, content_y + 95), "Provider              Accuracy     Precision     Recall     F1-Score     Latency     Error Rate", fill=(30, 41, 59), font=self._font)
            draw.text((45, content_y + 115), "Google AI Studio      91.3%        92.8%         89.9%      91.3%        3.20s       0.5%", fill=(37, 99, 235), font=self._font)
            draw.text((45, content_y + 135), "Groq Cloud            85.2%        87.1%         83.4%      85.2%        4.80s       2.3%", fill=(71, 85, 105), font=self._font)

            draw.rectangle([(30, content_y + 180), (w - 30, content_y + 420)], fill=(248, 250, 252), outline=(226, 232, 240))
            draw.text((45, content_y + 195), "Hypothesis Testing (McNemar with Edwards Continuity Correction, α = 0.05):", fill=(71, 85, 105), font=self._font)
            draw.text((45, content_y + 225), "• Gemini vs Groq: p = 0.0021 — Statistically Significant (p < 0.05)", fill=(22, 101, 52), font=self._font)
            draw.text((45, content_y + 255), "• Gemini vs UM LLM1: p = 0.0456 — Statistically Significant (p < 0.05)", fill=(22, 101, 52), font=self._font)
            draw.text((45, content_y + 285), "• Groq vs UM LLM1: p = 0.2840 — Not Significant (p ≥ 0.05)", fill=(71, 85, 105), font=self._font)

        return img

    def _add_info_bar(
        self,
        img: Image.Image,
        test_id: str,
        dataset: str,
        operation: str,
        target: str,
        decision: str,
        provider: str,
        model: str,
        latency: float,
    ) -> Image.Image:
        bar_height = 30
        new_img = Image.new("RGB", (img.width, img.height + bar_height), color=(15, 23, 42))  # slate-900
        # Paste original image below the bar
        new_img.paste(img.convert("RGB"), (0, bar_height))

        draw = ImageDraw.Draw(new_img)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        text = f"{test_id} | {dataset} | {operation} | {target} | {decision} | {provider} | {model} | {latency:.2f}s | {ts}"

        draw.text((12, 7), text, fill=(241, 245, 249), font=self._font)
        # Accent line under bar
        draw.line([(0, bar_height - 1), (img.width, bar_height - 1)], fill=(59, 130, 246), width=1)
        return new_img

    def _record_manifest(
        self,
        test_id: str,
        dataset: str,
        tab: str,
        path: Path,
        decision: str,
        provider: str,
        latency: float,
        synthetic: bool = False,
    ) -> None:
        try:
            rel_path = path.relative_to(self.output_root) if path.is_relative_to(self.output_root) else path
            entry = {
                "test_id": test_id,
                "dataset": dataset,
                "tab": tab,
                "path": str(rel_path).replace("\\", "/"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "decision": decision,
                "provider": provider,
                "latency": round(latency, 3),
                "synthetic": bool(synthetic),
            }
            with open(self.manifest_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.debug("Failed to write screenshot manifest: %s", exc)
