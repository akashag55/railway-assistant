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

The backend creates database tables automatically for this starter. Use Alembic migrations
before treating this as production software.

## Phase 1 walkthrough

1. Register at `/register`.
2. Log in at `/login`.
3. Search between station codes (for example, `NDLS` and `BCT`) and select a journey date.
4. Select a train from results to check availability by segment, class and quota.

## API endpoints

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/railway/trains/between?from=NDLS&to=BCT&date=02-11-2026`
- `GET /api/v1/railway/availability/{train_no}?from=NDLS&to=BCT&date=02-11-2026&travel_class=3A&quota=GN`

All RailKit requests are made server-side. Never expose `RAILKIT_API_KEY` in the frontend.

## Security / production TODO

This is a development starter, not a production-ready deployment:
- Move JWT storage from browser localStorage to secure HttpOnly cookies with CSRF protection.
- Add email verification, password reset, refresh-token rotation and rate limiting.
- Add Alembic migrations, structured logs, monitoring and automated tests.
- Restrict CORS to your deployed frontend origin.
- Review RailKit commercial/data redistribution terms before exposing data publicly.
- Add request caching and per-user quotas to control provider usage.
- Confirm provider endpoint access, rate limits, response freshness and segment-specific accuracy.
