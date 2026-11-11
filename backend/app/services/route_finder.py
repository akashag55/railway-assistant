"""Best-route search across direct trains, same-train split tickets, longer tickets
and one-change connections.

Deterministic: every result comes from RailKit data; nothing is inferred or invented.
Persistence, cancellation and quota checks are injected by the caller (route_jobs).
"""
from __future__ import annotations

import asyncio
import inspect
import math
from dataclasses import dataclass, field
from datetime import date as Date, datetime, time, timedelta
from typing import Any, Awaitable, Callable

from app.providers.railkit import RailKitError

from app.providers.railkit_parsing import (  # noqa: F401  (re-exported for callers and tests)
    AVAILABLE, BOOKABLE, LEVEL_NAMES, RAC, UNAVAILABLE, UNKNOWN, WAITLIST,
    bookable_classes, classify, duration_minutes, fmt_rail_date, hhmm, parse_rail_date,
)

@dataclass(frozen=True)
class Availability:
    travel_class: str
    level: int
    count: int | None = None
    text: str | None = None
    raw: str | None = None
    prediction: str | None = None
    prediction_pct: float | None = None
    fare: float | None = None
    error: str | None = None

    @property
    def rank(self) -> tuple[int, int]:
        """Lower is better. Any available seat is equally good; shorter RAC/WL is better."""
        if self.level == AVAILABLE:
            return (AVAILABLE, 0)
        if self.level in (RAC, WAITLIST):
            return (self.level, self.count if self.count is not None else 9999)
        return (self.level, 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "travel_class": self.travel_class, "level": LEVEL_NAMES[self.level], "count": self.count,
            "text": self.text, "raw": self.raw, "prediction": self.prediction,
            "prediction_pct": self.prediction_pct, "fare": self.fare, "error": self.error,
        }


# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------
SLEEPER_LADDER = ["1A", "2A", "3A", "3E", "SL"]
CHAIR_LADDER = ["EC", "CC", "2S"]
SL_MAX_LEG_MINUTES = 240  # Sleeper as a fallback only for legs of 4 hours or less.


def class_candidates(selected: str) -> list[str]:
    """Selected class first, then one class up, one down (and SL as a fallback for 3A)."""
    for ladder in (SLEEPER_LADDER, CHAIR_LADDER):
        if selected in ladder:
            i = ladder.index(selected)
            out = [selected]
            if i > 0:
                out.append(ladder[i - 1])
            if i + 1 < len(ladder):
                out.append(ladder[i + 1])
            if selected == "3A" and "SL" not in out:
                out.append("SL")
            return out
    return [selected]


def class_allowed(travel_class: str, selected: str, leg_minutes: int) -> bool:
    if travel_class == "SL" and selected != "SL":
        return leg_minutes <= SL_MAX_LEG_MINUTES
    return True


# ---------------------------------------------------------------------------
# Dates, times, stations
# ---------------------------------------------------------------------------
# Stations in the same city, treated as interchangeable for transfers. Coordinates
# from train routes (<= NEARBY_KM apart) cover stations not listed here.
CITY_GROUPS = [
    {"BCT", "MMCT", "CSMT", "LTT", "BDTS", "DDR", "BVI", "ADH", "TNA"},  # Mumbai
    {"NDLS", "DLI", "NZM", "ANVT", "DEE", "DEC", "DSA"},  # Delhi
    {"JP", "GADJ", "DPA"},  # Jaipur
    {"HWH", "SDAH", "KOAA", "SHM", "SRC"},  # Kolkata
    {"MAS", "MS", "PER"},  # Chennai
    {"SBC", "YPR", "SMVB", "BNC", "KJM"},  # Bengaluru
    {"SC", "HYB", "KCG", "LPI"},  # Hyderabad
    {"ADI", "SBT", "MAN"},  # Ahmedabad
    {"LKO", "LJN", "ASH"},  # Lucknow
    {"AGC", "AF", "IDH"},  # Agra
    {"PNBE", "RJPB", "PPTA", "DNR"},  # Patna
]
NEARBY_KM = 20.0
MIN_TRANSFER_MINUTES = 120
MAX_TRANSFER_MINUTES = 240
MIN_HUB_DISTANCE_KM = 50  # ignore hubs this close to either end


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


