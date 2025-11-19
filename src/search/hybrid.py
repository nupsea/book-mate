from collections import defaultdict
import logging

from src.search.bm25 import BM25Retriever
from src.search.vec import SemanticRetriever

logger = logging.getLogger(__name__)


class FusionRetriever:

    def __init__(
        self,
        transformer="BAAI/bge-small-en",
        alpha=0.7,
        bm25_index_path="INDEXES/bm25_index.pkl",
    ) -> None:
        self.bm25 = BM25Retriever()
        self.vec = SemanticRetriever(transformer=transformer)
        self.alpha = alpha
        self.bm25_index_path = bm25_index_path

    def build_index(self, chunks):
        self.bm25.build_index(chunks)
        self.bm25.save_index(self.bm25_index_path)
        self.vec.build_index(chunks)

    def load_bm25_index(self):
        """Load BM25 index from disk."""
        self.bm25.load_index(self.bm25_index_path)

    @staticmethod
    def rrf_fusion(bm25_results, embed_results, k=7, c=60):
        """
        Fuse BM25 + Embedding rankings using Reciprocal Rank Fusion (RRF).

        Returns:
            list of chunk_ids (top-k fused)
        """
        ranks = defaultdict(float)

        # BM25 contribution
        for rank, chunk in enumerate(bm25_results, start=1):
            ranks[chunk["id"]] += 1.0 / (c + rank)

        # Embedding contribution
        for rank, chunk in enumerate(embed_results, start=1):
            ranks[chunk["id"]] += 1.0 / (c + rank)

        # Sort by fused score
        fused = sorted(ranks.items(), key=lambda x: -x[1])[:k]
        return [cid for cid, _ in fused]

    def weighted_fusion(self, bm25_results, embed_results, topk=7):
        scores = defaultdict(float)
        for rank, c in enumerate(bm25_results, start=1):
            scores[c["id"]] += self.alpha * (1.0 / rank)
        for rank, c in enumerate(embed_results, start=1):
            scores[c["id"]] += (1 - self.alpha) * (1.0 / rank)
        return [cid for cid, _ in sorted(scores.items(), key=lambda x: -x[1])[:topk]]

    def id_search(self, query: str, topk=7, use_bm25=True, book_slug=None):
        """
        Hybrid search with automatic BM25 index loading.

        Args:
            query: Search query
            topk: Number of results to return
            use_bm25: If True, load and use BM25 index. If False, vector-only search.
            book_slug: If provided, only search within this book (e.g., 'aiw', 'gtr')
        """
        if use_bm25 and self.bm25.N == 0:
            try:
                self.load_bm25_index()
            except FileNotFoundError:
                logger.warning("BM25 index not found, using vector-only search")
                use_bm25 = False

        embed_results = self.vec.search(query, topk * 2, book_slug=book_slug)

        if not use_bm25:
            return [c["id"] for c in embed_results[:topk]]

        bm25_results = self.bm25.search(query, topk * 2, book_slug=book_slug)
        return self.weighted_fusion(bm25_results, embed_results, topk)
