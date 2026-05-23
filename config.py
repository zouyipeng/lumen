import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent
MAX_RETRIES = 3
MAX_PARALLEL_TASKS = 5

AGENT_NAMES = ("coordinator", "executor", "reviewer", "summarizer")


def _read_env(key: str, default: str | None = None) -> str | None:
    value = os.getenv(key)
    if value is None or value == "":
        return default
    return value


def resolve_llm_config(agent: str) -> dict:
    """Resolve LLM settings for an agent, falling back to global env vars."""
    prefix = agent.upper()
    temperature_raw = (
        _read_env(f"{prefix}_TEMPERATURE")
        or _read_env("TEMPERATURE")
        or "0"
    )
    return {
        "model": _read_env(f"{prefix}_MODEL_NAME") or _read_env("MODEL_NAME", "gpt-4o-mini"),
        "api_key": _read_env(f"{prefix}_API_KEY") or _read_env("OPENAI_API_KEY"),
        "base_url": _read_env(f"{prefix}_BASE_URL") or _read_env("OPENAI_BASE_URL"),
        "temperature": float(temperature_raw),
    }


@lru_cache(maxsize=len(AGENT_NAMES))
def get_llm(agent: str) -> ChatOpenAI:
    if agent not in AGENT_NAMES:
        raise ValueError(f"Unknown agent: {agent}. Expected one of {AGENT_NAMES}")

    settings = resolve_llm_config(agent)
    return ChatOpenAI(
        model=settings["model"],
        api_key=settings["api_key"],
        base_url=settings["base_url"],
        temperature=settings["temperature"],
    )


def load_prompt(name: str) -> str:
    path = PROJECT_ROOT / "prompts" / f"{name}.md"
    return path.read_text(encoding="utf-8")
