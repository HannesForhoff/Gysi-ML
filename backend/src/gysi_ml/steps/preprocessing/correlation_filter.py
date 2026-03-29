import pandas as pd

from gysi_ml.steps.base import BaseStep
from gysi_ml.steps.registry import register_step


@register_step("correlation_filter")
class CorrelationFilterStep(BaseStep):
    description = "Entfernt hochkorrelierte numerische Features (Pearson)"
    param_schema = {"threshold": {"type": "number", "default": 0.9}}

    def __init__(self, params: dict | None = None) -> None:
        super().__init__(params)
        self.threshold: float = float(self.params.get("threshold", 0.9))
        self._features_to_drop: list[str] = []

    def fit(self, df_train: pd.DataFrame) -> None:
        numeric_cols = df_train.select_dtypes(include="number").columns.tolist()
        if len(numeric_cols) < 2:
            self._features_to_drop = []
            return

        corr_matrix = df_train[numeric_cols].corr().abs()
        to_drop: set[str] = set()

        for i in range(len(numeric_cols)):
            for j in range(i + 1, len(numeric_cols)):
                if corr_matrix.iloc[i, j] >= self.threshold:
                    col_a = numeric_cols[i]
                    col_b = numeric_cols[j]
                    # Alphabetisch späteres Feature entfernen
                    to_drop.add(max(col_a, col_b))

        self._features_to_drop = sorted(to_drop)

    def transform(
        self, df_train: pd.DataFrame, df_test: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        cols_to_drop = [c for c in self._features_to_drop if c in df_train.columns]
        return (
            df_train.drop(columns=cols_to_drop),
            df_test.drop(columns=cols_to_drop),
        )

    def get_metadata(self) -> dict:
        return {"dropped_features": self._features_to_drop}
