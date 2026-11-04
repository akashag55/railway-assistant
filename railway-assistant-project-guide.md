# Railway Assistant --- Project Overview & AI Development Guide

> **Purpose:** This document is the living project brief for the Railway
> Assistant. It explains what the application is, how it is intended to
> work, its architecture, current implementation boundaries, and how
> another AI coding agent should safely add future features.
>
> **Project stage:** Personal-use MVP, designed with a path to
> multi-user and commercial use later.
>
> **Important:** Treat the actual repository code, configuration, tests,
> and current provider documentation as the source of truth. This
> document describes the intended direction and the initial Phase 1
> starter; update it when implementation decisions change.

------------------------------------------------------------------------

## 1. Project summary

Railway Assistant is a web-based application that helps users research
Indian railway journeys. It aims to make it easier to search trains
across multiple origin/destination stations and dates, compare direct
and connecting routes, inspect class-wise ticket availability, save
journeys, and monitor availability changes.

The initial use case is personal travel planning. The application is
being built with a multi-user architecture so that authentication,
user-owned searches, saved journeys, and monitoring can be extended
without redesigning the entire system.

The application is **not an IRCTC booking client**. Its initial scope is
railway information and journey research. It must not book tickets, make
payments, or claim that a ticket is confirmed unless the data provider
explicitly returns a current confirmed status for the exact journey
segment and quota. Users should verify details through official railway
channels before booking.

### Primary goals

1.  Search trains between two stations for a selected journey date.
2.  Retrieve train route and schedule details.
3.  Check seat availability for a specific train, source, destination,
    date, class, and quota.
4.  Search across multiple nearby stations and date ranges.
5.  Discover and compare direct and connecting journey options.
6.  Save searches and journeys against the signed-in user.
7.  Monitor selected train/date/class/segment combinations and notify
    users when availability changes.
8.  Add AI-assisted natural-language search and route reasoning later,
    without making the core data retrieval dependent on an LLM.

### Non-goals for the initial MVP

-   Ticket booking, cancellation, payment, or PNR modification.
-   Guaranteeing waitlist confirmation.
-   Scraping private IRCTC endpoints or bypassing captchas/access
    controls.
-   Building a complex multi-agent system before railway data retrieval
    is reliable.
-   Public commercial redistribution of provider data before the
    provider's terms and permissions are checked.

------------------------------------------------------------------------

## 2. Users and core workflows

### User types

-   **Registered user:** Can search railway data, save journeys, and
    manage their own monitoring rules.
-   **Future administrator:** May manage users, provider configuration,
    system health, quotas, and monitoring jobs. Admin functionality is
    not required in the first MVP.

All user-specific records must be scoped to the authenticated user. One
user must never be able to view or modify another user's saved searches,
journeys, or monitoring rules.

### Main workflows

#### A. Search trains

1.  User enters source station code, destination station code, journey
    date, and optional filters.
2.  Backend validates the input.
3.  Backend calls the configured railway data provider.
4.  Provider response is normalized into an internal response model.
5.  Frontend displays trains, timings, duration, and relevant route
    information.
6.  The application records useful search metadata without storing
    unnecessary sensitive data.

#### B. Check seat availability

1.  User selects a train from search results.
2.  User selects source and destination stations, journey date, travel
    class, and quota.
3.  Backend requests availability for that exact segment and journey
    date.
4.  The result is displayed with provider timestamp/freshness
    information when available.
5.  The UI distinguishes confirmed, RAC, waitlist, unavailable, and
    unknown/error states. Do not infer one state from another.

#### C. Search alternatives

1.  User provides a destination, date range, origin station group, and
    class preferences.
2.  The application finds candidate trains and station alternatives.
3.  It evaluates direct routes first.
4.  If requested, it searches connecting journeys, checking transfer
    station, transfer time, station changes, and overall journey
    duration.
5.  It ranks results using transparent criteria such as availability,
    total duration, number of transfers, departure time, and data
    freshness.

