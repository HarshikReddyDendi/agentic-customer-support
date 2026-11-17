from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr


class CustomerResponse(BaseModel):
    id: int
    name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class OrderCreate(BaseModel):
    customer_id: int
    product: str = Field(min_length=1, max_length=150)
    amount: float = Field(gt=0)
    status: str = "Processing"


class OrderResponse(BaseModel):
    id: int
    customer_id: int
    product: str
    amount: float
    status: str

    model_config = ConfigDict(from_attributes=True)


class TicketCreate(BaseModel):
    customer_id: int
    issue: str = Field(min_length=1, max_length=500)
    priority: Literal["Low", "Medium", "High"] = "Medium"


class TicketResponse(BaseModel):
    id: int
    customer_id: int
    issue: str
    priority: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class TicketUpdate(BaseModel):
    status: Literal["Open", "In Progress", "Resolved", "Closed"] | None = None
    priority: Literal["Low", "Medium", "High"] | None = None

    @model_validator(mode="after")
    def require_update(self) -> "TicketUpdate":
        if self.status is None and self.priority is None:
            raise ValueError("Provide status and/or priority")
        return self


class CustomerTokenRequest(BaseModel):
    customer_id: int = Field(gt=0)


class CustomerTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    order_id: int | None = Field(default=None, gt=0)


class ChatResponse(BaseModel):
    answer: str
    intent: str
    sources: list[str]
    needs_human: bool
    escalation_id: int | None = None
    ticket_id: int | None = None


class ConversationMessageResponse(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    sources: list[str]
    needs_human: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationHistoryResponse(BaseModel):
    customer_id: int
    messages: list[ConversationMessageResponse]


class EscalationUpdate(BaseModel):
    status: Literal["approved", "rejected", "resolved"]


class EscalationResponse(BaseModel):
    id: int
    customer_id: int
    reason: str
    status: str

    model_config = ConfigDict(from_attributes=True)
