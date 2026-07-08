"""Evaluierungs-Plots für Regressionsmodelle.

Erzeugt drei standardisierte Plots nach dem Training:
  - Predicted vs Actual (Scatterplot)
  - Distribution of Actual vs Predicted (KDE, zwei Kurven)
  - Residual Distribution (Histogramm + KDE)
"""
from __future__ import annotations

import os

import numpy as np


def generate_regression_eval_plots(
    y_true,
    y_pred,
    artifacts_path: str,
    run_id: str,
    model_name: str,
) -> list[dict]:
    """Erzeugt Predicted-vs-Actual, KDE-Verteilung und Residualverteilung.

    Parameters
    ----------
    y_true:
        Tatsächliche Zielwerte (Array-like).
    y_pred:
        Vorhergesagte Werte (Array-like).
    artifacts_path:
        Verzeichnis für PNG-Ausgaben.
    run_id:
        Eindeutige Run-ID für Dateinamen.
    model_name:
        Modellbezeichnung für Plot-Titel.

    Returns
    -------
    list[dict]
        Liste von Artifact-Dicts mit ``type`` und ``file_path``.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from scipy.stats import gaussian_kde

    os.makedirs(artifacts_path, exist_ok=True)
    artifacts: list[dict] = []

    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    # ------------------------------------------------------------------ #
    # 1. Predicted vs Actual
    # ------------------------------------------------------------------ #
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.scatter(y_true, y_pred, alpha=0.35, s=15, color="#4C72B0", label="Datenpunkte")
    min_val = float(min(y_true.min(), y_pred.min()))
    max_val = float(max(y_true.max(), y_pred.max()))
    ax.plot([min_val, max_val], [min_val, max_val], "r--", linewidth=1.5, label="Ideallinie (y=x)")
    ax.set_xlabel("Tatsächliche Werte")
    ax.set_ylabel("Vorhergesagte Werte")
    ax.set_title(f"{model_name} — Predicted vs Actual")
    ax.legend()
    ax.grid(linestyle="--", alpha=0.4)
    pva_path = os.path.join(artifacts_path, f"predicted_vs_actual_{run_id}.png")
    try:
        fig.savefig(pva_path, bbox_inches="tight", dpi=150)
    finally:
        plt.close(fig)
    artifacts.append({"type": "predicted_vs_actual", "file_path": pva_path})

    # ------------------------------------------------------------------ #
    # 2. Distribution of Actual vs Predicted (KDE)
    # ------------------------------------------------------------------ #
    fig, ax = plt.subplots(figsize=(9, 5))
    x_range = np.linspace(
        float(min(y_true.min(), y_pred.min())),
        float(max(y_true.max(), y_pred.max())),
        300,
    )
    kde_actual = gaussian_kde(y_true)
    kde_pred = gaussian_kde(y_pred)
    actual_vals = kde_actual(x_range)
    pred_vals = kde_pred(x_range)
    ax.plot(x_range, actual_vals, color="#4C72B0", linewidth=2, label="Tatsächlich")
    ax.fill_between(x_range, actual_vals, alpha=0.15, color="#4C72B0")
    ax.plot(x_range, pred_vals, color="#DD8452", linewidth=2, linestyle="--", label="Vorhergesagt")
    ax.fill_between(x_range, pred_vals, alpha=0.15, color="#DD8452")
    ax.set_xlabel("Wert")
    ax.set_ylabel("Dichte")
    ax.set_title(f"{model_name} — Verteilung: Tatsächlich vs Vorhergesagt (KDE)")
    ax.legend()
    ax.grid(linestyle="--", alpha=0.4)
    dist_path = os.path.join(artifacts_path, f"distribution_actual_vs_predicted_{run_id}.png")
    try:
        fig.savefig(dist_path, bbox_inches="tight", dpi=150)
    finally:
        plt.close(fig)
    artifacts.append({"type": "distribution_actual_vs_predicted", "file_path": dist_path})

    # ------------------------------------------------------------------ #
    # 3. Residual Distribution
    # ------------------------------------------------------------------ #
    residuals = y_true - y_pred
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(residuals, bins=40, density=True, color="#4C72B0", alpha=0.5, label="Residuen")
    kde_resid = gaussian_kde(residuals)
    x_resid = np.linspace(float(residuals.min()), float(residuals.max()), 300)
    ax.plot(x_resid, kde_resid(x_resid), color="#DD8452", linewidth=2, label="KDE")
    ax.axvline(0.0, color="red", linestyle="--", linewidth=1.2, label="Null-Linie")
    ax.set_xlabel("Residuum (Tatsächlich − Vorhergesagt)")
    ax.set_ylabel("Dichte")
    ax.set_title(f"{model_name} — Residualverteilung")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    resid_path = os.path.join(artifacts_path, f"residual_distribution_{run_id}.png")
    try:
        fig.savefig(resid_path, bbox_inches="tight", dpi=150)
    finally:
        plt.close(fig)
    artifacts.append({"type": "residual_distribution", "file_path": resid_path})

    return artifacts
