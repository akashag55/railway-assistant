from datetime import datetime, timedelta

import pytest

from app.api.v1 import railway
from app.providers.railkit import RailKitError
from app.providers.railkit_parsing import availability_result, train_search_result

# Shapes copied from real RailKit responses.
SEARCH = {"success": True, "data": [{
    "train_no": "12904", "train_name": "GOLDEN TEMPLE M", "source_stn_code": "ASR",
    "from_stn_name": "Hazrat Nizamuddin", "from_stn_code": "NZM",
    "to_stn_name": "Bandra Terminus", "to_stn_code": "BDTS",
    "from_time": "04:00", "to_time": "23:55", "travel_time": "19:55 hrs",
    "running_days": "1010100", "distance": "1365", "classes_of_travel": "1A,2A,3A,SL,GEN,PWD",
}]}
AVAILABILITY = {"success": True, "data": {
    "train": {"trainNo": "14701", "trainName": "ARAVALI EXPRESS", "from": "JP", "to": "BDTS",
              "fromStationName": "Jaipur Junction", "toStationName": "Mumbai Bandra Terminus",
              "travelClass": "3A", "quota": "GN"},
    "fare": {"baseFare": 1326, "reservationCharge": 40, "superfastCharge": 0, "serviceTax": 69, "totalFare": 1435},
    "availability": [
        {"date": "9-11-2026", "status": "WAITLIST", "availabilityText": "WL 5", "rawStatus": "RLWL16/WL5",
         "prediction": "81% Chance", "predictionPercentage": 81, "canBook": True},
        {"date": "10-11-2026", "status": "AVAILABLE", "availabilityText": "AVL 38", "canBook": True},
        {"date": "11-11-2026", "status": "SOMETHING_NEW", "availabilityText": "XYZ"},
    ],
}}


def test_train_search_uses_app_field_names():
    result = train_search_result(SEARCH, "NDLS", "BCT", "09-11-2026")
    train = result.trains[0]
    assert result.provider == "railkit" and result.fetched_at
    assert (train.train_no, train.from_code, train.to_code) == ("12904", "NZM", "BDTS")
    assert (train.departure, train.arrival, train.duration_minutes) == ("04:00", "23:55", 1195)
    assert train.running_days == ["Mon", "Wed", "Fri"]
    assert train.classes == ["1A", "2A", "3A", "SL"]  # GEN and PWD are not bookable
    assert "from_stn_code" not in result.model_dump_json()


def test_unusable_rows_are_skipped_but_never_invented():
    result = train_search_result({"data": [SEARCH["data"][0], {"train_name": "no number"}]}, "NDLS", "BCT", None)
    assert [t.train_no for t in result.trains] == ["12904"]


@pytest.mark.parametrize("payload", [{"data": {"oops": 1}}, {"nothing": []}, "html", {"data": [{"x": 1}]}])
def test_malformed_search_is_an_error_not_an_empty_list(payload):
    with pytest.raises(RailKitError):
        train_search_result(payload, "JP", "BCT", None)


def test_empty_search_is_a_real_empty_result():
    assert train_search_result({"success": True, "data": []}, "JP", "BCT", None).trains == []


def test_availability_statuses_dates_and_fare():
    result = availability_result(AVAILABILITY, "14701", "JP", "BDTS", "3A", "GN")
    assert (result.train_no, result.from_name, result.travel_class) == ("14701", "Jaipur Junction", "3A")
    assert result.fare.total == 1435 and result.fare.base == 1326
    assert [(d.date, d.status, d.count) for d in result.days] == [
        ("09-11-2026", "waitlist", 5), ("10-11-2026", "available", 38), ("11-11-2026", "unknown", None),
    ]
    assert result.days[0].prediction == "81% Chance" and result.days[0].raw_status == "RLWL16/WL5"


def test_malformed_availability_is_an_error():
    with pytest.raises(RailKitError):
        availability_result({"data": {"train": {}}}, "14701", "JP", "BDTS", "3A", "GN")


class FakeRailKit:
    payload = None

    def __init__(self, **_):
        pass

    async def search_trains(self, *_):
        return self.payload

    async def availability(self, *_):
        return self.payload


def test_endpoints_return_the_app_format(client, auth, monkeypatch):
    monkeypatch.setattr(railway, "RailKitProvider", FakeRailKit)
    h = auth()
    FakeRailKit.payload = SEARCH
    body = client.get("/api/v1/railway/trains/between?from=ndls&to=bct", headers=h).json()
    assert body["trains"][0]["from_code"] == "NZM" and body["from_code"] == "NDLS"

    FakeRailKit.payload = AVAILABILITY
    date = (datetime.now() + timedelta(days=3)).strftime("%d-%m-%Y")
    body = client.get(f"/api/v1/railway/availability/14701?from=JP&to=BDTS&date={date}", headers=h).json()
    assert body["days"][0]["status"] == "waitlist" and body["fare"]["total"] == 1435


def test_malformed_provider_response_is_a_502(client, auth, monkeypatch):
    monkeypatch.setattr(railway, "RailKitProvider", FakeRailKit)
    FakeRailKit.payload = {"data": "nonsense"}
    assert client.get("/api/v1/railway/trains/between?from=JP&to=BCT", headers=auth()).status_code == 502