#### D. Monitor availability

1.  User saves a specific train, date, source/destination segment,
    class, and quota.
2.  A scheduler checks only active monitoring records, subject to
    provider quotas and permitted request frequency.
3.  The application stores timestamped observations.
4.  It notifies the user only when a meaningful change occurs.
5.  Monitoring can be paused, edited, or deleted by the owning user.

------------------------------------------------------------------------

## 3. Technology stack and architecture

The intended stack is:

  -----------------------------------------------------------------------
  Layer                   Technology              Responsibility
  ----------------------- ----------------------- -----------------------
  Frontend                Next.js App Router +    Web application and
                          TypeScript              user interaction

  UI                      Tailwind CSS; shadcn/ui Minimal, accessible
                          where installed         interface

  Backend                 Python + FastAPI        API, validation,
                                                  business logic

  Database                PostgreSQL              Users, searches, saved
                                                  journeys, monitoring
                                                  and observations

  ORM                     SQLAlchemy 2.x          Database access and
                                                  models

  Migrations              Alembic                 Versioned database
                                                  schema changes

  Authentication          JWT-based               User identity and
                          authentication          protected endpoints
                          initially               

  Password hashing        Argon2 via a maintained Password storage
                          password-hashing        
                          library                 

  Railway provider        RailKit adapter         Train search and
                          initially               availability data

  Background jobs         APScheduler initially   Scheduled availability
                                                  checks

  Future AI               LangGraph               Multi-step planning and
                                                  tool orchestration

  Local development       Docker Compose          Reproducible local
                                                  services

  Deployment              Vercel for frontend;    Hosting
                          Render/AWS or           
                          equivalent for backend  
                          and database            
  -----------------------------------------------------------------------

### High-level request flow

``` text
Browser
  |
  v
Next.js frontend
  |
  | HTTPS / JSON API
  v
FastAPI backend
  |
  +--> Authentication and authorization
  |
  +--> Railway service layer
  |       |
  |       v
  |    Provider adapter interface
  |       |
  |       v
  |    RailKit (initial provider)
  |
  +--> PostgreSQL
  |
  +--> Scheduler (future monitoring phase)
  |
  +--> LangGraph (future AI phase)
```

### Architectural principles

-   The frontend must never call RailKit directly.
-   Provider credentials must remain on the backend.
-   The application must not expose provider API keys in `NEXT_PUBLIC_*`
    variables or browser bundles.
-   Provider-specific response formats must not leak throughout the
    application.
-   Business logic should live in backend services, not in route
    handlers or React components.
-   All user-owned data must be authorized server-side.
-   External provider failures must be handled gracefully.
-   LLMs may plan and explain searches, but deterministic backend
    functions must validate inputs and perform data retrieval.
-   Cache stable data such as station metadata and train schedules where
    permitted. Do not cache live availability beyond a deliberate,
    clearly disclosed freshness window.
-   Avoid unnecessary API calls. Respect provider rate limits and terms.

------------------------------------------------------------------------

## 4. Repository layout

The initial starter is intended to follow this structure. The actual
repository may evolve; inspect it before making changes.

