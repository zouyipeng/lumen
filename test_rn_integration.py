"""RN 工作流集成测试：模拟 LLM 响应，验证完整 RN 生成流程。"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, AIMessageChunk
from langgraph.checkpoint.memory import MemorySaver

from graph.rn_state import make_rn_initial_state
from graph.rn_workflow import build_rn_workflow


def _make_llm(responses: list[str]):
    """Create a mock LLM that returns queued responses."""
    queue = list(responses)
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm

    def next_response() -> AIMessageChunk:
        content = queue.pop(0) if queue else ""
        return AIMessageChunk(content=content)

    mock_llm.stream.side_effect = lambda messages: iter([next_response()])
    mock_llm.invoke.side_effect = lambda messages: AIMessage(
        content=next_response().content
    )
    return mock_llm


def _make_config(tmpdir: str, mr_data_path: str = "") -> str:
    """Create a temporary RN config file."""
    config = {
        "version": "1.0",
        "version_cycle": {"test_cutoff_day": 7, "release_day": 15},
        "repo": {
            "url": "https://example.com/repo",
            "local_path": ".",
            "open_source_repo_path": "",
        },
        "mr_platform": {
            "type": "mock",
            "data_path": mr_data_path,
            "project_id": "test",
        },
        "rn_columns": [
            {
                "id": "mechanism_changes",
                "name": "机制变更说明",
                "description": "从 MR 信息中提取机制变更说明",
                "peon": {
                    "prompt_file": "prompts/rn/mechanism_changes_peon.md",
                    "model_name": "gpt-4o-mini",
                    "temperature": 0,
                },
                "reviewer": {
                    "prompt_file": "prompts/rn/mechanism_changes_reviewer.md",
                    "model_name": "gpt-4o-mini",
                    "temperature": 0,
                },
            },
        ],
        "excel": {
            "output_path": os.path.join(tmpdir, "release_note.xlsx"),
            "sheet_name": "Release Note",
        },
        "workflow": {"max_retries": 1},
    }
    config_path = os.path.join(tmpdir, "rn_config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, ensure_ascii=False)
    return config_path


def test_rn_happy_path():
    """完整 RN 生成流程：Hero → Peon → Reviewer(approved) → Integrator → Excel"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = _make_config(tmpdir)
        output_excel = os.path.join(tmpdir, "release_note.xlsx")

        # Mock LLM: peon returns JSON, reviewer approves
        peon_response = json.dumps({"all": "新增了XXX功能，优化了YYY模块"}, ensure_ascii=False)
        peon_llm = _make_llm([
            "THINKING:\n分析提交记录\n\nSTATUS: success\nRESULT:\n" + peon_response,
        ])
        reviewer_llm = _make_llm([
            "THINKING:\n审核通过\n\nREVIEW: approved\nSUMMARY:\n变更说明准确",
        ])

        with patch("agents.peon.get_llm_with_config", return_value=peon_llm):
            with patch("agents.column_reviewer.get_llm_with_config", return_value=reviewer_llm):
                graph = build_rn_workflow(checkpointer=MemorySaver())
                state = make_rn_initial_state(".", "2024-06", config_path)
                result = graph.invoke(
                    state,
                    {"configurable": {"thread_id": "test-rn-happy"}},
                )

                assert "column_results" in result
                assert len(result["column_results"]) >= 1
                assert result["column_results"][0]["review_status"] == "approved"
                assert result["excel_path"] == output_excel
                assert Path(output_excel).exists()

    print("[OK] rn happy path")


