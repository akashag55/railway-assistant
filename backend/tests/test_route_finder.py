import asyncio

import pytest

from app.providers.railkit import RailKitError
from app.services.route_finder import (
    AVAILABLE, RAC, UNAVAILABLE, UNKNOWN, WAITLIST, RouteFinder, StopSearch, class_candidates, classify,
)
from tests.fakes import FakeProvider, info, row, stop

DATE, NEXT = "09-11-2026", "10-11-2026"
WL = ("WAITLIST", "WL 30")
OK = ("AVAILABLE", "AVAILABLE-0010")

ROUTE = info("11111", [
    stop("AII", "--", "08:00", 1, 0),
    stop("JP", "10:00", "10:10", 1, 130),
    stop("KOTA", "14:00", "14:10", 1, 370, halt=10),
    stop("SRT", "23:50", "00:10", 1, 900, halt=20),
    stop("BCT", "05:00", "05:10", 2, 1160),
    stop("VR", "06:00", "--", 2, 1210),
])
DIRECT = row("11111", "JP", "BCT", "10:10", "18:50")


def finder(provider, travel_class="3A", **kw):
    return RouteFinder(provider, "JP", "BCT", DATE, travel_class, **kw)


def groups(f):
    return asyncio.run(f.run())["groups"]


@pytest.mark.parametrize("status,text,expected", [
    ("WAITLIST", "WL 5", (WAITLIST, 5)),
    ("AVAILABLE", "AVAILABLE-0045", (AVAILABLE, 45)),
    ("RAC", "RAC 12", (RAC, 12)),
    ("NOT AVAILABLE", "NOT AVAILABLE", (UNAVAILABLE, None)),
    ("REGRET", "REGRET/WL", (UNAVAILABLE, None)),
    ("SOMETHING", "XYZ", (UNKNOWN, None)),
])
def test_classify(status, text, expected):
    assert classify(status, text) == expected


def test_class_candidates():
    assert class_candidates("3A") == ["3A", "2A", "3E", "SL"]
    assert class_candidates("1A") == ["1A", "2A"]
    assert class_candidates("CC") == ["CC", "EC", "2S"]


def test_split_beats_waitlisted_direct_and_uses_correct_dates():
    provider = FakeProvider(
        trains={("JP", "BCT", DATE): [DIRECT]}, routes={"11111": ROUTE},
        seats={
            ("11111", "JP", "BCT", DATE, "3A"): WL,
            ("11111", "JP", "SRT", DATE, "3A"): OK,
            ("11111", "SRT", "BCT", NEXT, "3A"): OK,  # train leaves SRT after midnight
        },
    )
    best = groups(finder(provider))["no_change"][0]
    assert best["kind"] == "split" and best["overall"] == "available"
    assert [leg["journey_date"] for leg in best["legs"]] == [DATE, NEXT]
    assert best["transfers"][0]["same_train"] is True


def test_longer_ticket_from_earlier_and_to_later_station():
    provider = FakeProvider(
        trains={("JP", "BCT", DATE): [DIRECT]}, routes={"11111": ROUTE},
        seats={
            ("11111", "JP", "BCT", DATE, "3A"): WL,
            ("11111", "AII", "BCT", DATE, "3A"): OK,
            ("11111", "JP", "VR", DATE, "3A"): ("RAC", "RAC 3"),
        },
    )
    options = [o for o in groups(finder(provider))["no_change"] if o["kind"] == "longer"]
    tickets = {(o["legs"][0]["ticket_from"], o["legs"][0]["ticket_to"]) for o in options}
    assert tickets == {("AII", "BCT"), ("JP", "VR")}
    assert all((o["legs"][0]["board"], o["legs"][0]["alight"]) == ("JP", "BCT") for o in options)
    assert all(o["warnings"] for o in options)


def test_sleeper_fallback_only_on_legs_of_four_hours_or_less():
    provider = FakeProvider(
        trains={("JP", "BCT", DATE): [DIRECT]}, routes={"11111": ROUTE},
        seats={("11111", "JP", "BCT", DATE, "3A"): WL, ("11111", "JP", "KOTA", DATE, "3A"): WL,
               ("11111", "KOTA", "BCT", DATE, "3A"): WL},
    )
    groups(finder(provider))
    sleeper = {(c[1], c[2]) for c in provider.seat_calls if c[4] == "SL"}
    assert ("JP", "KOTA") in sleeper  # 3h50
    assert ("JP", "BCT") not in sleeper and ("KOTA", "BCT") not in sleeper


def connection_provider(second_departure, second_board="KOTA"):
    first = row("22222", "JP", "KOTA", "10:00", "04:00")  # arrives 14:00
    second = row("33333", second_board, "BCT", second_departure, "12:00")
    return FakeProvider(
        trains={("JP", "BCT", DATE): [DIRECT], ("JP", "KOTA", DATE): [first], ("KOTA", "BCT", DATE): [second]},
        routes={"11111": ROUTE},
        seats={("11111", "JP", "BCT", DATE, "3A"): WL,
               ("22222", "JP", "KOTA", DATE, "3A"): OK,
               ("33333", second_board, "BCT", DATE, "3A"): OK},
    )


@pytest.mark.parametrize("departure,found", [
    ("15:00", False),  # 1 h wait: too short
    ("16:00", True),   # exactly 2 h
    ("18:00", True),   # exactly 4 h
    ("19:00", False),  # 5 h wait: too long
])
def test_connection_wait_window(departure, found):
    result = groups(finder(connection_provider(departure)))["with_change"]
    assert bool(result) is found
    if found:
        assert result[0]["kind"] == "connection"


