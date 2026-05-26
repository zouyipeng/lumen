import json
import warnings

from config import load_rn_config, resolve_excel_path
from graph.rn_state import RNWorkflowState
from tools.excel_tools import get_excel_layout, read_excel, read_excel_with_layout
from tools.git_tools import git_log
from tools.mr_platform import get_platform


def _compute_cycle_dates(version_cycle: str, config: dict) -> tuple[str, str]:
    """Compute start and end dates for a version cycle.

    version_cycle format: "YYYY-MM" (e.g., "2024-06")
    Logic: start = previous month's (release_day + 1), end = this month's test_cutoff_day
    """
    cycle_config = config.get("version_cycle", {})
    release_day = cycle_config.get("release_day", 15)
    test_cutoff_day = cycle_config.get("test_cutoff_day", 7)

    year, month = map(int, version_cycle.split("-"))

    end_date = f"{year}-{month:02d}-{test_cutoff_day:02d}"

    prev_month = month - 1
    prev_year = year
    if prev_month == 0:
        prev_month = 12
        prev_year = year - 1
    start_date = f"{prev_year}-{prev_month:02d}-{release_day + 1:02d}"

    return start_date, end_date


def _parse_existing_excel_legacy(excel_path: str, sheet_name: str) -> tuple[list[dict], list[dict], str]:
    """Legacy: read Excel with hardcoded first-4-column layout."""
    existing_commits = []
    existing_column_results = []
    last_commit_hash = ""

    excel_json = read_excel.invoke({"input_path": excel_path, "sheet_name": sheet_name})

    try:
        data = json.loads(excel_json) if isinstance(excel_json, str) else excel_json
    except json.JSONDecodeError:
        warnings.warn("读取已有 Excel 失败，将执行全量模式")
        return existing_commits, existing_column_results, last_commit_hash

    columns = data.get("columns", [])
    rows = data.get("rows", [])

    if not columns or not rows:
        return existing_commits, existing_column_results, last_commit_hash

    rn_column_names = columns[4:]

    for row in rows:
        if len(row) < 4:
            continue
        short_hash = row[0]
        existing_commits.append({
            "hash": short_hash,
            "short_hash": short_hash,
            "author": row[2],
            "date": row[3],
            "message": row[1],
        })

    for col_idx, col_name in enumerate(rn_column_names, start=4):
        structured = {}
        for row in rows:
            if col_idx < len(row) and len(row) >= 4:
                short_hash = row[0]
                value = row[col_idx]
                if value:
                    structured[short_hash] = value
        existing_column_results.append({
            "column_id": col_name,
            "column_name": col_name,
            "peon_output": "",
            "structured_result": structured,
            "review_status": "approved",
            "review_feedback": "",
            "retry_count": 0,
        })

    if existing_commits:
        last_commit_hash = existing_commits[-1]["hash"]

    return existing_commits, existing_column_results, last_commit_hash


def _parse_existing_excel(excel_path: str, config: dict) -> tuple[list[dict], list[dict], str]:
    """Read existing Excel using layout config or legacy fallback."""
    excel_config = config.get("excel", {})
    sheet_name = excel_config.get("sheet_name", "Release Note")
    rn_column_defs = config.get("rn_columns", [])
    rn_column_ids = [c["id"] for c in rn_column_defs]
    layout = get_excel_layout(excel_config, rn_column_ids)

    if excel_config.get("template_path") or excel_config.get("layout"):
        parsed = read_excel_with_layout(excel_path, sheet_name, layout, rn_column_defs)
        return (
            parsed["commits"],
            parsed["column_results"],
            parsed["last_commit_hash"],
        )

    return _parse_existing_excel_legacy(excel_path, sheet_name)


def _resolve_existing_excel_path(state: RNWorkflowState, excel_config: dict) -> str:
    if state.get("existing_excel_path"):
        return state["existing_excel_path"]
    output_template = excel_config.get("output_path", "release_note.xlsx")
    return resolve_excel_path(output_template, state["version_cycle"])


def hero_node(state: RNWorkflowState) -> dict:
    """Hero agent: load config, fetch commits and MRs for the version cycle."""
    config = load_rn_config(state["rn_config_path"])
    mode = state.get("mode", "full")

    if mode == "incremental":
        return _hero_incremental(state, config)
    return _hero_full(state, config)


def _hero_full(state: RNWorkflowState, config: dict) -> dict:
    """Full mode: fetch all commits and MRs for the version cycle."""
    start_date, end_date = _compute_cycle_dates(state["version_cycle"], config)

    repo_config = config.get("repo", {})
    local_path = repo_config.get("local_path", "")
    commits_json = git_log.invoke({"repo_path": local_path, "since": start_date, "until": end_date})

    try:
        commits = json.loads(commits_json) if isinstance(commits_json, str) else commits_json
    except json.JSONDecodeError:
        warnings.warn("git_log 返回的 JSON 解析失败，已跳过提交记录")
        commits = []

    mr_config = config.get("mr_platform", {})
    platform_type = mr_config.get("type", "mock")
    data_path = mr_config.get("data_path", "")
    project_id = mr_config.get("project_id", "")

    try:
        platform = get_platform(platform_type, data_path=data_path)
        mr_list = platform.fetch_mrs(project_id, start_date, end_date)
    except Exception as exc:
        warnings.warn(f"获取 MR 列表失败: {exc}")
        mr_list = []

    return {
        "rn_config": config,
        "commits": commits,
        "mr_list": mr_list,
        "cycle_start_date": start_date,
        "cycle_end_date": end_date,
    }


def _hero_incremental(state: RNWorkflowState, config: dict) -> dict:
    """Incremental mode: read existing Excel, fetch only new commits and MRs."""
    excel_config = config.get("excel", {})
    existing_excel_path = _resolve_existing_excel_path(state, excel_config)

    existing_commits, existing_column_results, last_commit_hash = _parse_existing_excel(
        existing_excel_path, config
    )

    if not last_commit_hash:
        warnings.warn("增量模式无法从已有 Excel 中提取最后 commit hash，回退到全量模式")
        return _hero_full(state, config)

    repo_config = config.get("repo", {})
    local_path = repo_config.get("local_path", "")
    commits_json = git_log.invoke({
        "repo_path": local_path,
        "since": "",
        "until": "",
        "since_commit": last_commit_hash,
    })

    try:
        commits = json.loads(commits_json) if isinstance(commits_json, str) else commits_json
    except json.JSONDecodeError:
        warnings.warn("git_log 增量返回的 JSON 解析失败，已跳过提交记录")
        commits = []

    last_commit_date = ""
    if existing_commits:
        last_commit_date = existing_commits[-1].get("date", "")[:10]

    mr_config = config.get("mr_platform", {})
    platform_type = mr_config.get("type", "mock")
    data_path = mr_config.get("data_path", "")
    project_id = mr_config.get("project_id", "")

    mr_list = []
    if last_commit_date:
        try:
            platform = get_platform(platform_type, data_path=data_path)
            from datetime import date
            today = date.today().isoformat()
            mr_list = platform.fetch_mrs(project_id, last_commit_date, today)
        except Exception as exc:
            warnings.warn(f"获取增量 MR 列表失败: {exc}")

    start_date, end_date = _compute_cycle_dates(state["version_cycle"], config)

    return {
        "rn_config": config,
        "commits": commits,
        "mr_list": mr_list,
        "cycle_start_date": start_date,
        "cycle_end_date": end_date,
        "existing_commits": existing_commits,
        "existing_column_results": existing_column_results,
        "last_commit_hash": last_commit_hash,
    }
