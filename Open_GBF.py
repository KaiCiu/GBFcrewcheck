
import json
import subprocess
import time
import urllib.request
from pathlib import Path

BROWSER_PATH = Path(
    r"C:\Program Files\SRWare Iron (64-Bit)\chrome.exe"
)

USER_DATA_DIR = (
    Path.home()
    / "AppData"
    / "Local"
    / "GBF-Automation-Chrome"
)

GBF_URL = "https://game.granbluefantasy.jp/#guild/member"
DEBUGGING_PORT = 9222

DEBUGGING_URL = (
    f"http://127.0.0.1:{DEBUGGING_PORT}/json/version"
)
PID_FILE = (
    Path(__file__).resolve().parent
    / "data"
    / "gbf_browser_pid.json"
)

def is_debugging_ready():
    """检查浏览器的远程调试接口是否可用。"""
    try:
        with urllib.request.urlopen(
            DEBUGGING_URL,
            timeout=2
        ) as response:
            return response.status == 200
    except Exception:
        return False


def main():
    if not BROWSER_PATH.exists():
        raise FileNotFoundError(
            f"找不到 SRWare Iron：{BROWSER_PATH}"
        )

    # 如果已有浏览器使用这个调试端口，就不重复启动
    if is_debugging_ready():
        # 当前浏览器不是本脚本新启动的，不记录为待关闭进程
        PID_FILE.unlink(missing_ok=True)

        print("检测到 SRWare Iron 调试接口已就绪。")
        print("复用现有浏览器，不重复启动。")
        print("本次不会自动关闭这个已有浏览器。")
        return

    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

    command = [
        str(BROWSER_PATH),
        f"--remote-debugging-port={DEBUGGING_PORT}",
        f"--user-data-dir={USER_DATA_DIR}",
        GBF_URL,
    ]

    print("正在启动 SRWare Iron……")
    process = subprocess.Popen(command)

    PID_FILE.parent.mkdir(parents=True, exist_ok=True)

    with PID_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            {"pid": process.pid},
            file,
            ensure_ascii=False,
            indent=2
        )

    print(f"已记录本次启动的浏览器 PID：{process.pid}")

    # 最多等待 30 秒，直到调试接口可用
    for attempt in range(1, 31):
        if is_debugging_ready():
            print("SRWare Iron 调试接口已就绪。")
            print("等待 5 秒，让 GBF 页面初始化……")
            time.sleep(5)
            print("浏览器初始化完成，未发送 F5。")
            return

        time.sleep(1)

    raise TimeoutError(
        "等待 30 秒后，仍无法连接 Iron 调试接口。"
        "请检查浏览器是否成功启动，以及 9222 端口是否被占用。"
    )


if __name__ == "__main__":
    main()
