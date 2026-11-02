"""RAG Administration & Learning Curve Telemetry utilities.

Provides functions to:
- Inspect active RAG memory status (database cases, vector files, acceptance/rejection breakdown)
- Flush RAG memory atomically for Cold-Start experimental benchmarks
- Extract and plot publication-grade Learning Curves over Time from tests.jsonl logs
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
from typing import Any


def get_default_paths() -> tuple[Path, Path]:
    base = Path.cwd()
    if not (base / "experiments").is_dir():
        # Fallback to repository root
        base = Path(__file__).resolve().parents[3]
    db_p = base / "experiments" / "runtime_bpmn.db"
    vec_p = base / "experiments" / "vector_index"
    return db_p, vec_p


def get_rag_status(db_path: Path | str | None = None, vector_dir: Path | str | None = None) -> dict[str, Any]:
    """Returns detailed statistics of active RAG memory."""
    def_db, def_vec = get_default_paths()
    db_p = Path(db_path) if db_path else def_db
    vec_p = Path(vector_dir) if vector_dir else def_vec

    status = {
        "database_exists": db_p.is_file(),
        "database_path": str(db_p),
        "total_cases": 0,
        "approved_cases": 0,
        "rejected_cases": 0,
        "active_cases": 0,
        "vector_dir_exists": vec_p.is_dir(),
        "vector_dir_path": str(vec_p),
        "vector_files_count": 0,
        "status_summary": "Empty (Cold Start Ready)",
    }

    if db_p.is_file():
        try:
            conn = sqlite3.connect(str(db_p))
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM rag_cases")
            status["total_cases"] = cur.fetchone()[0]

            cur.execute("SELECT count(*) FROM rag_cases WHERE active = 1")
            status["active_cases"] = cur.fetchone()[0]

            cur.execute("SELECT count(*) FROM rag_cases WHERE decision IN ('ACCEPT', 'APPROVE') AND active = 1")
            status["approved_cases"] = cur.fetchone()[0]

            cur.execute("SELECT count(*) FROM rag_cases WHERE decision = 'REJECT' AND active = 1")
            status["rejected_cases"] = cur.fetchone()[0]
            conn.close()
        except Exception as e:
            status["error"] = str(e)

    if vec_p.is_dir():
        npz_files = list(vec_p.glob("*.npz"))
        status["vector_files_count"] = len(npz_files)

    if status["total_cases"] > 0:
        status["status_summary"] = (
            f"Active: {status['total_cases']} cases "
            f"({status['approved_cases']} Approved, {status['rejected_cases']} Rejected) | "
            f"{status['vector_files_count']} vector indexes"
        )
    else:
        status["status_summary"] = "Empty (0 cases - Cold Start Ready)"

    return status


def flush_rag(db_path: Path | str | None = None, vector_dir: Path | str | None = None) -> dict[str, Any]:
    """Flushes RAG database cases and vector index files atomically."""
    def_db, def_vec = get_default_paths()
    db_p = Path(db_path) if db_path else def_db
    vec_p = Path(vector_dir) if vector_dir else def_vec

    res = {
        "deleted_cases": 0,
        "deleted_vector_files": 0,
        "success": True,
        "message": "",
    }

    if db_p.is_file():
        try:
            conn = sqlite3.connect(str(db_p))
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM rag_cases")
            count = cur.fetchone()[0]
            cur.execute("DELETE FROM rag_cases")
            conn.commit()
            conn.close()
            res["deleted_cases"] = count
        except Exception as e:
            res["success"] = False
            res["error"] = str(e)

    if vec_p.is_dir():
        try:
            for f in vec_p.glob("*.npz"):
                try:
                    f.unlink()
                    res["deleted_vector_files"] += 1
                except Exception:
                    pass
        except Exception as e:
            res["error_vectors"] = str(e)

    res["message"] = (
        f"Flushed {res['deleted_cases']} RAG database cases and "
        f"{res['deleted_vector_files']} vector index files. RAG is now in Cold-Start state (0 records)."
    )
    return res


def compute_learning_curve(run_dir: Path | str) -> dict[str, Any]:
    """Extracts step-by-step rolling accuracy from tests.jsonl."""
    folder = Path(run_dir)
    tests_file = folder / "tests.jsonl"
    if not tests_file.is_file():
        raise FileNotFoundError(f"tests.jsonl not found in {folder}")

    tests = []
    with open(tests_file, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.strip():
                try:
                    tests.append(json.loads(line))
                except Exception:
                    pass

    if not tests:
        raise ValueError(f"No valid test records found in {tests_file}")

    total_tests = len(tests)
    correct_cum = 0
    cum_acc = []
    window = min(30, max(5, total_tests // 10))
    rolling_acc = []
    window_buf = []

    for idx, t in enumerate(tests, 1):
        is_corr = bool(t.get("matched_ground_truth"))
        if is_corr:
            correct_cum += 1
        cum_acc.append(round((correct_cum / idx) * 100, 2))

        window_buf.append(1 if is_corr else 0)
        if len(window_buf) > window:
            window_buf.pop(0)
        rolling_acc.append(round((sum(window_buf) / len(window_buf)) * 100, 2))

    first_n = min(20, total_tests)
    initial_acc = cum_acc[first_n - 1] if total_tests >= first_n else cum_acc[-1]
    final_acc = cum_acc[-1]

    return {
        "total_tests": total_tests,
        "window_size": window,
        "initial_accuracy": initial_acc,
        "final_accuracy": final_acc,
        "cumulative_accuracy": cum_acc,
        "rolling_accuracy": rolling_acc,
        "run_folder": str(folder),
    }


def plot_learning_curve(run_dir: Path | str, output_png: Path | str | None = None, title: str | None = None) -> Path:
    """Generates a publication-grade Learning Curve figure using matplotlib."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    folder = Path(run_dir)
    curve_data = compute_learning_curve(folder)
    out_path = Path(output_png) if output_png else (folder / "learning_curve.png")

    cum = curve_data["cumulative_accuracy"]
    rolling = curve_data["rolling_accuracy"]
    x = list(range(1, len(cum) + 1))
    w_size = curve_data["window_size"]

    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)

    ax.plot(x, cum, label="Cumulative Accuracy (%)", color="#1D4ED8", linewidth=2.5)
    ax.plot(x, rolling, label=f"Rolling Window Accuracy (W={w_size})", color="#EA580C", linewidth=2.0, linestyle="--", alpha=0.9)

    ax.axhline(95.0, color="#16A34A", linestyle=":", linewidth=1.5, label="Target Benchmark (95%)", alpha=0.8)

    ax.set_xlabel("Number of Process Scenarios Evaluated (Sequential Time-Series)", fontsize=11, fontweight="bold", labelpad=8)
    ax.set_ylabel("Accuracy (%)", fontsize=11, fontweight="bold", labelpad=8)
    plot_title = title or f"Learning Curve Over Time: Continual Experience Adaptation ({folder.name})"
    ax.set_title(plot_title, fontsize=12, fontweight="bold", pad=12)

    ax.set_ylim(min(60.0, min(cum) - 5), 102.0)
    ax.grid(True, linestyle="--", alpha=0.4)

    # Initial vs Final annotations
    init_acc = curve_data["initial_accuracy"]
    final_acc = curve_data["final_accuracy"]
    ax.annotate(f"Initial: {init_acc:.1f}%", xy=(min(20, len(cum)), init_acc),
                xytext=(min(20, len(cum)) + 15, init_acc - 8),
                arrowprops=dict(facecolor="#1D4ED8", shrink=0.08, width=1.2, headwidth=6),
                fontweight="bold", color="#1D4ED8", fontsize=9)

    ax.annotate(f"Final: {final_acc:.1f}%", xy=(len(cum), final_acc),
                xytext=(len(cum) - int(len(cum) * 0.15), final_acc + 3 if final_acc < 96 else final_acc - 5),
                arrowprops=dict(facecolor="#16A34A", shrink=0.08, width=1.2, headwidth=6),
                fontweight="bold", color="#16A34A", fontsize=9)

    ax.legend(loc="lower right", frameon=True, framealpha=0.9, fontsize=9.5)
    plt.tight_layout()
    fig.savefig(str(out_path), dpi=300)
    plt.close(fig)

    return out_path
