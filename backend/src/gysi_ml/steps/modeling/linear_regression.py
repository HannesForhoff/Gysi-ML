import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from gysi_ml.steps.base import BaseStep
from gysi_ml.steps.registry import register_step


@register_step("train_linear_regression")
class LinearRegressionStep(BaseStep):
    """Trainiert eine Lineare Regression und berechnet Regressionsmetriken."""

    description = "Trainiert eine Lineare Regression und berechnet Regressionsmetriken"
    param_schema: dict = {}
    requires_split = True
    is_splitter = False
    TARGET_COL: str = "cnt"

    def __init__(self, params: dict | None = None) -> None:
        super().__init__(params=params)
        self.model: LinearRegression | None = None
        self._metrics: dict = {}
        self._feature_names: list = []

    def fit(self, df_train: pd.DataFrame) -> None:
        X_train = df_train.select_dtypes(include="number").drop(
            columns=[self.TARGET_COL], errors="ignore"
        )
        y_train = df_train[self.TARGET_COL]
        self._feature_names = list(X_train.columns)
        self.model = LinearRegression()
        try:
            self.model.fit(X_train, y_train)
        except ValueError as exc:
            nan_count = int(y_train.isna().sum())
            if nan_count > 0:
                raise ValueError(
                    f"Die Zielspalte '{self.TARGET_COL}' enthält {nan_count} fehlende Wert(e) (NaN). "
                    f"Bitte imputiere fehlende Werte in '{self.TARGET_COL}' vor dem Training "
                    f"(z.\u00a0B. 'Imputiere {self.TARGET_COL} mit dem Median')."
                ) from exc
            raise

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
        return df_train, df_test

    def get_metadata(self) -> dict:
        return {
            "target": self.TARGET_COL,
            "metrics": self._metrics,
            "feature_names": self._feature_names,
        }

    def generate_artifact(self, artifacts_path: str, run_id: str) -> list[dict] | None:
        if self.model is None or not self._feature_names:
            return None
        import os

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        os.makedirs(artifacts_path, exist_ok=True)
        artifacts = []

        # Koeffizienten-Plot: Top-20 nach absolutem Betrag
        coefs = self.model.coef_
        sorted_idx = np.argsort(np.abs(coefs))[::-1][:20]
        names_top20 = [self._feature_names[i] for i in sorted_idx]
        coefs_top20 = coefs[sorted_idx]

        fig, ax = plt.subplots(figsize=(10, 8))
        colors = ["steelblue" if c >= 0 else "tomato" for c in coefs_top20]
        ax.barh(names_top20, coefs_top20, color=colors)
        ax.axvline(0, color="black", linewidth=0.8)
        ax.set_xlabel("Regressionskoeffizient")
        ax.set_title("Lineare Regression — Koeffizienten (Top 20 nach |Betrag|)")
        ax.invert_yaxis()
        coef_path = os.path.join(artifacts_path, f"lr_coefficients_{run_id}.png")
        fig.savefig(coef_path, bbox_inches="tight", dpi=150)
        plt.close(fig)
        artifacts.append({"type": "lr_coefficients", "file_path": coef_path})

        return artifacts
