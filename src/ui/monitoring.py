"""
Gradio UI adapter for monitoring dashboard.
Uses the UI-agnostic MonitoringDashboard class.
"""

import gradio as gr
from src.monitoring.dashboard import MonitoringDashboard


def format_summary_stats() -> str:
    """Format summary statistics as markdown."""
    stats = MonitoringDashboard.get_summary_stats()

    return f"""
## Performance Metrics

**Total Queries:** {stats['total_queries']}
**Success Rate:** {stats['success_rate']}%
**Average Latency:** {stats['avg_latency_ms']} ms
**Errors:** {stats['error_count']}
"""


def format_llm_assessment() -> str:
    """Format LLM assessment data as markdown."""
    llm_data = MonitoringDashboard.get_llm_assessment_data()

    markdown = f"""## LLM Self-Assessment

**Queries Judged:** {llm_data['judged_queries']}

"""

    if llm_data["judged_queries"] > 0:
        for score in ["EXCELLENT", "ADEQUATE", "POOR"]:
            count = llm_data["scores"][score]
            pct = llm_data["percentages"][score]
            if count > 0:
                markdown += f"- **{score}**: {count} ({pct}%)\n"
    else:
        markdown += "_No assessments yet_\n"

    return markdown


def format_user_feedback() -> str:
    """Format user feedback data as markdown."""
    user_data = MonitoringDashboard.get_user_feedback_data()

    if user_data["rated_queries"] == 0:
        return """## User Feedback

_No user ratings yet_
"""

    markdown = f"""## User Feedback

**Rated Queries:** {user_data['rated_queries']}
**Average Rating:** {user_data['avg_rating']}/5.0

**Distribution:**

"""

    for i in range(5, 0, -1):
        count = user_data["rating_distribution"][i]
        stars = "★" * i
        markdown += f"- {stars} ({i}): {count}\n"

    return markdown


def format_tool_usage() -> str:
    """Format tool usage as markdown."""
    tool_usage = MonitoringDashboard.get_tool_usage()

    if not tool_usage:
        return """## Tool Usage

_No tools used yet_
"""

    markdown = "## Tool Usage\n\n"

    for tool, count in sorted(tool_usage.items(), key=lambda x: x[1], reverse=True):
        markdown += f"- **{tool}**: {count} calls\n"

    return markdown


def format_retry_stats() -> str:
    """Format retry statistics as markdown."""
    retry_stats = MonitoringDashboard.get_retry_stats()

    if retry_stats["total_retries"] == 0:
        return """## Query Retry Statistics

_No query retries yet_
"""

    markdown = f"""## Query Retry Statistics

**Total Retries:** {retry_stats['total_retries']}
**Successful Retries:** {retry_stats['successful_retries']} ({retry_stats['retry_success_rate']}%)
**Failed Retries:** {retry_stats['failed_retries']}
**Fallback to Context:** {retry_stats['fallback_to_context']}

_When search returns 0 results, the system automatically rephrases and retries the query. If retry also returns 0 results, the LLM uses available context (summaries) to respond._
"""

    return markdown


def format_latency_distribution() -> str:
    """Format latency distribution as markdown."""
    latency = MonitoringDashboard.get_latency_distribution()

    markdown = "## Latency Distribution\n\n"

    for bucket, count in latency.items():
        bar = "█" * min(count, 50) if count > 0 else ""
        markdown += f"- **{bucket}**: {count} {bar}\n"

    return markdown


def format_recent_errors() -> str:
    """Format recent errors as markdown."""
    errors = MonitoringDashboard.get_recent_errors(limit=5)

    if not errors:
        return "## Recent Errors\n\n_No recent errors_"

    markdown = "## Recent Errors\n\n"

    for err in errors:
        markdown += f"### {err['timestamp']}\n"
        markdown += f"- **Query**: {err['query']}\n"
        markdown += f"- **Error**: `{err['error']}`\n\n"

    return markdown


def create_monitoring_interface():
    """Create the monitoring dashboard tab using Gradio."""

    with gr.Column():
        gr.Markdown("# Monitoring Dashboard")
        gr.Markdown("Real-time metrics for Book Mate performance and quality")

        gr.Markdown(
            "**LLM Tracing:** View detailed OpenAI traces, prompts, and token usage at "
            "[Phoenix Dashboard](http://localhost:6006) (opens in new tab)"
        )

        with gr.Row():
            refresh_btn = gr.Button("Refresh Metrics", variant="primary")
            auto_refresh = gr.Checkbox(label="Auto-refresh (every 10s)", value=False)

        with gr.Tabs():
            with gr.Tab("Overview"):
                with gr.Row():
                    with gr.Column():
                        summary_display = gr.Markdown(value=format_summary_stats())
                        llm_display = gr.Markdown(value=format_llm_assessment())

                    with gr.Column():
                        user_display = gr.Markdown(value=format_user_feedback())
                        tool_display = gr.Markdown(value=format_tool_usage())

                with gr.Row():
                    retry_display = gr.Markdown(value=format_retry_stats())

            with gr.Tab("Query History"):
                queries_table = gr.Dataframe(
                    value=MonitoringDashboard.get_recent_queries_df(limit=50), wrap=True
                )

            with gr.Tab("Performance"):
                latency_display = gr.Markdown(value=format_latency_distribution())
                errors_display = gr.Markdown(value=format_recent_errors())

        # Refresh handler
        def refresh_all():
            return (
                format_summary_stats(),
                format_llm_assessment(),
                format_user_feedback(),
                format_tool_usage(),
                format_retry_stats(),
                MonitoringDashboard.get_recent_queries_df(limit=50),
                format_latency_distribution(),
                format_recent_errors(),
            )

        # Manual refresh
        refresh_btn.click(
            refresh_all,
            None,
            [
                summary_display,
                llm_display,
                user_display,
                tool_display,
                retry_display,
                queries_table,
                latency_display,
                errors_display,
            ],
        )

        # Auto-refresh with timer
        timer = gr.Timer(10)  # 10 seconds

        def auto_refresh_handler(is_enabled):
            """Only refresh if auto-refresh is enabled."""
            if is_enabled:
                return refresh_all()
            else:
                # Return current values (no update)
                return (
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                )

        timer.tick(
            auto_refresh_handler,
            inputs=[auto_refresh],
            outputs=[
                summary_display,
                llm_display,
                user_display,
                tool_display,
                retry_display,
                queries_table,
                latency_display,
                errors_display,
            ],
        )

    return refresh_btn
