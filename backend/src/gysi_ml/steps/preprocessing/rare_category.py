import pandas as pd

from gysi_ml.steps.base import BaseStep
from gysi_ml.steps.registry import register_step


@register_step("rare_category_bucketing")
class RareCategoryBucketingStep(BaseStep):
    description = "Bündelt seltene Kategorien zu '__rare__'"
    param_schema = {
        "min_frequency": {"type": "number", "default": 0.01},
        "columns": {"type": "array", "items": {"type": "string"}, "default": []},
    }

    def __init__(self, params: dict | None = None) -> None:
        super().__init__(params)
        self.min_frequency: float = float(self.params.get("min_frequency", 0.01))
        self._columns: list[str] = list(self.params.get("columns") or [])
        self._rare_categories: dict[str, set] = {}

    def fit(self, df_train: pd.DataFrame) -> None:
        if self._columns:
            # Explizite Spalten angegeben → beliebiger Dtype erlaubt (Fix Bug 1.5 Problem A+B)
            cat_cols = [c for c in self._columns if c in df_train.columns]
        else:
            # Kein columns-Parameter → nur String-artige Dtypes (Backward-Compat)
            cat_cols = df_train.select_dtypes(include=["object", "category", "string"]).columns.tolist()
        self._rare_categories = {}
        for col in cat_cols:
            frequencies = df_train[col].value_counts(normalize=True)
            self._rare_categories[col] = set(
                frequencies[frequencies < self.min_frequency].index
            )

    def transform(
        self, df_train: pd.DataFrame, df_test: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        result_train = df_train.copy()
        result_test = df_test.copy()
        for col, rare_cats in self._rare_categories.items():
            if col not in result_train.columns or not rare_cats:
                continue
            result_train[col] = result_train[col].apply(
                lambda x, rc=rare_cats: "__rare__" if x in rc else x
            )
            result_test[col] = result_test[col].apply(
                lambda x, rc=rare_cats: "__rare__" if x in rc else x
            )
        return result_train, result_test

    def get_metadata(self) -> dict:
        return {
            "min_frequency": self.min_frequency,
            "rare_categories_per_column": {
                col: len(cats) for col, cats in self._rare_categories.items()
            },
        }
