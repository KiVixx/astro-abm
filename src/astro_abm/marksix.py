from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import os
import random
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from html import unescape
from pathlib import Path
from typing import Any, Iterable

import requests


HISTORY_URL = "https://renavon.com/data/hkjc/hkjc_marksix_results/download/csv"
OFFICIAL_URL = "https://info.cld.hkjc.com/graphql/base/"
OFFICIAL_PAGE = "https://bet.hkjc.com/ch/marksix/results"
LEGACY_HISTORY_URL = "https://www.nfd.com.tw/house/year/{year}.htm"
OFFICIAL_QUERY = """fragment lotteryDrawsFragment on LotteryDraw {
    id year no openDate closeDate drawDate status snowballCode
    snowballName_en snowballName_ch
    lotteryPool { sell status totalInvestment jackpot unitBet estimatedPrize
      derivedFirstPrizeDiv lotteryPrizes { type winningUnit dividend } }
    drawResult { drawnNo xDrawnNo }
  }
  query marksixResult($lastNDraw: Int, $startDate: String, $endDate: String, $drawType: LotteryDrawType) {
    lotteryDraws(lastNDraw: $lastNDraw, startDate: $startDate, endDate: $endDate, drawType: $drawType) {
      ...lotteryDrawsFragment
    }
  }"""


