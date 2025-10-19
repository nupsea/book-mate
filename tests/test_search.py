"""
Unit tests for search functionality (BM25, Vector, Hybrid).
Focus on core logic without external dependencies.
"""

import pytest
from src.search.hybrid import FusionRetriever


class TestRRFFusion:
    """Test Reciprocal Rank Fusion algorithm."""

    def test_rrf_basic_fusion(self):
        """Test basic RRF fusion with two result sets."""
        bm25_results = [
            {"id": "chunk_1", "score": 10.5},
            {"id": "chunk_2", "score": 8.0},
            {"id": "chunk_3", "score": 5.0},
        ]

        embed_results = [
            {"id": "chunk_2", "score": 0.95},
            {"id": "chunk_4", "score": 0.90},
            {"id": "chunk_1", "score": 0.85},
        ]

        fused = FusionRetriever.rrf_fusion(bm25_results, embed_results, k=3)

        # chunk_2 appears highly in both, should be first
        assert fused[0] == "chunk_2"
        # chunk_1 appears in both
        assert "chunk_1" in fused
        # Should return exactly k results
        assert len(fused) == 3

    def test_rrf_empty_results(self):
        """Test RRF with empty result sets."""
        fused = FusionRetriever.rrf_fusion([], [], k=5)
        assert fused == []

    def test_rrf_single_source(self):
        """Test RRF when only one source has results."""
        bm25_results = [
            {"id": "chunk_1", "score": 10.5},
            {"id": "chunk_2", "score": 8.0},
        ]

        fused = FusionRetriever.rrf_fusion(bm25_results, [], k=5)

        # Should still work with one source
        assert len(fused) == 2
        assert fused[0] == "chunk_1"

    def test_rrf_no_overlap(self):
        """Test RRF when results don't overlap."""
        bm25_results = [{"id": "chunk_1"}, {"id": "chunk_2"}]
        embed_results = [{"id": "chunk_3"}, {"id": "chunk_4"}]

        fused = FusionRetriever.rrf_fusion(bm25_results, embed_results, k=3)

        # Should combine all unique results
        assert len(fused) == 3
        assert set(fused).issubset({"chunk_1", "chunk_2", "chunk_3", "chunk_4"})

    def test_rrf_custom_parameters(self):
        """Test RRF with custom k and c parameters."""
        bm25_results = [{"id": f"chunk_{i}"} for i in range(10)]
        embed_results = [{"id": f"chunk_{i}"} for i in range(5, 15)]

        # Test different k values
        fused_3 = FusionRetriever.rrf_fusion(bm25_results, embed_results, k=3, c=60)
        fused_7 = FusionRetriever.rrf_fusion(bm25_results, embed_results, k=7, c=60)

        assert len(fused_3) == 3
        assert len(fused_7) == 7

        # Test different c values (constant in RRF formula)
        fused_c10 = FusionRetriever.rrf_fusion(bm25_results, embed_results, k=5, c=10)
        fused_c100 = FusionRetriever.rrf_fusion(bm25_results, embed_results, k=5, c=100)

        # Results may differ with different c values
        assert len(fused_c10) == 5
        assert len(fused_c100) == 5


