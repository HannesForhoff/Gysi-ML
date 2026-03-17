import pandas as pd

from gysi_ml.steps.base import BaseStep
from gysi_ml.steps.registry import register_step


@register_step("rare_category_bucketing")
class RareCategoryBucketingStep(BaseStep):
    description = "Bündelt seltene Kategorien zu '__rare__'"
    param_schema = {"min_frequency": {"type": "number", "default": 0.01}}
    requires_split = True

    def __init__(self, params: dict | None = None) -> None:
        super().__init__(params)
        self.min_frequency: float = float(self.params.get("min_frequency", 0.01))
        self._rare_categories: dict[str, set] = {}

    def fit(self, df_train: pd.DataFrame) -> None:
        cat_cols = df_train.select_dtypes(include=["object", "category", "string"]).columns
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
            "rare_categories_per_column": {
                col: len(cats) for col, cats in self._rare_categories.items()
            }
        }
