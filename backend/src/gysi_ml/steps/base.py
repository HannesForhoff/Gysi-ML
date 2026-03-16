from abc import ABC, abstractmethod

import pandas as pd


class BaseStep(ABC):
    """Abstrakte Basisklasse für alle Pipeline-Steps."""

    description: str = ""
    param_schema: dict = {}
    requires_split: bool = False
    is_splitter: bool = False

    def __init__(self, params: dict | None = None) -> None:
        self.params: dict = params or {}

    @abstractmethod
    def fit(self, df_train: pd.DataFrame) -> None:
        """Passt den Step auf den Trainingsdatensatz an."""

    @abstractmethod
    def transform(
        self, df_train: pd.DataFrame, df_test: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Wendet den Step auf Train- und Test-Datensatz an."""

    def get_metadata(self) -> dict:
        """Gibt optionale Metadaten nach der Ausführung zurück."""
        return {}

    def generate_artifact(self, artifacts_path: str, run_id: str) -> dict | None:
        """Generiert ein Artefakt (z.B. Plot) nach der Step-Ausführung.
        Gibt dict mit 'type' und 'file_path' zurück oder None wenn kein Artefakt.
        Preprocessing-Steps geben immer None zurück (Default).
        """
        return None
