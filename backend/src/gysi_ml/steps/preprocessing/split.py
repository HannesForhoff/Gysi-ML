import pandas as pd
from sklearn.model_selection import train_test_split

from gysi_ml.steps.base import BaseStep
from gysi_ml.steps.registry import register_step


@register_step("split")
class SplitStep(BaseStep):
    """Teilt df_full reproduzierbar in Train/Test auf (sklearn train_test_split)."""

    description = "Teilt den Datensatz reproduzierbar in Train/Test auf"
    param_schema = {
        "test_size": {"type": "number", "default": 0.2},
        "random_state": {"type": "integer", "default": 42},
    }
    is_splitter = True

    def __init__(self, params: dict | None = None) -> None:
        super().__init__(params=params)
        self._train_rows: int | None = None
        self._test_rows: int | None = None
        self._test_size: float | None = None
        self._random_state: int | None = None

    def fit(self, df_full: pd.DataFrame) -> None:
        pass

    def transform(
        self, df_full: pd.DataFrame, _: pd.DataFrame | None
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        test_size = float(self.params.get("test_size", 0.2))
        random_state = int(self.params.get("random_state", 42))

        df_train, df_test = train_test_split(
            df_full,
            test_size=test_size,
            random_state=random_state,
            shuffle=True,
        )
        df_train = df_train.reset_index(drop=True)
        df_test = df_test.reset_index(drop=True)

        self._train_rows = len(df_train)
        self._test_rows = len(df_test)
        self._test_size = test_size
        self._random_state = random_state

        return df_train, df_test

    def get_metadata(self) -> dict:
        if self._train_rows is None:
            return {}
        return {
            "train_rows": self._train_rows,
            "test_rows": self._test_rows,
            "test_size": self._test_size,
            "random_state": self._random_state,
        }
