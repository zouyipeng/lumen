import json

from graph.rn_state import RNWorkflowState
from tools.excel_tools import write_excel


def _build_excel_data(results: list[dict], commits: list[dict]) -> str:
    """Build JSON data for Excel generation from column results and commits."""
    # Each commit becomes a row; each column result maps to a column value
    columns = ["提交哈希", "提交信息", "作者", "日期"]

    # Add column names from results
    for r in results:
        columns.append(r["column_name"])

    rows = []
    for commit in commits:
        row = [
            commit.get("short_hash", ""),
            commit.get("message", ""),
            commit.get("author", ""),
            commit.get("date", ""),
        ]
        # For each column result, extract the value for this commit
        for r in results:
            structured = r.get("structured_result", {})
            commit_hash = commit.get("hash", "")
            short_hash = commit.get("short_hash", "")
            # Try to find value by full hash, short hash, or "all" key
            value = structured.get(commit_hash) or structured.get(short_hash) or structured.get("all", "")
            row.append(str(value) if value else "")
        rows.append(row)

    return json.dumps({"columns": columns, "rows": rows}, ensure_ascii=False)


def _merge_column_results(existing: list[dict], new: list[dict]) -> list[dict]:
    """Merge existing and new column results. New results override existing for matching column_id."""
    by_id = {r["column_id"]: r for r in existing}
    for r in new:
        by_id[r["column_id"]] = r
    # Preserve original order: existing first, then new columns not in existing
    seen = set()
    merged = []
    for r in existing:
        if r["column_id"] not in seen:
            merged.append(by_id[r["column_id"]])
            seen.add(r["column_id"])
    for r in new:
        if r["column_id"] not in seen:
            merged.append(r)
            seen.add(r["column_id"])
    return merged


def integrator_node(state: RNWorkflowState) -> dict:
    """Integrator agent: collect all column results and generate Excel file."""
    mode = state.get("mode", "full")
    new_results = state.get("column_results", [])
    new_commits = state.get("commits", [])
    config = state.get("rn_config", {})

    excel_config = config.get("excel", {})
    output_path = excel_config.get("output_path", "release_note.xlsx")
    sheet_name = excel_config.get("sheet_name", "Release Note")

    if mode == "incremental":
        existing_commits = state.get("existing_commits", [])
        existing_column_results = state.get("existing_column_results", [])

        # Merge: old commits first, then new commits
        all_commits = existing_commits + new_commits

        # Merge column results: new results override existing for same column_id
        all_results = _merge_column_results(existing_column_results, new_results)

        # Build Excel with merged data
        excel_data = _build_excel_data(all_results, all_commits)

        result_msg = write_excel.invoke({
            "data": excel_data,
            "output_path": output_path,
            "sheet_name": sheet_name,
        })

        approved = sum(1 for r in new_results if r.get("review_status") == "approved")
        total_new = len(new_results)

        return {
            "excel_path": output_path,
            "final_response": (
                f"RN 已增量更新: {output_path}\n"
                f"新增 {len(new_commits)} 条提交，{total_new} 列处理（{approved} 列审核通过）。\n"
                f"总计 {len(all_commits)} 条提交记录。"
            ),
        }

    # Full mode
    excel_data = _build_excel_data(new_results, new_commits)

    result_msg = write_excel.invoke({
        "data": excel_data,
        "output_path": output_path,
        "sheet_name": sheet_name,
    })

    approved = sum(1 for r in new_results if r.get("review_status") == "approved")
    total = len(new_results)

    return {
        "excel_path": output_path,
        "final_response": (
            f"RN 已生成: {output_path}\n"
            f"共 {total} 列，{approved} 列审核通过，"
            f"{total - approved} 列未通过或超限。\n"
            f"包含 {len(new_commits)} 条提交记录。"
        ),
    }
