# Agentic AI Customer Support Automation Platform

An Agentic AI support platform built with Python 3.13, FastAPI, LangGraph,
Groq, Hugging Face embeddings, FAISS, SQLAlchemy, SQLite/PostgreSQL, and
Streamlit. It combines policy-grounded RAG, intent classification, database
tools, support-ticket workflows, human escalation, and customer-scoped access.

## Architecture

```mermaid
flowchart LR
    U[Customer] --> S[Streamlit UI]
    S --> A[FastAPI]
    A --> G[LangGraph workflow]
    G --> I[Groq intent agent]
    G --> R[FAISS RAG knowledge agent]
    G --> T[Customer, order, ticket tools]
    R --> K[Support policy documents]
    T --> D[(SQLite or PostgreSQL)]
    G --> H[Human escalation record]
    H --> AD[Admin review]
```

## Technology

- Python 3.13
- FastAPI and Pydantic
- SQLAlchemy with SQLite and PostgreSQL
- LangGraph and LangChain
- Groq model `openai/gpt-oss-20b`
- Sentence Transformers `sentence-transformers/all-MiniLM-L6-v2`
- FAISS
- Streamlit
- Python `unittest`

Docker and Docker Compose are optional deployment aids. They are not required
for local setup, FastAPI, Streamlit, SQLite, RAG, or LangGraph.

## Project structure

```text
app/
  agents/       intent and RAG agents
  api/          FastAPI dependencies
  core/         authentication configuration
  database/     models, sessions, and CRUD operations
  graph/        LangGraph state and workflow
  services/     document loading and FAISS storage
  tools/        customer, order, and ticket tools
frontend/       Streamlit dashboard
knowledge_base/ support policy source documents
tests/          unit and API tests
data/faiss/     local FAISS index and document metadata
```

## Installation

Run commands from the project root in Windows PowerShell.

```powershell
python -m venv .venv
& .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Python 3.13 is required for the tested environment.
This project uses `.venv`; do not install Docker Desktop or Docker Compose for
local development.

## Environment configuration

Copy `.env.example` to `.env`. Never commit `.env`. SQLite is the default and
requires no PostgreSQL service:

```text
DATABASE_URL=sqlite:///./customer_support.db
```

Generate independent secrets locally:

```powershell
& .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
& .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Put the first generated value in `AUTH_SECRET_KEY` and the second in
`CUSTOMER_TOKEN_ADMIN_KEY`. Both require at least 32 characters. Configure:

- `GROQ_API_KEY`
- `GROQ_MODEL`, normally `openai/gpt-oss-20b`
- `DATABASE_URL`, normally `sqlite:///./customer_support.db`
- `AUTH_SECRET_KEY`
- `CUSTOMER_TOKEN_ADMIN_KEY`

Rotating `AUTH_SECRET_KEY` invalidates existing bearer tokens. Keep
`CUSTOMER_TOKEN_ADMIN_KEY` separate and restricted.

The application refuses to start when either authentication secret is missing
or shorter than 32 characters. API responses include `X-Request-ID`; logs use
that identifier without logging authorization headers or request bodies.

## Database setup

SQLite is the default local database:

```powershell
& .\.venv\Scripts\python.exe -m app.database.init_db
```

SQLAlchemy creates chat history and escalation tables when the FastAPI
application starts. PostgreSQL is supported through `DATABASE_URL`, for example:

```text
postgresql+psycopg2://support_app:password@localhost:5432/customer_support
```

## Run the application

Start the API:

```powershell
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

API documentation is available at `http://127.0.0.1:8000/docs`.
Verify API health:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
```

Start Streamlit in another terminal:

```powershell
& .\.venv\Scripts\python.exe -m streamlit run frontend\streamlit_app.py
```

The dashboard opens at `http://localhost:8501`.
It requires a running FastAPI process at `http://127.0.0.1:8000` by default.
Set `SUPPORT_API_URL` to a different backend URL if needed.

## Windows local verification

1. Keep the existing `customer_support.db`; the application opens it through
   `DATABASE_URL` and does not create a second database.
2. Start FastAPI in one PowerShell terminal.
3. Start Streamlit in a second PowerShell terminal.
4. Check FastAPI with `/health`.
5. Check Streamlit at `http://127.0.0.1:8501`.
6. Enter the backend URL, customer ID, and bearer token in the sidebar.
7. Send a chat message and confirm history, answer sources, ticket data, or
   escalation status where applicable.

