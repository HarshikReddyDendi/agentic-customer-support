import unittest

from app.agents.intent_agent import IntentResult
from app.agents.knowledge_agent import KnowledgeAgentResult
from app.graph.workflow import build_support_workflow


class FakeIntentAgent:
    def __init__(self, intent: str) -> None:
        self.intent = intent
        self.last_message = ""

    def classify(self, message: str) -> IntentResult:
        self.last_message = message
        return IntentResult(
            intent=self.intent,
            confidence=0.99,
            explanation="Test classification",
        )


class FakeKnowledgeAgent:
    def __init__(self, needs_human: bool = False) -> None:
        self.needs_human = needs_human
        self.last_question = ""

    def answer_question(self, question: str) -> KnowledgeAgentResult:
        self.last_question = question
        return KnowledgeAgentResult(
            answer="Grounded answer" if not self.needs_human else "No policy answer.",
            sources=["refund_policy.txt"] if not self.needs_human else [],
            needs_human=self.needs_human,
        )


class SupportWorkflowTests(unittest.TestCase):
    def test_refund_request_routes_through_ticket_and_knowledge(self) -> None:
        intent_agent = FakeIntentAgent("refund_request")
        knowledge_agent = FakeKnowledgeAgent()
        workflow = build_support_workflow(
            intent_agent=intent_agent,
            knowledge_agent=knowledge_agent,
        )

        result = workflow.invoke(
            {"message": "I want a refund", "customer_id": 1}
        )

        self.assertEqual(result["answer"], "Grounded answer")
        self.assertEqual(knowledge_agent.last_question, "I want a refund")

    def test_duplicate_payment_routes_through_ticket_and_knowledge(self) -> None:
        workflow = build_support_workflow(
            intent_agent=FakeIntentAgent("payment_issue"),
            knowledge_agent=FakeKnowledgeAgent(),
        )

        result = workflow.invoke(
            {"message": "My payment was deducted twice", "customer_id": 1}
        )

        self.assertEqual(result["answer"], "Grounded answer")

    def test_complaint_routes_directly_to_escalation(self) -> None:
        workflow = build_support_workflow(
            intent_agent=FakeIntentAgent("complaint"),
            knowledge_agent=FakeKnowledgeAgent(),
        )

        result = workflow.invoke({"message": "I am extremely unhappy"})

        self.assertTrue(result["needs_human"])

    def test_human_support_request_routes_directly_to_escalation(self) -> None:
        workflow = build_support_workflow(
            intent_agent=FakeIntentAgent("human_support"),
            knowledge_agent=FakeKnowledgeAgent(),
        )

        result = workflow.invoke({"message": "Connect me to a human"})

        self.assertTrue(result["needs_human"])

    def test_product_question_routes_to_knowledge(self) -> None:
        intent_agent = FakeIntentAgent("product_question")
        knowledge_agent = FakeKnowledgeAgent()
        workflow = build_support_workflow(
            intent_agent=intent_agent,
            knowledge_agent=knowledge_agent,
        )

        result = workflow.invoke({"message": "What is the policy?"})

        self.assertEqual(result["answer"], "Grounded answer")
        self.assertEqual(result["sources"], ["refund_policy.txt"])
        self.assertFalse(result["needs_human"])
        self.assertEqual(intent_agent.last_message, "What is the policy?")
        self.assertEqual(knowledge_agent.last_question, "What is the policy?")

    def test_unresolved_knowledge_request_escalates(self) -> None:
        workflow = build_support_workflow(
            intent_agent=FakeIntentAgent("general_query"),
            knowledge_agent=FakeKnowledgeAgent(needs_human=True),
        )

        result = workflow.invoke({"message": "Unsupported question"})

        self.assertTrue(result["needs_human"])
        self.assertEqual(result["answer"], "No policy answer.")

    def test_order_lookup_requires_customer_and_order_ids(self) -> None:
        workflow = build_support_workflow(
            intent_agent=FakeIntentAgent("order_status"),
            knowledge_agent=FakeKnowledgeAgent(),
        )

        result = workflow.invoke({"message": "Where is my order?"})

        self.assertTrue(result["needs_human"])
        self.assertIn("customer and order details", result["answer"])


if __name__ == "__main__":
    unittest.main()
