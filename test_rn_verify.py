"""RN 工作流组件验证（无需 LLM API Key）。"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from config import get_llm_with_config, load_rn_config, load_prompt_from_file
from graph.rn_router import route_after_hero
from graph.rn_state import make_rn_initial_state
from graph.rn_workflow import build_rn_workflow
from langgraph.checkpoint.memory import MemorySaver
from tools.git_tools import git_log
from tools.mr_platform import MockMRPlatform, get_platform
from tools.excel_tools import write_excel, read_excel


def test_rn_config():
    """测试 RN 配置加载。"""
    config = load_rn_config("rn_config.example.json")
    assert config["version"] == "1.0"
    assert config["version_cycle"]["test_cutoff_day"] == 7
    assert config["version_cycle"]["release_day"] == 15
    assert len(config["rn_columns"]) == 2
    assert config["rn_columns"][0]["id"] == "mechanism_changes"
    assert config["rn_columns"][1]["id"] == "open_source_sync"
    print("[OK] rn config")


def test_rn_initial_state():
    """测试 RN 初始状态创建。"""
    state = make_rn_initial_state("https://example.com/repo", "2024-06", "rn_config.json")
    assert state["repo_url"] == "https://example.com/repo"
    assert state["version_cycle"] == "2024-06"
    assert state["rn_config_path"] == "rn_config.json"
    assert state["commits"] == []
    assert state["mr_list"] == []
    assert state["column_results"] == []
    assert state["mode"] == "full"
    assert state["existing_excel_path"] == ""
    assert state["existing_commits"] == []

    # Incremental mode
    state_inc = make_rn_initial_state("https://example.com/repo", "2024-06", "rn_config.json",
                                       mode="incremental", existing_excel_path="rn.xlsx")
    assert state_inc["mode"] == "incremental"
    assert state_inc["existing_excel_path"] == "rn.xlsx"
    print("[OK] rn initial state")


def test_route_after_hero():
    """测试 Hero 后路由逻辑。"""
    # No columns → END
    state_no_cols = {"rn_config": {"rn_columns": []}}
    result = route_after_hero(state_no_cols)
    assert result == "__end__"

    # With columns → fan-out
    columns = [
        {"id": "col1", "name": "列1", "peon": {}, "reviewer": {}},
        {"id": "col2", "name": "列2", "peon": {}, "reviewer": {}},
    ]
    state_with_cols = {"rn_config": {"rn_columns": columns}, "commits": [{"hash": "abc"}]}
    result = route_after_hero(state_with_cols)
    assert len(result) == 2
    assert result[0].node == "column_processor"
    assert result[1].node == "column_processor"

    # Incremental mode with no new commits → integrator
    state_inc_no_new = {"rn_config": {"rn_columns": columns}, "commits": [], "mode": "incremental"}
    result = route_after_hero(state_inc_no_new)
    assert result == "integrator"

    # Incremental mode with new commits → fan-out
    state_inc_with_new = {"rn_config": {"rn_columns": columns}, "commits": [{"hash": "abc"}], "mode": "incremental"}
    result = route_after_hero(state_inc_with_new)
    assert len(result) == 2

    print("[OK] route after hero")


def test_git_log():
    """测试 git_log 工具（使用当前仓库）。"""
    result = git_log.invoke({
        "repo_path": ".",
        "since": "2024-01-01",
        "until": "2030-01-01",
    })
    # Should return valid JSON
    commits = json.loads(result)
    assert isinstance(commits, list)
    if commits:
        assert "hash" in commits[0]
        assert "short_hash" in commits[0]
        assert "author" in commits[0]
        assert "date" in commits[0]
        assert "message" in commits[0]
    print("[OK] git log")


def test_mock_mr_platform():
    """测试 Mock MR 平台。"""
    # Create temp mock data
    mock_data = [
        {
            "id": "1",
            "title": "Test MR",
            "description": "Test description",
            "author": "test",
            "labels": [],
            "source_branch": "feature",
            "target_branch": "main",
            "merged_at": "2024-06-05T10:00:00+08:00",
        }
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(mock_data, f)
        tmp_path = f.name

    try:
        platform = MockMRPlatform(data_path=tmp_path)
        mrs = platform.fetch_mrs("test-project", "2024-06-01", "2024-06-10")
        assert len(mrs) == 1
        assert mrs[0]["title"] == "Test MR"

        # Out of range
        mrs_empty = platform.fetch_mrs("test-project", "2024-07-01", "2024-07-10")
        assert len(mrs_empty) == 0
    finally:
        os.unlink(tmp_path)

    print("[OK] mock mr platform")


def test_write_excel():
    """测试 Excel 生成工具。"""
    data = json.dumps({
        "columns": ["提交哈希", "提交信息", "机制变更说明"],
        "rows": [
            ["abc1234", "feat: add feature", "新增了XXX功能"],
            ["def5678", "fix: bug fix", "修复了YYY问题"],
        ],
    }, ensure_ascii=False)

    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "test_rn.xlsx")
        result = write_excel.invoke({
            "data": data,
            "output_path": output,
            "sheet_name": "Test",
        })
        assert "成功" in result
        assert Path(output).exists()
    print("[OK] write excel")


def test_read_excel():
    """测试 Excel 读取工具。"""
    data = json.dumps({
        "columns": ["提交哈希", "提交信息", "机制变更说明"],
        "rows": [
            ["abc1234", "feat: add feature", "新增了XXX功能"],
            ["def5678", "fix: bug fix", "修复了YYY问题"],
        ],
    }, ensure_ascii=False)

    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "test_read.xlsx")
        write_excel.invoke({"data": data, "output_path": output, "sheet_name": "Test"})

        # Read back
        result = read_excel.invoke({"input_path": output, "sheet_name": "Test"})
        parsed = json.loads(result)
        assert parsed["columns"] == ["提交哈希", "提交信息", "机制变更说明"]
        assert len(parsed["rows"]) == 2
        assert parsed["rows"][0][0] == "abc1234"
        assert parsed["rows"][1][2] == "修复了YYY问题"

        # Non-existent file
        result_empty = read_excel.invoke({"input_path": "/nonexistent.xlsx", "sheet_name": "Test"})
        parsed_empty = json.loads(result_empty)
        assert parsed_empty["columns"] == []
        assert parsed_empty["rows"] == []

    print("[OK] read excel")


def test_git_log_since_commit():
    """测试 git_log since_commit 参数（使用当前仓库）。"""
    # Get a commit hash first
    result = git_log.invoke({
        "repo_path": ".",
        "since": "2024-01-01",
        "until": "2030-01-01",
    })
    commits = json.loads(result)
    if len(commits) >= 2:
        # Use the second-to-last commit as since_commit
        since_hash = commits[1]["hash"]
        result_inc = git_log.invoke({
            "repo_path": ".",
            "since": "",
            "until": "",
            "since_commit": since_hash,
        })
        inc_commits = json.loads(result_inc)
        assert isinstance(inc_commits, list)
        # Should have at least 1 commit (the most recent one)
        assert len(inc_commits) >= 1
        # The since_commit itself should NOT be in the result
        for c in inc_commits:
            assert c["hash"] != since_hash
    print("[OK] git log since commit")


def test_rn_graph_compile():
    """测试 RN 工作流图编译。"""
    graph = build_rn_workflow(checkpointer=MemorySaver())
    nodes = set(graph.get_graph().nodes.keys())
    assert "hero" in nodes
    assert "column_processor" in nodes
    assert "integrator" in nodes
    print("[OK] rn graph compile")


def test_get_llm_with_config():
    """测试列级 LLM 配置。"""
    config = {"model_name": "gpt-4o", "temperature": 0.5}
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "MODEL_NAME": "gpt-4o-mini"}):
        llm = get_llm_with_config(config)
        assert llm.model_name == "gpt-4o"
        assert llm.temperature == 0.5
    print("[OK] get llm with config")


def test_load_prompt_from_file():
    """测试从文件加载提示词。"""
    content = load_prompt_from_file("prompts/rn/hero.md")
    assert "Hero Agent" in content
    print("[OK] load prompt from file")


if __name__ == "__main__":
    test_rn_config()
    test_rn_initial_state()
    test_route_after_hero()
    test_git_log()
    test_mock_mr_platform()
    test_write_excel()
    test_read_excel()
    test_git_log_since_commit()
    test_rn_graph_compile()
    test_get_llm_with_config()
    test_load_prompt_from_file()
    print("\n所有 RN 组件验证通过。")
    sys.exit(0)
