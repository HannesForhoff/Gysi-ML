import pandas as pd

from gysi_ml.steps.base import BaseStep
from gysi_ml.steps.registry import register_step


@register_step("outlier_handling")
class OutlierHandlingStep(BaseStep):
    description = "Behandelt Ausreißer via IQR oder Z-Score (Winsorization / Capping)"
    param_schema = {
        "method": {
            "type": "string",
            "enum": ["iqr", "zscore"],
            "default": "iqr",
        },
        "zscore_threshold": {"type": "number", "default": 3.0},
    }

    def __init__(self, params: dict | None = None) -> None:
        super().__init__(params)
        self.method: str = self.params.get("method", "iqr")
        self.zscore_threshold: float = float(self.params.get("zscore_threshold", 3.0))
        self._bounds: dict[str, tuple[float, float]] = {}
        self._stats: dict[str, tuple[float, float]] = {}
        self._outliers_treated: int = 0

    def fit(self, df_train: pd.DataFrame) -> None:
        self._bounds = {}
        self._stats = {}
        numeric_cols = df_train.select_dtypes(include="number").columns
        if self.method == "iqr":
            for col in numeric_cols:
                q1 = float(df_train[col].quantile(0.25))
                q3 = float(df_train[col].quantile(0.75))
                iqr = q3 - q1
                self._bounds[col] = (q1 - 1.5 * iqr, q3 + 1.5 * iqr)
        elif self.method == "zscore":
            for col in numeric_cols:
                mean = float(df_train[col].mean())
                std = float(df_train[col].std())
                self._stats[col] = (mean, std)

    def transform(
        self, df_train: pd.DataFrame, df_test: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        result_train = df_train.copy()
        result_test = df_test.copy()
        total_treated = 0

        if self.method == "iqr":
            for col, (lower, upper) in self._bounds.items():
                if col not in result_train.columns:
                    continue
                total_treated += int(
                    ((result_train[col] < lower) | (result_train[col] > upper)).sum()
                )
                total_treated += int(
                    ((result_test[col] < lower) | (result_test[col] > upper)).sum()
                )
                result_train[col] = result_train[col].clip(lower=lower, upper=upper)
                result_test[col] = result_test[col].clip(lower=lower, upper=upper)
        elif self.method == "zscore":
            for col, (mean, std) in self._stats.items():
                if col not in result_train.columns or std == 0:
                    continue
                lower = mean - self.zscore_threshold * std
                upper = mean + self.zscore_threshold * std
                total_treated += int(
                    ((result_train[col] < lower) | (result_train[col] > upper)).sum()
                )
                total_treated += int(
                    ((result_test[col] < lower) | (result_test[col] > upper)).sum()
                )
                result_train[col] = result_train[col].clip(lower=lower, upper=upper)
                result_test[col] = result_test[col].clip(lower=lower, upper=upper)

        self._outliers_treated = total_treated
        return result_train, result_test

    def get_metadata(self) -> dict:
        return {"outliers_treated": self._outliers_treated}
