import json
from pathlib import Path

from langchain_openai import ChatOpenAI

from agents.backends import CLIBackend, HTTPBackend

PROJECT_ROOT = Path(__file__).resolve().parent


def get_llm_with_config(agent_config: dict, *, default_config: dict | None = None):
    """Create LLM backend instance from agent-level config, falling back to default_config.

    Returns one of: ChatOpenAI, CLIBackend, HTTPBackend
    depending on the 'backend' field in config.
    """
    defaults = default_config or {}
    backend = agent_config.get("backend") or defaults.get("backend", "openai")

    if backend == "openai":
        return ChatOpenAI(
            model=agent_config.get("model_name") or defaults.get("model_name", "gpt-4o-mini"),
            api_key=agent_config.get("api_key") or defaults.get("api_key", ""),
            base_url=agent_config.get("base_url") or defaults.get("base_url"),
            temperature=float(agent_config.get("temperature", defaults.get("temperature", 0))),
        )
    elif backend == "cli":
        cli_command = agent_config.get("cli_command") or defaults.get("cli_command", "")
        if not cli_command:
            raise ValueError("CLI backend requires 'cli_command' in config")
        return CLIBackend(
            cli_command=cli_command,
            timeout=int(agent_config.get("cli_timeout", defaults.get("cli_timeout", 120))),
            cli_stdin=bool(agent_config.get("cli_stdin", defaults.get("cli_stdin", False))),
        )
    elif backend == "http":
        url = agent_config.get("http_url") or defaults.get("http_url", "")
        if not url:
            raise ValueError("HTTP backend requires 'http_url' in config")
        return HTTPBackend(
            url=url,
            headers=agent_config.get("http_headers") or defaults.get("http_headers"),
            timeout=int(agent_config.get("http_timeout", defaults.get("http_timeout", 120))),
            model_name=agent_config.get("model_name") or defaults.get("model_name", ""),
            response_path=agent_config.get("http_response_path") or defaults.get("http_response_path", "choices.0.message.content"),
        )
    else:
        raise ValueError(f"Unknown backend type: {backend!r}. Expected 'openai', 'cli', or 'http'.")


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
