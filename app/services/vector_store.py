import json
import logging
from dataclasses import dataclass
from pathlib import Path

import faiss
import numpy as np
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from app.services.document_loader import load_documents, split_documents

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_VECTOR_STORE_DIR = (
    Path(__file__).resolve().parents[2] / "data" / "faiss"
)
INDEX_FILENAME = "support_policies.faiss"
DOCUMENTS_FILENAME = "support_policies.json"


def create_embedding_model() -> HuggingFaceEmbeddings:
    """Create the local Hugging Face embedding model."""
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
        query_encode_kwargs={"normalize_embeddings": True},
    )


@dataclass
class PolicyVectorStore:
    index: faiss.Index
    documents: list[Document]
    embedding_model: HuggingFaceEmbeddings

    def similarity_search(
        self,
        query: str,
        k: int = 3,
    ) -> list[tuple[Document, float]]:
        """Return the most similar policy chunks and their cosine scores."""
        if not query.strip():
            raise ValueError("Search query cannot be empty")
        if k <= 0:
            raise ValueError("k must be greater than zero")

        query_vector = np.asarray(
            [self.embedding_model.embed_query(query)],
            dtype=np.float32,
        )
        scores, indices = self.index.search(
            query_vector,
            min(k, len(self.documents)),
        )

        results: list[tuple[Document, float]] = []
        for index, score in zip(indices[0], scores[0], strict=True):
            if index >= 0:
                results.append((self.documents[int(index)], float(score)))

        return results

    def save_local(
        self,
        directory: str | Path = DEFAULT_VECTOR_STORE_DIR,
    ) -> None:
        """Save the FAISS index and its associated document chunks."""
        directory_path = Path(directory)
        directory_path.mkdir(parents=True, exist_ok=True)

        faiss.write_index(
            self.index,
            str(directory_path / INDEX_FILENAME),
        )

        serialized_documents = [
            {
                "page_content": document.page_content,
                "metadata": document.metadata,
            }
            for document in self.documents
        ]
        (directory_path / DOCUMENTS_FILENAME).write_text(
            json.dumps(serialized_documents, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        logger.info("Saved FAISS vector store to %s", directory_path)


def build_vector_store(
    directory: str | Path = DEFAULT_VECTOR_STORE_DIR,
) -> PolicyVectorStore:
    """Load, split, embed, and save the support policies."""
    documents = load_documents()
    chunks = split_documents(documents)

    if not chunks:
        raise ValueError("No document chunks were produced")

    embedding_model = create_embedding_model()
    vectors = np.asarray(
        embedding_model.embed_documents(
            [chunk.page_content for chunk in chunks]
        ),
        dtype=np.float32,
    )

    if vectors.ndim != 2 or vectors.shape[0] != len(chunks):
        raise ValueError("Embedding output does not match the document chunks")
    if not np.isfinite(vectors).all():
        raise ValueError("Embedding output contains non-finite values")

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(np.ascontiguousarray(vectors))

    vector_store = PolicyVectorStore(
        index=index,
        documents=chunks,
        embedding_model=embedding_model,
    )
    vector_store.save_local(directory)

    logger.info(
        "Indexed %d chunks from %d policies",
        len(chunks),
        len(documents),
    )
    return vector_store


def load_vector_store(
    directory: str | Path = DEFAULT_VECTOR_STORE_DIR,
) -> PolicyVectorStore:
    """Load a previously saved FAISS index and its document chunks."""
    directory_path = Path(directory)
    index_path = directory_path / INDEX_FILENAME
    documents_path = directory_path / DOCUMENTS_FILENAME

    if not index_path.is_file() or not documents_path.is_file():
        raise FileNotFoundError(
            f"Vector store not found in {directory_path}; build it first"
        )

    index = faiss.read_index(str(index_path))
    payload = json.loads(documents_path.read_text(encoding="utf-8"))

    if not isinstance(payload, list):
        raise ValueError("Saved vector-store documents must be a JSON list")

    documents: list[Document] = []
    for item in payload:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("page_content"), str)
            or not isinstance(item.get("metadata"), dict)
        ):
            raise ValueError("Saved vector-store document has an invalid format")

        documents.append(
            Document(
                page_content=item["page_content"],
                metadata=item["metadata"],
            )
        )

    if index.ntotal != len(documents):
        raise ValueError(
            "FAISS index and saved document metadata have different sizes"
        )

    return PolicyVectorStore(
        index=index,
        documents=documents,
        embedding_model=create_embedding_model(),
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    vector_store = build_vector_store()
    questions = [
        "What is the refund period?",
        "How long does standard shipping take?",
        "What should a customer do if payment is deducted twice?",
    ]

    for question in questions:
        print(f"\nQuestion: {question}")
        for document, score in vector_store.similarity_search(question, k=1):
            print(f"Source: {document.metadata.get('source', 'unknown')}")
            print(f"Cosine similarity: {score:.3f}")
            print(f"Retrieved text: {document.page_content}")


if __name__ == "__main__":
    main()
