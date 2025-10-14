"""
UI-agnostic dashboard data provider for monitoring metrics.
Can be used with Gradio, Grafana, Streamlit, or any other visualization tool.
"""
from typing import Dict, List, Any
import pandas as pd
from src.monitoring.metrics import metrics_collector


class MonitoringDashboard:
    """Provides monitoring data in a UI-agnostic format."""

    @staticmethod
    def get_summary_stats() -> Dict[str, Any]:
        """
        Get high-level summary statistics.

        Returns:
            Dictionary with summary metrics suitable for any UI framework.
        """
        stats = metrics_collector.get_statistics()

        return {
            "total_queries": stats["total_queries"],
            "success_rate": stats["success_rate"],
            "avg_latency_ms": stats["avg_latency_ms"],
            "error_count": stats["error_count"],
            "success_count": stats["success_count"]
        }

    @staticmethod
    def get_llm_assessment_data() -> Dict[str, Any]:
        """
        Get LLM self-assessment data.

        Returns:
            Dictionary with LLM assessment metrics.
        """
        stats = metrics_collector.get_statistics()
        llm_data = stats["llm_assessment"]

        return {
            "judged_queries": llm_data.get("judged_queries", 0),
            "distribution": llm_data.get("distribution", {}),
            "scores": {
                "EXCELLENT": llm_data.get("distribution", {}).get("EXCELLENT", {}).get("count", 0),
                "ADEQUATE": llm_data.get("distribution", {}).get("ADEQUATE", {}).get("count", 0),
                "POOR": llm_data.get("distribution", {}).get("POOR", {}).get("count", 0)
            },
            "percentages": {
                "EXCELLENT": llm_data.get("distribution", {}).get("EXCELLENT", {}).get("percentage", 0),
                "ADEQUATE": llm_data.get("distribution", {}).get("ADEQUATE", {}).get("percentage", 0),
                "POOR": llm_data.get("distribution", {}).get("POOR", {}).get("percentage", 0)
            }
        }

    @staticmethod
    def get_user_feedback_data() -> Dict[str, Any]:
        """
        Get user feedback statistics.

        Returns:
            Dictionary with user feedback metrics.
        """
        stats = metrics_collector.get_statistics()
        user_feedback = stats.get("user_feedback", {})

        if not user_feedback or user_feedback.get("rated_queries", 0) == 0:
            return {
                "rated_queries": 0,
                "avg_rating": 0.0,
                "rating_distribution": {i: 0 for i in range(1, 6)}
            }

        rating_dist = user_feedback.get("rating_distribution", {})

        return {
            "rated_queries": user_feedback["rated_queries"],
            "avg_rating": user_feedback["avg_rating"],
            "rating_distribution": {
                i: rating_dist.get(f"{i}_stars", 0) for i in range(1, 6)
            }
        }

    @staticmethod
    def get_tool_usage() -> Dict[str, int]:
        """
        Get tool usage statistics.

        Returns:
            Dictionary mapping tool names to call counts.
        """
        stats = metrics_collector.get_statistics()
        return stats.get("tool_usage", {})

    @staticmethod
    def get_latency_distribution() -> Dict[str, int]:
        """
        Get latency distribution buckets.

        Returns:
            Dictionary with latency bucket counts.
        """
        return metrics_collector.get_latency_buckets()

    @staticmethod
    def get_recent_queries_df(limit: int = 20) -> pd.DataFrame:
        """
        Get recent queries as a pandas DataFrame.

        Args:
            limit: Number of recent queries to return

        Returns:
            DataFrame with query details.
        """
        queries = metrics_collector.get_recent_queries(limit=limit)

        if not queries:
            return pd.DataFrame(columns=[
                "query_id", "timestamp", "query", "book", "latency_ms",
                "success", "llm_score", "user_rating"
            ])

        return pd.DataFrame(queries)

    @staticmethod
    def get_recent_errors(limit: int = 10) -> List[Dict[str, str]]:
        """
        Get recent error details.

        Args:
            limit: Maximum number of errors to return

        Returns:
            List of error dictionaries with timestamp, query, and error message.
        """
        stats = metrics_collector.get_statistics()
        return stats.get("recent_errors", [])[:limit]

    @staticmethod
    def get_all_metrics() -> Dict[str, Any]:
        """
        Get all metrics in a single call.
        Useful for external integrations (REST API, Grafana, etc.).

        Returns:
            Complete metrics dictionary.
        """
        return {
            "summary": MonitoringDashboard.get_summary_stats(),
            "llm_assessment": MonitoringDashboard.get_llm_assessment_data(),
            "user_feedback": MonitoringDashboard.get_user_feedback_data(),
            "tool_usage": MonitoringDashboard.get_tool_usage(),
            "latency_distribution": MonitoringDashboard.get_latency_distribution(),
            "recent_queries": MonitoringDashboard.get_recent_queries_df().to_dict(orient="records"),
            "recent_errors": MonitoringDashboard.get_recent_errors()
        }
