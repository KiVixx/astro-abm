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
    if not str(path) or not target.exists() or target.is_dir():
        return pd.DataFrame()
    try:
        return read_table(target)
    except ValueError:
        return pd.DataFrame()


def read_aspect_chunk_windows(path: str | Path) -> pd.DataFrame:
    return read_aspect_chunk_table(path, table_name="astro_event_windows")


def read_aspect_chunk_events(path: str | Path) -> pd.DataFrame:
    return read_aspect_chunk_table(path, table_name="astro_aspect_events")


def read_aspect_chunk_table(path: str | Path, *, table_name: str) -> pd.DataFrame:
    root = Path(path)
    if not str(path) or not root.exists():
        return pd.DataFrame()
    files = discover_aspect_chunk_files(root, table_name=table_name)
    frames = [read_table(file) for file in files]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def discover_aspect_chunk_files(path: str | Path, *, table_name: str) -> list[Path]:
    root = Path(path)
    if not str(path) or not root.exists():
        return []
    files: list[Path] = []
    for directory in sorted(root.glob("year=*/body_pair=*")):
        parquet = directory / f"{table_name}.parquet"
        csv = directory / f"{table_name}.csv"
        if parquet.exists():
            files.append(parquet)
        elif csv.exists():
            files.append(csv)
    return files