``` text
railway-assistant/
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── (auth)/
│   │   │   │   ├── login/
│   │   │   │   └── register/
│   │   │   ├── (dashboard)/
│   │   │   │   ├── dashboard/
│   │   │   │   ├── search/
│   │   │   │   ├── routes/
│   │   │   │   └── monitoring/
│   │   │   ├── layout.tsx
│   │   │   └── page.tsx
│   │   ├── components/
│   │   ├── lib/
│   │   ├── services/
│   │   └── types/
│   ├── public/
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   ├── core/
│   │   ├── database/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── providers/
│   │   ├── services/
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   └── requirements.txt
│
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

### Backend module responsibilities

-   `api/v1/`: HTTP route definitions, request/response wiring,
    dependency injection.
-   `core/`: settings, security utilities, logging and shared
    configuration.
-   `database/`: engine, session and database dependencies.
-   `models/`: SQLAlchemy persistence models.
-   `schemas/`: Pydantic request and response schemas.
-   `providers/`: external railway provider adapters and provider
    contracts.
-   `services/`: application use cases, orchestration and domain logic.
-   `tests/`: unit, integration and API tests.

### Frontend module responsibilities

-   `app/`: route segments and page-level composition.
-   `components/`: reusable UI components.
-   `lib/`: shared utilities and API client.
-   `services/`: frontend service functions for backend endpoints.
-   `types/`: shared TypeScript types and API response types.

------------------------------------------------------------------------

## 5. Railway data provider integration

### Initial provider: RailKit

RailKit is the first provider being evaluated for train search and seat
availability. It is an independent railway information provider, not an
official IRCTC API. Treat its output as third-party data and verify
critical information through official railway channels.

The starter includes a provider adapter so that the rest of the backend
can call a stable internal interface.

Intended provider operations:

``` python
class RailwayProvider:
    async def search_trains(self, from_code, to_code, date):
        ...

    async def get_train_route(self, train_number):
        ...

    async def get_availability(
        self,
        train_number,
        from_code,
        to_code,
        journey_date,
        travel_class,
        quota,
    ):
        ...

    async def get_fare(
        self,
        train_number,
        from_code,
        to_code,
        journey_date,
        travel_class,
        quota,
    ):
        ...
