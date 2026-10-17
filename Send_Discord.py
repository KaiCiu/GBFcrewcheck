
import os
import json
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CHANGES_DIR = BASE_DIR / "data" / "changes"


def send_discord_message(message: str) -> None:
    """使用 Discord Bot API 发送消息。"""
    token = os.environ.get("DISCORD_BOT_TOKEN")
    channel_id = os.environ.get("DISCORD_CHANNEL_ID")

    if not token or not channel_id:
        raise RuntimeError(
            "缺少 DISCORD_BOT_TOKEN 或 DISCORD_CHANNEL_ID 环境变量。"
        )

    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    payload = json.dumps({"content": message}).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
            "User-Agent": "GBFGuildTracker/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            print("Discord 回應狀態：", response.status)

    except urllib.error.HTTPError as e:
        print("Discord HTTP 狀態碼：", e.code)
        print(
            "Discord 錯誤內容：",
            e.read().decode("utf-8", errors="replace")
        )
        raise


def main():
    # 使用电脑当前本地日期
    today = datetime.now().astimezone().strftime("%Y-%m-%d")
    report_path = CHANGES_DIR / f"{today}.txt"

    if not report_path.exists():
        raise FileNotFoundError(
            f"找不到当天的日报：{report_path}\n"
            "请先运行 Report_Changes.py。"
        )

    report = report_path.read_text(encoding="utf-8").strip()

    if not report:
        raise ValueError("当天日报文件为空，取消发送。")

    # Discord 单条普通消息最多 2000 个字符
    if len(report) > 2000:
        raise ValueError(
            f"日报有 {len(report)} 个字符，超过 Discord 单条消息限制。"
            "需要改为分段发送。"
        )

    send_discord_message(report)
    print(f"发送成功：{report_path.name}")


if __name__ == "__main__":
    main()
