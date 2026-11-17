import logging
import time
import uuid
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Protocol

from fastapi import Depends, FastAPI, HTTPException, status
from starlette.requests import Request
from starlette.responses import Response
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.agents.knowledge_agent import FALLBACK_ANSWER
from app.api.dependencies import get_current_customer
from app.core.security import (
    TOKEN_MAX_AGE_SECONDS,
    auth_configuration_status,
    issue_customer_token,
    validate_auth_configuration,
    verify_admin_key,
)
from app.database.connection import Base, engine, get_db
from app.database.crud import (
    create_support_ticket,
    get_customer_by_id,
    get_order_for_customer,
    update_support_ticket,
)
from app.database.models import (
    ConversationMessage,
    Customer,
    Order,
    SupportEscalation,
    SupportTicket,
)
from app.graph.state import SupportState
from app.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationHistoryResponse,
    CustomerCreate,
    CustomerResponse,
    CustomerTokenRequest,
    CustomerTokenResponse,
    EscalationResponse,
    EscalationUpdate,
    OrderCreate,
    OrderResponse,
    TicketCreate,
    TicketResponse,
    TicketUpdate,
)

logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(application: FastAPI):
    del application
    validate_auth_configuration()
    yield


app = FastAPI(
    title="Agentic AI Customer Support API",
    description="Backend APIs for AI-powered customer support automation",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_audit_log(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    started_at = time.monotonic()
    try:
        response: Response = await call_next(request)
    except Exception:
        elapsed_ms = round((time.monotonic() - started_at) * 1000, 2)
        logger.exception(
            "Request failed",
            extra={"request_id": request_id, "elapsed_ms": elapsed_ms},
        )
        raise

    elapsed_ms = round((time.monotonic() - started_at) * 1000, 2)
    logger.info(
        "HTTP %s %s -> %d (%sms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        extra={"request_id": request_id},
    )
    response.headers["X-Request-ID"] = request_id
    return response


class SupportWorkflow(Protocol):
    def invoke(self, input: SupportState) -> SupportState:
        ...


@lru_cache(maxsize=1)
def get_support_workflow() -> SupportWorkflow:
    from app.graph.workflow import build_support_workflow

    return build_support_workflow()


@app.get("/")
def home() -> dict[str, str]:
    return {"message": "Agentic AI Customer Support API is running"}


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        logger.exception("Database health check failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from error
    return {
        "status": "ok",
        "database": "ok",
        "authentication": auth_configuration_status(),
    }


@app.post("/auth/token", response_model=CustomerTokenResponse)
def create_customer_token(
    data: CustomerTokenRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
) -> CustomerTokenResponse:
    customer = get_customer_by_id(db, data.customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return CustomerTokenResponse(
        access_token=issue_customer_token(customer.id),
        expires_in=TOKEN_MAX_AGE_SECONDS,
    )


@app.post("/customers", response_model=CustomerResponse, status_code=201)
def create_customer(
    data: CustomerCreate,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
) -> Customer:
    customer = Customer(name=data.name.strip(), email=str(data.email).lower())
    db.add(customer)
    try:
        db.commit()
        db.refresh(customer)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Customer email already exists",
        ) from error
    return customer


@app.get("/customers", response_model=list[CustomerResponse])
def get_customers(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
) -> list[Customer]:
    return list(db.scalars(select(Customer).order_by(Customer.id)).all())


@app.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> Order:
    order = get_order_for_customer(db, order_id, customer.id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.post("/orders", response_model=OrderResponse, status_code=201)
def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
) -> Order:
    customer = get_customer_by_id(db, data.customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    order = Order(
        customer_id=data.customer_id,
        product=data.product.strip(),
        amount=data.amount,
        status=data.status,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@app.post("/tickets", response_model=TicketResponse, status_code=201)
def create_ticket(
    data: TicketCreate,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> SupportTicket:
    if data.customer_id != customer.id:
        raise HTTPException(status_code=404, detail="Customer not found")
    try:
        return create_support_ticket(
            db,
            customer_id=customer.id,
            issue=data.issue,
            priority=data.priority,
        )
    except (ValueError, LookupError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/tickets", response_model=list[TicketResponse])
def get_tickets(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> list[SupportTicket]:
    return list(
        db.scalars(
            select(SupportTicket)
            .where(SupportTicket.customer_id == customer.id)
            .order_by(SupportTicket.id)
        ).all()
    )


@app.patch("/tickets/{ticket_id}", response_model=TicketResponse)
def patch_ticket(
    ticket_id: int,
    data: TicketUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
) -> SupportTicket:
    try:
        return update_support_ticket(
            db,
            ticket_id,
            status=data.status,
            priority=data.priority,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Ticket not found") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/chat", response_model=ChatResponse)
def chat(
    data: ChatRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
    workflow: SupportWorkflow = Depends(get_support_workflow),
) -> ChatResponse:
    graph_input: SupportState = {
        "message": data.message,
        "customer_id": customer.id,
    }
    if data.order_id is not None:
        graph_input["order_id"] = data.order_id

    try:
        result = workflow.invoke(graph_input)
    except Exception as error:
        logger.exception("Customer-support workflow failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The support workflow is temporarily unavailable",
        ) from error

    answer = result.get("answer") or FALLBACK_ANSWER
    intent = result.get("intent") or "general_query"
    sources = result.get("sources") or []
    needs_human = result.get("needs_human", False)
    ticket_id = result.get("ticket_id")
    escalation_id = None

    if needs_human:
        escalation = SupportEscalation(
            customer_id=customer.id,
            reason=f"Workflow escalation for intent: {intent}",
            context=f"Customer message: {data.message}\nAssistant response: {answer}",
        )
        db.add(escalation)
        db.flush()
        escalation_id = escalation.id

    db.add_all(
        [
            ConversationMessage(
                customer_id=customer.id,
                role="user",
                content=data.message,
            ),
            ConversationMessage(
                customer_id=customer.id,
                role="assistant",
                content=answer,
                sources=sources,
                needs_human=needs_human,
            ),
        ]
    )
    try:
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception("Could not save chat history")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The conversation could not be saved",
        ) from error

    return ChatResponse(
        answer=answer,
        intent=intent,
        sources=sources,
        needs_human=needs_human,
        escalation_id=escalation_id,
        ticket_id=ticket_id if isinstance(ticket_id, int) else None,
    )


@app.get(
    "/chat/history/{customer_id}",
    response_model=ConversationHistoryResponse,
)
def chat_history(
    customer_id: int,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> ConversationHistoryResponse:
    if customer_id != customer.id:
        raise HTTPException(status_code=404, detail="Conversation history not found")

    messages = list(
        db.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.customer_id == customer.id)
            .order_by(
                ConversationMessage.created_at.desc(),
                ConversationMessage.id.desc(),
            )
            .limit(100)
        ).all()
    )
    messages.reverse()
    return ConversationHistoryResponse(
        customer_id=customer.id,
        messages=messages,
    )


@app.get(
    "/escalations",
    response_model=list[EscalationResponse],
)
def get_escalations(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> list[SupportEscalation]:
    return list(
        db.scalars(
            select(SupportEscalation)
            .where(SupportEscalation.customer_id == customer.id)
            .order_by(
                SupportEscalation.created_at.desc(),
                SupportEscalation.id.desc(),
            )
        ).all()
    )


@app.patch(
    "/escalations/{escalation_id}",
    response_model=EscalationResponse,
)
def update_escalation(
    escalation_id: int,
    data: EscalationUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
) -> SupportEscalation:
    escalation = db.get(SupportEscalation, escalation_id)
    if escalation is None:
        raise HTTPException(status_code=404, detail="Escalation not found")
    if escalation.status != "pending":
        raise HTTPException(
            status_code=409,
            detail="Escalation has already been reviewed",
        )
    escalation.status = data.status
    db.commit()
    db.refresh(escalation)
    return escalation
