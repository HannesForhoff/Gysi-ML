from __future__ import annotations

from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from gysi_ml.steps.base import BaseStep
from gysi_ml.steps.registry import register_step


@register_step("train_ebm")
class EBMStep(BaseStep):
    """Trainiert ein Explainable Boosting Machine-Modell und erzeugt einen globalen Erklärungsplot."""

    description = "Trainiert ein Explainable Boosting Machine-Modell und erzeugt einen globalen Erklärungsplot"
    param_schema = {
        "random_state": {"type": "integer", "default": 42},
    }
    requires_split = True
    is_splitter = False
    TARGET_COL: str = "cnt"

    def __init__(self, params: dict | None = None) -> None:
        super().__init__(params=params)
        self.model: Any = None
        self._metrics: dict = {}
        self._feature_names: list = []
        self._df_train: pd.DataFrame | None = None
        self._df_test: pd.DataFrame | None = None
        self._y_test: np.ndarray | None = None
        self._y_pred: np.ndarray | None = None

    def fit(self, df_train: pd.DataFrame) -> None:
        X_train = df_train.select_dtypes(include="number").drop(
            columns=[self.TARGET_COL], errors="ignore"
        )
        y_train = df_train[self.TARGET_COL]
        self._feature_names = list(X_train.columns)

        from interpret.glassbox import ExplainableBoostingRegressor

        self.model = ExplainableBoostingRegressor(
            random_state=int(self.params.get("random_state", 42)),
        )
        self.model.fit(X_train, y_train)

    def transform(
        self, df_train: pd.DataFrame, df_test: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        if self.model is None:
            raise RuntimeError(
                "transform() wurde vor fit() aufgerufen. Bitte zuerst fit(df_train) aufrufen."
            )
        X_train = df_train[self._feature_names]
        y_train = df_train[self.TARGET_COL]
        y_train_pred = self.model.predict(X_train)
        train_rmse = float(np.sqrt(mean_squared_error(y_train, y_train_pred)))
        train_mae = float(mean_absolute_error(y_train, y_train_pred))
        train_r2 = float(r2_score(y_train, y_train_pred))

        X_test = df_test[self._feature_names]
        y_test = df_test[self.TARGET_COL]
        y_pred = self.model.predict(X_test)
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        mae = float(mean_absolute_error(y_test, y_pred))
        r2 = float(r2_score(y_test, y_pred))

        self._metrics = {
            "rmse": rmse, "mae": mae, "r2": r2,
            "train_rmse": train_rmse, "train_mae": train_mae, "train_r2": train_r2,
        }
        self._df_train = df_train
        self._df_test = df_test
        self._y_test = np.asarray(y_test, dtype=float)
        self._y_pred = np.asarray(y_pred, dtype=float)
        return df_train, df_test

    def get_metadata(self) -> dict:
        return {
            "target": self.TARGET_COL,
            "metrics": self._metrics,
            "feature_names": self._feature_names,
        }

    def generate_artifact(self, artifacts_path: str, run_id: str) -> list[dict] | None:
        if self.model is None:
            return None

        import os

        os.makedirs(artifacts_path, exist_ok=True)
        artifacts = []

        # EBM Global Explanation Plot
        ebm_global = self.model.explain_global()
        global_data = ebm_global.data()
        feature_names = global_data["names"]
        feature_scores = [float(s) for s in global_data["scores"]]

        combined = sorted(
            zip(feature_names, feature_scores),
            key=lambda x: abs(x[1]),
            reverse=True,
        )[:20]
        names_top20 = [c[0] for c in combined]
        scores_top20 = [c[1] for c in combined]

        fig, ax = plt.subplots(figsize=(10, 8))
        try:
            ax.barh(names_top20, scores_top20)
            ax.set_xlabel("Mittlere absolute Auswirkung")
            ax.set_title("EBM — Globale Feature-Wichtigkeit (Top 20)")
            ax.invert_yaxis()
            file_path = os.path.join(artifacts_path, f"ebm_global_explanation_{run_id}.png")
            fig.savefig(file_path, bbox_inches="tight", dpi=150)
        finally:
            plt.close(fig)
        artifacts.append({"type": "ebm_global_explanation", "file_path": file_path})

        # Validation Curve: max_bins (Modellkomplexität) auf X, RMSE auf Y
        if self._df_train is not None and self._df_test is not None:
            from gysi_ml.steps.modeling._overfitting_plot import generate_validation_curve_plot
            bins_values = [4, 8, 16, 32, 64, 128, 256]
            artifacts.append(
                generate_validation_curve_plot(
                    model=self.model,
                    df_train=self._df_train,
                    df_test=self._df_test,
                    feature_names=self._feature_names,
                    target_col=self.TARGET_COL,
                    artifacts_path=artifacts_path,
                    run_id=run_id,
                    model_name="EBM",
                    param_name="max_bins",
                    param_values=bins_values,
                    param_label="Binning-Auflösung (max_bins)",
                )
            )

        if self._y_test is not None and self._y_pred is not None:
            from gysi_ml.steps.modeling._eval_plots import generate_regression_eval_plots
            artifacts.extend(
                generate_regression_eval_plots(
                    y_true=self._y_test,
                    y_pred=self._y_pred,
                    artifacts_path=artifacts_path,
                    run_id=run_id,
                    model_name="EBM",
                )
            )

        return artifacts
