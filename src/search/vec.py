import os
import logging
import sys

# Ensure logging goes to stderr only (critical for MCP compatibility)
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )

from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class SemanticRetriever:

    COLLECTION = "book_chunks"

    def __init__(self, transformer="BAAI/bge-small-en") -> None:
        super().__init__()
        self.embedder = SentenceTransformer(transformer)
        qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        qdrant_port = int(os.getenv("QDRANT_PORT", 6333))
        self.qdrant = QdrantClient(qdrant_host, port=qdrant_port)

        self.embeddings = []
        self.ids = []

    def embed_batch(self, chunks):
        texts = [c["text"] for c in chunks]
        vecs = self.embedder.encode(texts, normalize_embeddings=True).tolist()
        return vecs

    def build_index(self, chunks):

        vectors = self.embed_batch(chunks)
        logger.info("Vector shape: %d x %d", len(vectors), len(vectors[0]))

        if not self.qdrant.collection_exists(SemanticRetriever.COLLECTION):
            self.qdrant.create_collection(
                collection_name=SemanticRetriever.COLLECTION,
                vectors_config=models.VectorParams(
                    size=len(vectors[0]), distance=models.Distance.COSINE
                ),
            )

        # Upsert points using chunk ID hash for unique identification
        import hashlib

        self.qdrant.upsert(
            collection_name=SemanticRetriever.COLLECTION,
            points=[
                models.PointStruct(
                    id=int(hashlib.md5(chunks[i]["id"].encode()).hexdigest()[:16], 16)
                    % (10**9),
                    vector=vectors[i],
                    payload=chunks[i],
                )
                for i in range(len(chunks))
            ],
        )
        logger.info("Inserted %d chunks into Qdrant", len(chunks))

    def search(self, query, topk=7, book_slug=None):
        if not self.qdrant.collection_exists(SemanticRetriever.COLLECTION):
            logger.warning(
                "Collection '%s' does not exist in Qdrant", SemanticRetriever.COLLECTION
            )
            return []

        vec = self.embedder.encode([query], normalize_embeddings=True)[0].tolist()

        # Build query filter if book_slug is provided
        query_filter = None
        if book_slug:
            from qdrant_client.models import Filter, FieldCondition, MatchText
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="id",
                        match=MatchText(text=book_slug)
                    )
                ]
            )

        hits = self.qdrant.query_points(
            collection_name=SemanticRetriever.COLLECTION,
            query=vec,
            limit=topk,
            query_filter=query_filter
        ).points
        return [
            {"id": h.payload["id"], "text": h.payload["text"], "score": h.score}
            for h in hits
        ]

    def id_search(self, query: str, topk=7):
        search_results = self.search(query, topk)
        return [c["id"] for c in search_results]

    def get_chunks_by_ids(self, chunk_ids: list):
        """Retrieve chunks from Qdrant by their chunk IDs."""
        if not self.qdrant.collection_exists(SemanticRetriever.COLLECTION):
            return []

        import hashlib

        results = []
        for chunk_id in chunk_ids:
            point_id = int(hashlib.md5(chunk_id.encode()).hexdigest()[:16], 16) % (
                10**9
            )
            try:
                point = self.qdrant.retrieve(
                    collection_name=SemanticRetriever.COLLECTION, ids=[point_id]
                )
                if point:
                    results.append(
                        {"id": point[0].payload["id"], "text": point[0].payload["text"]}
                    )
            except Exception as e:
                logger.warning("Could not retrieve chunk %s: %s", chunk_id, e)
                results.append({"id": chunk_id, "text": "[Text not found]"})
        return results

    def cleanup(self):
        self.embeddings = []
        self.ids = []
        self.qdrant.delete_collection(SemanticRetriever.COLLECTION)
        logger.info("Semantic index cleared.")
