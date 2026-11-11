# Railway Assistant — Phase 1 starter

A multi-user Next.js + FastAPI application with PostgreSQL, JWT authentication,
and a RailKit provider adapter for train search and seat availability.

## Important RailKit plan note

RailKit's current documentation lists REST endpoints for train search and seat availability.
Its pricing page currently describes the Free tier (50 requests/month) as SDK-only and
the Advance tier (₹89/month) as including API endpoint access. Confirm your account's
exact access before using the REST adapter. Do not assume a free key can call REST.

References:
- https://railkit.in/docs
- https://railkit.in/docs/train-search
- https://railkit.in/docs/seat-availability
- https://railkit.in/pricing

RailKit says it is an independent service using publicly available railway information,
not an official IRCTC API. Treat returned availability as provider data and verify before
making travel decisions: https://railkit.in/contact

## Prerequisites

- Docker Desktop / Docker Engine with Compose
- RailKit API key for live integration
- Node.js 20+ and Python 3.11+ only if running services outside Docker

## Run locally

1. Copy `.env.example` to `.env`.
2. Set `RAILKIT_API_KEY` in `.env` if you have REST API access.
3. Set `JWT_SECRET` to a long random secret.
4. Run:

   ```bash
   docker compose up --build
   ```

5. Open:
   - Frontend: http://localhost:3000
   - Backend docs: http://localhost:8000/docs
   - Health: http://localhost:8000/health

The backend runs `alembic upgrade head` on startup, so the schema is always current.
After changing a model, add a migration in `backend/alembic/versions/`.

Run the backend tests (RailKit is simulated, so they use no API requests):

```bash
docker compose exec backend python -m pytest tests -q
```

Check the frontend (lint, then types):

```bash
docker compose exec frontend npm run lint
docker compose exec frontend npx tsc --noEmit
```

The frontend container has no live reload: after changing frontend code or
dependencies, rebuild it with `docker compose up -d --build --no-deps frontend`.
Dependencies are locked in `frontend/package-lock.json`; update it with `npm install`.

## Phase 1 walkthrough

1. Create an account or log in on the home page.
2. Search between station codes (for example, `JP` and `BCT`) and pick a journey date.
3. Click a class button on a train to see availability under that train.
4. If everything is waitlisted, use **Find best route**.

## Find best route

A background search, run once per click, that looks for better ways to make the journey:

- **Same-train split:** two tickets on one train, split at a stop in between.
- **Longer ticket:** a ticket from an earlier or to a later station on the same train.
- **Connecting trains:** one change, 2-4 hours wait, same station or a nearby one.
- **Nearby classes:** one class up and down (for 3A: 2A, 3E, and SL on legs of 4 hours or less).

Results are in two groups, "No train change" and "With train change", ranked by
available, then RAC, then lowest waitlist. Results appear while the search runs.

There is no per-search request limit, so one search can use a large share of the monthly
allowance. A search stops when usage logged by this app reaches
`RAILKIT_MONTHLY_QUOTA - RAILKIT_MONTHLY_RESERVE`. Requests are paced under RailKit's limit
of 600 per 10 minutes. Searches run inside the backend process, so a restart ends them.

## API endpoints

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/railway/trains/between?from=JP&to=BCT&date=16-11-2026`: returns `TrainSearchResult`
- `GET /api/v1/railway/availability/{train_no}?from=JP&to=BDTS&date=16-11-2026&travel_class=3A&quota=GN`: returns `AvailabilityResult`

- `POST /api/v1/routes/search` (start), `GET /api/v1/routes/search` (recent)
- `GET /api/v1/routes/search/{id}` (progress and results), `POST /api/v1/routes/search/{id}/cancel`

Railway responses use the app's own formats (`backend/app/schemas/railway.py`), not
RailKit's. Each one includes the provider name and when it was fetched. The full schemas
are at http://localhost:8000/docs. All RailKit-specific parsing lives in
`backend/app/providers/railkit_parsing.py`, so switching providers means changing the
adapter, not the API or frontend. A provider response that can't be understood is a
502 error, never an empty result. Missing values are left empty, never filled in.

Train search results can start or end at another station in the same city (for example
NZM for NDLS, BDTS for BCT). Availability must be checked for the train's own stations.
RailKit sometimes returns trains with no class list. The page then offers every class.

All RailKit requests are made server-side. Never expose `RAILKIT_API_KEY` in the frontend.

## Security / production TODO

This is a development starter, not a production-ready deployment:
- Move JWT storage from browser localStorage to secure HttpOnly cookies with CSRF protection.
- Add email verification, password reset, refresh-token rotation and rate limiting.
- Add structured logs and monitoring.
- Restrict CORS to your deployed frontend origin.
- Review RailKit commercial/data redistribution terms before exposing data publicly.
- Add request caching and per-user quotas to control provider usage.
- Confirm provider endpoint access, rate limits, response freshness and segment-specific accuracy.
