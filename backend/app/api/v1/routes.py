from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.v1.railway import validate_date
from app.database.session import get_db
from app.models.route_search import RouteSearch
from app.models.user import User
from app.schemas.routes import RouteSearchCreate, RouteSearchOut
from app.services import route_jobs

router = APIRouter(prefix="/routes", tags=["Route finder"])


def _owned_search(search_id: int, user: User, db: Session) -> RouteSearch:
    search = db.get(RouteSearch, search_id)
    if search is None or search.user_id != user.id:  # same 404 either way: don't reveal other users' ids
        raise HTTPException(status_code=404, detail="Route search not found")
    return search


@router.post("/search", response_model=RouteSearchOut, status_code=202)
async def start_search(
    payload: RouteSearchCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    validate_date(payload.date)
    if route_jobs.active_search(db, user.id):
        raise HTTPException(status_code=409, detail="You already have a route search running. Wait for it or cancel it.")
    search = RouteSearch(
        user_id=user.id, status="queued", from_code=payload.from_code.upper(), to_code=payload.to_code.upper(),
        journey_date=payload.date, travel_class=payload.travel_class,
        progress={"phase": "Queued", "requests": 0, "checks": 0, "options": 0}, results={},
    )
    db.add(search)
    db.commit()
    db.refresh(search)
    route_jobs.start(search.id)
    return search


@router.get("/search", response_model=list[RouteSearchOut])
def list_searches(
    limit: int = Query(default=5, ge=1, le=20),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(RouteSearch).where(RouteSearch.user_id == user.id).order_by(RouteSearch.id.desc()).limit(limit)
    ).all()


@router.get("/search/{search_id}", response_model=RouteSearchOut)
def get_search(search_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _owned_search(search_id, user, db)


@router.post("/search/{search_id}/cancel", response_model=RouteSearchOut)
def cancel_search(search_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    search = _owned_search(search_id, user, db)
    if search.status in route_jobs.ACTIVE_STATUSES:
        route_jobs.request_cancel(search.id)
    return search