```

Only implement operations that are confirmed in the provider's current
documentation and enabled for the configured subscription.

### Plan and access caveat

The earlier provider review found that RailKit's published pricing
distinguishes SDK access from REST API access. The starter's FastAPI
adapter uses REST. Before assuming it will work, confirm the current
plan, endpoint access, authentication header, base URL, request
parameters, quotas, and response format with the provider.

Do not invent endpoints or assume that an SDK function and REST endpoint
have identical access rights.

### Provider adapter rules

1.  Read the current official provider documentation before changing
    request paths or payloads.
2.  Keep all provider-specific code in the provider adapter.
3.  Normalize provider responses into application-owned Pydantic
    schemas.
4.  Preserve raw provider response data only when necessary for
    debugging, with secrets and personal data removed.
5.  Capture provider name, retrieval timestamp, and freshness metadata
    where available.
6.  Handle authentication failures, rate limits, timeouts, unavailable
    upstream services, and malformed responses.
7.  Never silently convert a provider error into "no trains" or "no
    seats."
8.  Do not claim a result is live unless the provider documents its
    freshness and the response supports that claim.
9.  Respect provider usage limits and redistribution terms.

### Internal response concepts

The application should eventually normalize data into concepts such as:

-   `TrainSummary`: train number, train name, source, destination,
    departure, arrival, duration, running days.
-   `TrainStop`: station code, station name, arrival, departure, halt
    duration, sequence.
-   `AvailabilityResult`: train, segment, journey date, class, quota,
    status, available count if supplied, waitlist/RAC value if supplied,
    fare if supplied, provider and fetched-at timestamp.
-   `ProviderError`: provider, error category, retryability, safe
    user-facing message.

Use optional fields when a provider does not return a value. Do not
fabricate missing data.

------------------------------------------------------------------------

## 6. Authentication and security requirements

The application is intended to support multiple users.

### Required behavior

-   Registration with email and password.
-   Login and logout.
-   Protected backend endpoints.
-   Passwords stored only as secure password hashes.
-   User-owned data scoped to the authenticated user.
-   No user can access another user's saved journeys or monitoring
    rules.
-   Validate and constrain all incoming data.
-   Rate-limit authentication and expensive provider-backed endpoints.
-   Keep secrets in environment variables or a managed secret store.

### Starter security caveat

The initial starter may use a bearer access token stored in browser
local storage for development simplicity. This is not the preferred
production design. Before public deployment, migrate to secure HttpOnly
cookies with appropriate `Secure`, `SameSite`, and CSRF protections, and
implement refresh-token rotation, logout/revocation, email verification,
password reset, and rate limiting.

Do not claim authentication is production-ready until these controls are
implemented and tested.

------------------------------------------------------------------------

## 7. Data model direction

The initial starter may contain only a user table. Future features
should add models incrementally.

Suggested entities:

  -----------------------------------------------------------------------
  Entity                              Purpose
  ----------------------------------- -----------------------------------
  `User`                              Account identity and authentication

  `SavedSearch`                       User's reusable search criteria

  `Journey`                           A saved direct or multi-leg journey

  `JourneyLeg`                        One train segment within a journey

  `MonitoringRule`                    Train/date/segment/class/quota to
                                      monitor

  `AvailabilityObservation`           Timestamped result from each check

  `Station`                           Cached station metadata

  `Train`                             Cached train metadata, if useful

  `ProviderRequestLog`                Usage, latency and error accounting
                                      without secrets
  -----------------------------------------------------------------------

Every user-owned table should have a user ownership relationship and
appropriate indexes. Use database constraints to prevent duplicate or
invalid records where appropriate.

------------------------------------------------------------------------

## 8. Planned product roadmap

### Implementation status (November 2026)

-   RailKit is on the Advance plan (REST access). Limits seen: 600 requests per
    10 minutes; 10,000 per month.
-   Phase 1 is complete, with backend tests and Alembic migrations.
-   Part of Phase 3 is built early as **Find best route**: same-train splits,
    longer tickets and one-change connections, as a deterministic background
    job in `backend/app/services/route_finder.py` and `route_jobs.py`.
-   Two-change routes, the quota picker and the rest of Phase 2 are not built.

### Phase 1 --- Foundation and first provider integration

-   Monorepo and local Docker environment.
-   Next.js frontend.
-   FastAPI backend.
-   PostgreSQL connection.
-   User registration and login.
-   RailKit provider adapter.
-   Train search between two stations.
-   Seat availability for a selected train, segment, date, class and
    quota.
-   Basic error handling and API documentation.

**Phase 1 acceptance criteria:**

-   A user can register and log in.
-   Protected endpoints reject unauthenticated requests.
-   A user can submit a train search from the web interface.
-   Backend makes the provider request without exposing credentials to
    the browser.
-   Provider responses and provider errors are handled correctly.
-   A user can request availability for an exact train segment.
-   Tests cover authentication, validation, provider success and
    provider failure.

### Phase 2 --- Multi-station and multi-date search

-   Station search/autocomplete.
-   Nearby or user-selected alternative stations.
-   Date-range search.
-   Multiple class and quota options.
-   Search result filtering, sorting and deduplication.
-   Request budgeting, caching and concurrency controls.

### Phase 3 --- Route discovery

-   Direct route search.
-   Connecting train discovery.
-   Transfer station and transfer-time validation.
-   Avoid impossible or impractical connections.
-   Compare total duration, waiting time, number of changes and
    availability.
-   Show the source and freshness of each leg's data.

### Phase 4 --- Saved journeys and availability monitoring

-   Save searches and journeys.
-   Configure monitoring rules.
-   Background scheduler.
-   Availability history.
-   Change detection and notifications.
-   Per-user monitoring limits and provider quota management.

### Phase 5 --- AI assistant

Introduce LangGraph only after deterministic search and route services
are stable.

Potential agent tools:

-   `search_trains`
-   `get_train_route`
-   `check_availability`
-   `search_alternative_stations`
-   `find_connecting_routes`
-   `compare_journeys`
-   `save_journey`
-   `create_monitoring_rule`

The agent should call backend services through controlled interfaces. It
must not bypass authentication, permissions, provider limits, or
validation.

### Phase 6 --- Deployment and product hardening

-   Production frontend and backend deployments.
-   Managed PostgreSQL.
-   Secure secret management.
-   Migrations and backups.
-   Monitoring, structured logs and alerts.
-   Authentication hardening.
-   API usage controls.
-   Provider terms and commercial redistribution review.
-   Privacy policy and terms if opened to external users.

------------------------------------------------------------------------

## 9. UI and UX direction

The chosen UI direction is **minimal and functional**.

Design principles:

-   Clear typography and restrained color palette.
-   Prioritize search and results over decorative dashboard widgets.
-   Responsive layouts for laptop, tablet and mobile.
-   Accessible labels, keyboard navigation and visible focus states.
-   Clear loading, empty, error and stale-data states.
-   Show source and last-updated time for availability results when
    provided.
-   Distinguish confirmed, RAC, waitlist, unavailable and unknown
    states.
-   Avoid displaying fabricated sample availability as real data.
-   Keep search filters understandable and avoid overloading the initial
    search form.

Core navigation:

-   Dashboard
-   Train Search
-   Route Explorer
-   Availability Monitoring
-   Saved Journeys
-   Account / Settings

------------------------------------------------------------------------

## 10. Local development and deployment

### Local development

Docker Compose should run:

-   PostgreSQL.
-   FastAPI backend.
-   Next.js frontend.

Use `.env.example` to document required variables. Never commit `.env`
or credentials.

### Deployment direction

-   Frontend: Vercel or another Next.js-compatible host.
-   Backend: Render, AWS, or another host that supports persistent
    FastAPI services.
-   Database: managed PostgreSQL.
-   Scheduler: initially within the backend for local development; move
    to a dedicated worker or scheduler service if deployment requires
    multiple backend instances.

Do not run multiple independent schedulers against the same monitoring
jobs without a coordination/locking strategy. Avoid relying on an
ephemeral filesystem for persistent database or monitoring data.

------------------------------------------------------------------------

## 11. Definition of done for any feature

A feature is not complete merely because the UI looks correct.

A feature is complete when:

1.  Requirements and edge cases are understood.
2.  Existing architecture and conventions are inspected.
3.  Backend validation and authorization are implemented.
4.  Database changes have migrations where applicable.
5.  Frontend loading, success, empty and error states are implemented.
6.  Tests cover expected behavior and important failure paths.
7.  API documentation and types are updated.
8.  No secrets or private data are exposed.
9.  Existing features continue to work.
10. Documentation is updated.

------------------------------------------------------------------------

# 12. Reusable prompt for future AI coding agents

Copy the prompt below into another AI coding agent whenever you want to
add, modify, or debug a feature in this repository. Replace the feature
brief section with your specific request.

## MASTER PROJECT CONTEXT PROMPT

``` text
You are acting as a senior full-stack software architect and engineer
working on an existing project called "Railway Assistant".

