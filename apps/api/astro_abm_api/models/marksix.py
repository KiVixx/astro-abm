from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class MarkSixDrawRecord(BaseModel):
    draw_id: str
    draw_date: date | None = None
    draw_year: int
    draw_number: int
    numbers: list[int]
    extra_number: int
    draw_type: str
    is_snowball: bool
    total_sales: float | None = None
    jackpot_amount: float | None = None
    first_prize_dividend: float | None = None
    source: str
    source_is_official: bool


class MarkSixStatus(BaseModel):
    total_draws: int
    coverage_start: date | None = None
    coverage_end: date | None = None
    official_verified_draws: int
    history_start_year: int | None = None
    legacy_draws_without_dates: int
    historical_source: str
    legacy_historical_source: str
    official_source: str
    coverage_note: str


class MarkSixFrequency(BaseModel):
    number: int
    main_count: int
    extra_count: int


class MarkSixWorldlineRequest(BaseModel):
    horizon_draws: Literal[1, 3, 5, 10] = 3
    worldline_count: int = Field(default=1, ge=1, le=5)
    seed: str | None = Field(default=None, max_length=128)
    language: Literal["en", "zh-Hant"] = "zh-Hant"
    generation_mode: Literal["uniform_random_demo_v1", "astro_association_entertainment_v1"] = "uniform_random_demo_v1"
    astro_body: Literal["Mercury", "Venus", "Mars", "Jupiter", "Saturn"] = "Mercury"
    astro_condition: Literal["retrograde", "direct", "pre_station", "retrograde_entry", "retrograde_core", "retrograde_exit", "post_station"] = "retrograde"
    astro_context_type: Literal["planet_motion", "moon_phase"] = "planet_motion"
    moon_phase_condition: Literal["new_moon_zone", "first_quarter_zone", "full_moon_zone", "last_quarter_zone", "waxing_other", "waning_other"] = "full_moon_zone"


class MarkSixSimulatedDraw(BaseModel):
    date: date
    draw_index: int
    numbers: list[int]
    extra_number: int


class MarkSixWorldline(BaseModel):
    worldline_id: str
    generation_mode: str
    draws: list[MarkSixSimulatedDraw]
    disclaimer: str
    astro_context: dict | None = None


class MarkSixWorldlineResponse(BaseModel):
    worldlines: list[MarkSixWorldline]
    historical_draw_count: int
    coverage_start: date | None = None
    coverage_end: date | None = None
    method_note: str


class MarkSixAstroNumberStat(BaseModel):
    number: int
    condition_hits: int
    condition_rate: float
    baseline_hits: int
    baseline_rate: float
    rate_difference: float
    lift: float | None = None
    p_value: float
    q_value_fdr: float


class MarkSixAstroResearch(BaseModel):
    context_type: str = "planet_motion"
    body: str
    condition: str
    number_role: str
    start_date: date
    end_date: date | None = None
    rule_era: str
    total_draws: int
    condition_draws: int
    baseline_draws: int
    numbers: list[MarkSixAstroNumberStat]
    method_notes: list[str]