# ---------------------------------------------------------------------------
# Train routes
# ---------------------------------------------------------------------------
@dataclass
class Stop:
    code: str
    name: str
    arr: int | None  # minutes since 00:00 of the train's start day
    dep: int | None
    distance: float
    halt: int
    coords: tuple[float, float] | None


@dataclass
class TrainRoute:
    train_no: str
    name: str
    classes: tuple[str, ...]
    stops: list[Stop]

    def index(self, code: str) -> int | None:
        for i, stop in enumerate(self.stops):
            if stop.code == code:
                return i
        return None


def parse_train_info(payload: Any) -> TrainRoute | None:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict) or not isinstance(data.get("route"), list):
        return None
    info = data.get("trainInfo") or {}
    stops: list[Stop] = []
    for raw in data["route"]:
        try:
            base = (int(raw.get("day") or 1) - 1) * 1440
        except (TypeError, ValueError):
            return None
        arr, dep = hhmm(raw.get("arrival")), hhmm(raw.get("departure"))
        arr = base + arr if arr is not None else None
        dep = base + dep if dep is not None else None
        if arr is not None and dep is not None and dep < arr:
            dep += 1440  # departs after midnight
        coords = raw.get("coordinates") or {}
        lat, lon = coords.get("latitude"), coords.get("longitude")
        try:
            distance = float(raw.get("distance") or 0)
        except (TypeError, ValueError):
            distance = 0.0
        stops.append(Stop(
            code=str(raw.get("stnCode") or "").upper(), name=str(raw.get("stnName") or ""),
            arr=arr, dep=dep, distance=distance, halt=int(raw.get("haltMinutes") or 0),
            coords=(float(lat), float(lon)) if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) else None,
        ))
    if len(stops) < 2:
        return None
    classes = bookable_classes(info.get("prs_classes") or info.get("classes"))
    return TrainRoute(str(info.get("train_no") or ""), str(info.get("train_name") or ""), classes, stops)


