import pandas as pd

from gysi_ml.steps.base import BaseStep
from gysi_ml.steps.registry import register_step

TARGET_COL = "cnt"


@register_step("drop_columns")
class DropColumnsStep(BaseStep):
    description = "Entfernt explizit benannte Spalten (Features) aus dem Datensatz"
    param_schema = {
        "columns": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Liste der Spalten, die aus dem Datensatz entfernt werden sollen. "
                f"Die Zielspalte '{TARGET_COL}' kann nicht entfernt werden."
            ),
        }
    }

    def __init__(self, params: dict | None = None) -> None:
        super().__init__(params)
        self._columns_to_drop: list[str] = list(self.params.get("columns", []))
        self._dropped: list[str] = []

    def fit(self, df_train: pd.DataFrame) -> None:
        if not self._columns_to_drop:
            raise ValueError("drop_columns: Keine Spalten angegeben. Bitte 'columns' befüllen.")

        # Zielspalte schützen
        if TARGET_COL in self._columns_to_drop:
            raise ValueError(
                f"drop_columns: Die Zielspalte '{TARGET_COL}' darf nicht entfernt werden."
            )

        # Nicht vorhandene Spalten melden
        missing = [c for c in self._columns_to_drop if c not in df_train.columns]
        if missing:
            available = sorted(df_train.columns.tolist())
            raise ValueError(
                f"drop_columns: Spalten nicht im Datensatz gefunden: {missing}. "
                f"Verfügbare Spalten: {available}"
            )

        self._dropped = list(self._columns_to_drop)

    def transform(
        self, df_train: pd.DataFrame, df_test: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        return (
            df_train.drop(columns=self._dropped),
            df_test.drop(columns=self._dropped, errors="ignore"),
        )

    def get_metadata(self) -> dict:
        return {"dropped_columns": self._dropped}
