from __future__ import annotations

from itertools import combinations

from .aspects import ordered_body_pair


ASTRO_BODY_ORDER = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto")

ASPECT_PROFILES = {
    "macro_core": ("Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"),
    "market_core": ("Mercury", "Venus", "Mars", "Jupiter", "Saturn"),
    "lunar_short_term": ("Moon", "Sun", "Mercury", "Venus", "Mars", "Saturn", "Uranus"),
    "all_no_moon": ("Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"),
    "all": ASTRO_BODY_ORDER,
}


def parse_aspect_bodies(value: str | None, *, profile: str | None = None) -> tuple[str, ...]:
    if value:
        return tuple(_normalize_body(part) for part in value.split(",") if part.strip())
    if profile:
        if profile not in ASPECT_PROFILES:
            raise ValueError(f"Unknown aspect profile: {profile}")
        return ASPECT_PROFILES[profile]
    return ASPECT_PROFILES["market_core"]


def parse_aspect_pairs(value: str | None) -> tuple[tuple[str, str], ...]:
    if not value:
        return ()
    pairs = []
    for raw_pair in value.split(","):
        token = raw_pair.strip()
        if not token:
            continue
        separator = "/" if "/" in token else "-" if "-" in token else "_"
        parts = [part for part in token.split(separator) if part]
        if len(parts) != 2:
            raise ValueError(f"Invalid aspect pair: {raw_pair}")
        pairs.append(ordered_body_pair(_normalize_body(parts[0]), _normalize_body(parts[1])))
    return tuple(dict.fromkeys(pairs))


def resolve_aspect_pairs(
    *,
    profile: str | None = None,
    aspect_bodies: str | None = None,
    aspect_pairs: str | None = None,
    include_moon_aspects: bool = False,
) -> tuple[tuple[str, str], ...]:
    explicit_pairs = parse_aspect_pairs(aspect_pairs)
    pairs = explicit_pairs or tuple(combinations(parse_aspect_bodies(aspect_bodies, profile=profile), 2))
    normalized = tuple(ordered_body_pair(left, right) for left, right in pairs)
    if not include_moon_aspects:
        normalized = tuple(pair for pair in normalized if "Moon" not in pair)
    return tuple(dict.fromkeys(normalized))


def pair_slug(pair: tuple[str, str]) -> str:
    return f"{pair[0]}_{pair[1]}"


def _normalize_body(value: str) -> str:
    body = value.strip().replace(" ", "").title()
    lookup = {body.lower(): body for body in ASTRO_BODY_ORDER}
    if body.lower() not in lookup:
        raise ValueError(f"Unknown aspect body: {value}")
    return lookup[body.lower()]
