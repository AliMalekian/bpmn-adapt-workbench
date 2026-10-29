"""Render high-fidelity screenshots of DesktopApp states for publication."""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def capture_desktop_app_visual(app, output_path: str | Path, active_tab_name: str | None = None) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    width, height = 1280, 820
    img = Image.new("RGB", (width, height), color="#f1f5f9")
    draw = ImageDraw.Draw(img)
    
    # Try to load a nice font, fallback to default
    try:
        font_title = ImageFont.truetype("segoeui.ttf", 14)
        font_bold = ImageFont.truetype("segoeuib.ttf", 12)
        font_regular = ImageFont.truetype("segoeui.ttf", 11)
        font_mono = ImageFont.truetype("consola.ttf", 11)
    except Exception:
        font_title = font_bold = font_regular = font_mono = ImageFont.load_default()

    # 1. Window Title Bar
    draw.rectangle([(0, 0), (width, 32)], fill="#1e293b")
    draw.text((12, 8), "Defense-Ready BPMN Adaptation Workbench", fill="#ffffff", font=font_title)
    import datetime
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    draw.text((width - 320, 8), f"Timestamp: {ts}", fill="#94a3b8", font=font_mono)
    # Window controls (min, max, close)
    draw.text((width - 60, 8), "—   □   ✕", fill="#94a3b8", font=font_title)
    
    # 2. Form Frame ("Process and request")
    form_top, form_bottom = 40, 205
    draw.rectangle([(10, form_top), (width - 10, form_bottom)], fill="#ffffff", outline="#cbd5e1", width=1)
    draw.rectangle([(20, form_top - 6), (150, form_top + 8)], fill="#ffffff")
    draw.text((24, form_top - 6), "Process and request", fill="#0f172a", font=font_bold)
    
    # Form fields
    fields = [
        ("Process folder:", app.folder.get()),
        ("User request:", app.request.get()),
        ("Target element:", app.target.get()),
        ("Runtime state:", app.state.get()),
        ("Run ID:", app.run_id.get()),
    ]
    
    y = form_top + 18
    for label, val in fields:
        draw.text((25, y + 2), label, fill="#334155", font=font_regular)
        # Entry box
        draw.rectangle([(130, y), (820, y + 22)], fill="#f8fafc", outline="#cbd5e1", width=1)
        draw.text((136, y + 3), str(val)[:100], fill="#0f172a", font=font_mono)
        y += 28

    # Form right side controls
    rx = 850
    # Browse button
    draw.rectangle([(rx, form_top + 18), (rx + 80, form_top + 40)], fill="#e2e8f0", outline="#94a3b8", width=1)
    draw.text((rx + 18, form_top + 22), "Browse", fill="#0f172a", font=font_regular)

    # Operation
    draw.text((rx, form_top + 48), "Operation", fill="#334155", font=font_regular)
    draw.rectangle([(rx + 90, form_top + 46), (rx + 220, form_top + 68)], fill="#f8fafc", outline="#cbd5e1", width=1)
    draw.text((rx + 96, form_top + 49), app.operation.get() + "  ▼", fill="#0f172a", font=font_regular)

    # Action
    draw.text((rx, form_top + 76), "Action", fill="#334155", font=font_regular)
    draw.rectangle([(rx + 90, form_top + 74), (rx + 220, form_top + 96)], fill="#f8fafc", outline="#cbd5e1", width=1)
    draw.text((rx + 96, form_top + 77), app.action.get() + "  ▼", fill="#0f172a", font=font_regular)

    # Run and Cancel Buttons
    draw.rectangle([(rx, form_top + 104), (rx + 100, form_top + 130)], fill="#2563eb", outline="#1d4ed8", width=1)
    draw.text((rx + 36, form_top + 109), "Run", fill="#ffffff", font=font_bold)

    draw.rectangle([(rx + 115, form_top + 104), (rx + 215, form_top + 130)], fill="#f1f5f9", outline="#cbd5e1", width=1)
    draw.text((rx + 145, form_top + 109), "Cancel", fill="#475569", font=font_regular)

    # Status
    st = app.status.get()
    st_color = "#16a34a" if "completed" in st.lower() or "ready" in st.lower() else "#b91c1c"
    draw.text((rx, form_top + 138), f"Status: {st}", fill=st_color, font=font_bold)

    # 3. Notebook Tabs
    tabs = [
        "Project", "DB Facts", "RAG Evidence", "Planning",
        "Model & Migration", "Validation & Simulation", "Evaluation",
        "Provenance", "Export"
    ]
    current_tab = active_tab_name or "Project"
    
    tab_y = form_bottom + 12
    tx = 15
    for tab in tabs:
        is_active = (tab == current_tab)
        tw = int(draw.textlength(tab, font=font_regular)) + 24
        if is_active:
            draw.rectangle([(tx, tab_y), (tx + tw, tab_y + 26)], fill="#ffffff", outline="#cbd5e1", width=1)
            draw.rectangle([(tx, tab_y), (tx + tw, tab_y + 3)], fill="#2563eb") # top accent
            draw.text((tx + 12, tab_y + 6), tab, fill="#1e293b", font=font_bold)
        else:
            draw.rectangle([(tx, tab_y + 2), (tx + tw, tab_y + 26)], fill="#e2e8f0", outline="#cbd5e1", width=1)
            draw.text((tx + 12, tab_y + 6), tab, fill="#64748b", font=font_regular)
        tx += tw + 4

    # 4. Notebook Panel Body
    panel_top = tab_y + 26
    panel_bottom = height - 12
    draw.rectangle([(10, panel_top), (width - 10, panel_bottom)], fill="#ffffff", outline="#cbd5e1", width=1)

    # Extract text from the active panel widget
    panel_widget = app.panels.get(current_tab)
    content_text = ""
    if panel_widget and hasattr(panel_widget, "text"):
        content_text = panel_widget.text.get("1.0", "end-1c")

    lines = content_text.splitlines()[:38]  # display first 38 lines in viewport
    py = panel_top + 12
    for line in lines:
        if line.startswith("# ") or (line and line[0].isupper() and ":" not in line and "{" not in line):
            draw.text((25, py), line, fill="#0f172a", font=font_bold)
        elif line.startswith("  ") or line.startswith("{") or line.startswith("}"):
            draw.text((25, py), line, fill="#1e293b", font=font_mono)
        else:
            draw.text((25, py), line, fill="#334155", font=font_mono)
        py += 17

    # Scrollbar indicator on the right
    sb_x = width - 24
    draw.rectangle([(sb_x, panel_top + 2), (sb_x + 10, panel_bottom - 2)], fill="#f8fafc")
    draw.rectangle([(sb_x + 1, panel_top + 10), (sb_x + 9, panel_top + 80)], fill="#cbd5e1")

    img.save(str(output_path), "PNG")
    return output_path
