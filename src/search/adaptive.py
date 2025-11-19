"""
Adaptive hybrid search with dynamic alpha and query preprocessing.
"""

import re
import logging
from src.search.hybrid import FusionRetriever

logger = logging.getLogger(__name__)


class AdaptiveRetriever(FusionRetriever):
    """
    Enhanced FusionRetriever with:
    1. Dynamic alpha based on query type
    2. Query preprocessing (stop word removal)
    3. Increased candidate pool for better fusion
    """

    # Common stop words to remove
    STOP_WORDS = {
        "what",
        "when",
        "where",
        "who",
        "why",
        "how",
        "does",
        "do",
        "did",
        "is",
        "are",
        "was",
        "were",
        "the",
        "a",
        "an",
        "about",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "this",
        "that",
        "these",
        "those",
        "and",
        "or",
        "but",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_alpha = kwargs.get("alpha", 0.7)

    def preprocess_query(self, query: str) -> str:
        """
        Preprocess query to improve keyword matching.

        Args:
            query: Raw user query

        Returns:
            Preprocessed query with stop words removed
        """
        # Convert to lowercase
        query_lower = query.lower()

        # Remove punctuation except hyphens
        query_clean = re.sub(r"[^\w\s-]", " ", query_lower)

        # Split and filter stop words
        words = query_clean.split()
        filtered_words = [w for w in words if w not in self.STOP_WORDS and len(w) > 2]

        # If we filtered out everything, return original query
        if not filtered_words:
            return query

        return " ".join(filtered_words)

    def get_dynamic_alpha(self, query: str) -> float:
        """
        Determine optimal alpha based on query characteristics.

        Note: Testing showed fixed α=0.7 performs better than dynamic alpha.
        This method is kept for potential future use.

        Args:
            query: User query

        Returns:
            Dynamic alpha value (0.0 to 1.0)
        """
        # Question queries benefit from semantic search
        if "?" in query:
            return 0.5  # Balanced approach for questions

        # Very short keyword queries benefit from BM25
        word_count = len(query.split())
        if word_count <= 3:
            return 0.8  # Heavy BM25 for keywords

        # Medium-length queries use base alpha
        if word_count <= 8:
            return self.base_alpha  # Default 0.7

        # Long descriptive queries benefit from semantic
        return 0.6  # Slightly more semantic weight

    def search(
        self,
        query: str,
        topk: int = 7,
        use_preprocessing: bool = True,
        use_dynamic_alpha: bool = False,
        candidate_multiplier: int = 3,
        book_slug: str = None,
    ):
        """
        Adaptive search with query preprocessing.

        Key improvement: Query preprocessing (stop word removal) provides +8% Hit@5.
        Recommended: use_preprocessing=True, use_dynamic_alpha=False (fixed α=0.7)

        Args:
            query: Search query
            topk: Number of results to return
            use_preprocessing: Whether to preprocess query (recommended: True)
            use_dynamic_alpha: Whether to use dynamic alpha (recommended: False, use fixed α=0.7)
            candidate_multiplier: Retrieve topk * multiplier candidates before fusion
            book_slug: If provided, only search within this book (e.g., 'aiw', 'gtr')

        Returns:
            List of chunk IDs
        """
        # Determine alpha
        if use_dynamic_alpha:
            alpha = self.get_dynamic_alpha(query)
        else:
            alpha = self.base_alpha

        # Preprocess query
        if use_preprocessing:
            processed_query = self.preprocess_query(query)
        else:
            processed_query = query

        # Load BM25 index if needed
        if self.bm25.N == 0:
            try:
                self.load_bm25_index()
            except FileNotFoundError:
                logger.warning("BM25 index not found, using vector-only search")
                embed_results = self.vec.search(query, topk, book_slug=book_slug)
                return [c["id"] for c in embed_results]

        # Retrieve more candidates for better fusion
        candidate_count = topk * candidate_multiplier

        # Get results from both systems with book filtering
        embed_results = self.vec.search(query, candidate_count, book_slug=book_slug)
        bm25_results = self.bm25.search(processed_query, candidate_count, book_slug=book_slug)

        # Apply weighted fusion with dynamic alpha
        scores = {}
        for rank, c in enumerate(bm25_results, start=1):
            scores[c["id"]] = scores.get(c["id"], 0) + alpha * (1.0 / rank)

        for rank, c in enumerate(embed_results, start=1):
            scores[c["id"]] = scores.get(c["id"], 0) + (1 - alpha) * (1.0 / rank)

        # Sort and return top-k
        sorted_results = sorted(scores.items(), key=lambda x: -x[1])[:topk]
        return [cid for cid, _ in sorted_results]

    def id_search(self, query: str, topk: int = 7, **kwargs):
        """Alias for search() to maintain compatibility."""
        return self.search(query, topk, **kwargs)


if __name__ == "__main__":
    # Test preprocessing
    retriever = AdaptiveRetriever()

    test_queries = [
        "What does Telemachus feel about the suitors?",
        "Odysseus Cyclops",
        "Why did Ulysses reveal his true name to the Cyclops?",
        "golden sandals",
    ]

    print("=== Query Preprocessing Test ===\n")
    for query in test_queries:
        processed = retriever.preprocess_query(query)
        alpha = retriever.get_dynamic_alpha(query)
        print(f"Original: {query}")
        print(f"Processed: {processed}")
        print(f"Alpha: {alpha}")
        print()
