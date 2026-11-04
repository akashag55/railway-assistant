from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class RouteSearchCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_code: str = Field(alias="from", min_length=2, max_length=5, pattern="^[A-Za-z0-9]+$")
    to_code: str = Field(alias="to", min_length=2, max_length=5, pattern="^[A-Za-z0-9]+$")
    date: str = Field(description="First train's departure date, DD-MM-YYYY")
    travel_class: str = Field(default="3A", pattern="^(1A|2A|3A|3E|SL|CC|2S|EC|EA|FC|VS|CH|HS|VC|VA)$")


class RouteSearchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    from_code: str
    to_code: str
    journey_date: str
    travel_class: str
    progress: dict
    results: dict
    error: str | None
    created_at: datetime
    finished_at: datetime | None
