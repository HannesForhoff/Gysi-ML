import pandas as pd

from gysi_ml.steps.base import BaseStep
from gysi_ml.steps.registry import register_step


@register_step("impute_missing")
class ImputationStep(BaseStep):
    description = "Imputiert fehlende Werte numerischer Spalten"
    param_schema = {
        "strategy": {
            "type": "string",
            "enum": ["median", "mean", "most_frequent"],
            "default": "median",
        }
    }

    def __init__(self, params: dict | None = None) -> None:
        super().__init__(params)
        self.strategy: str = self.params.get("strategy", "median")
        self._fill_values: dict[str, float] = {}
        self._imputed_per_col: dict[str, int] = {}

    def fit(self, df_train: pd.DataFrame) -> None:
        numeric_cols = df_train.select_dtypes(include="number").columns
        for col in numeric_cols:
            if self.strategy == "median":
                self._fill_values[col] = df_train[col].median()
            elif self.strategy == "mean":
                self._fill_values[col] = df_train[col].mean()
            elif self.strategy == "most_frequent":
                self._fill_values[col] = df_train[col].value_counts().idxmax()

    def transform(
        self, df_train: pd.DataFrame, df_test: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        result_train = df_train.copy()
        result_test = df_test.copy()
        self._imputed_per_col = {}
        for col, val in self._fill_values.items():
            if col not in result_train.columns:
                continue
            n_train = int(result_train[col].isna().sum())
            n_test = int(result_test[col].isna().sum())
            self._imputed_per_col[col] = n_train + n_test
            result_train[col] = result_train[col].fillna(val)
            result_test[col] = result_test[col].fillna(val)
        return result_train, result_test

    def get_metadata(self) -> dict:
        return {"imputed_values_per_column": self._imputed_per_col}
