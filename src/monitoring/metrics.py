"""
Metrics collector for monitoring Book Mate performance.
"""

import time
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum
import threading
import os


class LLMRelevanceScore(Enum):
    """LLM self-assessment score categories."""

    EXCELLENT = "EXCELLENT"
    ADEQUATE = "ADEQUATE"
    POOR = "POOR"
    NOT_JUDGED = "NOT_JUDGED"


@dataclass
class QueryMetric:
    """Single query metric."""

    timestamp: datetime
    query: str
    response: str
    book_slug: Optional[str]
    latency_ms: float
    success: bool
    error_message: Optional[str] = None
    tool_calls: list[str] = field(default_factory=list)
    num_results: Optional[int] = None

    # LLM Self-Assessment
    llm_relevance_score: LLMRelevanceScore = LLMRelevanceScore.NOT_JUDGED
    llm_reasoning: Optional[str] = None

    # User Feedback
    user_rating: Optional[int] = None  # 1-5 stars
    user_comment: Optional[str] = None

    # Unique ID for feedback tracking
    query_id: Optional[str] = None

    # Query Retry Tracking
    retry_attempted: bool = False
    original_query: Optional[str] = None  # If this is a rephrased query
    rephrased_query: Optional[str] = None  # The rephrased version
    retry_results: Optional[int] = None  # Results from retry attempt
    fallback_to_context: bool = False  # True if LLM used context instead of search


