import pandas as pd

from gysi_ml.steps.base import BaseStep
from gysi_ml.steps.registry import register_step


@register_step("split")
class SplitStep(BaseStep):
    """Teilt df_full in Trainings- und Testdaten (zeitbasiert, kein Shuffling).

    Dieser Step setzt context.is_split = True im Executor.
    Wird in Story 1.5 um Stratifizierung und random_state ergänzt.
    """

    description = "Teilt den Datensatz in Trainings- und Testdaten"
    param_schema = {
        "test_size": {"type": "number", "default": 0.2},
    }
    is_splitter = True

    def fit(self, df_full: pd.DataFrame) -> None:
        pass

    def transform(
        self, df_full: pd.DataFrame, df_test: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        test_size = float(self.params.get("test_size", 0.2))
        split_idx = int(len(df_full) * (1.0 - test_size))
        df_train = df_full.iloc[:split_idx].reset_index(drop=True)
        df_test = df_full.iloc[split_idx:].reset_index(drop=True)
        return df_train, df_test

    def get_metadata(self) -> dict:
        return {}
