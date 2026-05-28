import json
from pathlib import Path

from langchain_openai import ChatOpenAI

PROJECT_ROOT = Path(__file__).resolve().parent


def get_llm_with_config(agent_config: dict, *, default_config: dict | None = None) -> ChatOpenAI:
    """Create LLM instance from agent-level config, falling back to default_config."""
    defaults = default_config or {}
    return ChatOpenAI(
        model=agent_config.get("model_name") or defaults.get("model_name", "gpt-4o-mini"),
        api_key=agent_config.get("api_key") or defaults.get("api_key", ""),
        base_url=agent_config.get("base_url") or defaults.get("base_url"),
        temperature=float(agent_config.get("temperature", defaults.get("temperature", 0))),
    )


def load_prompt_from_file(path: str) -> str:
    """Load prompt file from absolute or project-relative path."""
    p = Path(path) if Path(path).is_absolute() else PROJECT_ROOT / path
    return p.read_text(encoding="utf-8")


def load_config(config_path: str) -> dict:
    """Load maintenance configuration JSON file."""
    p = Path(config_path) if Path(config_path).is_absolute() else PROJECT_ROOT / config_path
    return json.loads(p.read_text(encoding="utf-8"))


def resolve_project_path(path: str) -> Path:
    """Resolve absolute or project-relative path."""
    p = Path(path)
    if p.is_absolute():
        return p
    return PROJECT_ROOT / p
