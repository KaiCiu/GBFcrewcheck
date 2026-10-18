
import json
import subprocess
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

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
DEBUGGING_PAGES_URL = (
    f"http://127.0.0.1:{DEBUGGING_PORT}/json/list"
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


def get_gbf_pages():
    """获取当前浏览器中 GBF 网页的 URL。"""
    try:
        with urllib.request.urlopen(
            DEBUGGING_PAGES_URL,
            timeout=3
        ) as response:
            pages = json.loads(response.read().decode("utf-8"))

        return [
            page["url"]
            for page in pages
            if page.get("type") == "page"
            and urlsplit(page.get("url", "")).hostname
            == "game.granbluefantasy.jp"
        ]
    except Exception as error:
        print(f"读取 GBF 页面失败：{error}")
        return []


def is_login_page(url):
    """判断是否位于 GBF 根页面。"""
    parsed = urlsplit(url)

    return (
        parsed.scheme == "https"
        and parsed.hostname == "game.granbluefantasy.jp"
        and parsed.path in ("", "/")
        and not parsed.fragment
    )


def wait_for_correct_page():
    """
    如果 GBF 位于根页面，提示重新登录并等待。
    浏览器不会被关闭；按回车后重新检查。
    """
    while True:
        pages = get_gbf_pages()

        if not pages:
            print("暂时没有检测到 GBF 页面，等待 3 秒后重试……")
            time.sleep(3)
            continue

        root_pages = [
            url for url in pages
            if is_login_page(url)
        ]

        if root_pages:
            print("\n检测到 GBF 根页面，可能已经掉线。")
            print("请重新登录！")
            print("请在浏览器中完成登录，并进入骑空团成员页面。")
            input("完成后按回车，重新检查网页地址……")
            continue

        member_pages = [
            url for url in pages
            if "#guild/member" in url
        ]

        if member_pages:
            print("已检测到骑空团成员页面。")
            print("可以继续执行后续采集。")
            return

        print("当前不是预期的成员页面。")
        print("请在浏览器中进入骑空团成员页面。")
        input("进入后按回车，重新检查网页地址……")


def main():
    if not BROWSER_PATH.exists():
        raise FileNotFoundError(
            f"找不到 SRWare Iron：{BROWSER_PATH}"
        )

    # 复用已启动的浏览器
    if is_debugging_ready():
        PID_FILE.unlink(missing_ok=True)

        print("检测到 SRWare Iron 调试接口已就绪。")
        print("复用现有浏览器，不重复启动。")
        print("本次不会自动关闭这个已有浏览器。")

        wait_for_correct_page()
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
            break

        time.sleep(1)
    else:
        raise TimeoutError(
            "等待 30 秒后，仍无法连接 Iron 调试接口。"
            "请检查浏览器是否成功启动，以及 9222 端口是否被占用。"
        )

    wait_for_correct_page()


if __name__ == "__main__":
    main()
