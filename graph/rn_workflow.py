from langgraph.graph import END, START, StateGraph

from agents.column_processor import column_processor_node
from agents.hero import hero_node
from agents.integrator import integrator_node
from graph.rn_router import route_after_hero
from graph.rn_state import RNWorkflowState


def build_rn_workflow(*, checkpointer=None):
    """Build the Release Note generation workflow graph.

    START → hero → [column_processor_1, ..., column_processor_N] (fan-out) → integrator → END
                 ↘ integrator (incremental mode, no new commits)
    """
    builder = StateGraph(RNWorkflowState)

    builder.add_node("hero", hero_node)
    builder.add_node("column_processor", column_processor_node)
    builder.add_node("integrator", integrator_node)

    builder.add_edge(START, "hero")
    builder.add_conditional_edges("hero", route_after_hero)
    builder.add_edge("column_processor", "integrator")
    builder.add_edge("integrator", END)

    if checkpointer is not None:
        return builder.compile(checkpointer=checkpointer)
    return builder.compile()


# LangGraph Studio / `langgraph dev` entry point
rn_graph = build_rn_workflow()
