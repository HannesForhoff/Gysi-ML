import pandas as pd

from gysi_ml.steps.base import BaseStep
from gysi_ml.steps.registry import register_step


@register_step("time_feature_encoding")
class TimeFeatureEncodingStep(BaseStep):
    description = "Leitet Wochentag und Monat aus Datumsspalte ab"
    param_schema = {"column": {"type": "string", "default": "dteday"}}

    def __init__(self, params: dict | None = None) -> None:
        super().__init__(params)
        self._column: str = self.params.get("column", "dteday")

    def fit(self, df_train: pd.DataFrame) -> None:
        pass  # stateless

    def transform(
        self, df_train: pd.DataFrame, df_test: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        return self._apply(df_train), self._apply(df_test)

    def _apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if self._column not in df.columns:
            return df.copy()
        result = df.copy()
        dates = pd.to_datetime(result[self._column])
        result["weekday"] = dates.dt.dayofweek
        result["month"] = dates.dt.month
        result = result.drop(columns=[self._column])
        return result

    def get_metadata(self) -> dict:
        return {
            "derived_features": ["weekday", "month"],
            "dropped_column": self._column,
        }
