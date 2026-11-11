"""Turns RailKit's response formats into application data. All knowledge of RailKit
field names lives here and in railkit.py."""
import re
from datetime import date as Date, datetime, timezone
from typing import Any

from app.providers.railkit import RailKitError
from app.schemas.railway import (
    AvailabilityDay, AvailabilityResult, Fare, TrainSearchResult, TrainSummary,
)

PROVIDER = "railkit"

# ---------------------------------------------------------------------------
# Availability status
# ---------------------------------------------------------------------------
AVAILABLE, RAC, WAITLIST, UNAVAILABLE, UNKNOWN = range(5)
LEVEL_NAMES = {AVAILABLE: "available", RAC: "rac", WAITLIST: "waitlist", UNAVAILABLE: "unavailable", UNKNOWN: "unknown"}


def classify(status: str | None, text: str | None) -> tuple[int, int | None]:
    """RailKit status/availabilityText -> (level, count). Unknown text stays UNKNOWN."""
    s = f"{status or ''} {text or ''}".upper()
    match = re.search(r"\d+", text or "")
    count = int(match.group()) if match else None
    if re.search(r"REGRET|NOT AVAILABLE|CANCELLED|DEPARTED|CHART PREPARED", s):
        return UNAVAILABLE, None
    if re.search(r"\bRAC\b", s):
        return RAC, count
    if re.search(r"WAITLIST|\bWL\b|GNWL|RLWL|PQWL|TQWL", s):
        return WAITLIST, count
    if re.search(r"AVAILABLE|\bAVL\b|CURR_AVBL", s):
        return AVAILABLE, count
    return UNKNOWN, None


# ---------------------------------------------------------------------------
# Classes, dates and times
# ---------------------------------------------------------------------------
# Reserved classes the seat-availability endpoint accepts (GEN, PWD, PC, LDS... are not).
BOOKABLE = {"1A", "2A", "3A", "3E", "SL", "EC", "CC", "2S", "EA", "FC", "VS", "CH", "HS", "VC", "VA"}
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]  # RailKit running_days is Monday-first


def bookable_classes(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, list):
        items = value
    else:
        return ()
    return tuple(c.strip().upper() for c in items if isinstance(c, str) and c.strip().upper() in BOOKABLE)


def parse_rail_date(value: str) -> Date:
    d, m, y = (int(p) for p in value.split("-"))
    return Date(y, m, d)


def fmt_rail_date(value: Date) -> str:
    return value.strftime("%d-%m-%Y")


def hhmm(value: Any) -> int | None:
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", str(value or "").strip())
    return int(match[1]) * 60 + int(match[2]) if match else None


def duration_minutes(value: Any) -> int | None:
    match = re.match(r"\s*(\d+):(\d{2})", str(value or ""))
    return int(match[1]) * 60 + int(match[2]) if match else None


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value) if isinstance(value, str) and value.strip() else None
    except ValueError:
        return None


def _time(value: Any) -> str | None:
    minutes = hhmm(value)
    return f"{minutes // 60:02d}:{minutes % 60:02d}" if minutes is not None else None


def _running_days(value: Any) -> list[str]:
    if isinstance(value, str) and re.fullmatch(r"[01]{7}", value):
        return [day for day, flag in zip(WEEKDAYS, value) if flag == "1"]
    return []


# ---------------------------------------------------------------------------
# Response conversion
# ---------------------------------------------------------------------------
def _data(payload: Any, kind: str) -> Any:
    if not isinstance(payload, dict) or "data" not in payload:
        raise RailKitError(f"RailKit returned an unexpected {kind} response.")
    return payload["data"]


def train_search_result(payload: Any, from_code: str, to_code: str, date: str | None) -> TrainSearchResult:
    rows = _data(payload, "train search")
    if not isinstance(rows, list):
        raise RailKitError("RailKit returned an unexpected train search response.")
    trains = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        train_no, frm, to = _text(row.get("train_no")), _text(row.get("from_stn_code")), _text(row.get("to_stn_code"))
        if not (train_no and frm and to):
            continue  # a row we cannot use for availability; never invent the missing parts
        trains.append(TrainSummary(
            train_no=train_no, train_name=_text(row.get("train_name")) or "",
            from_code=frm.upper(), from_name=_text(row.get("from_stn_name")),
            to_code=to.upper(), to_name=_text(row.get("to_stn_name")),
            departure=_time(row.get("from_time")), arrival=_time(row.get("to_time")),
            duration_minutes=duration_minutes(row.get("travel_time")),
            running_days=_running_days(row.get("running_days")),
            classes=list(bookable_classes(row.get("classes_of_travel"))),
            distance_km=_number(row.get("distance")),
        ))
    if rows and not trains:
        raise RailKitError("RailKit returned train search results in an unexpected format.")
    return TrainSearchResult(
        provider=PROVIDER, fetched_at=datetime.now(timezone.utc),
        from_code=from_code, to_code=to_code, date=date, trains=trains,
    )


def availability_result(
    payload: Any, train_no: str, from_code: str, to_code: str, travel_class: str, quota: str,
) -> AvailabilityResult:
    data = _data(payload, "availability")
    if not isinstance(data, dict) or not isinstance(data.get("availability"), list):
        raise RailKitError("RailKit returned an unexpected availability response.")
    train = data.get("train") if isinstance(data.get("train"), dict) else {}
    fare_raw = data.get("fare") if isinstance(data.get("fare"), dict) else None

    days = []
    for day in data["availability"]:
        if not isinstance(day, dict):
            continue
        try:
            date = fmt_rail_date(parse_rail_date(str(day.get("date"))))
        except (ValueError, TypeError):
            continue
        level, count = classify(day.get("status"), day.get("availabilityText"))
        can_book = day.get("canBook")
        days.append(AvailabilityDay(
            date=date, status=LEVEL_NAMES[level], count=count,
            text=_text(day.get("availabilityText")), raw_status=_text(day.get("rawStatus")),
            prediction=_text(day.get("prediction")), prediction_pct=_number(day.get("predictionPercentage")),
            can_book=can_book if isinstance(can_book, bool) else None,
        ))

    fare = None
    if fare_raw:
        fare = Fare(
            base=_number(fare_raw.get("baseFare")), reservation=_number(fare_raw.get("reservationCharge")),
            superfast=_number(fare_raw.get("superfastCharge")), tax=_number(fare_raw.get("serviceTax")),
            total=_number(fare_raw.get("totalFare")),
        )
    return AvailabilityResult(
        provider=PROVIDER, fetched_at=datetime.now(timezone.utc),
        train_no=_text(train.get("trainNo")) or train_no, train_name=_text(train.get("trainName")),
        from_code=(_text(train.get("from")) or from_code).upper(), from_name=_text(train.get("fromStationName")),
        to_code=(_text(train.get("to")) or to_code).upper(), to_name=_text(train.get("toStationName")),
        travel_class=_text(train.get("travelClass")) or travel_class, quota=_text(train.get("quota")) or quota,
        fare=fare, days=days,
    )
