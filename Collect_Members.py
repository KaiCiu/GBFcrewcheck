#Collect_Members.py
import os
import signal
import json
import re
import subprocess
import time
import sys
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# 项目根目录下的 data 文件夹
DATA_DIR = Path(__file__).resolve().parent / "data"

# 按运行日期命名，例如 members_20261017.json
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_FILE = DATA_DIR / f"members_{TIMESTAMP}.json"


def read_members(page):
    """读取当前页的成员信息。"""
    return page.locator(".lis-member").evaluate_all(
        """cards => cards.map(card => {
            const getText = selector => {
                const element = card.querySelector(selector);
                return element ? element.innerText.trim() : "";
            };

            const profile = card.querySelector(
                ".btn-member-profile[data-location-href]"
            );

            const href = profile
                ? profile.getAttribute("data-location-href") || ""
                : "";

            const match = href.match(/profile\\/(\\d+)/);

            return {
                "id": match ? match[1] : "",
                "name": getText(".txt-name"),
                "rank": getText(".txt-rank"),
                "last": getText(".prt-member-login")
            };
        })"""
    )


def get_total_pages(page):
    """从分页控件中识别总页数。"""
    button = page.locator(
        "#pagination-member .btn-forward-last"
    ).first

    if button.count():
        value = button.get_attribute("page")
        if value and value.isdigit():
            return int(value)

    numbers = page.locator(
        "#pagination-member .btn-page-number"
    ).evaluate_all(
        """elements => elements
            .map(element => Number(element.getAttribute("page")))
            .filter(number => Number.isInteger(number) && number > 0)"""
    )

    if numbers:
        return max(numbers)

    raise RuntimeError("无法识别总页数，请确认已打开公会成员页面。")


def get_expected_count(page):
    """读取页面显示的公会成员总人数。"""
    text = page.locator("body").inner_text()
    match = re.search(r"所属団員数\s*(\d+)", text)

    return int(match.group(1)) if match else None


def get_current_page(page):
    """尝试读取当前激活的页码。"""
    active = page.locator(
        "#pagination-member .prt-page-number[disable='true']:visible"
    ).first

    if active.count():
        value = active.get_attribute("page")
        if value and value.isdigit():
            return int(value)

    return None



def click_page(page, target_page):
    """点击目标页，并通过分页控件确认切换结果。"""
    button = page.locator(
        f"#pagination-member "
        f".btn-page-number[page='{target_page}']:visible"
    ).first

    if button.count() == 0:
        raise RuntimeError(
            f"找不到第 {target_page} 页的可见按钮。"
        )

    # 如果已经在目标页，不重复点击
    active_page = page.locator(
        f"#pagination-member "
        f".prt-page-number[page='{target_page}'][disable='true']:visible"
    ).first

    if active_page.count() > 0:
        print(f"已经处于第 {target_page} 页。")
        return

    print(f"点击第 {target_page} 页……")
    button.click()

    # 优先等待分页控件明确标记目标页为当前页
    try:
        page.locator(
            f"#pagination-member "
            f".prt-page-number[page='{target_page}'][disable='true']:visible"
        ).first.wait_for(state="visible", timeout=10000)

        # 等待列表渲染完成
        page.wait_for_timeout(800)
        print(f"分页控件已确认切换到第 {target_page} 页。")
        return

    except PlaywrightTimeoutError:
        pass

    # 备用检查：读取当前页面的分页状态和成员数量
    current_page = get_current_page(page)
    member_count = page.locator(".lis-member").count()

    print(f"备用检查：当前页码={current_page}，成员卡片数={member_count}")

    if current_page == target_page and member_count > 0:
        page.wait_for_timeout(800)
        print(f"已确认第 {target_page} 页。")
        return

    raise RuntimeError(
        f"无法确认切换到第 {target_page} 页。"
        f"当前识别页码={current_page}，成员卡片数={member_count}。"
        "请检查浏览器中的分页状态。"
    )

def collect_once(page):
    """完整抓取一次；失败时抛出异常，由外层负责重试。"""

    # 刷新后必须确认回到第一页
    current_page = get_current_page(page)

    if current_page != 1:
        click_page(page, 1)

    total_pages = get_total_pages(page)
    expected_count = get_expected_count(page)

    print(f"识别到总页数：{total_pages}")

    if expected_count is not None:
        print(f"页面显示成员总数：{expected_count}")

    all_members = []
    seen_ids = set()
    seen_names = set()

    for target_page in range(1, total_pages + 1):
        if target_page > 1:
            print(f"\n正在切换到第 {target_page} 页……")
            click_page(page, target_page)

        members = read_members(page)

        if not members:
            raise RuntimeError(
                f"第 {target_page} 页没有读取到成员。"
            )

        new_count = 0

        for member in members:
            name = member["name"]
            member_id = member["id"]

            if not name:
                continue

            if member_id and member_id in seen_ids:
                continue

            if not member_id and name in seen_names:
                continue

            if member_id:
                seen_ids.add(member_id)

            seen_names.add(name)
            all_members.append(member)
            new_count += 1

        print(
            f"第 {target_page}/{total_pages} 页："
            f"读取 {len(members)} 人，新增 {new_count} 人"
        )

    if expected_count is not None and len(all_members) != expected_count:
        raise RuntimeError(
            f"人数校验失败：页面显示 {expected_count} 人，"
            f"实际采集 {len(all_members)} 人。"
        )

    if not all_members:
        raise RuntimeError("最终采集结果为空。")

    return all_members

