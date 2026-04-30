import os

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from gysi_ml.steps.base import BaseStep
from gysi_ml.steps.registry import register_step


@register_step("plot_distribution")
class PlotDistributionStep(BaseStep):
    """Erstellt Verteilungsplots für ein Feature – optional gruppiert nach einem zweiten Feature."""

    description = (
        "Erstellt Verteilungsplots für ein Feature. "
        "Ohne 'group_by': Histogramm + Boxplot. "
        "Mit 'group_by': Mittelwert-Balkendiagramm + gruppierter Boxplot."
    )
    param_schema = {
        "feature": {
            "type": "string",
            "description": "Spalte die visualisiert wird (z.B. 'cnt', 'temp').",
        },
        "group_by": {
            "type": ["string", "null"],
            "default": None,
            "description": (
                "Optionale Gruppierungsspalte (z.B. 'season', 'weathersit'). "
                "Wenn angegeben, werden Mittelwert-Balken und gruppierter Boxplot erzeugt."
            ),
        },
    }
    requires_split = False
    is_splitter = False

    def __init__(self, params: dict | None = None) -> None:
        super().__init__(params)
        self._feature: str = self.params.get("feature", "")
        self._group_by: str | None = self.params.get("group_by") or None
        self._df_snapshot: pd.DataFrame | None = None

    def fit(self, df_train: pd.DataFrame) -> None:
        if not self._feature:
            raise ValueError("plot_distribution: Parameter 'feature' ist erforderlich.")
        if self._feature not in df_train.columns:
            raise ValueError(
                f"plot_distribution: Feature '{self._feature}' nicht im Datensatz gefunden."
            )
        if self._group_by and self._group_by not in df_train.columns:
            raise ValueError(
                f"plot_distribution: group_by-Spalte '{self._group_by}' nicht im Datensatz gefunden."
            )
        self._df_snapshot = df_train[[self._feature] + ([self._group_by] if self._group_by else [])].copy()

    def transform(
        self, df_train: pd.DataFrame, df_test: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        # Rein visueller Step – Daten werden nicht verändert
        return df_train, df_test

    def get_metadata(self) -> dict:
        if self._df_snapshot is None:
            return {}
        meta: dict = {"feature": self._feature}
        if self._group_by:
            meta["group_by"] = self._group_by
        series = self._df_snapshot[self._feature].dropna()
        meta["n_values"] = int(series.count())
        meta["mean"] = round(float(series.mean()), 4) if len(series) > 0 else None
        meta["median"] = round(float(series.median()), 4) if len(series) > 0 else None
        return meta

    def generate_artifact(self, artifacts_path: str, run_id: str) -> dict | None:
        if self._df_snapshot is None:
            return None
        os.makedirs(artifacts_path, exist_ok=True)

        if self._group_by:
            return self._generate_grouped_plot(artifacts_path, run_id)
        else:
            return self._generate_univariate_plot(artifacts_path, run_id)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _generate_univariate_plot(self, artifacts_path: str, run_id: str) -> dict:
        """Histogramm + Boxplot nebeneinander für ein einzelnes Feature."""
        series = self._df_snapshot[self._feature].dropna()

        fig, (ax_hist, ax_box) = plt.subplots(1, 2, figsize=(12, 4))

        # Histogramm
        ax_hist.hist(series, bins=30, edgecolor="white", linewidth=0.4)
        ax_hist.set_title(f"Verteilung: {self._feature}")
        ax_hist.set_xlabel(self._feature)
        ax_hist.set_ylabel("Häufigkeit")

        # Boxplot
        ax_box.boxplot(series, orientation="horizontal", patch_artist=True)
        ax_box.set_title(f"Boxplot: {self._feature}")
        ax_box.set_xlabel(self._feature)
        ax_box.set_yticks([])

        fig.tight_layout()
        file_name = f"{run_id}_plot_distribution_{self._feature}.png"
        file_path = os.path.join(artifacts_path, file_name)
        fig.savefig(file_path, dpi=120)
        plt.close(fig)

        return {
            "type": "plot_distribution",
            "file_path": file_path,
            "label": f"Verteilung: {self._feature}",
        }

    def _generate_grouped_plot(self, artifacts_path: str, run_id: str) -> dict:
        """Mittelwert-Balkendiagramm + Boxplot gruppiert nach group_by."""
        df = self._df_snapshot.dropna(subset=[self._feature])
        groups = sorted(df[self._group_by].dropna().unique())

        fig, (ax_bar, ax_box) = plt.subplots(1, 2, figsize=(14, 5))

        # Balkendiagramm: Mittelwert pro Gruppe
        means = df.groupby(self._group_by)[self._feature].mean().reindex(groups)
        ax_bar.bar([str(g) for g in groups], means.values)
        ax_bar.set_title(f"Mittelwert {self._feature} nach {self._group_by}")
        ax_bar.set_xlabel(self._group_by)
        ax_bar.set_ylabel(f"Mittelwert {self._feature}")

        # Boxplot: Verteilung pro Gruppe
        data_per_group = [df.loc[df[self._group_by] == g, self._feature].values for g in groups]
        ax_box.boxplot(data_per_group, tick_labels=[str(g) for g in groups], showfliers=False)
        ax_box.set_title(f"{self._feature} nach {self._group_by} (Boxplot)")
        ax_box.set_xlabel(self._group_by)
        ax_box.set_ylabel(self._feature)

        fig.tight_layout()
        file_name = f"{run_id}_plot_distribution_{self._feature}_by_{self._group_by}.png"
        file_path = os.path.join(artifacts_path, file_name)
        fig.savefig(file_path, dpi=120)
        plt.close(fig)

        return {
            "type": "plot_distribution",
            "file_path": file_path,
            "label": f"{self._feature} nach {self._group_by}",
        }