## Authentication

The API issues short-lived customer bearer tokens through:

```text
POST /auth/token
X-Admin-Key: <customer-token-admin-key>
{"customer_id": 1}
```

Tokens expire after one hour. Send one to a customer endpoint as:

```text
Authorization: Bearer <token>
```

Customer endpoints reject mismatched customer IDs. Orders, tickets, history,
and escalation records are filtered by the authenticated customer. Sensitive
ticket updates and escalation reviews require the admin key.

## API endpoints

| Method | Endpoint | Access |
|---|---|---|
| GET | `/` | Public |
| GET | `/health` | Public, reports auth configuration flags |
| POST | `/auth/token` | Admin key |
| POST | `/customers` | Admin key |
| GET | `/customers` | Admin key |
| GET | `/orders/{order_id}` | Customer token and ownership |
| POST | `/orders` | Admin key |
| POST | `/tickets` | Customer token and ownership |
| GET | `/tickets` | Customer token |
| PATCH | `/tickets/{ticket_id}` | Admin key |
| POST | `/chat` | Customer token |
| GET | `/chat/history/{customer_id}` | Customer token and ownership |
| GET | `/escalations` | Customer token |
| PATCH | `/escalations/{escalation_id}` | Admin key |

## Tests

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Unit tests use mocks or isolated in-memory SQLite databases. Live Groq calls
are not used by the ordinary suite.

## Docker

Docker is optional and has not been verified in this project environment.
Do not install or depend on Docker for local development.

Docker Compose runs PostgreSQL, the FastAPI API, and Streamlit. Docker is not
required for local SQLite development.

```powershell
docker compose up --build
```

Services:

- API: `http://127.0.0.1:8000`
- Streamlit: `http://127.0.0.1:8501`
- PostgreSQL: internal Compose network port `5432`

PostgreSQL data and FAISS data use named volumes. The existing SQLite database
is not mounted or deleted.

### Docker verification checklist

Docker Desktop and Docker Compose have not been executed in this workspace.
When Docker is available, run these checks:

1. `docker --version`
2. `docker compose version`
3. Copy `.env.example` to `.env` and set real Groq, auth, admin, and PostgreSQL secrets.
4. `docker compose config` to verify variable interpolation without printing secret values.
5. `docker compose up --build -d`
6. `docker compose ps` and confirm all services are healthy/running.
7. Open `http://127.0.0.1:8000/health`.
8. Open `http://127.0.0.1:8000/docs`.
9. Open `http://127.0.0.1:8501` and test authenticated chat.
10. `docker compose logs --tail=100 api`
11. `docker compose exec postgres pg_isready -U support_app -d customer_support`
12. Stop with `docker compose down`; use `docker compose down -v` only if deleting
   the PostgreSQL and FAISS volumes is explicitly approved.

## PostgreSQL migration

PostgreSQL compatibility is implemented through `DATABASE_URL`, but migration
from SQLite has not been executed. Do not run an import or migration until a
backup is available and the target database is approved.

The migration must preserve:

- `customers`
- `orders`
- `support_tickets`
- `conversation_messages`
- `support_escalations`

Before migration:

1. Back up `customer_support.db`.
2. Start PostgreSQL and set `DATABASE_URL`.
3. Start the API once to let SQLAlchemy create tables.
4. Export SQLite rows and load PostgreSQL using a reviewed migration script.
5. Validate row counts and foreign keys.
6. Test the application against PostgreSQL.
7. Keep SQLite untouched until PostgreSQL verification passes.

No migration tooling or destructive SQLite operation is included in the
application.

## Security considerations

- `.env` is excluded from Git.
- Secrets are never printed or logged.
- Signed bearer tokens expire after one hour.
- Customer data access is ownership-filtered.
- Administrative actions require a separate key.
- The knowledge agent treats policy excerpts and customer messages as
  untrusted input.
- Unsupported policy answers use a human-support fallback.
- Refund and financial actions are not performed by the agent.

## Known limitations

- Live Groq and Hugging Face network availability must be verified in each
  deployment environment.
- Authentication has no password/login provider or refresh-token revocation
  system.
- Human escalation approval is status-only and does not integrate a live
  operations queue.
- PostgreSQL migration tooling is not included yet.
- SQLite, FAISS, and in-process workflow state are suitable for local development,
  not horizontal production scaling.
