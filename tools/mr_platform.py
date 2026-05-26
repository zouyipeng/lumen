import json
from abc import ABC, abstractmethod
from pathlib import Path

from langchain_core.tools import tool


class MRPlatform(ABC):
    """Abstract interface for MR/PR platforms."""

    @abstractmethod
    def fetch_mrs(self, project_id: str, since: str, until: str) -> list[dict]:
        """Fetch merged MRs/PRs in the given date range.

        Returns a list of dicts with keys: id, title, description, author,
        labels, source_branch, target_branch, merged_at.
        """
        ...


class MockMRPlatform(MRPlatform):
    """Mock MR platform that loads data from a local JSON file."""

    def __init__(self, data_path: str = ""):
        self._data_path = data_path

    def fetch_mrs(self, project_id: str, since: str, until: str) -> list[dict]:
        if not self._data_path:
            return []
        path = Path(self._data_path)
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        # Filter by date range if merged_at is present
        # since/until are YYYY-MM-DD; merged_at may be ISO 8601 with time.
        # Compare only the date portion to avoid format mismatch.
        result = []
        for mr in data:
            merged_at = mr.get("merged_at", "")
            merged_date = merged_at[:10]  # Extract YYYY-MM-DD part
            if since <= merged_date <= until:
                result.append(mr)
        return result


_PLATFORM_REGISTRY: dict[str, type[MRPlatform]] = {
    "mock": MockMRPlatform,
}


def register_platform(name: str, cls: type[MRPlatform]) -> None:
    """Register a new MR platform implementation."""
    _PLATFORM_REGISTRY[name] = cls


def get_platform(platform_type: str, **kwargs) -> MRPlatform:
    """Get an MR platform instance by type name."""
    cls = _PLATFORM_REGISTRY.get(platform_type)
    if cls is None:
        raise ValueError(f"Unknown MR platform type: {platform_type}. Available: {list(_PLATFORM_REGISTRY)}")
    return cls(**kwargs)


@tool
def fetch_mr_list(platform_type: str, data_path: str, project_id: str, since: str, until: str) -> str:
    """获取 MR/PR 列表。platform_type 为平台类型（如 mock），data_path 为数据文件路径，project_id 为项目 ID，since/until 为日期范围。"""
    try:
        platform = get_platform(platform_type, data_path=data_path)
        mrs = platform.fetch_mrs(project_id, since, until)
        return json.dumps(mrs, ensure_ascii=False, indent=2)
    except Exception as exc:
        return f"错误: 获取 MR 列表失败 - {exc}"


MR_TOOLS = [fetch_mr_list]