def test_connection_rejects_a_far_station():
    assert not groups(finder(connection_provider("16:00", second_board="RTM")))["with_change"]


def test_connection_allows_a_station_in_the_same_city():
    first = row("22222", "JP", "BCT", "10:00", "04:00")
    second = row("33333", "BDTS", "VR", "16:00", "01:00")
    provider = FakeProvider(
        trains={("JP", "VR", DATE): [row("11111", "JP", "VR", "10:10", "19:50")],
                ("JP", "BCT", DATE): [first], ("BCT", "VR", DATE): [second]},
        routes={"11111": info("11111", [
            stop("JP", "--", "10:10", 1, 0), stop("BCT", "05:00", "05:10", 2, 300), stop("VR", "06:00", "--", 2, 600),
        ])},
        seats={("11111", "JP", "VR", DATE, "3A"): WL, ("22222", "JP", "BCT", DATE, "3A"): OK,
               ("33333", "BDTS", "VR", DATE, "3A"): OK},
    )
    options = groups(RouteFinder(provider, "JP", "VR", DATE, "3A"))["with_change"]
    assert options and "Station change" in options[0]["warnings"][0]


def test_results_are_grouped_and_nearby_class_can_improve_an_option():
    provider = connection_provider("16:00")
    provider.seats[("11111", "JP", "BCT", DATE, "2A")] = ("RAC", "RAC 2")
    result = groups(finder(provider))
    assert result["no_change"][0]["overall"] == "rac"
    assert result["no_change"][0]["legs"][0]["availability"]["travel_class"] == "2A"
    assert result["with_change"][0]["overall"] == "available"


def test_failed_checks_do_not_become_routes():
    provider = FakeProvider(trains={("JP", "BCT", DATE): [DIRECT]}, routes={"11111": ROUTE},
                            seats={("11111", "JP", "BCT", DATE, "3A"): WL})
    assert [o["kind"] for o in groups(finder(provider))["no_change"]] == ["direct"]


def test_no_direct_trains_gives_a_note():
    assert asyncio.run(finder(FakeProvider()).run())["notes"]


def test_should_stop_keeps_results_found_so_far():
    provider = FakeProvider(trains={("JP", "BCT", DATE): [DIRECT]}, routes={"11111": ROUTE},
                            seats={("11111", "JP", "BCT", DATE, "3A"): WL})
    f = finder(provider, should_stop=lambda: "stop" if provider.seat_calls else None)
    with pytest.raises(StopSearch):
        asyncio.run(f.run())
    assert f.snapshot()["groups"]["no_change"]


def test_plan_error_aborts_search():
    class Refused(FakeProvider):
        async def search_trains(self, *args):
            raise RailKitError("plan", status_code=503)

    with pytest.raises(RailKitError):
        asyncio.run(finder(Refused()).run())


def test_a_temporary_rejection_is_retried_and_the_route_is_kept():
    class Flaky(FakeProvider):
        async def availability(self, train_no, frm, to, date, travel_class, quota):
            first_try = (train_no, frm, to, date, travel_class) not in self.seat_calls
            result = await super().availability(train_no, frm, to, date, travel_class, quota)
            if first_try:
                raise RailKitError("Unable to process", status_code=400)
            return result

    provider = Flaky(trains={("JP", "BCT", DATE): [DIRECT]}, routes={"11111": ROUTE},
                     seats={("11111", "JP", "BCT", DATE, "3A"): OK})
    f = finder(provider)
    assert groups(f)["no_change"][0]["overall"] == "available"
    assert f.failed_checks == 0


def test_failed_checks_are_reported_in_the_notes():
    provider = FakeProvider(trains={("JP", "BCT", DATE): [DIRECT]}, routes={"11111": ROUTE},
                            seats={("11111", "JP", "BCT", DATE, "3A"): WL})
    f = finder(provider)
    result = asyncio.run(f.run())
    assert f.failed_checks > 0 and "routes may be missing" in result["notes"][0]


def test_available_direct_skips_splits_and_outranks_a_longer_ticket_with_more_seats():
    other = row("44444", "JP", "BCT", "11:00", "18:00")
    provider = FakeProvider(
        trains={("JP", "BCT", DATE): [DIRECT, other]},
        routes={"11111": ROUTE, "44444": info("44444", [
            stop("AII", "--", "09:00", 1, 0), stop("JP", "10:50", "11:00", 1, 130), stop("BCT", "05:00", "--", 2, 1160),
        ])},
        seats={("11111", "JP", "BCT", DATE, "3A"): ("AVAILABLE", "AVL 3"),
               ("44444", "JP", "BCT", DATE, "3A"): WL,
               ("44444", "AII", "BCT", DATE, "3A"): ("AVAILABLE", "AVL 90")},
    )
    options = groups(finder(provider))["no_change"]
    assert [o["kind"] for o in options[:2]] == ["direct", "longer"]
    assert not any(c[0] == "11111" and c[2] != "BCT" for c in provider.seat_calls)


def test_a_dropped_connection_is_retried():
    class Dropping(FakeProvider):
        drops = 2

        async def availability(self, *args):
            if self.drops:
                self.drops -= 1
                raise RailKitError("Could not connect to RailKit.", status_code=504)
            return await super().availability(*args)

    provider = Dropping(trains={("JP", "BCT", DATE): [DIRECT]}, routes={"11111": ROUTE},
                        seats={("11111", "JP", "BCT", DATE, "3A"): OK})
    assert groups(finder(provider))["no_change"][0]["overall"] == "available"
