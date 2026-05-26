import operator
from typing import Annotated, Literal

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class CommitInfo(TypedDict):
    hash: str
    short_hash: str
    author: str
    date: str           # ISO 8601
    message: str


class MRInfo(TypedDict):
    id: str
    title: str
    description: str
    author: str
    labels: list[str]
    source_branch: str
    target_branch: str
    merged_at: str      # ISO 8601


class ColumnResult(TypedDict):
    column_id: str
    column_name: str
    peon_output: str
    structured_result: dict   # {commit_hash: value}
    review_status: Literal["approved", "rejected", "max_retries_exceeded"]
    review_feedback: str
    retry_count: int


class RNWorkflowState(TypedDict):
    messages: Annotated[list, add_messages]
    # 输入
    repo_url: str
    version_cycle: str               # 如 "2024-06" 或 "v3.2.0"
    rn_config_path: str
    rn_config: dict
    mode: str                        # "full" | "incremental"
    existing_excel_path: str         # 增量模式下的已有 Excel 路径
    # Hero 输出
    commits: list[CommitInfo]
    mr_list: list[MRInfo]
    cycle_start_date: str
    cycle_end_date: str
    # 增量模式：已有数据
    existing_commits: list[CommitInfo]
    existing_column_results: list[ColumnResult]
    last_commit_hash: str
    # Fan-out 传参（Send 设置）
    column_config: dict
    # Column Processor 输出（operator.add 累积）
    column_results: Annotated[list[ColumnResult], operator.add]
    # Integrator 输出
    excel_path: str
    final_response: str


def make_rn_initial_state(repo_url: str, version_cycle: str, rn_config_path: str,
                          *, mode: str = "full", existing_excel_path: str = "") -> dict:
    """Create a RNWorkflowState dict with sensible defaults."""
    return {
        "messages": [],
        "repo_url": repo_url,
        "version_cycle": version_cycle,
        "rn_config_path": rn_config_path,
        "rn_config": {},
        "mode": mode,
        "existing_excel_path": existing_excel_path,
        "commits": [],
        "mr_list": [],
        "cycle_start_date": "",
        "cycle_end_date": "",
        "existing_commits": [],
        "existing_column_results": [],
        "last_commit_hash": "",
        "column_config": {},
        "column_results": [],
        "excel_path": "",
        "final_response": "",
    }