def default_db_path() -> Path:
    configured = os.getenv("ASTRO_ABM_MARKSIX_DB_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "astro_research/data/local/marksix/marksix.sqlite3"


@dataclass(frozen=True)
class MarkSixDraw:
    draw_id: str
    draw_date: str | None
    draw_year: int
    draw_number: int
    numbers: tuple[int, int, int, int, int, int]
    extra_number: int
    draw_type: str = "Normal"
    is_snowball: bool = False
    total_sales: float | None = None
    jackpot_amount: float | None = None
    first_prize_dividend: float | None = None
    source: str = "historical_archive"
    source_url: str = HISTORY_URL
    source_is_official: bool = False


@dataclass(frozen=True)
class MarkSixSyncSummary:
    database_path: str
    history_fetched: int
    official_fetched: int
    rows_written: int
    total_rows: int
    coverage_start: str | None
    coverage_end: str | None
    warnings: tuple[str, ...]

    @property
    def errors(self) -> tuple[str, ...]:
        return self.warnings

    @property
    def fetched(self) -> int:
        return self.history_fetched + self.official_fetched


def _connect(path: Path | None = None) -> sqlite3.Connection:
    db_path = path or default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS marksix_draws (
          draw_id TEXT PRIMARY KEY,
          draw_date TEXT,
          draw_year INTEGER NOT NULL,
          draw_number INTEGER NOT NULL,
          ball_1 INTEGER NOT NULL, ball_2 INTEGER NOT NULL,
          ball_3 INTEGER NOT NULL, ball_4 INTEGER NOT NULL,
          ball_5 INTEGER NOT NULL, ball_6 INTEGER NOT NULL,
          extra_number INTEGER NOT NULL,
          draw_type TEXT NOT NULL,
          is_snowball INTEGER NOT NULL,
          total_sales REAL,
          jackpot_amount REAL,
          first_prize_dividend REAL,
          source TEXT NOT NULL,
          source_url TEXT NOT NULL,
          source_is_official INTEGER NOT NULL,
          retrieved_at TEXT NOT NULL,
          UNIQUE(draw_year, draw_number)
        );
        CREATE INDEX IF NOT EXISTS idx_marksix_draw_date
          ON marksix_draws(draw_date DESC);
        CREATE TABLE IF NOT EXISTS marksix_sync_runs (
          run_at TEXT PRIMARY KEY,
          history_fetched INTEGER NOT NULL,
          official_fetched INTEGER NOT NULL,
          rows_written INTEGER NOT NULL,
          status TEXT NOT NULL,
          note TEXT
        );
        """
    )
    return connection


def _number(value: Any) -> float | None:
    if value in (None, "", "null"):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def _validate_draw(draw: MarkSixDraw) -> MarkSixDraw:
    if draw.draw_date is not None:
        date.fromisoformat(draw.draw_date)
    if len(draw.numbers) != 6 or len(set(draw.numbers)) != 6:
        raise ValueError(f"{draw.draw_id}: six unique main numbers are required")
    all_numbers = (*draw.numbers, draw.extra_number)
    if any(value < 1 or value > 49 for value in all_numbers):
        raise ValueError(f"{draw.draw_id}: numbers must be between 1 and 49")
    if draw.extra_number in draw.numbers:
        raise ValueError(f"{draw.draw_id}: extra number duplicates a main number")
    return draw


def parse_history_csv(payload: bytes) -> list[MarkSixDraw]:
    if payload.startswith(b"\x1f\x8b"):
        payload = gzip.decompress(payload)
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
    draws: list[MarkSixDraw] = []
    for row in reader:
        if str(row.get("has_results", "true")).lower() not in {"true", "1", "yes"}:
            continue
        draw_date = str(row.get("draw_date") or "")[:10]
        draw_id = str(row.get("draw_id") or row.get("draw_record_id") or "").strip()
        numbers = tuple(int(row[f"ball_{index}"]) for index in range(1, 7))
        draw = MarkSixDraw(
            draw_id=draw_id,
            draw_date=draw_date,
            draw_year=int(row.get("draw_year") or draw_date[:4]),
            draw_number=int(row.get("draw_number_in_year") or "".join(filter(str.isdigit, draw_id))[4:]),
            numbers=numbers,  # type: ignore[arg-type]
            extra_number=int(row["extra_ball"]),
            draw_type=str(row.get("draw_type_name") or "Normal"),
            is_snowball=str(row.get("is_snowball_draw", "false")).lower() in {"true", "1", "yes"},
            total_sales=_number(row.get("total_sales")),
            jackpot_amount=_number(row.get("jackpot_amount")),
            first_prize_dividend=_number(row.get("first_prize_dividend")),
        )
        draws.append(_validate_draw(draw))
    return draws


def parse_legacy_history_html(payload: bytes, *, expected_year: int) -> list[MarkSixDraw]:
    text = payload.decode("big5", errors="replace")
    draws: list[MarkSixDraw] = []
    for raw_row in re.findall(r"<tr[^>]*>(.*?)</tr>", text, flags=re.IGNORECASE | re.DOTALL):
        cells = []
        for raw_cell in re.findall(r"<td[^>]*>(.*?)</td>", raw_row, flags=re.IGNORECASE | re.DOTALL):
            value = re.sub(r"<[^>]+>", "", raw_cell)
            value = unescape(value).replace("&nbsp;", " ").strip()
            if re.fullmatch(r"\d+", value):
                cells.append(int(value))
        if len(cells) != 9 or cells[0] != expected_year:
            continue
        year, draw_number, *numbers = cells
        draw = MarkSixDraw(
            draw_id=f"{year}{draw_number:03d}N",
            draw_date=None,
            draw_year=year,
            draw_number=draw_number,
            numbers=tuple(numbers[:6]),  # type: ignore[arg-type]
            extra_number=numbers[6],
            source="nfd_legacy_archive",
            source_url=LEGACY_HISTORY_URL.format(year=year),
            source_is_official=False,
        )
        draws.append(_validate_draw(draw))
    return draws


def _parse_official_date(value: str) -> str:
    return date.fromisoformat(value[:10]).isoformat()


def parse_official_draws(payload: dict[str, Any]) -> list[MarkSixDraw]:
    rows = payload.get("data", {}).get("lotteryDraws") or []
    draws: list[MarkSixDraw] = []
    for row in rows:
        result = row.get("drawResult") or {}
        raw_main = result.get("drawnNo") or []
        raw_extra = result.get("xDrawnNo")
        if len(raw_main) != 6 or raw_extra in (None, ""):
            continue
        pool = row.get("lotteryPool") or {}
        first_prize = next(
            (item.get("dividend") for item in pool.get("lotteryPrizes") or [] if str(item.get("type")) == "1"),
            None,
        )
        draw = MarkSixDraw(
            draw_id=str(row.get("id") or f"{row['year']}{int(row['no']):03d}N"),
            draw_date=_parse_official_date(str(row["drawDate"])),
            draw_year=int(row["year"]),
            draw_number=int(row["no"]),
            numbers=tuple(int(value) for value in raw_main),  # type: ignore[arg-type]
            extra_number=int(raw_extra),
            draw_type="Normal",
            is_snowball=bool(row.get("snowballCode")),
            total_sales=_number(pool.get("totalInvestment")),
            jackpot_amount=_number(pool.get("jackpot")),
            first_prize_dividend=_number(first_prize),
            source="hkjc_official",
            source_url=OFFICIAL_PAGE,
            source_is_official=True,
        )
        draws.append(_validate_draw(draw))
    return draws


def fetch_history(*, timeout: float = 60.0) -> list[MarkSixDraw]:
    response = requests.get(HISTORY_URL, timeout=timeout)
    response.raise_for_status()
    return parse_history_csv(response.content)


def fetch_legacy_history(*, timeout: float = 30.0) -> list[MarkSixDraw]:
    draws: list[MarkSixDraw] = []
    for year in range(1976, 1993):
        response = requests.get(LEGACY_HISTORY_URL.format(year=year), timeout=timeout)
        response.raise_for_status()
        year_draws = parse_legacy_history_html(response.content, expected_year=year)
        if not year_draws:
            raise RuntimeError(f"Legacy archive returned no rows for {year}")
        draws.extend(year_draws)
    return draws


def fetch_official_latest(*, timeout: float = 30.0) -> list[MarkSixDraw]:
    response = requests.post(
        OFFICIAL_URL,
        json={
            "operationName": "marksixResult",
            "variables": {"lastNDraw": 30, "startDate": None, "endDate": None, "drawType": "All"},
            "query": OFFICIAL_QUERY,
        },
        headers={"Content-Type": "application/json", "Origin": "https://bet.hkjc.com"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(f"HKJC response error: {payload['errors'][0].get('message', 'unknown')}")
    return parse_official_draws(payload)


def _upsert(connection: sqlite3.Connection, draws: Iterable[MarkSixDraw]) -> int:
    retrieved_at = datetime.now(UTC).isoformat()
    count = 0
    for draw in draws:
        connection.execute(
            """INSERT INTO marksix_draws VALUES (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            ) ON CONFLICT(draw_id) DO UPDATE SET
              draw_date=excluded.draw_date, draw_year=excluded.draw_year,
              draw_number=excluded.draw_number, ball_1=excluded.ball_1,
              ball_2=excluded.ball_2, ball_3=excluded.ball_3,
              ball_4=excluded.ball_4, ball_5=excluded.ball_5,
              ball_6=excluded.ball_6, extra_number=excluded.extra_number,
              draw_type=excluded.draw_type, is_snowball=excluded.is_snowball,
              total_sales=excluded.total_sales, jackpot_amount=excluded.jackpot_amount,
              first_prize_dividend=excluded.first_prize_dividend,
              source=CASE WHEN excluded.source_is_official=1 THEN excluded.source ELSE marksix_draws.source END,
              source_url=CASE WHEN excluded.source_is_official=1 THEN excluded.source_url ELSE marksix_draws.source_url END,
              source_is_official=MAX(marksix_draws.source_is_official, excluded.source_is_official),
              retrieved_at=excluded.retrieved_at""",
            (
                draw.draw_id, draw.draw_date, draw.draw_year, draw.draw_number,
                *draw.numbers, draw.extra_number, draw.draw_type, int(draw.is_snowball),
                draw.total_sales, draw.jackpot_amount, draw.first_prize_dividend,
                draw.source, draw.source_url, int(draw.source_is_official), retrieved_at,
            ),
        )
        count += 1
    return count


def database_status(path: Path | None = None) -> dict[str, Any]:
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT count(*) AS total, min(draw_date) AS start, max(draw_date) AS end, "
            "sum(source_is_official) AS official, min(draw_year) AS start_year, "
            "sum(CASE WHEN draw_date IS NULL THEN 1 ELSE 0 END) AS legacy FROM marksix_draws"
        ).fetchone()
    return {
        "total_draws": int(row["total"] or 0),
        "coverage_start": row["start"],
        "coverage_end": row["end"],
        "official_verified_draws": int(row["official"] or 0),
        "history_start_year": row["start_year"],
        "legacy_draws_without_dates": int(row["legacy"] or 0),
        "database_path": str(path or default_db_path()),
    }


def sync_marksix(*, full_history: bool | None = None, path: Path | None = None) -> MarkSixSyncSummary:
    db_path = path or default_db_path()
    status_before = database_status(db_path)
    include_history = status_before["total_draws"] == 0 if full_history is None else full_history
    warnings: list[str] = []
    history: list[MarkSixDraw] = []
    official: list[MarkSixDraw] = []
    if include_history:
        try:
            history = fetch_history()
        except Exception as error:
            warnings.append(f"Historical archive unavailable: {type(error).__name__}: {error}")
        try:
            history = [*fetch_legacy_history(), *history]
        except Exception as error:
            warnings.append(f"1976-1992 legacy archive unavailable: {type(error).__name__}: {error}")
    try:
        official = fetch_official_latest()
    except Exception as error:
        warnings.append(f"Official HKJC latest results unavailable: {type(error).__name__}: {error}")
    if not history and not official and status_before["total_draws"] == 0:
        raise RuntimeError("No Mark Six data could be downloaded. " + " ".join(warnings))
    with _connect(db_path) as connection:
        written = _upsert(connection, history)
        written += _upsert(connection, official)
        run_at = datetime.now(UTC).isoformat()
        connection.execute(
            "INSERT INTO marksix_sync_runs VALUES (?, ?, ?, ?, ?, ?)",
            (run_at, len(history), len(official), written, "warning" if warnings else "ok", " | ".join(warnings)),
        )
        connection.commit()
    status = database_status(db_path)
    return MarkSixSyncSummary(
        database_path=str(db_path), history_fetched=len(history), official_fetched=len(official),
        rows_written=written, total_rows=status["total_draws"],
        coverage_start=status["coverage_start"], coverage_end=status["coverage_end"],
        warnings=tuple(warnings),
    )


def list_draws(*, limit: int = 20, path: Path | None = None) -> list[dict[str, Any]]:
    with _connect(path) as connection:
        rows = connection.execute(
            "SELECT * FROM marksix_draws ORDER BY draw_year DESC, draw_number DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "draw_id": row["draw_id"], "draw_date": row["draw_date"],
        "draw_year": row["draw_year"], "draw_number": row["draw_number"],
        "numbers": [row[f"ball_{index}"] for index in range(1, 7)],
        "extra_number": row["extra_number"], "draw_type": row["draw_type"],
        "is_snowball": bool(row["is_snowball"]), "total_sales": row["total_sales"],
        "jackpot_amount": row["jackpot_amount"], "first_prize_dividend": row["first_prize_dividend"],
        "source": row["source"], "source_is_official": bool(row["source_is_official"]),
    }


def number_frequencies(path: Path | None = None) -> list[dict[str, int]]:
    counts = {number: {"main_count": 0, "extra_count": 0} for number in range(1, 50)}
    with _connect(path) as connection:
        rows = connection.execute(
            "SELECT ball_1, ball_2, ball_3, ball_4, ball_5, ball_6, extra_number FROM marksix_draws"
        ).fetchall()
    for row in rows:
        for index in range(6):
            counts[int(row[index])]["main_count"] += 1
        counts[int(row[6])]["extra_count"] += 1
    return [{"number": number, **values} for number, values in counts.items()]


def _next_draw_dates(start: date, count: int) -> list[date]:
    dates: list[date] = []
    cursor = start
    while len(dates) < count:
        if cursor.weekday() in {1, 3, 5}:  # Illustrative Tue/Thu/Sat slots only.
            dates.append(cursor)
        cursor += timedelta(days=1)
    return dates


def generate_worldlines(
    *, horizon_draws: int, worldline_count: int, seed: str | None = None,
    language: str = "zh-Hant",
) -> list[dict[str, Any]]:
    seed_material = seed or os.urandom(24).hex()
    dates = _next_draw_dates(datetime.now(UTC).date() + timedelta(days=1), horizon_draws)
    worldlines: list[dict[str, Any]] = []
    for worldline_index in range(worldline_count):
        digest = hashlib.sha256(f"{seed_material}:{worldline_index}".encode()).digest()
        rng = random.Random(int.from_bytes(digest))
        simulated = []
        for draw_index, draw_date in enumerate(dates):
            selected = rng.sample(range(1, 50), 7)
            simulated.append({
                "date": draw_date.isoformat(), "draw_index": draw_index + 1,
                "numbers": sorted(selected[:6]), "extra_number": selected[6],
            })
        disclaimer = (
            "每個合法號碼組合的機率相同；歷史結果不能預測未來開獎。僅供娛樂與情境推演，非投注或財務建議。只限18歲或以上人士。"
            if language == "zh-Hant" else
            "Every valid combination has equal probability; historical results cannot predict future draws. For entertainment and scenario rehearsal only, not betting or financial advice. Adults 18+ only."
        )
        worldlines.append({
            "worldline_id": f"marksix-{hashlib.sha256(digest).hexdigest()[:10]}",
            "generation_mode": "uniform_random_demo_v1", "draws": simulated,
            "disclaimer": disclaimer,
        })
    return worldlines


def public_sync_summary(summary: MarkSixSyncSummary) -> dict[str, Any]:
    return asdict(summary)
