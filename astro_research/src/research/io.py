from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_table(path: str | Path) -> pd.DataFrame:
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(target)
    if target.suffix == ".parquet":
        return pd.read_parquet(target)
    if target.suffix == ".csv":
        return pd.read_csv(target)
    raise ValueError(f"Unsupported table format: {target}")


def read_optional_table(path: str | Path) -> pd.DataFrame:
    target = Path(path)
    if not str(path) or not target.exists():
        return pd.DataFrame()
    return read_table(target)


def read_aspect_chunk_windows(path: str | Path) -> pd.DataFrame:
    root = Path(path)
    if not str(path) or not root.exists():
        return pd.DataFrame()
    files = sorted(root.glob("year=*/body_pair=*/astro_event_windows.parquet"))
    if not files:
        files = sorted(root.glob("year=*/body_pair=*/astro_event_windows.csv"))
    frames = [read_table(file) for file in files]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
