import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.tree import DecisionTreeRegressor

from gysi_ml.steps.base import BaseStep
from gysi_ml.steps.modeling._overfitting_plot import generate_validation_curve_plot
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
        self.model = DecisionTreeRegressor(
            max_depth=self.params.get("max_depth"),
            random_state=int(self.params.get("random_state", 42)),
        )
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
        self._df_train = df_train
        self._df_test = df_test
        self._y_test = np.asarray(y_test, dtype=float)
        self._y_pred = np.asarray(y_pred, dtype=float)
        return df_train, df_test

    def get_metadata(self) -> dict:
        return {
            "target": self.TARGET_COL,
            "max_depth": self.params.get("max_depth"),
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

        # Feature Importance Plot
        importances = self.model.feature_importances_
        indices = importances.argsort()[::-1][:20]
        names_top20 = [self._feature_names[i] for i in indices]
        importances_top20 = importances[indices]

        fig, ax = plt.subplots(figsize=(10, 8))
        ax.barh(names_top20, importances_top20)
        ax.set_xlabel("Feature Importance")
        ax.set_title("Decision Tree — Feature Importance (Top 20)")
        ax.invert_yaxis()
        fi_path = os.path.join(artifacts_path, f"feature_importance_{run_id}.png")
        fig.savefig(fi_path, bbox_inches="tight", dpi=150)
        plt.close(fig)
        artifacts.append({"type": "feature_importance", "file_path": fi_path})

        # Validation Curve: max_depth (Modellkomplexität) auf X, RMSE auf Y
        if self._df_train is not None and self._df_test is not None:
            depths = list(range(1, 21))  # max_depth 1 bis 20
            artifacts.append(
                generate_validation_curve_plot(
                    model=self.model,
                    df_train=self._df_train,
                    df_test=self._df_test,
                    feature_names=self._feature_names,
                    target_col=self.TARGET_COL,
                    artifacts_path=artifacts_path,
                    run_id=run_id,
                    model_name="Decision Tree",
                    param_name="max_depth",
                    param_values=depths,
                    param_label="Baumtiefe (max_depth)",
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
                    model_name="Decision Tree",
                )
            )

        return artifacts