Your responsibility is to understand the current codebase, implement
the requested feature safely, preserve existing functionality, and
leave the project in a maintainable state.

PROJECT CONTEXT
----------------

Railway Assistant is a web-based Indian railway journey research
application.

Its goals include:
- Searching trains between stations.
- Fetching train routes and schedules.
- Checking seat availability for a specific train, segment, date,
  travel class and quota.
- Searching multiple stations and date ranges.
- Discovering direct and connecting routes.
- Comparing journey options.
- Saving user-specific journeys and searches.
- Monitoring selected trains and notifying users about availability
  changes.
- Introducing AI-assisted journey planning with LangGraph in a later
  phase.

This application is initially for personal use but is designed to
support multiple users and possible commercial expansion.

It is NOT an IRCTC ticket-booking application. Do not implement
booking, payment or cancellation unless explicitly requested and
the required official authorization/integration exists.

TECHNOLOGY STACK
----------------

Frontend:
- Next.js App Router
- React
- TypeScript
- Tailwind CSS
- Minimal, responsive UI

Backend:
- Python
- FastAPI
- Pydantic
- SQLAlchemy 2.x

Database:
- PostgreSQL
- Alembic migrations

Authentication:
- JWT-based authentication in the initial implementation
- Argon2 password hashing
- Secure production cookie-based authentication is a hardening goal

Railway data:
- RailKit is the initial provider being evaluated.
- Provider-specific code must remain isolated in backend/providers.
- Never expose railway API keys in frontend code.

