import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.tree import DecisionTreeRegressor

from gysi_ml.steps.base import BaseStep
from gysi_ml.steps.registry import register_step


@register_step("train_decision_tree")
class DecisionTreeStep(BaseStep):
    """Trainiert einen Decision-Tree-Regressor und berechnet Regressionsmetriken."""

    description = "Trainiert einen Decision-Tree-Regressor und berechnet Regressionsmetriken"
    param_schema = {
        "max_depth": {"type": ["integer", "null"], "default": None},
        "random_state": {"type": "integer", "default": 42},
    }
    requires_split = True
    is_splitter = False
    TARGET_COL: str = "cnt"

    def __init__(self, params: dict | None = None) -> None:
        super().__init__(params=params)
        self.model: DecisionTreeRegressor | None = None
        self._metrics: dict = {}
        self._feature_names: list = []

    def fit(self, df_train: pd.DataFrame) -> None:
        X_train = df_train.select_dtypes(include="number").drop(
            columns=[self.TARGET_COL], errors="ignore"
        )
        y_train = df_train[self.TARGET_COL]
        self._feature_names = list(X_train.columns)
        self.model = DecisionTreeRegressor(
            max_depth=self.params.get("max_depth"),
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
        X_test = df_test[self._feature_names]
        y_test = df_test[self.TARGET_COL]
        y_pred = self.model.predict(X_test)
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        mae = float(mean_absolute_error(y_test, y_pred))
        r2 = float(r2_score(y_test, y_pred))
        self._metrics = {"rmse": rmse, "mae": mae, "r2": r2}
        return df_train, df_test

    def get_metadata(self) -> dict:
        return {
            "target": self.TARGET_COL,
            "max_depth": self.params.get("max_depth"),
            "metrics": self._metrics,
            "feature_names": self._feature_names,
        }

    def generate_artifact(self, artifacts_path: str, run_id: str) -> dict | None:
        if self.model is None or not self._feature_names:
            return None
        import os

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        os.makedirs(artifacts_path, exist_ok=True)
        importances = self.model.feature_importances_
        indices = importances.argsort()[::-1][:20]
        names_top20 = [self._feature_names[i] for i in indices]
        importances_top20 = importances[indices]

        fig, ax = plt.subplots(figsize=(10, 8))
        ax.barh(names_top20, importances_top20)
        ax.set_xlabel("Feature Importance")
        ax.set_title("Decision Tree — Feature Importance (Top 20)")
        ax.invert_yaxis()

        file_path = os.path.join(artifacts_path, f"feature_importance_{run_id}.png")
        fig.savefig(file_path, bbox_inches="tight", dpi=150)
        plt.close(fig)
        return {"type": "feature_importance", "file_path": file_path}
