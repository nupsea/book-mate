"""
Database persistence layer for metrics.
"""

import psycopg2
from typing import Optional, List, Dict, Any
from src.monitoring.metrics import QueryMetric, LLMRelevanceScore
from src.content.store import DB_CONFIG


class MetricsPersistence:
    """Handles saving and loading metrics from PostgreSQL."""

    def __init__(self, conn=None):
        self.conn = conn or psycopg2.connect(**DB_CONFIG)

    def save_query_metric(self, metric: QueryMetric):
        """Save a single query metric to database."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO query_metrics (
                    query_id, timestamp, query, response, book_slug,
                    latency_ms, success, error_message, tool_calls, num_results,
                    llm_relevance_score, llm_reasoning, user_rating, user_comment,
                    retry_attempted, original_query, rephrased_query, retry_results, fallback_to_context
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (query_id) DO UPDATE SET
                    user_rating = EXCLUDED.user_rating,
                    user_comment = EXCLUDED.user_comment
            """,
                (
                    metric.query_id,
                    metric.timestamp,
                    metric.query,
                    metric.response,
                    metric.book_slug,
                    metric.latency_ms,
                    metric.success,
                    metric.error_message,
                    metric.tool_calls,
                    metric.num_results,
                    (
                        metric.llm_relevance_score.value
                        if metric.llm_relevance_score
                        else None
                    ),
                    metric.llm_reasoning,
                    metric.user_rating,
                    metric.user_comment,
                    metric.retry_attempted,
                    metric.original_query,
                    metric.rephrased_query,
                    metric.retry_results,
                    metric.fallback_to_context,
                ),
            )
        self.conn.commit()

    def update_user_feedback(
        self, query_id: str, rating: int, comment: Optional[str] = None
    ) -> bool:
        """Update user feedback for a specific query."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE query_metrics
                SET user_rating = %s, user_comment = %s
                WHERE query_id = %s
            """,
                (rating, comment, query_id),
            )
            updated = cur.rowcount > 0
        self.conn.commit()
        return updated

    def get_recent_metrics(self, limit: int = 100) -> List[QueryMetric]:
        """Load recent metrics from database."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT query_id, timestamp, query, response, book_slug,
                       latency_ms, success, error_message, tool_calls, num_results,
                       llm_relevance_score, llm_reasoning, user_rating, user_comment,
                       retry_attempted, original_query, rephrased_query, retry_results, fallback_to_context
                FROM query_metrics
                ORDER BY timestamp DESC
                LIMIT %s
            """,
                (limit,),
            )
            rows = cur.fetchall()

        metrics = []
        for row in rows:
            llm_score = LLMRelevanceScore.NOT_JUDGED
            if row[10]:
                try:
                    llm_score = LLMRelevanceScore[row[10]]
                except KeyError:
                    pass

            metric = QueryMetric(
                query_id=row[0],
                timestamp=row[1],
                query=row[2],
                response=row[3] or "",
                book_slug=row[4],
                latency_ms=row[5],
                success=row[6],
                error_message=row[7],
                tool_calls=row[8] or [],
                num_results=row[9],
                llm_relevance_score=llm_score,
                llm_reasoning=row[11],
                user_rating=row[12],
                user_comment=row[13],
                retry_attempted=row[14] or False,
                original_query=row[15],
                rephrased_query=row[16],
                retry_results=row[17],
                fallback_to_context=row[18] or False,
            )
            metrics.append(metric)

        return metrics

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get aggregated statistics from database."""
        with self.conn.cursor() as cur:
            # Overall stats
            cur.execute(
                """
                SELECT
                    COUNT(*) as total_queries,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END) as success_count,
                    SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as error_count,
                    AVG(latency_ms) as avg_latency,
                    COUNT(CASE WHEN user_rating IS NOT NULL THEN 1 END) as rated_queries,
                    AVG(user_rating) as avg_rating
                FROM query_metrics
            """
            )
            row = cur.fetchone()

        if not row or row[0] == 0:
            return {
                "total_queries": 0,
                "success_count": 0,
                "error_count": 0,
                "success_rate": 0.0,
                "avg_latency_ms": 0.0,
                "rated_queries": 0,
                "avg_rating": 0.0,
            }

        total, success, errors, avg_lat, rated, avg_rat = row
        success_rate = (success / total * 100) if total > 0 else 0.0

        return {
            "total_queries": total,
            "success_count": success,
            "error_count": errors,
            "success_rate": round(success_rate, 2),
            "avg_latency_ms": round(avg_lat, 2) if avg_lat else 0.0,
            "rated_queries": rated or 0,
            "avg_rating": round(avg_rat, 2) if avg_rat else 0.0,
        }

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
