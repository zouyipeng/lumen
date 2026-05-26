import json
import subprocess
from pathlib import Path

from langchain_core.tools import tool


@tool
def git_log(repo_path: str, since: str, until: str, since_commit: str = "") -> str:
    """获取指定时间范围内的 git 提交记录。返回 JSON 数组，每项包含 hash, short_hash, author, date, message。
    当 since_commit 非空时，使用 git log <since_commit>..HEAD 获取增量提交，忽略 since/until 参数。"""
    try:
        cmd = ["git", "-C", repo_path, "log",
               "--format={\"hash\":\"%H\",\"short_hash\":\"%h\",\"author\":\"%an\",\"date\":\"%aI\",\"message\":\"%s\"}",
               "--no-merges"]

        if since_commit:
            cmd.append(f"{since_commit}..HEAD")
        else:
            cmd.extend(["--since", since, "--until", until])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return f"错误: git log 失败 - {result.stderr.strip()}"

        lines = [line for line in result.stdout.strip().splitlines() if line.strip()]
        if not lines:
            return json.dumps([], ensure_ascii=False)

        commits = []
        for line in lines:
            try:
                commit = json.loads(line)
                # Escape newlines in message
                commit["message"] = commit.get("message", "").replace("\n", " ")
                commits.append(commit)
            except json.JSONDecodeError:
                continue
        return json.dumps(commits, ensure_ascii=False, indent=2)

    except subprocess.TimeoutExpired:
        return "错误: git log 执行超时"
    except Exception as exc:
        return f"错误: {exc}"


@tool
def git_diff_commits(repo_path: str, commit_hash: str) -> str:
    """获取指定提交的 diff 内容。"""
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "show", "--stat", "--patch", commit_hash],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return f"错误: git show 失败 - {result.stderr.strip()}"
        # Truncate if too long
        output = result.stdout
        if len(output) > 8000:
            output = output[:8000] + "\n... (内容过长，已截断)"
        return output
    except subprocess.TimeoutExpired:
        return "错误: git show 执行超时"
    except Exception as exc:
        return f"错误: {exc}"


@tool
def git_diff_repos(source_repo: str, target_repo: str, since: str) -> str:
    """比较两个仓库的差异，用于判断开源同步。返回源仓库中存在但目标仓库中不存在的提交。"""
    try:
        # Get commits in source since the given date
        result = subprocess.run(
            [
                "git", "-C", source_repo, "log",
                "--format={\"hash\":\"%H\",\"short_hash\":\"%h\",\"author\":\"%an\",\"date\":\"%aI\",\"message\":\"%s\"}",
                "--since", since,
                "--no-merges",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return f"错误: 获取源仓库提交失败 - {result.stderr.strip()}"

        source_commits = []
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            try:
                source_commits.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        # Check which commits exist in target repo by cherry-pick notation
        missing = []
        for commit in source_commits:
            check = subprocess.run(
                ["git", "-C", target_repo, "log", "--oneline", "--grep", commit["message"][:60]],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if not check.stdout.strip():
                missing.append(commit)

        return json.dumps(missing, ensure_ascii=False, indent=2)

    except subprocess.TimeoutExpired:
        return "错误: 仓库比较执行超时"
    except Exception as exc:
        return f"错误: {exc}"


GIT_TOOLS = [git_log, git_diff_commits, git_diff_repos]
