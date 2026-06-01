import os
import sys

from .agent import app
from .token_tracker import token_tracker


def run_agent(file_path: str):
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return

    # 初始化状态
    initial_state = {
        "book_path": file_path,
        "metadata": {},
        "full_text": "",
        "chapters": {},
        "overview": "",
        "candidates": [],
        "verified_units": [],
        "rejected_units": [],
        "relations": {},
        "final_skills": [],
        "errors": [],
        "stats": {},
    }

    print(f"开始执行 Book2Skill Agent...")
    print(f"处理文件: {file_path}")

    try:
        # 使用 stream 模式运行，并增加中断保护
        for output in app.stream(initial_state, config={"recursion_limit": 50}):
            for node_name, state_update in output.items():
                print(f">>> 节点 [{node_name}] 执行完毕", flush=True)

                # 关键产出实时反馈
                if node_name == "overview":
                    print(f"    [OK] 整书理解已生成", flush=True)
                elif node_name == "extract":
                    count = len(state_update.get("candidates", []))
                    print(f"    [OK] 提取到 {count} 个候选单元", flush=True)
                elif node_name == "verify":
                    v_count = len(state_update.get("verified_units", []))
                    r_count = len(state_update.get("rejected_units", []))
                    print(f"    [OK] 审计通过: {v_count}, 淘汰: {r_count}", flush=True)
                elif node_name == "ria":
                    count = len(state_update.get("final_skills", []))
                    print(f"    [OK] 成功生成 {count} 个 SKILL.md", flush=True)

        print(
            "\n任务全部完成！请在 books/ 目录下查看生成的专业 Skill Set。", flush=True
        )

    except KeyboardInterrupt:
        print(
            "\n\n[User Interrupt] 用户强行中断。程序正在清理资源并退出...", flush=True
        )
        sys.exit(1)
    except Exception as e:
        print(f"\n[Fatal Error] 运行崩溃: {e}", flush=True)
        sys.exit(1)
    finally:
        # 无论成功或失败，打印最终 Token 消耗统计
        token_tracker.print_summary()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_file = sys.argv[1]
    else:
        epubs = [f for f in os.listdir(".") if f.endswith(".epub")]
        if epubs:
            target_file = epubs[0]
        else:
            print("用法: python -m book2skill_agent.run <书籍路径>")
            sys.exit(1)

    run_agent(target_file)
