from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class PipelineContext:
    """Zustandsobjekt das durch alle Steps einer Pipeline gereicht wird."""

    df_full: pd.DataFrame
    df_train: pd.DataFrame | None = None
    df_test: pd.DataFrame | None = None
    step_results: list[dict] = field(default_factory=list)
    is_split: bool = False

    def add_step_result(self, step_type: str, metadata: dict) -> None:
        """Fügt das Ergebnis eines Steps zur Liste hinzu."""
        self.step_results.append({"step_type": step_type, "metadata": metadata})