class MetricsCollector:
    """Thread-safe metrics collector."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):
            self.initialized = True
            self.queries: list[QueryMetric] = []
            self.tool_usage: dict[str, int] = defaultdict(int)
            self.error_count: int = 0
            self.success_count: int = 0
            self.total_latency_ms: float = 0.0
            self.llm_score_counts: dict[str, int] = defaultdict(int)
            self.user_rating_counts: dict[int, int] = defaultdict(int)
            self._max_history = 1000  # Keep last 1000 queries in memory

            # Initialize DB persistence if enabled
            self.use_db = os.getenv("PERSIST_METRICS", "true").lower() == "true"
            self.db = None
            if self.use_db:
                try:
                    from src.monitoring.persistence import MetricsPersistence

                    self.db = MetricsPersistence()
                    print("[METRICS] Database persistence enabled")

                    # Load recent metrics from database
                    self._load_from_database()
                except Exception as e:
                    print(f"[METRICS] Database persistence disabled: {e}")
                    self.use_db = False

    def _load_from_database(self):
        """Load recent metrics from database on startup."""
        if not self.db:
            return

        try:
            # Load last 1000 queries from DB
            loaded_metrics = self.db.get_recent_metrics(limit=self._max_history)

            if loaded_metrics:
                print(f"[METRICS] Loaded {len(loaded_metrics)} metrics from database")

                # Populate in-memory structures
                for metric in reversed(
                    loaded_metrics
                ):  # Reverse to maintain chronological order
                    self.queries.append(metric)

                    # Update aggregates
                    if metric.success:
                        self.success_count += 1
                    else:
                        self.error_count += 1

                    self.total_latency_ms += metric.latency_ms

                    # Track tool usage
                    for tool in metric.tool_calls:
                        self.tool_usage[tool] += 1

                    # Track LLM scores
                    self.llm_score_counts[metric.llm_relevance_score.value] += 1

                    # Track user ratings
                    if metric.user_rating is not None:
                        self.user_rating_counts[metric.user_rating] += 1
            else:
                print("[METRICS] No historical metrics found in database")

        except Exception as e:
            print(f"[METRICS] Failed to load from database: {e}")

    def record_query(self, metric: QueryMetric):
        """Record a query metric."""
        with self._lock:
            self.queries.append(metric)

            # Keep only recent queries in memory
            if len(self.queries) > self._max_history:
                self.queries = self.queries[-self._max_history :]

            # Update aggregates
            if metric.success:
                self.success_count += 1
            else:
                self.error_count += 1

            self.total_latency_ms += metric.latency_ms

            # Track tool usage
            for tool in metric.tool_calls:
                self.tool_usage[tool] += 1

            # Track LLM scores
            self.llm_score_counts[metric.llm_relevance_score.value] += 1

            # Track user ratings
            if metric.user_rating is not None:
                self.user_rating_counts[metric.user_rating] += 1

            # Persist to database
            if self.use_db and self.db:
                try:
                    self.db.save_query_metric(metric)
                except Exception as e:
                    print(f"[METRICS] Failed to save to DB: {e}")

    def update_user_feedback(
        self, query_id: str, rating: int, comment: Optional[str] = None
    ):
        """Update user feedback for a specific query."""
        with self._lock:
            # Update in-memory
            updated = False
            for query in reversed(self.queries):
                if query.query_id == query_id:
                    # Remove old rating from counts if exists
                    if query.user_rating is not None:
                        self.user_rating_counts[query.user_rating] -= 1

                    # Update query
                    query.user_rating = rating
                    query.user_comment = comment

                    # Add new rating to counts
                    self.user_rating_counts[rating] += 1
                    updated = True
                    break

            # Update in database
            if self.use_db and self.db:
                try:
                    self.db.update_user_feedback(query_id, rating, comment)
                    updated = True
                except Exception as e:
                    print(f"[METRICS] Failed to update feedback in DB: {e}")

            return updated

    def get_statistics(self) -> dict:
        """Get current statistics."""
        with self._lock:
            total_queries = len(self.queries)

            if total_queries == 0:
                return {
                    "total_queries": 0,
                    "success_count": 0,
                    "error_count": 0,
                    "success_rate": 0.0,
                    "avg_latency_ms": 0.0,
                    "tool_usage": {},
                    "recent_errors": [],
                    "llm_assessment": {"judged_queries": 0, "distribution": {}},
                    "user_feedback": {},
                }

            # Calculate success rate
            success_rate = (
                (self.success_count / (self.success_count + self.error_count)) * 100
                if (self.success_count + self.error_count) > 0
                else 0.0
            )

            # Calculate average latency
            avg_latency = self.total_latency_ms / total_queries

            # Get recent errors (last 10)
            recent_errors = [
                {
                    "timestamp": q.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "query": q.query[:100],
                    "error": q.error_message,
                }
                for q in self.queries[-50:]
                if not q.success
            ][-10:]

            # LLM Assessment Distribution
            judged_queries = sum(
                1
                for q in self.queries
                if q.llm_relevance_score != LLMRelevanceScore.NOT_JUDGED
            )
            llm_assessment = {}

            if judged_queries > 0:
                for score_type in LLMRelevanceScore:
                    count = self.llm_score_counts[score_type.value]
                    if score_type != LLMRelevanceScore.NOT_JUDGED and count > 0:
                        percentage = (count / judged_queries) * 100
                        llm_assessment[score_type.value] = {
                            "count": count,
                            "percentage": round(percentage, 1),
                        }

            # User Feedback Distribution
            rated_queries = sum(1 for q in self.queries if q.user_rating is not None)
            user_feedback = {}

            if rated_queries > 0:
                total_stars = sum(
                    rating * count for rating, count in self.user_rating_counts.items()
                )
                avg_rating = total_stars / rated_queries

                user_feedback = {
                    "rated_queries": rated_queries,
                    "avg_rating": round(avg_rating, 2),
                    "rating_distribution": {
                        f"{stars}_stars": self.user_rating_counts.get(stars, 0)
                        for stars in range(1, 6)
                    },
                }

            return {
                "total_queries": total_queries,
                "success_count": self.success_count,
                "error_count": self.error_count,
                "success_rate": round(success_rate, 2),
                "avg_latency_ms": round(avg_latency, 2),
                "tool_usage": dict(self.tool_usage),
                "recent_errors": recent_errors,
                "llm_assessment": {
                    "judged_queries": judged_queries,
                    "distribution": llm_assessment,
                },
                "user_feedback": user_feedback,
            }

    def get_recent_queries(self, limit: int = 20) -> list[dict]:
        """Get recent queries for display."""
        with self._lock:
            return [
                {
                    "query_id": q.query_id,
                    "timestamp": q.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "query": q.query[:80],
                    "book": q.book_slug or "N/A",
                    "latency_ms": round(q.latency_ms, 2),
                    "success": "OK" if q.success else "FAIL",
                    "tools": ", ".join(q.tool_calls) if q.tool_calls else "None",
                    "llm_score": self._format_llm_score(q.llm_relevance_score),
                    "user_rating": self._format_user_rating(q.user_rating),
                }
                for q in reversed(self.queries[-limit:])
            ]

    def _format_llm_score(self, score: LLMRelevanceScore) -> str:
        """Format LLM score for display."""
        emoji_map = {
            LLMRelevanceScore.EXCELLENT: "🟢 Excellent",
            LLMRelevanceScore.ADEQUATE: "🟡 Adequate",
            LLMRelevanceScore.POOR: "🔴 Poor",
            LLMRelevanceScore.NOT_JUDGED: "⚪ N/A",
        }
        return emoji_map.get(score, "⚪ N/A")

    def _format_user_rating(self, rating: Optional[int]) -> str:
        """Format user rating for display."""
        if rating is None:
            return "○ Not rated"
        return "⭐" * rating + f" ({rating}/5)"

    def get_latency_buckets(self) -> dict[str, int]:
        """Get latency distribution in buckets."""
        with self._lock:
            buckets = {
                "< 1s": 0,
                "1s - 2s": 0,
                "2s - 5s": 0,
                "5s - 10s": 0,
                "> 10s": 0,
            }

            for q in self.queries:
                if q.latency_ms < 1000:
                    buckets["< 1s"] += 1
                elif q.latency_ms < 2000:
                    buckets["1s - 2s"] += 1
                elif q.latency_ms < 5000:
                    buckets["2s - 5s"] += 1
                elif q.latency_ms < 10000:
                    buckets["5s - 10s"] += 1
                else:
                    buckets["> 10s"] += 1

            return buckets

    def reset_metrics(self):
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self.queries.clear()
            self.tool_usage.clear()
            self.error_count = 0
            self.success_count = 0
            self.total_latency_ms = 0.0
            self.llm_score_counts.clear()
            self.user_rating_counts.clear()


# Global singleton instance
metrics_collector = MetricsCollector()


class QueryTimer:
    """Context manager for timing queries."""

    def __init__(self, query: str, book_slug: Optional[str] = None):
        self.query = query
        self.book_slug = book_slug
        self.start_time = None
        self.tool_calls = []
        self.num_results = None
        self.success = True
        self.error_message = None
        self.response = ""
        self.llm_relevance_score = LLMRelevanceScore.NOT_JUDGED
        self.llm_reasoning = None
        self.query_id = None
        self.retry_attempted = False
        self.original_query = None
        self.rephrased_query = None
        self.retry_results = None
        self.fallback_to_context = False

    def __enter__(self):
        self.start_time = time.time()
        # Generate unique ID for this query
        self.query_id = f"{int(time.time() * 1000)}_{id(self)}"
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        latency_ms = (time.time() - self.start_time) * 1000

        if exc_type is not None:
            self.success = False
            self.error_message = str(exc_val)

        metric = QueryMetric(
            timestamp=datetime.now(),
            query=self.query,
            response=self.response,
            book_slug=self.book_slug,
            latency_ms=latency_ms,
            success=self.success,
            error_message=self.error_message,
            tool_calls=self.tool_calls,
            num_results=self.num_results,
            llm_relevance_score=self.llm_relevance_score,
            llm_reasoning=self.llm_reasoning,
            query_id=self.query_id,
            retry_attempted=self.retry_attempted,
            original_query=self.original_query,
            rephrased_query=self.rephrased_query,
            retry_results=self.retry_results,
            fallback_to_context=self.fallback_to_context,
        )

        metrics_collector.record_query(metric)
        return False  # Don't suppress exceptions

    def add_tool_call(self, tool_name: str):
        """Add a tool call to this query."""
        self.tool_calls.append(tool_name)

    def set_num_results(self, count: int):
        """Set number of results returned."""
        self.num_results = count

    def set_response(self, response: str):
        """Set the response text."""
        self.response = response

    def set_llm_assessment(
        self, score: LLMRelevanceScore, reasoning: Optional[str] = None
    ):
        """Set LLM self-assessment score."""
        self.llm_relevance_score = score
        self.llm_reasoning = reasoning

    def set_retry_info(
        self, original_query: str, rephrased_query: str, retry_results: int
    ):
        """Record retry attempt information."""
        self.retry_attempted = True
        self.original_query = original_query
        self.rephrased_query = rephrased_query
        self.retry_results = retry_results

    def set_fallback_to_context(self, enabled: bool = True):
        """Mark that LLM fell back to context knowledge instead of search."""
        self.fallback_to_context = enabled