# ---------------------------------------------------------------------------
# Legs and options
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Leg:
    train_no: str
    train_name: str
    board: str  # where you get on
    alight: str  # where you get off
    ticket_from: str  # ticket origin (differs from board for a longer ticket)
    ticket_to: str
    journey_date: str  # DD-MM-YYYY the train leaves ticket_from
    depart: datetime  # at board
    arrive: datetime  # at alight
    classes: tuple[str, ...] = ()  # classes the train offers; () = not listed
    board_name: str = ""
    alight_name: str = ""

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.train_no, self.ticket_from, self.ticket_to, self.journey_date)

    @property
    def minutes(self) -> int:
        return int((self.arrive - self.depart).total_seconds() // 60)


KIND_TITLES = {
    "direct": "Direct train",
    "split": "Same train, split into 2 tickets",
    "longer": "Same train, longer ticket",
    "connection": "Connecting trains",
}


@dataclass
class Option:
    kind: str  # direct | split | longer | connection
    legs: list[Leg]
    warnings: list[str] = field(default_factory=list)

    @property
    def group(self) -> str:
        return "with_change" if self.kind == "connection" else "no_change"

    @property
    def key(self) -> tuple:
        return (self.kind, tuple(leg.key for leg in self.legs))


def leg_from_search_row(row: dict, date_str: str) -> Leg | None:
    dep, dur = hhmm(row.get("from_time")), duration_minutes(row.get("travel_time"))
    if dep is None or dur is None:
        return None
    depart = datetime.combine(parse_rail_date(date_str), time()) + timedelta(minutes=dep)
    frm, to = str(row.get("from_stn_code") or "").upper(), str(row.get("to_stn_code") or "").upper()
    if not frm or not to or not row.get("train_no"):
        return None
    return Leg(
        train_no=str(row["train_no"]), train_name=str(row.get("train_name") or ""),
        board=frm, alight=to, ticket_from=frm, ticket_to=to, journey_date=date_str,
        depart=depart, arrive=depart + timedelta(minutes=dur),
        classes=bookable_classes(row.get("classes_of_travel")),
        board_name=str(row.get("from_stn_name") or ""), alight_name=str(row.get("to_stn_name") or ""),
    )


def leg_on_route(route: TrainRoute, start: Date, b: int, a: int, ticket_from: int | None = None,
                 ticket_to: int | None = None) -> Leg | None:
    """Leg boarding at stop index b and alighting at a, for a train that started on `start`."""
    tf = b if ticket_from is None else ticket_from
    tt = a if ticket_to is None else ticket_to
    board, alight, origin = route.stops[b], route.stops[a], route.stops[tf]
    if board.dep is None or alight.arr is None or origin.dep is None:
        return None
    day0 = datetime.combine(start, time())
    return Leg(
        train_no=route.train_no, train_name=route.name,
        board=board.code, alight=alight.code,
        ticket_from=origin.code, ticket_to=route.stops[tt].code,
        journey_date=fmt_rail_date(start + timedelta(days=origin.dep // 1440)),
        depart=day0 + timedelta(minutes=board.dep), arrive=day0 + timedelta(minutes=alight.arr),
        classes=route.classes, board_name=board.name, alight_name=alight.name,
    )


# ---------------------------------------------------------------------------
# Finder
# ---------------------------------------------------------------------------
class StopSearch(Exception):
    """Raised when the search must stop early (cancelled, quota reserve reached)."""


MaybeAwaitable = Awaitable[None] | None
TOP_PER_GROUP = 15
KIND_ORDER = {"direct": 0, "split": 1, "longer": 2, "connection": 3}  # simplest booking first


async def _maybe_await(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


class RouteFinder:
    # RailKit sometimes rejects valid checks with HTTP 400 in bursts, so a rejected
    # check is retried once, after a longer pause when many fail in a row.
    SHORT_RETRY_SECONDS = 2.0
    LONG_RETRY_SECONDS = 30.0
    BURST_REJECTIONS = 10
    MAX_LONG_PAUSES = 10
    # Connection failures (HTTP 504 from the adapter): retry with 20 s, 40 s, 60 s waits.
    OUTAGE_RETRIES = 3
    OUTAGE_RETRY_SECONDS = 20.0

    def __init__(
        self,
        provider: Any,
        from_code: str,
        to_code: str,
        journey_date: str,
        travel_class: str,
        *,
        load_route: Callable[[str], Any] | None = None,
        save_route: Callable[[str, dict], Any] | None = None,
        report: Callable[[dict, dict], MaybeAwaitable] | None = None,
        should_stop: Callable[[], str | None] | None = None,
    ):
        self.provider = provider
        self.from_code, self.to_code = from_code.upper(), to_code.upper()
        self.date = journey_date
        self.selected = travel_class
        self.load_route, self.save_route = load_route, save_route
        self.report_cb, self.should_stop = report, should_stop

        self.requests = 0
        self.checks = 0
        self.phase = "Starting"
        self.notes: list[str] = []
        self.options: dict[tuple, Option] = {}
        self.best: dict[tuple, Availability] = {}  # leg key -> best availability found
        self._avail_cache: dict[tuple, Availability] = {}
        self._search_cache: dict[tuple, list[dict]] = {}
        self._routes: dict[str, TrainRoute | None] = {}
        self._coords: dict[str, tuple[float, float]] = {}
        self._connection_failures = 0
        self.failed_checks = 0
        self._rejections_in_a_row = 0
        self._long_pauses = 0

    # ----- provider access -------------------------------------------------
    async def _provider_call(self, fn: Callable[..., Awaitable[Any]], *args: Any) -> Any:
        reason = self.should_stop() if self.should_stop else None
        if reason:
            raise StopSearch(reason)
        self.requests += 1
        for attempt in range(self.OUTAGE_RETRIES + 1):
            try:
                result = await fn(*args)
                self._connection_failures = 0
                return result
            except RailKitError as exc:
                if exc.status_code != 504 or attempt == self.OUTAGE_RETRIES:
                    if exc.status_code == 504:
                        self._connection_failures += 1
                    raise
            # Connection dropped: wait for it to come back before giving up.
            await asyncio.sleep(self.OUTAGE_RETRY_SECONDS * (attempt + 1))
            reason = self.should_stop() if self.should_stop else None
            if reason:
                raise StopSearch(reason)

    def _is_fatal(self, exc: RailKitError) -> bool:
        """Plan/key problems, persistent rate limits and repeated outages end the search."""
        return exc.status_code in (503, 429) or self._connection_failures >= 5

    async def search(self, frm: str, to: str, date_str: str) -> list[dict]:
        key = (frm, to, date_str)
        if key not in self._search_cache:
            try:
                payload = await self._provider_call(self.provider.search_trains, frm, to, date_str)
                rows = payload.get("data") if isinstance(payload, dict) else None
                self._search_cache[key] = [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
            except RailKitError as exc:
                if self._is_fatal(exc):
                    raise
                self.failed_checks += 1
                self._search_cache[key] = []
        return self._search_cache[key]

    async def route(self, train_no: str) -> TrainRoute | None:
        if train_no in self._routes:
            return self._routes[train_no]
        payload = await _maybe_await(self.load_route(train_no)) if self.load_route else None
        if payload is None:
            try:
                payload = await self._provider_call(self.provider.train_info, train_no)
                if self.save_route and isinstance(payload, dict):
                    await _maybe_await(self.save_route(train_no, payload))
            except RailKitError as exc:
                if self._is_fatal(exc):
                    raise
                payload = None
        route = parse_train_info(payload) if payload else None
        if route and not route.train_no:
            route.train_no = train_no
        if route:
            for stop in route.stops:
                if stop.coords:
                    self._coords.setdefault(stop.code, stop.coords)
        self._routes[train_no] = route
        return route

    async def check(self, leg: Leg, travel_class: str) -> Availability:
        key = (*leg.key, travel_class)
        if key in self._avail_cache:
            return self._avail_cache[key]
        for attempt in (1, 2):
            try:
                payload = await self._provider_call(
                    self.provider.availability, leg.train_no, leg.ticket_from, leg.ticket_to,
                    leg.journey_date, travel_class, "GN",
                )
                result = self._parse_availability(payload, leg.journey_date, travel_class)
                self._rejections_in_a_row = 0
                break
            except RailKitError as exc:
                if self._is_fatal(exc):
                    raise
                self._rejections_in_a_row += 1
                if attempt == 1:
                    await asyncio.sleep(self._retry_pause())
                    continue
                self.failed_checks += 1
                result = Availability(travel_class, UNKNOWN, error=str(exc))
        self.checks += 1
        self._avail_cache[key] = result
        await self._report()
        return result

    def _retry_pause(self) -> float:
        if self._rejections_in_a_row >= self.BURST_REJECTIONS and self._long_pauses < self.MAX_LONG_PAUSES:
            self._long_pauses += 1
            self._rejections_in_a_row = 0
            return self.LONG_RETRY_SECONDS
        return self.SHORT_RETRY_SECONDS

    @staticmethod
    def _parse_availability(payload: Any, date_str: str, travel_class: str) -> Availability:
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            return Availability(travel_class, UNKNOWN, error="RailKit returned no availability data.")
        fare = (data.get("fare") or {}).get("totalFare")
        target = parse_rail_date(date_str)
        for day in data.get("availability") or []:
            try:
                if parse_rail_date(str(day.get("date"))) != target:
                    continue
            except (ValueError, TypeError):
                continue
            level, count = classify(day.get("status"), day.get("availabilityText"))
            return Availability(
                travel_class, level, count, day.get("availabilityText"), day.get("rawStatus"),
                day.get("prediction"), day.get("predictionPercentage"),
                float(fare) if isinstance(fare, (int, float)) else None,
            )
        return Availability(travel_class, UNKNOWN, error="RailKit returned no availability for this date.")

    async def evaluate(self, leg: Leg, classes: list[str]) -> Availability | None:
        """Check `leg` in each allowed class (stopping at the first available seat)."""
        best = self.best.get(leg.key)
        for travel_class in classes:
            if best and best.level == AVAILABLE:
                break
            if leg.classes and travel_class not in leg.classes:
                continue
            if not class_allowed(travel_class, self.selected, leg.minutes):
                continue
            result = await self.check(leg, travel_class)
            if best is None or result.rank < best.rank:
                best = result
        if best:
            self.best[leg.key] = best
        elif classes == [self.selected] and len(class_candidates(self.selected)) > 1:
            # This train doesn't offer the selected class; try the nearby ones.
            return await self.evaluate(leg, class_candidates(self.selected))
        return best

    # ----- options and ranking -------------------------------------------
    def add_option(self, option: Option) -> None:
        self.options.setdefault(option.key, option)

    def score(self, option: Option) -> tuple:
        results = [self.best.get(leg.key) for leg in option.legs]
        worst = max((r.rank if r else (UNKNOWN, 0)) for r in results)
        trains = len({leg.train_no for leg in option.legs})
        total = int((option.legs[-1].arrive - option.legs[0].depart).total_seconds() // 60)
        return (worst, KIND_ORDER[option.kind], len(option.legs), trains, total)

    def snapshot(self) -> dict:
        groups: dict[str, list[dict]] = {"no_change": [], "with_change": []}
        ranked = sorted(
            (o for o in self.options.values() if all(self.best.get(l.key) for l in o.legs)),
            key=self.score,
        )
        for option in ranked:
            bucket = groups[option.group]
            if len(bucket) < TOP_PER_GROUP:
                bucket.append(self._option_dict(option))
        notes = list(self.notes)
        if self.failed_checks:
            notes.append(
                f"{self.failed_checks} checks failed even after a retry. Many are normal (the train doesn't offer "
                "that class or date), but if RailKit was having problems, some routes may be missing."
            )
        return {"groups": groups, "notes": notes}

    def _option_dict(self, option: Option) -> dict:
        legs = []
        for leg in option.legs:
            result = self.best[leg.key]
            legs.append({
                "train_no": leg.train_no, "train_name": leg.train_name,
                "board": leg.board, "board_name": leg.board_name,
                "alight": leg.alight, "alight_name": leg.alight_name,
                "ticket_from": leg.ticket_from, "ticket_to": leg.ticket_to,
                "journey_date": leg.journey_date,
                "depart": leg.depart.isoformat(timespec="minutes"),
                "arrive": leg.arrive.isoformat(timespec="minutes"),
                "minutes": leg.minutes,
                "availability": result.to_dict(),
            })
        transfers = []
        for prev, nxt in zip(option.legs, option.legs[1:]):
            transfers.append({
                "at": prev.alight, "to": nxt.board,
                "wait_minutes": int((nxt.depart - prev.arrive).total_seconds() // 60),
                "same_train": prev.train_no == nxt.train_no,
            })
        worst_level, _ = self.score(option)[0]
        return {
            "kind": option.kind, "title": KIND_TITLES[option.kind], "group": option.group,
            "overall": LEVEL_NAMES[worst_level],
            "total_minutes": int((option.legs[-1].arrive - option.legs[0].depart).total_seconds() // 60),
            "total_fare": sum(l["availability"]["fare"] or 0 for l in legs) if all(l["availability"]["fare"] is not None for l in legs) else None,
            "legs": legs, "transfers": transfers, "warnings": option.warnings,
        }

    def progress(self) -> dict:
        return {"phase": self.phase, "requests": self.requests, "checks": self.checks,
                "options": len(self.options), "failed_checks": self.failed_checks}

    async def _report(self) -> None:
        if self.report_cb:
            await _maybe_await(self.report_cb(self.progress(), self.snapshot()))

    # ----- stations ------------------------------------------------------
    def nearby(self, a: str, b: str) -> bool:
        if a == b:
            return True
        if any(a in g and b in g for g in CITY_GROUPS):
            return True
        ca, cb = self._coords.get(a), self._coords.get(b)
        return bool(ca and cb and _haversine_km(ca, cb) <= NEARBY_KM)

    # ----- search phases --------------------------------------------------
    async def run(self) -> dict:
        selected_only = [self.selected]

        self.phase = "Finding direct trains"
        await self._report()
        rows = await self.search(self.from_code, self.to_code, self.date)
        direct: list[tuple[Leg, TrainRoute | None]] = []
        for row in rows:
            leg = leg_from_search_row(row, self.date)
            if leg:
                direct.append((leg, None))
        if not direct:
            self.notes.append("RailKit returned no direct trains for this date, so splits and connections "
                              "could not be derived.")
            return self.snapshot()

        self.phase = f"Checking {len(direct)} direct trains"
        for leg, _ in direct:
            await self.evaluate(leg, selected_only)
            self.add_option(Option("direct", [leg]))

        self.phase = "Loading train routes"
        await self._report()
        with_routes: list[tuple[Leg, TrainRoute, int, int, Date]] = []
        for leg, _ in direct:
            route = await self.route(leg.train_no)
            if not route:
                continue
            b, a = route.index(leg.board), route.index(leg.alight)
            if b is None or a is None or a <= b or route.stops[b].dep is None:
                continue
            start = parse_rail_date(self.date) - timedelta(days=route.stops[b].dep // 1440)
            with_routes.append((leg, route, b, a, start))

        await self._split_phase(with_routes, selected_only)
        await self._longer_phase(with_routes, selected_only)
        await self._connection_phase(with_routes, selected_only)

        alternates = class_candidates(self.selected)
        if len(alternates) > 1:
            self.phase = "Trying nearby classes (" + ", ".join(alternates[1:]) + ")"
            for option in sorted(self.options.values(), key=self.score):
                for leg in option.legs:
                    await self.evaluate(leg, alternates)

        self.phase = "Done"
        return self.snapshot()

    async def _split_phase(self, trains: list, classes: list[str]) -> None:
        for n, (leg, route, b, a, start) in enumerate(trains, 1):
            direct = self.best.get(leg.key)
            if direct and direct.level == AVAILABLE:
                continue  # one ticket with a seat beats two
            self.phase = f"Split tickets: train {leg.train_no} ({n}/{len(trains)})"
            mid = (route.stops[b].distance + route.stops[a].distance) / 2
            points = sorted(range(b + 1, a), key=lambda k: (-route.stops[k].halt, abs(route.stops[k].distance - mid)))
            for k in points:
                first, second = leg_on_route(route, start, b, k), leg_on_route(route, start, k, a)
                if not first or not second:
                    continue
                r1 = await self.evaluate(first, classes)
                if not r1 or r1.level >= UNAVAILABLE:
                    continue
                r2 = await self.evaluate(second, classes)
                if not r2 or r2.level >= UNAVAILABLE:
                    continue
                self.add_option(Option("split", [first, second], [
                    f"Two tickets on the same train; you may need to change seat/coach at {route.stops[k].code}.",
                ]))
                if r1.level == AVAILABLE and r2.level == AVAILABLE:
                    break  # a fully confirmed split cannot be beaten for this train

    async def _longer_phase(self, trains: list, classes: list[str]) -> None:
        for n, (leg, route, b, a, start) in enumerate(trains, 1):
            direct = self.best.get(leg.key)
            if direct and direct.level == AVAILABLE:
                continue
            self.phase = f"Longer tickets: train {leg.train_no} ({n}/{len(trains)})"
            board_name, alight_name = route.stops[b].code, route.stops[a].code
            for k in range(b - 1, -1, -1):  # ticket from an earlier station, nearest first
                ticket = leg_on_route(route, start, b, a, ticket_from=k)
                if not ticket:
                    continue
                result = await self.evaluate(ticket, classes)
                if result and result.level < UNAVAILABLE:
                    self.add_option(Option("longer", [ticket], [
                        f"Ticket is from {ticket.ticket_from} but you board at {board_name}. Your seat is held only if "
                        "the boarding point is changed per railway rules; confirm before booking.",
                    ]))
                    if result.level == AVAILABLE:
                        break
            for k in range(a + 1, len(route.stops)):  # ticket to a later station, nearest first
                ticket = leg_on_route(route, start, b, a, ticket_to=k)
                if not ticket:
                    continue
                result = await self.evaluate(ticket, classes)
                if result and result.level < UNAVAILABLE:
                    self.add_option(Option("longer", [ticket], [
                        f"Ticket is to {ticket.ticket_to} but you get off at {alight_name}. You pay the longer fare.",
                    ]))
                    if result.level == AVAILABLE:
                        break

    def _hubs(self, trains: list) -> list[str]:
        score: dict[str, float] = {}
        for _, route, b, a, _ in trains:
            origin, dest = route.stops[b].distance, route.stops[a].distance
            for stop in route.stops[b + 1:a]:
                if stop.distance - origin < MIN_HUB_DISTANCE_KM or dest - stop.distance < MIN_HUB_DISTANCE_KM:
                    continue
                score[stop.code] = score.get(stop.code, 0) + 1 + stop.halt / 10
        return sorted(score, key=lambda code: -score[code])

    async def _connection_phase(self, trains: list, classes: list[str]) -> None:
        hubs = self._hubs(trains)
        for n, hub in enumerate(hubs, 1):
            self.phase = f"Connections via {hub} ({n}/{len(hubs)})"
            await self._report()
            first_legs = [l for l in (leg_from_search_row(r, self.date) for r in await self.search(self.from_code, hub, self.date)) if l]
            pairs: list[tuple[Leg, Leg]] = []
            for first in first_legs:
                window_start = first.arrive + timedelta(minutes=MIN_TRANSFER_MINUTES)
                window_end = first.arrive + timedelta(minutes=MAX_TRANSFER_MINUTES)
                for day in sorted({window_start.date(), window_end.date()}):
                    date_str = fmt_rail_date(day)
                    for row in await self.search(hub, self.to_code, date_str):
                        second = leg_from_search_row(row, date_str)
                        if not second or second.train_no == first.train_no:
                            continue
                        if not (window_start <= second.depart <= window_end):
                            continue
                        if not self.nearby(first.alight, second.board):
                            continue
                        pairs.append((first, second))
            pairs.sort(key=lambda p: p[1].arrive - p[0].depart)
            for first, second in pairs:
                r1 = await self.evaluate(first, classes)
                if not r1 or r1.level >= UNAVAILABLE:
                    continue
                r2 = await self.evaluate(second, classes)
                if not r2 or r2.level >= UNAVAILABLE:
                    continue
                warnings = []
                if first.alight != second.board:
                    warnings.append(f"Station change: arrive {first.alight}, depart {second.board}. Allow travel time.")
                self.add_option(Option("connection", [first, second], warnings))
