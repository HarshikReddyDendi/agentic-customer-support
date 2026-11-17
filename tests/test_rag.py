import unittest

from app.services.document_loader import load_documents, split_documents
from app.services.vector_store import (
    build_vector_store,
    load_vector_store,
)


class RagTests(unittest.TestCase):
    def test_documents_split_and_retain_source_metadata(self) -> None:
        documents = load_documents()
        chunks = split_documents(documents)

        self.assertGreaterEqual(len(documents), 3)
        self.assertGreater(len(chunks), 0)
        sources = {chunk.metadata["source"] for chunk in chunks}
        self.assertIn("refund_policy.txt", sources)
        self.assertIn("shipping_policy.txt", sources)
        self.assertIn("payment_faq.txt", sources)

    def test_saved_vector_store_retrieves_policy_context(self) -> None:
        vector_store = load_vector_store()
        result = vector_store.similarity_search(
            "What should I do if a charge posts twice?",
            k=1,
        )

        self.assertEqual(len(result), 1)
        document, _score = result[0]
        self.assertEqual(document.metadata["source"], "payment_faq.txt")
        self.assertIn("charge posts twice", document.page_content.lower())

    def test_vector_store_can_be_rebuilt(self) -> None:
        vector_store = build_vector_store()

        self.assertEqual(vector_store.index.ntotal, len(vector_store.documents))


if __name__ == "__main__":
    unittest.main()