Infrastructure:
- Docker Compose for local development
- Vercel-compatible frontend deployment
- Render/AWS-compatible backend deployment

Future AI:
- LangGraph, introduced only when deterministic railway services are
  sufficiently stable.

ARCHITECTURAL RULES
-------------------

1. FIRST INSPECT THE REPOSITORY.

Before changing anything:
- Inspect the existing folder structure.
- Read README and project documentation.
- Inspect package.json and Python requirements.
- Inspect relevant frontend components and backend modules.
- Inspect database models and existing migrations.
- Inspect existing API routes and schemas.
- Identify current implementation status.
- Identify existing conventions and reusable code.

Do not assume that the project is identical to an earlier scaffold.
The checked-out repository is the source of truth.

2. PRESERVE THE EXISTING ARCHITECTURE.

- Do not rewrite the project unnecessarily.
- Do not replace working libraries without a strong reason.
- Do not duplicate existing utilities or services.
- Keep frontend and backend responsibilities separate.
- Keep provider-specific integration isolated.
- Use existing patterns unless they are demonstrably unsafe or broken.

3. PLAN BEFORE IMPLEMENTING.

Before coding:
- Restate the requested feature.
- Explain the user workflow.
- Identify affected frontend, backend, database and provider modules.
- Identify API contracts and data changes.
- Identify authentication and authorization requirements.
- Identify edge cases and failure scenarios.
- Give a concise implementation plan.

For a small, unambiguous change, keep the plan short and proceed.
Ask a question only if a missing requirement blocks a safe implementation.

4. BACKEND ENGINEERING RULES.

- Use FastAPI routers for HTTP endpoints.
- Keep business logic in service modules.
- Use Pydantic schemas for request and response validation.
- Use SQLAlchemy for database access.
- Use Alembic migrations for schema changes.
- Add indexes and constraints where justified.
- Handle external API timeouts, authentication errors, rate limits,
  server errors and malformed responses.
- Never turn an upstream API error into an empty successful result.
- Use appropriate HTTP status codes.
- Add structured logging without logging secrets.
- Validate all external input.
- Protect all user-specific resources with server-side authorization.

5. RAILWAY DATA RULES.

- Read the current provider documentation before implementing or
  modifying an endpoint.
- Never invent provider endpoint URLs, parameters, headers or response
  fields.
- Verify that the user's subscription supports the required endpoint.
- Keep API keys exclusively on the backend.
- Normalize provider responses into internal application schemas.
- Preserve provider source and retrieval timestamps when available.
- Treat availability as time-sensitive and segment-specific.
- Never claim that a ticket is confirmed based on an estimate.
- Never fabricate train, fare, schedule or availability information.
- Respect provider quotas, caching restrictions and terms of use.
- Do not scrape private endpoints or bypass access controls.
- If provider documentation is insufficient, clearly identify what
  needs verification instead of guessing.

6. FRONTEND ENGINEERING RULES.

- Use TypeScript and existing project conventions.
- Prefer reusable components.
- Keep API calls in service/lib modules rather than duplicating fetch
  logic in components.
- Use typed request and response models.
- Implement loading, empty, success and error states.
- Make the interface responsive and accessible.
- Follow the existing minimal visual design.
- Do not show fabricated railway results as real data.
- Display data freshness and provider limitations where relevant.
- Do not put secrets in NEXT_PUBLIC environment variables.

7. MULTI-USER AND SECURITY RULES.

- Every user-owned resource must be scoped to the authenticated user.
- Never trust a user_id supplied by the browser when the identity can
  be obtained from the authenticated session.
- Prevent cross-user access to saved searches, journeys and monitoring
  rules.
- Hash passwords using the existing secure password-hashing library.
- Do not log passwords, tokens, API keys or sensitive information.
- Do not weaken authentication or authorization to make a feature work.
- Flag production security gaps rather than claiming they are solved.

8. DATABASE RULES.

