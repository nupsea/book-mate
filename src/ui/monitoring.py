"""
Gradio UI adapter for monitoring dashboard.
Uses the UI-agnostic MonitoringDashboard class.
"""

import gradio as gr
import pandas as pd
from src.monitoring.dashboard import MonitoringDashboard


def get_summary_stats_table() -> pd.DataFrame:
    """Get summary statistics as a DataFrame for table display."""
    stats = MonitoringDashboard.get_summary_stats()

    data = {
        "Metric": ["Total Queries", "Success Rate", "Avg Latency", "Errors"],
        "Value": [
            stats['total_queries'],
            f"{stats['success_rate']}%",
            f"{stats['avg_latency_ms']} ms",
            stats['error_count']
        ]
    }

    return pd.DataFrame(data)


def get_llm_assessment_table() -> pd.DataFrame:
    """Get LLM assessment data as a DataFrame."""
    llm_data = MonitoringDashboard.get_llm_assessment_data()

    if llm_data["judged_queries"] == 0:
        return pd.DataFrame({"Quality": [], "Count": [], "Percentage": []})

    data = {
        "Quality": [],
        "Count": [],
        "Percentage": []
    }

    for score in ["EXCELLENT", "ADEQUATE", "POOR"]:
        count = llm_data["scores"][score]
        if count > 0:
            data["Quality"].append(score)
            data["Count"].append(count)
            data["Percentage"].append(f"{llm_data['percentages'][score]}%")

    return pd.DataFrame(data)


def get_user_feedback_table() -> pd.DataFrame:
    """Get user feedback data as a DataFrame."""
    user_data = MonitoringDashboard.get_user_feedback_data()

    if user_data["rated_queries"] == 0:
        return pd.DataFrame({"Rating": [], "Count": []})

    data = {
        "Rating": [],
        "Count": []
    }

    for i in range(5, 0, -1):
        count = user_data["rating_distribution"][i]
        stars = "★" * i
        data["Rating"].append(f"{stars} ({i})")
        data["Count"].append(count)

    return pd.DataFrame(data)


def get_tool_usage_table() -> pd.DataFrame:
    """Get tool usage data as a DataFrame."""
    tool_usage = MonitoringDashboard.get_tool_usage()

    if not tool_usage:
        return pd.DataFrame({"Tool": [], "Calls": []})

    data = {
        "Tool": [],
        "Calls": []
    }

    for tool, count in sorted(tool_usage.items(), key=lambda x: x[1], reverse=True):
        data["Tool"].append(tool)
        data["Calls"].append(count)

    return pd.DataFrame(data)


def get_retry_stats_table() -> pd.DataFrame:
    """Get retry statistics as a DataFrame."""
    retry_stats = MonitoringDashboard.get_retry_stats()

    if retry_stats["total_retries"] == 0:
        return pd.DataFrame({"Metric": [], "Value": []})

    data = {
        "Metric": [
            "Total Retries",
            "Successful Retries",
            "Failed Retries",
            "Fallback to Context"
        ],
        "Value": [
            retry_stats['total_retries'],
            f"{retry_stats['successful_retries']} ({retry_stats['retry_success_rate']}%)",
            retry_stats['failed_retries'],
            retry_stats['fallback_to_context']
        ]
    }

    return pd.DataFrame(data)


def get_latency_distribution_table() -> pd.DataFrame:
    """Get latency distribution as a DataFrame."""
    latency = MonitoringDashboard.get_latency_distribution()

    data = {
        "Latency Range": [],
        "Count": []
    }

    for bucket, count in latency.items():
        data["Latency Range"].append(bucket)
        data["Count"].append(count)

    return pd.DataFrame(data)


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

        gr.Markdown(
            "**[LLM Tracing](http://localhost:6006)** - View detailed OpenAI traces, prompts, and token usage"
        )

        with gr.Row():
            refresh_btn = gr.Button("Refresh Metrics", variant="primary")
            auto_refresh = gr.Checkbox(label="Auto-refresh (every 10s)", value=False)

        with gr.Tabs():
            with gr.Tab("Overview"):
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### Performance Metrics")
                        summary_table = gr.Dataframe(
                            value=get_summary_stats_table(),
                            headers=["Metric", "Value"],
                            datatype=["str", "str"],
                            interactive=False,
                            wrap=True
                        )

                        gr.Markdown("### LLM Self-Assessment")
                        llm_table = gr.Dataframe(
                            value=get_llm_assessment_table(),
                            headers=["Quality", "Count", "Percentage"],
                            datatype=["str", "number", "str"],
                            interactive=False,
                            wrap=True
                        )

                    with gr.Column():
                        gr.Markdown("### User Feedback")
                        user_data = MonitoringDashboard.get_user_feedback_data()
                        if user_data["rated_queries"] > 0:
                            gr.Markdown(f"**Rated Queries:** {user_data['rated_queries']} | **Avg Rating:** {user_data['avg_rating']}/5.0")
                        user_table = gr.Dataframe(
                            value=get_user_feedback_table(),
                            headers=["Rating", "Count"],
                            datatype=["str", "number"],
                            interactive=False,
                            wrap=True
                        )

                        gr.Markdown("### Tool Usage")
                        tool_table = gr.Dataframe(
                            value=get_tool_usage_table(),
                            headers=["Tool", "Calls"],
                            datatype=["str", "number"],
                            interactive=False,
                            wrap=True
                        )

                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### Query Retry Statistics")
                        retry_table = gr.Dataframe(
                            value=get_retry_stats_table(),
                            headers=["Metric", "Value"],
                            datatype=["str", "str"],
                            interactive=False,
                            wrap=True
                        )

            with gr.Tab("Query History"):
                queries_table = gr.Dataframe(
                    value=MonitoringDashboard.get_recent_queries_df(limit=50), wrap=True
                )

            with gr.Tab("Performance"):
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### Latency Distribution")
                        latency_table = gr.Dataframe(
                            value=get_latency_distribution_table(),
                            headers=["Latency Range", "Count"],
                            datatype=["str", "number"],
                            interactive=False,
                            wrap=True
                        )

                    with gr.Column():
                        gr.Markdown("### Recent Errors")
                        errors_display = gr.Markdown(value=format_recent_errors())

        # Refresh handler
        def refresh_all():
            return (
                get_summary_stats_table(),
                get_llm_assessment_table(),
                get_user_feedback_table(),
                get_tool_usage_table(),
                get_retry_stats_table(),
                MonitoringDashboard.get_recent_queries_df(limit=50),
                get_latency_distribution_table(),
                format_recent_errors(),
            )

        # Manual refresh
        refresh_btn.click(
            refresh_all,
            None,
            [
                summary_table,
                llm_table,
                user_table,
                tool_table,
                retry_table,
                queries_table,
                latency_table,
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
                summary_table,
                llm_table,
                user_table,
                tool_table,
                retry_table,
                queries_table,
                latency_table,
                errors_display,
            ],
        )

    return refresh_btn
