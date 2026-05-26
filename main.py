import argparse
import logging
import uuid

from langgraph.checkpoint.memory import MemorySaver

from graph.rn_state import make_rn_initial_state
from graph.rn_workflow import build_rn_workflow

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser(description="Release Note 生成工作流")
    parser.add_argument("--repo", required=True, help="仓库 URL")
    parser.add_argument("--version", required=True, help="版本周期标识（如 2024-06 或 v3.2.0）")
    parser.add_argument("--config", default="rn_config.json", help="RN 配置文件路径")
    parser.add_argument("--mode", choices=["full", "incremental"], default="full",
                        help="生成模式：full=全量, incremental=增量")
    parser.add_argument("--existing-excel", default="",
                        help="增量模式下的已有 Excel 文件路径（默认使用配置中的 output_path）")
    args = parser.parse_args()

    graph = build_rn_workflow(checkpointer=MemorySaver())
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = make_rn_initial_state(
        args.repo, args.version, args.config,
        mode=args.mode, existing_excel_path=args.existing_excel,
    )

    print(f"\n{'=' * 60}")
    print(f"版本周期: {args.version}")
    print(f"仓库: {args.repo}")
    print(f"配置: {args.config}")
    print(f"模式: {args.mode}")
    if args.mode == "incremental" and args.existing_excel:
        print(f"已有 Excel: {args.existing_excel}")
    print(f"{'=' * 60}")

    result = graph.invoke(initial_state, config)

    print(f"\n{'=' * 60}")
    print("最终结果:")
    print(f"{'=' * 60}")
    print(result.get("final_response", "工作流已完成，但未生成最终回复。"))


if __name__ == "__main__":
    main()
