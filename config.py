import json
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent


def _read_env(key: str, default: str | None = None) -> str | None:
    value = os.getenv(key)
    if value is None or value == "":
        return default
    return value


def get_llm_with_config(agent_config: dict) -> ChatOpenAI:
    """Create LLM instance from column-level config (independent model/temperature/api_key)."""
    return ChatOpenAI(
        model=agent_config.get("model_name") or _read_env("MODEL_NAME", "gpt-4o-mini"),
        api_key=agent_config.get("api_key") or _read_env("OPENAI_API_KEY"),
        base_url=agent_config.get("base_url") or _read_env("OPENAI_BASE_URL"),
        temperature=float(agent_config.get("temperature", 0)),
    )


def load_prompt_from_file(path: str) -> str:
    """Load prompt file from absolute or project-relative path."""
    p = Path(path) if Path(path).is_absolute() else PROJECT_ROOT / path
    return p.read_text(encoding="utf-8")


def load_rn_config(config_path: str) -> dict:
    """Load RN configuration JSON file."""
    p = Path(config_path) if Path(config_path).is_absolute() else PROJECT_ROOT / config_path
    return json.loads(p.read_text(encoding="utf-8"))


def resolve_excel_path(path_template: str, version_cycle: str) -> str:
    """Resolve Excel output path, replacing {version} with version_cycle."""
    return path_template.replace("{version}", version_cycle)


def resolve_rn_params(config: dict, *,
                      repo_url: str | None = None,
                      version_cycle: str | None = None,
                      mode: str | None = None,
                      existing_excel: str | None = None) -> dict:
    """Resolve RN workflow parameters: CLI args override config values.

    Returns a dict with keys: repo_url, version_cycle, mode, existing_excel.
    Raises ValueError if version_cycle cannot be resolved from either source.
    """
    resolved_repo_url = repo_url or config.get("repo", {}).get("url", "")
    resolved_version = version_cycle or config.get("version_cycle", {}).get("current", "")
    if not resolved_version:
        raise ValueError(
            "version_cycle 未指定。请通过 --version 参数或在配置文件 version_cycle.current 中设置。"
        )
    resolved_mode = mode or config.get("workflow", {}).get("mode", "full")
    resolved_existing_excel = existing_excel or config.get("workflow", {}).get("existing_excel", "")

    return {
        "repo_url": resolved_repo_url,
        "version_cycle": resolved_version,
        "mode": resolved_mode,
        "existing_excel": resolved_existing_excel,
    }


def resolve_project_path(path: str) -> Path:
    """Resolve absolute or project-relative path."""
    p = Path(path)
    if p.is_absolute():
        return p
    return PROJECT_ROOT / p
