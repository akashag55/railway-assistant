"""Application-owned railway data shapes. Provider adapters convert their responses into
these, so RailKit's field names never reach the API or the frontend."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AvailabilityStatus = Literal["available", "rac", "waitlist", "unavailable", "unknown"]


class TrainSummary(BaseModel):
    train_no: str
    train_name: str
    from_code: str = Field(description="Station this train leaves from for the searched journey")
    from_name: str | None = None
    to_code: str
    to_name: str | None = None
    departure: str | None = Field(default=None, description="HH:MM local time at from_code")
    arrival: str | None = Field(default=None, description="HH:MM local time at to_code")
    duration_minutes: int | None = None
    running_days: list[str] = Field(default_factory=list, description="Mon..Sun the train runs; empty if not given")
    classes: list[str] = Field(default_factory=list, description="Bookable classes; empty if the provider listed none")
    distance_km: float | None = None


class TrainSearchResult(BaseModel):
    provider: str
    fetched_at: datetime
    from_code: str
    to_code: str
    date: str | None
    trains: list[TrainSummary]


class Fare(BaseModel):
    base: float | None = None
    reservation: float | None = None
    superfast: float | None = None
    tax: float | None = None
    total: float | None = None


class AvailabilityDay(BaseModel):
    date: str = Field(description="DD-MM-YYYY")
    status: AvailabilityStatus
    count: int | None = Field(default=None, description="Seats, RAC or waitlist number when given")
    text: str | None = Field(default=None, description="Provider text, e.g. 'WL 5'")
    raw_status: str | None = None
    prediction: str | None = Field(default=None, description="Provider estimate, not a confirmation")
    prediction_pct: float | None = None
    can_book: bool | None = None


class AvailabilityResult(BaseModel):
    provider: str
    fetched_at: datetime
    train_no: str
    train_name: str | None = None
    from_code: str
    from_name: str | None = None
    to_code: str
    to_name: str | None = None
    travel_class: str
    quota: str
    fare: Fare | None = None
    days: list[AvailabilityDay]
