import os

import pandas as pd

from gysi_ml.steps.base import BaseStep
from gysi_ml.steps.registry import register_step


@register_step("correlation_filter")
class CorrelationFilterStep(BaseStep):
    description = "Entfernt hochkorrelierte numerische Features (Pearson)"
    param_schema = {
        "threshold": {"type": "number", "default": 0.9},
        "features_to_drop": {
            "type": "array",
            "items": {"type": "string"},
            "default": [],
            "description": (
                "Explizite Liste der zu entfernenden Features. "
                "Übersteuert die automatische max()-Fallback-Logik. "
                "Wird vom LLM nach Nutzerbestätigung befüllt."
            ),
        },
    }

    def __init__(self, params: dict | None = None) -> None:
        super().__init__(params)
        self.threshold: float = float(self.params.get("threshold", 0.9))
        # Explizit vom Nutzer bestätigte Features (übersteuert Fallback-Logik)
        self._explicit_drop: list[str] = list(self.params.get("features_to_drop", []))
        self._features_to_drop: list[str] = []
        self._corr_pairs: list[dict] = []
        self._independent_features: list[str] = []
        self._df_filtered: pd.DataFrame | None = None

    def fit(self, df_train: pd.DataFrame) -> None:
        numeric_cols = df_train.select_dtypes(include="number").columns.tolist()
        if len(numeric_cols) < 2:
            self._features_to_drop = []
            self._corr_pairs = []
            self._independent_features = numeric_cols[:]
            return

        corr_matrix = df_train[numeric_cols].corr().abs()
        to_drop: set[str] = set()
        self._corr_pairs = []

        for i in range(len(numeric_cols)):
            for j in range(i + 1, len(numeric_cols)):
                val = corr_matrix.iloc[i, j]
                if val >= self.threshold:
                    col_a = numeric_cols[i]
                    col_b = numeric_cols[j]
                    # Nutzer-Entscheidung hat Vorrang; Fallback: alphabetisch späteres Feature
                    if col_a in self._explicit_drop:
                        dropped = col_a
                    elif col_b in self._explicit_drop:
                        dropped = col_b
                    else:
                        dropped = max(col_a, col_b)
                    to_drop.add(dropped)
                    self._corr_pairs.append(
                        {
                            "col_a": col_a,
                            "col_b": col_b,
                            "value": round(float(val), 4),
                            "dropped": dropped,
                        }
                    )

        # Explizit angegebene Features die keinem korrelierten Paar angehören,
        # aber trotzdem entfernt werden sollen (seltener Sonderfall)
        for feat in self._explicit_drop:
            if feat in numeric_cols and feat not in to_drop:
                to_drop.add(feat)

        self._features_to_drop = sorted(to_drop)

        # Features ohne starke Korrelation zu irgendeinem anderen Feature
        correlated_features: set[str] = set()
        for p in self._corr_pairs:
            correlated_features.add(p["col_a"])
            correlated_features.add(p["col_b"])
        self._independent_features = sorted(
            col for col in numeric_cols if col not in correlated_features
        )

    def transform(
        self, df_train: pd.DataFrame, df_test: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        cols_to_drop = [c for c in self._features_to_drop if c in df_train.columns]
        df_train_filtered = df_train.drop(columns=cols_to_drop)
        df_test_filtered = df_test.drop(columns=cols_to_drop)
        # Für generate_artifact() speichern
        self._df_filtered = df_train_filtered
        return df_train_filtered, df_test_filtered

    def get_metadata(self) -> dict:
        return {
            "dropped_features": self._features_to_drop,
            "corr_pairs": self._corr_pairs,
            "independent_features": self._independent_features,
        }

    def generate_artifact(self, artifacts_path: str, run_id: str) -> list[dict] | None:
        if self._df_filtered is None:
            return None
        os.makedirs(artifacts_path, exist_ok=True)
        path = os.path.join(artifacts_path, f"{run_id}_correlation_filter.csv")
        self._df_filtered.to_csv(path, index=False, float_format="%.6f")
        return [{"type": "correlation_filter_result", "file_path": path}]