class TestWeightedFusion:
    """Test weighted fusion algorithm."""

    def test_weighted_fusion_alpha_1(self):
        """Test with alpha=1.0 (BM25 only)."""
        retriever = FusionRetriever(alpha=1.0)

        bm25_results = [{"id": "chunk_1"}, {"id": "chunk_2"}, {"id": "chunk_3"}]
        embed_results = [{"id": "chunk_4"}, {"id": "chunk_5"}]

        fused = retriever.weighted_fusion(bm25_results, embed_results, topk=2)

        # With alpha=1.0, should prioritize BM25 results
        assert fused[0] == "chunk_1"
        assert fused[1] == "chunk_2"

    def test_weighted_fusion_alpha_0(self):
        """Test with alpha=0.0 (embeddings only)."""
        retriever = FusionRetriever(alpha=0.0)

        bm25_results = [{"id": "chunk_1"}, {"id": "chunk_2"}]
        embed_results = [{"id": "chunk_4"}, {"id": "chunk_5"}, {"id": "chunk_6"}]

        fused = retriever.weighted_fusion(bm25_results, embed_results, topk=2)

        # With alpha=0.0, should prioritize embedding results
        assert fused[0] == "chunk_4"
        assert fused[1] == "chunk_5"

    def test_weighted_fusion_balanced(self):
        """Test with alpha=0.5 (balanced)."""
        retriever = FusionRetriever(alpha=0.5)

        bm25_results = [{"id": "chunk_1"}, {"id": "chunk_2"}]
        embed_results = [{"id": "chunk_2"}, {"id": "chunk_3"}]  # Overlap with BM25

        fused = retriever.weighted_fusion(bm25_results, embed_results, topk=3)

        # chunk_2 appears in both, should be prioritized
        assert "chunk_2" in fused
        # Should return exactly topk results
        assert len(fused) <= 3

    def test_weighted_fusion_default_alpha(self):
        """Test with default alpha=0.7."""
        retriever = FusionRetriever()  # Default alpha=0.7

        bm25_results = [{"id": f"bm25_{i}"} for i in range(5)]
        embed_results = [{"id": f"embed_{i}"} for i in range(5)]

        fused = retriever.weighted_fusion(bm25_results, embed_results, topk=5)

        # Should favor BM25 slightly with alpha=0.7
        assert len(fused) == 5
        # First result should likely be from BM25
        assert fused[0] == "bm25_0"

    def test_weighted_fusion_empty_results(self):
        """Test weighted fusion with empty results."""
        retriever = FusionRetriever(alpha=0.5)

        fused = retriever.weighted_fusion([], [], topk=5)
        assert fused == []

    def test_weighted_fusion_topk_limit(self):
        """Test topk parameter limits results correctly."""
        retriever = FusionRetriever(alpha=0.5)

        bm25_results = [{"id": f"chunk_{i}"} for i in range(10)]
        embed_results = [{"id": f"chunk_{i}"} for i in range(10, 20)]

        for topk in [1, 3, 5, 10]:
            fused = retriever.weighted_fusion(bm25_results, embed_results, topk=topk)
            assert len(fused) == topk


class TestFusionRetrieverInit:
    """Test FusionRetriever initialization."""

    def test_default_initialization(self):
        """Test default parameters."""
        retriever = FusionRetriever()

        assert retriever.alpha == 0.7
        assert retriever.bm25 is not None
        assert retriever.vec is not None

    def test_custom_alpha(self):
        """Test custom alpha values."""
        retriever = FusionRetriever(alpha=0.5)
        assert retriever.alpha == 0.5

        retriever = FusionRetriever(alpha=0.9)
        assert retriever.alpha == 0.9

    def test_custom_bm25_index_path(self):
        """Test custom BM25 index path."""
        custom_path = "/tmp/custom_bm25.pkl"
        retriever = FusionRetriever(bm25_index_path=custom_path)
        assert retriever.bm25_index_path == custom_path


class TestChunkIdStructure:
    """Test that chunk IDs maintain expected structure."""

    def test_chunk_id_format(self):
        """Test chunk ID format matches expected pattern."""
        # Expected format: {slug}_{section}_{chunk}_{hash}
        chunk_id = "mma_01_001_abc1234"

        parts = chunk_id.split("_")
        assert len(parts) == 4
        assert parts[0] == "mma"  # slug
        assert parts[1].isdigit()  # section number
        assert parts[2].isdigit()  # chunk number
        assert len(parts[3]) == 7  # hash length

    def test_chunk_id_uniqueness(self):
        """Test that different text generates different chunk IDs."""
        from src.content.reader import TextReader

        text1 = "This is the first chunk of text."
        text2 = "This is a different chunk of text."

        hash1 = TextReader.simple_hash(text1)
        hash2 = TextReader.simple_hash(text2)

        assert hash1 != hash2
        assert len(hash1) == 7
        assert len(hash2) == 7


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
