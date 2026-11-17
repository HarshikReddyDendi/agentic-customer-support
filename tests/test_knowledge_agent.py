import unittest

from langchain_core.documents import Document

from app.agents.knowledge_agent import (
    FALLBACK_ANSWER,
    GroundedAnswer,
    KnowledgeAgent,
)


class FakeVectorStore:
    last_query: str | None = None

    def similarity_search(
        self,
        query: str,
        k: int = 3,
    ) -> list[tuple[Document, float]]:
        self.last_query = query
        return [
            (
                Document(
                    page_content="Refunds may be requested within 30 days.",
                    metadata={"source": "refund_policy.txt"},
                ),
                0.8,
            )
        ][:k]


class FakeAnswerChain:
    def __init__(self, result: GroundedAnswer) -> None:
        self.result = result
        self.last_input: dict[str, str] | None = None

    def invoke(self, input: dict[str, str]) -> GroundedAnswer:
        self.last_input = input
        return self.result


class KnowledgeAgentTests(unittest.TestCase):
    def test_supported_answer_returns_validated_source(self) -> None:
        vector_store = FakeVectorStore()
        chain = FakeAnswerChain(
            GroundedAnswer(
                answer="Refunds may be requested within 30 days.",
                supported_by_context=True,
                source_ids=[1],
            )
        )
        agent = KnowledgeAgent(vector_store=vector_store, chain=chain)

        result = agent.answer_question("What is the refund period?")

        self.assertEqual(result.answer, "Refunds may be requested within 30 days.")
        self.assertEqual(result.sources, ["refund_policy.txt"])
        self.assertFalse(result.needs_human)
        self.assertEqual(vector_store.last_query, "What is the refund period?")
        self.assertIn("[1] Source: refund_policy.txt", chain.last_input["context"])

    def test_unsupported_answer_uses_safe_fallback(self) -> None:
        chain = FakeAnswerChain(
            GroundedAnswer(
                answer="I don't know.",
                supported_by_context=False,
                source_ids=[],
            )
        )
        agent = KnowledgeAgent(vector_store=FakeVectorStore(), chain=chain)

        result = agent.answer_question("Do you offer price matching?")

        self.assertEqual(result.answer, FALLBACK_ANSWER)
        self.assertEqual(result.sources, [])
        self.assertTrue(result.needs_human)

    def test_invalid_source_reference_uses_safe_fallback(self) -> None:
        chain = FakeAnswerChain(
            GroundedAnswer(
                answer="The policy says yes.",
                supported_by_context=True,
                source_ids=[2],
            )
        )
        agent = KnowledgeAgent(vector_store=FakeVectorStore(), chain=chain)

        result = agent.answer_question("What is the refund period?")

        self.assertEqual(result.answer, FALLBACK_ANSWER)
        self.assertTrue(result.needs_human)

    def test_blank_question_is_rejected(self) -> None:
        agent = KnowledgeAgent(
            vector_store=FakeVectorStore(),
            chain=FakeAnswerChain(
                GroundedAnswer(
                    answer="Not used.",
                    supported_by_context=False,
                )
            ),
        )

        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            agent.answer_question("  ")


if __name__ == "__main__":
    unittest.main()
