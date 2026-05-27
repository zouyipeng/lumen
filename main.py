import argparse
import logging
import uuid

from langgraph.checkpoint.memory import MemorySaver

from config import load_rn_config, resolve_rn_params
from graph.rn_state import make_rn_initial_state
from graph.rn_workflow import build_rn_workflow

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser(description="Release Note 生成工作流")
    parser.add_argument("--repo", default=None, help="仓库 URL（覆盖配置文件中的 repo.url）")
    parser.add_argument("--version", default=None, help="版本周期标识，如 2024-06（覆盖配置文件中的 version_cycle.current）")
    parser.add_argument("--config", default="rn_config.json", help="RN 配置文件路径")
    parser.add_argument("--mode", choices=["full", "incremental"], default=None,
                        help="生成模式：full=全量, incremental=增量（覆盖配置文件中的 workflow.mode）")
    parser.add_argument("--existing-excel", default=None,
                        help="增量模式下的已有 Excel 文件路径（覆盖配置文件中的 workflow.existing_excel）")
    args = parser.parse_args()

    # 加载配置
    rn_config = load_rn_config(args.config)

    # 合并参数：CLI 覆盖配置
    try:
        params = resolve_rn_params(
            rn_config,
            repo_url=args.repo,
            version_cycle=args.version,
            mode=args.mode,
            existing_excel=args.existing_excel,
        )
    except ValueError as e:
        parser.error(str(e))
        return

    graph = build_rn_workflow(checkpointer=MemorySaver())
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = make_rn_initial_state(
        params["repo_url"], params["version_cycle"], args.config,
        mode=params["mode"], existing_excel_path=params["existing_excel"],
    )

    print(f"\n{'=' * 60}")
    print(f"版本周期: {params['version_cycle']}")
    print(f"仓库: {params['repo_url']}")
    print(f"配置: {args.config}")
    print(f"模式: {params['mode']}")
    if params["mode"] == "incremental":
        from config import resolve_excel_path
        excel_path = params["existing_excel"] or resolve_excel_path(
            rn_config.get("excel", {}).get("output_path", "release_note.xlsx"),
            params["version_cycle"],
        )
        print(f"已有 Excel: {excel_path}")
    print(f"{'=' * 60}")

    result = graph.invoke(initial_state, config)

    print(f"\n{'=' * 60}")
    print("最终结果:")
    print(f"{'=' * 60}")
    print(result.get("final_response", "工作流已完成，但未生成最终回复。"))


if __name__ == "__main__":
    main()
