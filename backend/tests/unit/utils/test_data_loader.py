"""Unit-Tests für data_loader.py (Bug 1.8)."""

import pandas as pd
import pytest

from gysi_ml.utils.data_loader import load_bikes_dataset


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def csv_with_dash_sentinel(tmp_path):
    """Mini-CSV mit '-' als N/A-Sentinel in einer Spalte."""
    csv = tmp_path / "bikes.csv"
    csv.write_text("windspeed,cnt\n0.1,500\n-,300\n0.3,200\n")
    return str(csv)


@pytest.fixture
def csv_clean_numeric(tmp_path):
    """Mini-CSV ohne Sentinels — alle Spalten numerisch."""
    csv = tmp_path / "bikes.csv"
    csv.write_text("windspeed,cnt,temp\n0.1,500,20.5\n0.2,300,18.0\n0.3,200,22.1\n")
    return str(csv)


@pytest.fixture
def csv_various_sentinels(tmp_path):
    """Mini-CSV mit verschiedenen N/A-Sentinel-Varianten."""
    csv = tmp_path / "bikes.csv"
    # b=NA, c=N/A, d=? — alle sollen zu NaN werden
    csv.write_text("a,b,c,d,e\n1,NA,N/A,?,1\n2,2,2,2,2\n")
    return str(csv)


# ---------------------------------------------------------------------------
# Bug 1.8 — '-' wird als NaN erkannt
# ---------------------------------------------------------------------------


def test_dash_sentinel_becomes_nan(csv_with_dash_sentinel):
    """`'-'` in windspeed wird als NaN erkannt, nicht als String-Wert."""
    df = load_bikes_dataset(csv_with_dash_sentinel)
    assert df["windspeed"].isna().sum() == 1


def test_windspeed_loaded_as_numeric_after_dash_sentinel(csv_with_dash_sentinel):
    """windspeed hat nach dem Laden einen numerischen Dtype, nicht StringDtype."""
    df = load_bikes_dataset(csv_with_dash_sentinel)
    assert pd.api.types.is_numeric_dtype(df["windspeed"]), (
        f"windspeed sollte numerisch sein, ist aber: {df['windspeed'].dtype}"
    )


def test_non_na_values_preserved(csv_with_dash_sentinel):
    """Reguläre Werte werden korrekt als Floats eingelesen."""
    df = load_bikes_dataset(csv_with_dash_sentinel)
    non_null = df["windspeed"].dropna()
    assert len(non_null) == 2
    assert float(non_null.iloc[0]) == pytest.approx(0.1)
    assert float(non_null.iloc[1]) == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Bug 1.8 — Defensive: weitere Sentinel-Varianten
# ---------------------------------------------------------------------------


def test_various_na_sentinels_become_nan(csv_various_sentinels):
    """NA, N/A und ? werden ebenfalls als NaN erkannt."""
    df = load_bikes_dataset(csv_various_sentinels)
    # Spalte b: "NA" → NaN
    assert df["b"].isna().sum() == 1
    # Spalte c: "N/A" → NaN
    assert df["c"].isna().sum() == 1
    # Spalte d: "?" → NaN
    assert df["d"].isna().sum() == 1


# ---------------------------------------------------------------------------
# Bug 1.8 — Numerische Spalten ohne Sentinel bleiben numerisch
# ---------------------------------------------------------------------------


def test_clean_numeric_columns_have_numeric_dtype(csv_clean_numeric):
    """Sauber numerische Spalten haben numerischen Dtype."""
    df = load_bikes_dataset(csv_clean_numeric)
    for col in ["windspeed", "cnt", "temp"]:
        assert pd.api.types.is_numeric_dtype(df[col]), (
            f"Spalte '{col}' sollte numerisch sein, ist aber: {df[col].dtype}"
        )
