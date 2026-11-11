from datetime import datetime, timedelta, timezone
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from app.api.deps import get_current_user
from app.models.user import User
from app.providers.railkit import RailKitProvider, RailKitError
from app.providers.railkit_parsing import availability_result, train_search_result
from app.schemas.railway import AvailabilityResult, TrainSearchResult
from app.services.route_jobs import log_provider_request

router = APIRouter(prefix="/railway", tags=["Railway"])


IST = timezone(timedelta(hours=5, minutes=30))  # Indian Railways dates are IST; no DST.


def validate_date(value: str) -> str:
    try:
        journey = datetime.strptime(value, "%d-%m-%Y").date()
    except ValueError:
        raise HTTPException(status_code=422, detail="Date must be DD-MM-YYYY")
    if journey < datetime.now(IST).date():
        raise HTTPException(status_code=422, detail="Journey date is in the past. Choose today or a later date.")
    return value


def provider_error(exc: RailKitError):
    # Never forward 401 here: the frontend treats 401 as "your login expired".
    raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("/trains/between", response_model=TrainSearchResult)
async def search_trains(
    from_code: str = Query(alias="from", min_length=2, max_length=5, pattern="^[A-Za-z0-9]+$"),
    to_code: str = Query(alias="to", min_length=2, max_length=5, pattern="^[A-Za-z0-9]+$"),
    date: str | None = Query(default=None, description="Journey date in DD-MM-YYYY; trains that run that day"),
    user: User = Depends(get_current_user),
):
    """Trains between two stations. Results can start or end at nearby stations of the same city."""
    if date:
        validate_date(date)
    frm, to = from_code.upper(), to_code.upper()
    try:
        payload = await RailKitProvider(on_request=log_provider_request).search_trains(frm, to, date)
        return train_search_result(payload, frm, to, date)
    except RailKitError as exc:
        provider_error(exc)


@router.get("/availability/{train_no}", response_model=AvailabilityResult)
async def check_availability(
    train_no: str,
    from_code: str = Query(alias="from", min_length=2, max_length=5, pattern="^[A-Za-z0-9]+$"),
    to_code: str = Query(alias="to", min_length=2, max_length=5, pattern="^[A-Za-z0-9]+$"),
    date: str = Query(description="Journey date in DD-MM-YYYY"),
    travel_class: str = Query(default="3A", pattern="^(1A|2A|3A|3E|SL|CC|2S|EC|EA|FC|VS|CH|HS|VC|VA)$"),
    quota: str = Query(default="GN", pattern="^(GN|TQ|LD|DF|FT|LB|PT|YU|DP|HP|PH|SS)$"),
    user: User = Depends(get_current_user),
):
    """Seat availability for one train segment, class and quota: the requested date plus the next few run dates."""
    if not re.fullmatch(r"\d{5}", train_no):
        raise HTTPException(status_code=422, detail="Train number must contain five digits")
    validate_date(date)
    frm, to = from_code.upper(), to_code.upper()
    try:
        payload = await RailKitProvider(on_request=log_provider_request).availability(
            train_no, frm, to, date, travel_class, quota
        )
        return availability_result(payload, train_no, frm, to, travel_class, quota)
    except RailKitError as exc:
        provider_error(exc)
