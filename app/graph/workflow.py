import logging
from collections.abc import Callable
from typing import Literal, Protocol

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agents.intent_agent import CustomerIntentAgent, IntentResult
from app.agents.knowledge_agent import KnowledgeAgent, KnowledgeAgentResult
from app.database.connection import SessionLocal
from app.tools.order_tools import lookup_customer_order
from app.database.crud import create_support_ticket
from app.graph.state import SupportState

logger = logging.getLogger(__name__)

HANDOFF_MESSAGE = (
    "I’m handing this request to a human support agent for further help."
)


class IntentClassifier(Protocol):
    def classify(self, message: str) -> IntentResult:
        ...


class KnowledgeResponder(Protocol):
    def answer_question(self, question: str) -> KnowledgeAgentResult:
        ...


def build_support_workflow(
    intent_agent: IntentClassifier | None = None,
    knowledge_agent: KnowledgeResponder | None = None,
    session_factory: Callable[[], Session] = SessionLocal,
):
    classifier = intent_agent or CustomerIntentAgent()
    knowledge = knowledge_agent or KnowledgeAgent()

    def classify_node(state: SupportState) -> SupportState:
        message = state.get("message", "")
        result = classifier.classify(message)
        return {
            "intent": result.intent,
            "intent_confidence": result.confidence,
            "intent_explanation": result.explanation,
        }

    def route_intent(
        state: SupportState,
    ) -> Literal["knowledge", "order_lookup", "ticket", "escalate"]:
        intent = state.get("intent")
        if intent == "order_status":
            return "order_lookup"
        if intent in {"complaint", "human_support"}:
            return "escalate"
        if intent in {"refund_request", "payment_issue"}:
            return "ticket"
        return "knowledge"

    def knowledge_node(state: SupportState) -> SupportState:
        result = knowledge.answer_question(state.get("message", ""))
        return {
            "answer": result.answer,
            "sources": result.sources,
            "needs_human": result.needs_human,
        }

    def order_lookup_node(state: SupportState) -> SupportState:
        customer_id = state.get("customer_id")
        order_id = state.get("order_id")
        if customer_id is None or order_id is None:
            return {
                "answer": (
                    "Please provide your customer and order details so I can "
                    "check this order."
                ),
                "sources": [],
                "needs_human": True,
            }

        with session_factory() as db:
            order = lookup_customer_order(
                db,
                order_id=order_id,
                customer_id=customer_id,
            )

        if order is None:
            return {
                "answer": "I couldn't verify that order for this customer.",
                "sources": [],
                "needs_human": True,
            }

        return {
            "answer": (
                f"Order {order.id} for {order.product} is currently "
                f"{order.status}."
            ),
            "sources": [],
            "needs_human": False,
        }

    def route_completion(
        state: SupportState,
    ) -> Literal["escalate", "finish"]:
        return "escalate" if state.get("needs_human", False) else "finish"

    def ticket_node(state: SupportState) -> SupportState:
        customer_id = state.get("customer_id")
        if customer_id is None:
            return {
                "answer": state.get("answer") or HANDOFF_MESSAGE,
                "needs_human": True,
            }

        intent = state.get("intent", "general_query")
        try:
            with session_factory() as db:
                ticket = create_support_ticket(
                    db,
                    customer_id=customer_id,
                    issue=state.get("message", "").strip(),
                    priority="High" if intent == "payment_issue" else "Medium",
                )
        except (LookupError, ValueError) as error:
            logger.warning("Could not create support ticket: %s", error)
            return {
                "answer": state.get("answer") or HANDOFF_MESSAGE,
                "needs_human": True,
            }

        return {
            "ticket_id": ticket.id,
            "needs_human": state.get("needs_human", False),
        }

    def escalation_node(state: SupportState) -> SupportState:
        logger.info("Support request routed to human escalation")
        return {
            "answer": state.get("answer") or HANDOFF_MESSAGE,
            "needs_human": True,
        }

    graph = StateGraph(SupportState)
    graph.add_node("classify", classify_node)
    graph.add_node("knowledge", knowledge_node)
    graph.add_node("order_lookup", order_lookup_node)
    graph.add_node("ticket", ticket_node)
    graph.add_node("escalate", escalation_node)

    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify",
        route_intent,
        {
            "knowledge": "knowledge",
            "order_lookup": "order_lookup",
            "ticket": "ticket",
            "escalate": "escalate",
        },
    )
    graph.add_edge("ticket", "knowledge")
    graph.add_conditional_edges(
        "knowledge",
        route_completion,
        {"escalate": "escalate", "finish": END},
    )
    graph.add_conditional_edges(
        "order_lookup",
        route_completion,
        {"escalate": "escalate", "finish": END},
    )
    graph.add_edge("escalate", END)
    return graph.compile()
