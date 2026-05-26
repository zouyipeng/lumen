import json
import warnings

from config import resolve_excel_path, resolve_project_path
from graph.rn_state import RNWorkflowState
from tools.excel_tools import (
    copy_template,
    get_excel_layout,
    read_excel_with_layout,
    write_excel_legacy,
    write_excel_with_layout,
)


def _merge_column_results(existing: list[dict], new: list[dict]) -> list[dict]:
    """Merge existing and new column results. New results override existing for matching column_id."""
    by_id = {r["column_id"]: r for r in existing}
    for r in new:
        by_id[r["column_id"]] = r
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


def _build_legacy_excel_data(results: list[dict], commits: list[dict]) -> str:
    """Build JSON data for legacy Excel generation (no template)."""
    columns = ["提交哈希", "提交信息", "作者", "日期"]
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
        for r in results:
            structured = r.get("structured_result", {})
            commit_hash = commit.get("hash", "")
            short_hash = commit.get("short_hash", "")
            value = structured.get(commit_hash) or structured.get(short_hash) or structured.get("all", "")
            row.append(str(value) if value else "")
        rows.append(row)

    return json.dumps({"columns": columns, "rows": rows}, ensure_ascii=False)


def _resolve_output_path(state: RNWorkflowState, excel_config: dict) -> str:
    output_template = excel_config.get("output_path", "release_note.xlsx")
    return resolve_excel_path(output_template, state["version_cycle"])


def _write_excel(state: RNWorkflowState, commits: list[dict], results: list[dict], *, write_metadata: bool) -> str:
    config = state.get("rn_config", {})
    excel_config = config.get("excel", {})
    output_path = _resolve_output_path(state, excel_config)
    sheet_name = excel_config.get("sheet_name", "Release Note")
    template_path = excel_config.get("template_path", "")
    rn_column_defs = config.get("rn_columns", [])
    rn_column_ids = [c["id"] for c in rn_column_defs]
    layout = get_excel_layout(excel_config, rn_column_ids)

    if template_path:
        out = resolve_project_path(output_path)
        if write_metadata or not out.exists():
            copy_template(template_path, output_path)
        write_excel_with_layout(
            output_path,
            sheet_name,
            layout,
            commits,
            results,
            metadata=excel_config.get("metadata"),
            metadata_values={
                "version": state.get("version_cycle", ""),
                "cycle_start": state.get("cycle_start_date", ""),
                "cycle_end": state.get("cycle_end_date", ""),
            },
            write_metadata=write_metadata,
        )
    else:
        excel_data = _build_legacy_excel_data(results, commits)
        write_excel_legacy(excel_data, output_path, sheet_name)

    return output_path


def integrator_node(state: RNWorkflowState) -> dict:
    """Integrator agent: collect all column results and generate Excel file."""
    mode = state.get("mode", "full")
    new_results = state.get("column_results", [])
    new_commits = state.get("commits", [])

    if mode == "incremental":
        existing_commits = state.get("existing_commits", [])
        existing_column_results = state.get("existing_column_results", [])

        all_commits = existing_commits + new_commits
        all_results = _merge_column_results(existing_column_results, new_results)

        config = state.get("rn_config", {})
        excel_config = config.get("excel", {})
        output_path = _resolve_output_path(state, excel_config)
        if excel_config.get("template_path") and not resolve_project_path(output_path).exists():
            warnings.warn(f"增量模式输出文件不存在，已从模板创建: {output_path}")

        _write_excel(state, all_commits, all_results, write_metadata=False)

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

    _write_excel(state, new_commits, new_results, write_metadata=True)

    output_path = _resolve_output_path(state, state.get("rn_config", {}).get("excel", {}))
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