- Do not make undocumented manual schema changes.
- Create Alembic migrations for database schema changes.
- Preserve existing records.
- Consider nullable fields, defaults, uniqueness, indexes and
  referential integrity.
- Do not drop or rename existing columns without explaining the
  migration and compatibility implications.

9. TESTING RULES.

Add or update tests for:
- Normal successful behavior.
- Invalid input.
- Missing or expired authentication.
- Unauthorized access to another user's resources.
- Empty results.
- Provider timeout or unavailability.
- Provider authentication failure.
- Provider rate limiting.
- Malformed or incomplete provider responses.
- Important edge cases for the requested feature.

Mock external provider calls in automated tests.
Do not consume real provider quota unnecessarily.

Run relevant checks:
- Frontend lint/type checking/build.
- Backend tests.
- Python syntax/import checks.
- Migration checks when database changes are made.

Never claim a test passed unless you actually ran it and observed
the result. If a command cannot be run, say so explicitly.

10. DOCUMENTATION RULES.

Update relevant documentation:
- README.md
- API documentation or endpoint descriptions
- Environment variable examples
- Setup instructions
- Feature/project documentation
- Migration instructions where relevant

Never put real credentials in documentation.

11. IMPLEMENTATION AND DELIVERY RULES.

When implementing a feature:
- Make the smallest coherent set of changes.
- Keep code readable and modular.
- Avoid unnecessary dependencies.
- Explain new dependencies and why they are needed.
- Do not silently remove existing functionality.
- Do not leave fake implementations presented as complete features.
- Clearly mark any unimplemented or provider-dependent behavior.

At the end, provide:

A. Summary of what was implemented.
B. Files created, changed or removed.
C. API endpoints added or modified.
D. Database models and migrations added.
E. Environment variables or dependencies required.
F. Tests and commands executed, with actual outcomes.
G. Exact steps to run and verify the feature locally.
H. Known limitations and follow-up work.

If you cannot complete something, explain precisely what remains
and why. Do not claim completion without evidence.

CURRENT FEATURE REQUEST
-----------------------

[REPLACE THIS SECTION WITH THE FEATURE YOU WANT TO ADD]

EXPECTED USER EXPERIENCE
------------------------

[DESCRIBE WHAT THE USER SHOULD BE ABLE TO DO]

ACCEPTANCE CRITERIA
-------------------

[LIST THE CONDITIONS THAT MUST BE TRUE FOR THE FEATURE TO BE COMPLETE]
```

------------------------------------------------------------------------

## 13. How to use this document

For every new feature:

1.  Give the AI coding agent access to the repository.
2.  Share this Markdown document as project context.
3.  Paste the Master Project Context Prompt.
4.  Replace the feature request, expected experience and acceptance
    criteria.
5.  Ask the agent to inspect the codebase before modifying files.
6.  Review its implementation plan before allowing major architectural
    changes.

### Example future feature request

``` text
CURRENT FEATURE REQUEST

Implement a multi-station train search feature.

EXPECTED USER EXPERIENCE

I should be able to enter multiple origin stations, multiple
destination stations, and a date range.

The application should search all valid combinations, remove
duplicate trains, and show results in one consolidated list.

ACCEPTANCE CRITERIA

- Support multiple source stations.
- Support multiple destination stations.
- Support a configurable date range.
- Avoid duplicate API calls where possible.
- Show the originating and destination station for each result.
- Display API errors separately from empty results.
- Respect provider request limits.
- Add backend tests and frontend loading/error states.
```

------------------------------------------------------------------------

## 14. Project maintenance rule

Keep this file updated as the architecture evolves.

When a feature changes: - Update the project summary if the product
scope changes. - Update the technology stack if a dependency is
replaced. - Update the repository structure when modules move. - Update
provider details when API access or pricing changes. - Update the
roadmap when phases are completed. - Record important architectural
decisions and their rationale.

**The objective is to make this document a reliable handoff between you,
the repository, and any AI coding agent you use in the future.**
