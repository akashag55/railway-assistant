from datetime import datetime, timedelta, timezone
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from app.api.deps import get_current_user
from app.models.user import User
from app.providers.railkit import RailKitProvider, RailKitError

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


@router.get("/trains/between")
async def search_trains(
    from_code: str = Query(alias="from", min_length=2, max_length=5, pattern="^[A-Za-z0-9]+$"),
    to_code: str = Query(alias="to", min_length=2, max_length=5, pattern="^[A-Za-z0-9]+$"),
    date: str | None = None,
    user: User = Depends(get_current_user),
):
    if date:
        validate_date(date)
    try:
        return await RailKitProvider().search_trains(from_code.upper(), to_code.upper(), date)
    except RailKitError as exc:
        provider_error(exc)


@router.get("/availability/{train_no}")
async def check_availability(
    train_no: str,
    from_code: str = Query(alias="from", min_length=2, max_length=5),
    to_code: str = Query(alias="to", min_length=2, max_length=5),
    date: str = Query(description="Journey date in DD-MM-YYYY"),
    travel_class: str = Query(default="3A", pattern="^(1A|2A|3A|3E|SL|CC|2S|EC|EA|FC)$"),
    quota: str = Query(default="GN", pattern="^(GN|TQ|LD|DF|FT|LB|PT|YU|DP|HP|PH|SS)$"),
    user: User = Depends(get_current_user),
):
    if not re.fullmatch(r"\d{5}", train_no):
        raise HTTPException(status_code=422, detail="Train number must contain five digits")
    validate_date(date)
    try:
        return await RailKitProvider().availability(
            train_no, from_code.upper(), to_code.upper(), date, travel_class, quota
        )
    except RailKitError as exc:
        provider_error(exc)
