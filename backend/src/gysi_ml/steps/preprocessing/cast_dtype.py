import pandas as pd

from gysi_ml.steps.base import BaseStep
from gysi_ml.steps.registry import register_step

_SUPPORTED_DTYPES = ("int64", "float64", "str", "object", "category", "bool", "datetime64")


@register_step("cast_dtype")
class CastDtypeStep(BaseStep):
    description = (
        "Ändert den Datentypen einzelner Spalten. "
        "Unterstützte Zieltypen: int64, float64, str, object, category, bool, datetime64."
    )
    param_schema = {
        "columns": {
            "type": "object",
            "description": (
                "Mapping von Spaltenname zu Zieldatentyp. "
                "Beispiel: {\"season\": \"category\", \"cnt\": \"int64\"}"
            ),
            "additionalProperties": {
                "type": "string",
                "enum": list(_SUPPORTED_DTYPES),
            },
        },
        "datetime_format": {
            "type": "string",
            "description": (
                "Optionales strptime-Format für datetime64-Casts, z.B. \"%Y-%m-%d\". "
                "Wird ignoriert, wenn kein datetime64-Cast stattfindet."
            ),
        },
    }

    def __init__(self, params: dict | None = None) -> None:
        super().__init__(params)
        self._columns: dict[str, str] = dict(self.params.get("columns", {}))
        self._datetime_format: str | None = self.params.get("datetime_format", None)
        self._cast_results: dict[str, dict[str, str]] = {}  # col → {old_dtype, new_dtype}

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _validate_params(self, df: pd.DataFrame) -> None:
        if not self._columns:
            raise ValueError(
                "cast_dtype: Der Parameter 'columns' fehlt oder ist leer. "
                "Bitte ein Mapping von Spaltenname zu Zieldatentyp angeben, "
                "z.B. {\"season\": \"category\"}."
            )

        missing = [c for c in self._columns if c not in df.columns]
        if missing:
            raise ValueError(
                f"cast_dtype: Folgende Spalten wurden nicht im Datensatz gefunden: {missing}. "
                f"Verfügbare Spalten: {sorted(df.columns.tolist())}"
            )

        unsupported = [
            f"{col!r} → {dtype!r}"
            for col, dtype in self._columns.items()
            if dtype not in _SUPPORTED_DTYPES
        ]
        if unsupported:
            raise ValueError(
                f"cast_dtype: Nicht unterstützte Zieldatentypen: {unsupported}. "
                f"Erlaubte Typen: {list(_SUPPORTED_DTYPES)}"
            )

    # ------------------------------------------------------------------
    # Core cast logic (applied per-DataFrame)
    # ------------------------------------------------------------------

    def _cast_series(self, series: pd.Series, target: str, col: str) -> pd.Series:
        current = str(series.dtype)

        # No-op if dtype already matches (handles aliases like str/object)
        actual_target = "object" if target == "str" else target
        if current == actual_target or (actual_target == "object" and current == "object"):
            return series

        try:
            if target == "datetime64":
                return pd.to_datetime(series, format=self._datetime_format, utc=False)
            elif target == "category":
                return series.astype("category")
            elif target in ("str", "object"):
                # astype(str) in pandas 2.x → StringDtype; .astype(object) fixiert auf "object"
                return series.astype(str).astype(object)
            elif target == "bool":
                return series.astype(bool)
            elif target == "int64":
                return series.astype("int64")
            elif target == "float64":
                return series.astype("float64")
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError(
                f"cast_dtype: Spalte '{col}' (aktueller Typ: {current!r}) kann nicht "
                f"nach '{target}' konvertiert werden. "
                f"Ursache: {exc}"
            ) from exc

        # Unreachable — only here to satisfy type checker
        raise ValueError(f"cast_dtype: Unbekannter Zieldatentyp '{target}'")  # pragma: no cover

    def _apply(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        for col, target in self._columns.items():
            if col not in result.columns:
                continue  # already validated in fit; skip silently on test df
            result[col] = self._cast_series(result[col], target, col)
        return result

    # ------------------------------------------------------------------
    # BaseStep interface
    # ------------------------------------------------------------------

    def fit(self, df_train: pd.DataFrame) -> None:
        self._validate_params(df_train)
        # Dry-run on a single-row sample to catch cast errors early
        sample = df_train.head(1)
        for col, target in self._columns.items():
            old_dtype = str(df_train[col].dtype)
            self._cast_series(sample[col], target, col)
            self._cast_results[col] = {"old_dtype": old_dtype, "new_dtype": target}

    def transform(
        self, df_train: pd.DataFrame, df_test: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        return self._apply(df_train), self._apply(df_test)

    def get_metadata(self) -> dict:
        return {"casts_applied": self._cast_results}  # {col: {old_dtype, new_dtype}}
