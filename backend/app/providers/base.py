from typing import Protocol, Any


class RailwayProvider(Protocol):
    async def search_trains(self, from_code: str, to_code: str, date: str | None) -> Any: ...
    async def availability(
        self, train_no: str, from_code: str, to_code: str,
        date: str, travel_class: str, quota: str
    ) -> Any: ...
