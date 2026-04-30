import pandas as pd
from catboost import CatBoostRegressor

from gysi_ml.steps.base import BaseStep
from gysi_ml.steps.registry import register_step


@register_step("catboost_feature_selection")
class CatBoostFeatureSelectionStep(BaseStep):
    """Selektiert die wichtigsten Features mittels CatBoost Feature Importance."""

    description = "Selektiert die wichtigsten Features mittels CatBoost Feature Importance"
    param_schema = {
        "top_n": {"type": "integer", "default": 8},
        "random_state": {"type": "integer", "default": 42},
        "analysis_only": {
            "type": "boolean",
            "default": True,
            "description": (
                "Wenn True: nur Analyse — kein Feature wird entfernt. "
                "Standard für den ersten Aufruf, damit der Nutzer die Ergebnisse sieht "
                "und entscheiden kann, welche Features entfernt werden sollen."
            ),
        },
        "features_to_drop": {
            "type": "array",
            "items": {"type": "string"},
            "default": [],
            "description": (
                "Explizite Liste der zu entfernenden Features nach Nutzerbestätigung. "
                "Wenn gesetzt, wird analysis_only ignoriert und der Drop durchgeführt."
            ),
        },
    }
    requires_split = True
    is_splitter = False
    TARGET_COL: str = "cnt"

    def __init__(self, params: dict | None = None) -> None:
        super().__init__(params=params)
        self._selected_features: list[str] = []
        self._removed_features: list[str] = []
        self._feature_importances: list[dict] = []
        self._dropped_target_nan: int = 0
        explicit_drop = list(self.params.get("features_to_drop", []))
        self._analysis_only: bool = bool(self.params.get("analysis_only", True)) and not explicit_drop
        self._explicit_drop: list[str] = explicit_drop

    def fit(self, df_train: pd.DataFrame) -> None:
        top_n = int(self.params.get("top_n", 8))
        random_state = int(self.params.get("random_state", 42))

        # CatBoost toleriert NaN in Features, aber nicht in der Zielspalte
        target_nan = df_train[self.TARGET_COL].isna().sum()
        if target_nan > 0:
            df_train = df_train.dropna(subset=[self.TARGET_COL])
            self._dropped_target_nan = int(target_nan)

        X_train = df_train.select_dtypes(include="number").drop(
            columns=[self.TARGET_COL], errors="ignore"
        )
        y_train = df_train[self.TARGET_COL]

        model = CatBoostRegressor(random_seed=random_state, verbose=0)
        model.fit(X_train, y_train)

        importances = model.get_feature_importance()
        feature_names = list(X_train.columns)
        sorted_features = sorted(
            zip(feature_names, importances),
            key=lambda x: x[1],
            reverse=True,
        )
        if self._explicit_drop:
            # Nutzer hat explizit bestimmte Features zum Entfernen angegeben
            drop_set = set(self._explicit_drop) & set(feature_names)
            self._selected_features = [f for f in feature_names if f not in drop_set]
            self._removed_features = sorted(drop_set)
        else:
            # top_n-basierte Selektion (Vorschlag im Analyse-Modus oder direkte Ausführung)
            self._selected_features = [f[0] for f in sorted_features[:top_n]]
            self._removed_features = [f for f in feature_names if f not in set(self._selected_features)]

        selected_set = set(self._selected_features)
        self._feature_importances = [
            {
                "name": name,
                "importance": round(float(score), 2),
                "selected": name in selected_set,
            }
            for name, score in sorted_features
        ]

    def transform(
        self, df_train: pd.DataFrame, df_test: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        # Im Analyse-Modus werden keine Features entfernt — Datensatz bleibt unverändert.
        if self._analysis_only:
            return df_train, df_test
        keep_cols = [c for c in self._selected_features if c in df_train.columns] + [self.TARGET_COL]
        return df_train[keep_cols], df_test[keep_cols]

    def get_metadata(self) -> dict:
        meta: dict = {
            "analysis_only": self._analysis_only,
            "selected_features": self._selected_features,
            "removed_features": self._removed_features,
            "feature_importances": self._feature_importances,
        }
        warnings: list[str] = []
        if self._dropped_target_nan > 0:
            warnings.append(
                f"{self._dropped_target_nan} Zeile(n) mit fehlendem Zielwert (cnt) "
                f"wurden für das Training ignoriert. Empfehlung: Imputation zuerst durchführen."
            )
        if warnings:
            meta["warnings"] = warnings
        return meta

    def generate_artifact(self, artifacts_path: str, run_id: str) -> dict | None:
        return None
