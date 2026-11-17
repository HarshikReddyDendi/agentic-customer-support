# Project Status

## Current snapshot

The project is in active development. The existing `.env` file and SQLite
database are preserved. No Git repository is initialized in this workspace.

## Checklist

| Area | Status | Evidence / next work |
|---|---|---|
| Database models and SQLite file | TESTED | Existing data remains intact; added chat-history and escalation tables through SQLAlchemy metadata and exercised them in isolated API tests. |
| Database session configuration | TESTED | Added engine/session dependency and verified `import app.main` succeeds. |
| Intent classification | TESTED | Live Groq classified human-support and complaint requests successfully. |
| Policy document loader | TESTED | Existing loader and three policy files are present; prior run reported 3 documents and 3 chunks. |
| FAISS vector store | TESTED | Saved FAISS index and JSON metadata exist under `data/faiss`; live RAG retrieval and answer generation were verified. |
| Groq knowledge agent | TESTED | Live refund, shipping, duplicate-payment, 90-day refund, and unsupported policy checks passed; unsupported price matching used human fallback. |
| Customer/order/ticket tools | TESTED | Added reusable lookup/ticket CRUD tools; 5 in-memory SQLite tests pass, including customer ownership validation for order lookup. |
| LangGraph workflow and escalation | TESTED | Workflow is integrated with chat; unresolved requests create escalation records and admin review is tested. |
| FastAPI routes and authorization | TESTED | Chat, history, ticket patch, health, customer-scoped orders/tickets, admin token/customer creation, and escalation review pass API tests. |
| Authentication configuration | TESTED LIVE | `.env` contains 32-character-or-longer auth and admin secrets. The application loads both through dotenv; `/health` reports both flags true. The live token endpoint issued a customer token. |
| Authenticated end-to-end chat | TESTED LIVE | Existing customer 1 completed real Groq refund and complaint chats. Invalid bearer returned 401 and mismatched history returned 404. |
| Ticket and escalation persistence | TESTED LIVE | Refund chat created ticket 10 and complaint chat created escalation 1. History returned 4 persisted messages. Admin updates resolved ticket 10 and approved escalation 1. |
| Streamlit frontend | TESTED PARTIAL | Streamlit returned HTTP 200 and browser rendering showed the login/auth gate. Full UI entry with a live bearer token was not automated in the browser. |
| Automated tests | TESTED | Forty-two unit, API, security, RAG, workflow, and infrastructure tests pass. Live integration calls are tracked separately and are not paid API tests by default. |
| Local Windows deployment | TESTED | Python 3.13 `.venv`, FastAPI, Streamlit, SQLite, authenticated chat, and frontend/API HTTP communication all started and responded locally. |
| Security audit | TESTED | Customer creation requires admin authorization. Startup rejects missing auth secrets. Ticket values are constrained. Invalid, expired, missing, and wrong-key paths have focused tests. |
| Docker configuration | OPTIONAL / UNVERIFIED | Dockerfile, Compose review, Docker checklist, and static YAML validation are present. Docker Desktop, Docker build/start, and Compose startup have not been executed. |
| PostgreSQL deployment | NOT TESTED | Environment-based `DATABASE_URL` support exists. PostgreSQL startup and SQLite migration have not been executed; existing SQLite data remains untouched. |
| Git repository | BLOCKED | The workspace is not currently a Git repository; no commits or pushes were attempted. |

## Audit checks

- Python interpreter: `.venv` Python 3.13.18.
- Required RAG, Groq, FastAPI, SQLAlchemy, LangGraph, and Streamlit packages are installed.
- `.env` contains a non-empty `GROQ_API_KEY`; its value was not displayed.
- `.env` contains `AUTH_SECRET_KEY` and `CUSTOMER_TOKEN_ADMIN_KEY`; values were not displayed or modified.
- Runtime dotenv loading is implemented in the security module.
- Live `/auth/token` issued a bearer token for customer 1 and returned a one-hour expiry.
- Wrong admin key returned 403; invalid bearer token returned 401.
- Customer 1's refund chat classified `refund_request`, cited `refund_policy.txt`, and created ticket 10.
- Customer 1's complaint chat classified `complaint`, created escalation 1, and persisted chat history.
- Admin patch resolved ticket 10 and approved escalation 1.
- Authentication validation requires both secrets to contain at least 32 characters.
- Live FastAPI `/health` returned status `ok`, database `ok`, and both auth flags `true`.
- Live Groq RAG returned five policy answers: refund, shipping, duplicate payment, 90-day refund, and unsupported price matching.
- Live Groq intent classification returned `human_support` and `complaint`.
- Docker and Docker Compose were not available in the environment, so container build/start remains unverified.
- Local Windows verification passed without Docker: FastAPI `/health`, Streamlit health, bearer-token issuance, authenticated chat, and history retrieval responded successfully.
- The FastAPI restart audit encountered a port-8000 conflict with an existing local listener. The existing listener remained healthy and served `/health`, `/docs`, and `/openapi.json`; no secrets were exposed.
- API responses include an `X-Request-ID` for correlation; request logs do not include request bodies or authorization headers.
- `customer_support.db` was inspected read-only for schema and existing customer IDs; no customer PII was displayed.
- Initial application import failed because `app/database/connection.py` was empty; that defect is fixed and the API now imports.

## Current task

Local Windows verification passed for Python 3.13, FastAPI, Streamlit, SQLite,
authenticated chat, RAG retrieval, and frontend/API HTTP communication.
Customer creation is now admin-only. Live Docker build/start and PostgreSQL
migration remain unverified because Docker is unavailable and SQLite data was
preserved. Docker is optional; no Docker Desktop installation or Docker runtime
dependency is required for local use.
