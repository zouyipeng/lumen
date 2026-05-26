from langgraph.graph import END
from langgraph.types import Send

from graph.rn_state import RNWorkflowState


def route_after_hero(state: RNWorkflowState):
    """Fan-out to column_processor for each RN column, or skip to integrator if no new commits in incremental mode."""
    rn_config = state.get("rn_config", {})
    columns = rn_config.get("rn_columns", [])
    commits = state.get("commits", [])

    if not columns:
        return END

    # Incremental mode with no new commits: skip column processing, go directly to integrator
    if state.get("mode") == "incremental" and not commits:
        return "integrator"

    return [
        Send("column_processor", {
            "column_config": col,
            "rn_config": rn_config,
            "commits": commits,
            "mr_list": state.get("mr_list", []),
            "cycle_start_date": state.get("cycle_start_date", ""),
            "cycle_end_date": state.get("cycle_end_date", ""),
        })
        for col in columns
    ]
