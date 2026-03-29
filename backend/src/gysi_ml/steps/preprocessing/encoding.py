import pandas as pd

from gysi_ml.steps.base import BaseStep
from gysi_ml.steps.registry import register_step


@register_step("encode_categorical")
class CategoricalEncodingStep(BaseStep):
    description = "Encodiert kategorische Features (Label oder One-Hot)"
    param_schema = {
        "method": {
            "type": "string",
            "enum": ["label", "onehot"],
            "default": "label",
        }
    }

    def __init__(self, params: dict | None = None) -> None:
        super().__init__(params)
        self.method: str = self.params.get("method", "label")
        self._label_encoders: dict[str, dict] = {}
        self._onehot_categories: dict[str, list] = {}
        self._encoded_columns: list[str] = []

    def fit(self, df_train: pd.DataFrame) -> None:
        cat_cols = list(df_train.select_dtypes(include=["object", "category", "string"]).columns)
        self._encoded_columns = cat_cols
        if self.method == "label":
            for col in cat_cols:
                unique_vals = sorted(df_train[col].dropna().unique().tolist())
                self._label_encoders[col] = {v: i for i, v in enumerate(unique_vals)}
        else:  # onehot
            for col in cat_cols:
                self._onehot_categories[col] = sorted(
                    df_train[col].dropna().unique().tolist()
                )

    def transform(
        self, df_train: pd.DataFrame, df_test: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        result_train = df_train.copy()
        result_test = df_test.copy()

        if self.method == "label":
            for col, mapping in self._label_encoders.items():
                if col not in result_train.columns:
                    continue
                result_train[col] = (
                    result_train[col].map(mapping).fillna(-1).astype(int)
                )
                result_test[col] = (
                    result_test[col].map(mapping).fillna(-1).astype(int)
                )
        else:  # onehot
            for col, known_cats in self._onehot_categories.items():
                if col not in result_train.columns:
                    continue
                known_col_names = [f"{col}_{cat}" for cat in known_cats]
                dummies_train = pd.get_dummies(result_train[col], prefix=col, dtype=int).reindex(
                    columns=known_col_names, fill_value=0
                )
                dummies_test = pd.get_dummies(result_test[col], prefix=col, dtype=int).reindex(
                    columns=known_col_names, fill_value=0
                )
                result_train = pd.concat(
                    [result_train.drop(columns=[col]), dummies_train], axis=1
                )
                result_test = pd.concat(
                    [result_test.drop(columns=[col]), dummies_test], axis=1
                )

        return result_train, result_test

    def get_metadata(self) -> dict:
        return {"encoded_columns": self._encoded_columns}
