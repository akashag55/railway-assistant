from app.providers.railkit import RailKitError


def stop(code, arrival, departure, day, distance, halt=5):
    return {"stnCode": code, "stnName": code, "arrival": arrival, "departure": departure,
            "day": str(day), "distance": str(distance), "haltMinutes": halt}


def info(train_no, stops, classes=("1A", "2A", "3A", "3E", "SL")):
    return {"success": True, "data": {
        "trainInfo": {"train_no": train_no, "train_name": f"T{train_no}", "prs_classes": list(classes)},
        "route": stops,
    }}


def row(train_no, frm, to, dep, duration, classes=""):
    return {"train_no": train_no, "train_name": f"T{train_no}", "from_stn_code": frm, "to_stn_code": to,
            "from_stn_name": frm, "to_stn_name": to, "from_time": dep, "travel_time": f"{duration} hrs",
            "classes_of_travel": classes}


class FakeProvider:
    """In-memory RailKit. Availability not listed in `seats` answers like RailKit: HTTP 400."""

    def __init__(self, trains=None, routes=None, seats=None):
        self.trains, self.routes, self.seats = trains or {}, routes or {}, seats or {}
        self.seat_calls = []

    async def search_trains(self, frm, to, date):
        return {"success": True, "data": self.trains.get((frm, to, date), [])}

    async def train_info(self, train_no):
        if train_no not in self.routes:
            raise RailKitError("no such train", status_code=400)
        return self.routes[train_no]

    async def availability(self, train_no, frm, to, date, travel_class, quota):
        self.seat_calls.append((train_no, frm, to, date, travel_class))
        key = (train_no, frm, to, date, travel_class)
        if key not in self.seats:
            raise RailKitError("Unable to process", status_code=400)
        status, text = self.seats[key]
        return {"success": True, "data": {"fare": {"totalFare": 100}, "availability": [
            {"date": date, "status": status, "availabilityText": text, "rawStatus": text},
        ]}}