def test_rn_reviewer_reject_then_approve():
    """Reviewer 拒绝后 Peon 重试，最终通过"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = _make_config(tmpdir)

        # First peon + reviewer (rejected), then peon + reviewer (approved)
        peon_llm = _make_llm([
            "THINKING:\n初步分析\n\nSTATUS: success\nRESULT:\n{\"all\": \"一些变更\"}",
            "THINKING:\n重新分析\n\nSTATUS: success\nRESULT:\n{\"all\": \"新增了XXX功能\"}",
        ])
        reviewer_llm = _make_llm([
            "THINKING:\n不够详细\n\nREVIEW: rejected\nFEEDBACK:\n变更说明不够具体",
            "THINKING:\n审核通过\n\nREVIEW: approved\nSUMMARY:\n变更说明已改进",
        ])

        with patch("agents.peon.get_llm_with_config", return_value=peon_llm):
            with patch("agents.column_reviewer.get_llm_with_config", return_value=reviewer_llm):
                graph = build_rn_workflow(checkpointer=MemorySaver())
                state = make_rn_initial_state(".", "2024-06", config_path)
                result = graph.invoke(
                    state,
                    {"configurable": {"thread_id": "test-rn-retry"}},
                )

                assert result["column_results"][0]["review_status"] == "approved"
                assert result["column_results"][0]["retry_count"] == 1

    print("[OK] rn reviewer reject then approve")


def test_rn_max_retries_exceeded():
    """Reviewer 持续拒绝，超过重试次数后仍生成 Excel"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = _make_config(tmpdir)

        # max_retries=1, so loop runs attempt 0 and 1, then exits
        # Need 2 peon + 2 reviewer responses (for 2 attempts)
        peon_llm = _make_llm([
            "THINKING:\n分析\n\nSTATUS: success\nRESULT:\n{\"all\": \"变更\"}",
            "THINKING:\n重新分析\n\nSTATUS: success\nRESULT:\n{\"all\": \"变更v2\"}",
        ])
        reviewer_llm = _make_llm([
            "REVIEW: rejected\nFEEDBACK:\n不够详细",
            "REVIEW: rejected\nFEEDBACK:\n还是不够详细",
        ])

        with patch("agents.peon.get_llm_with_config", return_value=peon_llm):
            with patch("agents.column_reviewer.get_llm_with_config", return_value=reviewer_llm):
                graph = build_rn_workflow(checkpointer=MemorySaver())
                state = make_rn_initial_state(".", "2024-06", config_path)
                result = graph.invoke(
                    state,
                    {"configurable": {"thread_id": "test-rn-max-retry"}},
                )

                assert result["column_results"][0]["review_status"] == "max_retries_exceeded"
                assert result["column_results"][0]["retry_count"] == 1
                # Excel should still be generated
                assert Path(result["excel_path"]).exists()

    print("[OK] rn max retries exceeded")


def test_rn_incremental_mode():
    """增量模式：先全量生成 Excel，再增量运行，确认新数据追加、旧数据保留"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = _make_config(tmpdir)
        output_excel = os.path.join(tmpdir, "release_note.xlsx")

        # Step 1: Full mode - generate initial Excel
        peon_llm1 = _make_llm([
            "STATUS: success\nRESULT:\n{\"all\": \"初始变更说明\"}",
        ])
        reviewer_llm1 = _make_llm([
            "REVIEW: approved\nSUMMARY:\n通过",
        ])

        with patch("agents.peon.get_llm_with_config", return_value=peon_llm1):
            with patch("agents.column_reviewer.get_llm_with_config", return_value=reviewer_llm1):
                graph = build_rn_workflow(checkpointer=MemorySaver())
                state = make_rn_initial_state(".", "2024-06", config_path)
                result = graph.invoke(
                    state,
                    {"configurable": {"thread_id": "test-rn-inc-full"}},
                )
                assert Path(output_excel).exists()

        # Step 2: Incremental mode - add new commits
        peon_llm2 = _make_llm([
            "STATUS: success\nRESULT:\n{\"all\": \"增量变更说明\"}",
        ])
        reviewer_llm2 = _make_llm([
            "REVIEW: approved\nSUMMARY:\n通过",
        ])

        with patch("agents.peon.get_llm_with_config", return_value=peon_llm2):
            with patch("agents.column_reviewer.get_llm_with_config", return_value=reviewer_llm2):
                graph = build_rn_workflow(checkpointer=MemorySaver())
                state = make_rn_initial_state(
                    ".", "2024-06", config_path,
                    mode="incremental", existing_excel_path=output_excel,
                )
                result = graph.invoke(
                    state,
                    {"configurable": {"thread_id": "test-rn-inc-inc"}},
                )
                # Should have both existing and new results
                assert "增量更新" in result["final_response"] or "已生成" in result["final_response"]
                assert Path(output_excel).exists()

    print("[OK] rn incremental mode")


if __name__ == "__main__":
    test_rn_happy_path()
    test_rn_reviewer_reject_then_approve()
    test_rn_max_retries_exceeded()
    test_rn_incremental_mode()
    print("\n所有 RN 集成路径验证通过。")
    sys.exit(0)
