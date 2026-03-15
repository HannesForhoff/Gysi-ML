import pandas as pd


def load_bikes_dataset(path: str) -> pd.DataFrame:
    """Lädt das Bike-Dataset als DataFrame.

    Args:
        path: Pfad zur bikes.csv (Komma-separiert, Header in Zeile 0).

    Returns:
        pd.DataFrame mit allen Spalten und Zeilen.
    """
    return pd.read_csv(path, sep=",", header=0)
