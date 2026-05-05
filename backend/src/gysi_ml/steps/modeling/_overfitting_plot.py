"""Validation Curve: zeigt Train- und Test-Fehler über wachsende Modellkomplexität.

Interpretation:
  - Trainings-RMSE fällt mit steigender Komplexität (Modell passt sich besser an)
  - Test-RMSE fällt zuerst, steigt dann wieder → Overfitting ab dem Minimum
  - Bleibt Test-RMSE dauerhaft hoch (ähnlich Train) → Underfitting
"""
from __future__ import annotations

import os

import numpy as np


def generate_validation_curve_plot(
    model,
    df_train,
    df_test,
    feature_names: list[str],
    target_col: str,
    artifacts_path: str,
    run_id: str,
    model_name: str,
    param_name: str,
    param_values: list,
    param_label: str,
) -> dict:
    """Erzeugt eine Validation Curve (X = Modellkomplexität, Y = RMSE).

    Trainiert das Modell für jeden Komplexitätswert neu und misst RMSE
    jeweils auf Train- und Testset.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.base import clone
    from sklearn.metrics import mean_squared_error

    X_train = df_train[feature_names].values
    y_train = df_train[target_col].values
    X_test = df_test[feature_names].values
    y_test = df_test[target_col].values

    train_errors: list[float] = []
    test_errors: list[float] = []

    for val in param_values:
        m = clone(model)
        m.set_params(**{param_name: val})
        m.fit(X_train, y_train)
        train_errors.append(float(np.sqrt(mean_squared_error(y_train, m.predict(X_train)))))
        test_errors.append(float(np.sqrt(mean_squared_error(y_test, m.predict(X_test)))))

    x_labels = [str(v) for v in param_values]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(x_labels, train_errors, "o-", color="#4C72B0", label="Training RMSE")
    ax.plot(x_labels, test_errors,  "o-", color="#DD8452", label="Test RMSE")
    ax.fill_between(x_labels, train_errors, test_errors,
                    alpha=0.12, color="gray", label="Lücke (Overfitting)")
    ax.set_xlabel(param_label)
    ax.set_ylabel("RMSE (Fehler)")
    ax.set_title(f"{model_name} — Validation Curve (Overfitting-Check)")
    ax.legend(loc="upper right")
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    # Optimum markieren (Min. Test-RMSE)
    best_idx = int(np.argmin(test_errors))
    ax.axvline(x=x_labels[best_idx], color="#2ca02c", linestyle="--",
               linewidth=1.2, label=f"Bestes Modell ({x_labels[best_idx]})")
    ax.legend(loc="upper right")

    os.makedirs(artifacts_path, exist_ok=True)
    file_path = os.path.join(artifacts_path, f"learning_curve_{run_id}.png")
    fig.savefig(file_path, bbox_inches="tight", dpi=150)
    plt.close(fig)

    return {"type": "learning_curve", "file_path": file_path}

    fig.savefig(file_path, bbox_inches="tight", dpi=150)
    plt.close(fig)

    return {"type": "learning_curve", "file_path": file_path}
