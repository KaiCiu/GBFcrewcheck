
import subprocess
import sys
from pathlib import Path


def run_step(script_dir, script_name, description):
    """运行一个脚本；失败时停止整个流程。"""
    script_path = script_dir / script_name

    if not script_path.exists():
        raise FileNotFoundError(
            f"找不到脚本：{script_path}"
        )

    print("\n" + "=" * 50)
    print(f"开始执行：{description}")
    print(f"脚本：{script_name}")
    print("=" * 50, flush=True)

    subprocess.run(
        [sys.executable, str(script_path)],
        check=True,
        cwd=str(script_dir)
    )

    print(f"完成：{description}", flush=True)


def main():
    script_dir = Path(__file__).resolve().parent

    steps = [
        (
            "Collect_Members.py",
            "抓取 GBF 公会成员并保存 JSON"
        ),
        (
            "Database.py",
            "更新成员历史数据库"
        ),
        (
            "Report_Changes.py",
            "生成每日成员变动报告"
        ),
        (
            "Send_Discord.py",
            "发送变动报告到 Discord"
        ),
    ]

    print("GBF 成员追踪程序启动。", flush=True)

    for script_name, description in steps:
        run_step(
            script_dir,
            script_name,
            description
        )

    print("\n" + "=" * 50)
    print("GBF 成员追踪流程全部完成！")
    print("=" * 50, flush=True)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(
            f"\n流程中断：脚本 {e.cmd} 执行失败，"
            f"退出代码为 {e.returncode}。"
        )
        sys.exit(e.returncode)
    except Exception as e:
        print(f"\n程序发生错误：{e}")
        sys.exit(1)
