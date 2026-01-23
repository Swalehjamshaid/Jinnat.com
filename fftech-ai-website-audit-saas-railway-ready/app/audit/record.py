
# app/audit/record.py
from __future__ import annotations

import os
import uuid
from typing import Dict, Any

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt


def _ensure_tmp_dir() -> str:
    out_dir = "/tmp"
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    return out_dir


def _plot_overall(ax, score: float):
    # Donut chart showing overall score
    score = max(0, min(100, float(score)))
    remaining = 100 - score
    colors = ["#2ecc71", "#eeeeee"] if score >= 60 else ["#e67e22", "#eeeeee"]
    wedges, _ = ax.pie(
        [score, remaining],
        startangle=90,
        colors=colors,
        wedgeprops=dict(width=0.36, edgecolor="white"),
    )
    ax.set_title(f"Overall Score: {score:.0f}", fontsize=13, pad=10)
    ax.axis("equal")


def _plot_breakdown(ax, breakdown: Dict[str, float]):
    labels = []
    values = []
    for k in ("onpage", "performance", "coverage"):
        if k in breakdown:
            labels.append(k.capitalize())
            values.append(breakdown[k])
    if not labels:
        labels, values = ["Onpage", "Performance", "Coverage"], [0, 0, 0]

    bars = ax.bar(labels, values, color=["#3498db", "#9b59b6", "#f1c40f"])
    ax.bar_label(bars, fmt="%.0f", label_type="edge", padding=3, fontsize=9)
    ax.set_ylim(0, 100)
    ax.set_title("Category Breakdown (0–100)", fontsize=12)
    ax.grid(axis="y", linestyle=":", alpha=0.4)


def _plot_status(ax, status_dist: Dict[str, int]):
    # Convert keys to strings for safety
    items = sorted(((str(k), v) for k, v in (status_dist or {}).items()), key=lambda x: int(x[0]) if x[0].isdigit() else 0)
    labels = [k for k, _ in items][:8]
    values = [v for _, v in items][:8]

    if not labels:
        labels, values = ["200", "404"], [0, 0]

    bars = ax.bar(labels, values, color="#95a5a6")
    ax.bar_label(bars, fmt="%d", label_type="edge", padding=3, fontsize=9)
    ax.set_title("HTTP Status Distribution", fontsize=12)
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    ax.set_ylim(0, max(values + [1]))


def generate_charts(audit_result: Dict[str, Any]) -> str:
    """
    Builds a 3-panel figure:
      - Overall score donut
      - Breakdown bar
      - Status code distribution bar
    Returns the absolute path to the saved PNG.
    """
    overall = float(audit_result.get("overall_score", 0.0))
    breakdown = audit_result.get("breakdown") or {}
    status_dist = (audit_result.get("issues_overview") or {}).get("http_status_distribution") or {}

    out_dir = _ensure_tmp_dir()
    out_path = os.path.join(out_dir, f"audit_chart_{uuid.uuid4().hex}.png")

    plt.style.use("seaborn-v0_8")
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.2), constrained_layout=True)

    _plot_overall(axes[0], overall)
    _plot_breakdown(axes[1], breakdown)
    _plot_status(axes[2], status_dist)

    fig.suptitle("FF Tech AI Website Audit — Visual Summary", fontsize=14, fontweight="bold")
    fig.savefig(out_path, dpi=160)
    plt.close(fig)

    return out_path
