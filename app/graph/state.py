from typing import TypedDict


class SupportState(TypedDict, total=False):
    message: str
    customer_id: int
    order_id: int
    intent: str
    intent_confidence: float
    intent_explanation: str
    answer: str
    sources: list[str]
    needs_human: bool
    ticket_id: int