def close_gbf_browser():
    """只关闭 Open_GBF.py 本次启动的浏览器。"""
    pid_file = (
        Path(__file__).resolve().parent
        / "data"
        / "gbf_browser_pid.json"
    )

    if not pid_file.exists():
        print("没有本次启动的浏览器 PID，不自动关闭现有浏览器。")
        return

    try:
        with pid_file.open("r", encoding="utf-8") as file:
            data = json.load(file)

        pid = int(data["pid"])

        if os.name == "nt":
            # Windows：结束指定 PID 的进程
            import subprocess

            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"
            )

            if result.returncode == 0:
                print(f"已关闭本次启动的浏览器，PID：{pid}")
            else:
                print(
                    f"关闭浏览器失败："
                    f"{result.stderr.strip() or result.stdout.strip()}"
                )
        else:
            os.kill(pid, signal.SIGTERM)
            print(f"已发送关闭信号给浏览器，PID：{pid}")

    except (KeyError, ValueError, OSError, json.JSONDecodeError) as e:
        print(f"关闭浏览器时发生错误：{e}")

    finally:
        pid_file.unlink(missing_ok=True)


def main():
    # 1. 调用 Open_GBF.py 启动浏览器
    script_dir = Path(__file__).resolve().parent
    open_gbf_script = script_dir / "Open_GBF.py"

    if not open_gbf_script.exists():
        raise FileNotFoundError(
            f"找不到浏览器启动脚本：{open_gbf_script}"
        )

    print("正在启动 GBF 浏览器……")

    subprocess.run(
        [sys.executable, str(open_gbf_script)],
        check=True
    )

    # 2. 等待浏览器和 GBF 页面初始化
    print("等待 5 秒，让 GBF 页面加载……")
    time.sleep(5)

    # 3. 连接已经启动的浏览器
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(
            "http://127.0.0.1:9222"
        )

        context = browser.contexts[0]
        print("已连接 SRWare Iron。")

        # 4. 寻找公会成员页面
        page = None

        for tab in context.pages:
            try:
                if tab.locator(".lis-member").count() > 0:
                    page = tab
                    break
            except PlaywrightTimeoutError:
                continue

        if page is None:
            print("未找到成员列表，尝试打开公会成员页面。")

            page = context.pages[0] if context.pages else context.new_page()

            page.goto(
                "https://game.granbluefantasy.jp/#guild/member",
                wait_until="domcontentloaded",
                timeout=30000
            )

            page.wait_for_timeout(5000)

        print(f"当前页面：{page.url}")

        page.locator(".lis-member").first.wait_for(
            state="visible",
            timeout=15000
        )

        # 5. 最多尝试完整抓取 3 次
        all_members = None
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            print(
                f"\n========== "
                f"第 {attempt}/{max_attempts} 次抓取 =========="
            )

            try:
                # 等待成员列表出现
                page.locator(".lis-member").first.wait_for(
                    state="visible",
                    timeout=15000
                )

                # 确认处于第一页
                current_page = get_current_page(page)

                if current_page != 1:
                    print("当前不在第一页，尝试切回第一页……")
                    click_page(page, 1)

                # 完整抓取所有页，并执行人数校验
                all_members = collect_once(page)

                print(f"\n抓取成功，共 {len(all_members)} 人。")
                break

            except Exception as e:
                print(f"第 {attempt} 次抓取失败：{e}")
                all_members = None

                if attempt == max_attempts:
                    print("已达到最大尝试次数，停止抓取。")
                    raise RuntimeError(
                        "连续 3 次抓取失败，未保存本次数据。"
                    ) from e

                # 失败后刷新页面，等待 5 秒
                print("刷新页面，等待 5 秒后重新尝试……")


                try:
                    page.reload(
                        wait_until="domcontentloaded",
                        timeout=30000
                    )

                    page.wait_for_timeout(5000)

                    # 等待成员列表重新出现
                    page.locator(".lis-member").first.wait_for(
                        state="visible",
                        timeout=15000
                    )

                    current_page = get_current_page(page)
                    print(f"刷新后识别到页码：{current_page}")

                except Exception as reload_error:
                    print(f"刷新或页面恢复失败：{reload_error}")

        if all_members is None:
            raise RuntimeError("抓取失败，没有生成成员数据。")

        # 6. 全部抓取成功后，才保存 JSON
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        with OUTPUT_FILE.open("w", encoding="utf-8") as file:
            json.dump(
                all_members,
                file,
                ensure_ascii=False,
                indent=2
            )

        print(f"数据已保存到：{OUTPUT_FILE}")

        print("\n前 3 名成员示例：")
        print(
            json.dumps(
                all_members[:3],
                ensure_ascii=False,
                indent=2
            )
        )

        # 不调用 browser.close()，避免主动关闭整个浏览器


if __name__ == "__main__":
    try:
        main()
    finally:
        close_gbf_browser()