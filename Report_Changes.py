
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "gbf_history.db"
OUTPUT_DIR = BASE_DIR / "data" / "changes"

# 超过 14 天才列入，即 15 天起
INACTIVE_DAYS = 14


def format_date(snapshot_time):
    """将数据库日期转换为 YYYYMMDD。"""
    return snapshot_time[:10].replace("-", "")


def format_rank(rank):
    """将等级格式化为 Rank 100。"""
    if rank is None:
        return "未知等级"
    return f"Rank {rank}"


def get_inactive_days(last_login):
    """
    从 GBF 的登录时间文本中提取未登录天数。
    例如：最終ログイン: 28日前 -> 28
    小时、1 天以内等情况不算超过 14 天。
    """
    if not last_login:
        return None

    match = re.search(r"(\d+)\s*日前", last_login)
    if not match:
        return None

    return int(match.group(1))


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not DB_PATH.exists():
        print(f"数据库不存在：{DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # 获取所有快照
        snapshots = conn.execute("""
            SELECT id, snapshot_time
            FROM snapshots
            ORDER BY snapshot_time, id
        """).fetchall()

        if not snapshots:
            print("数据库中没有快照记录。")
            return

        # 按日期整理人员和等级变化
        daily_changes = defaultdict(list)

        rows = conn.execute("""
            SELECT snapshot_time, change_type, member_id, name,
                   old_rank, new_rank
            FROM member_changes
            ORDER BY snapshot_time, id
        """).fetchall()

        for row in rows:
            date_key = format_date(row["snapshot_time"])
            daily_changes[date_key].append(row)

        # 每天使用该日期最后一个快照，读取当时的成员登录情况
        daily_snapshots = {}
        for snapshot in snapshots:
            date_key = format_date(snapshot["snapshot_time"])
            daily_snapshots[date_key] = snapshot

        dates = sorted(daily_snapshots)

        for date_key in dates:
            changes = daily_changes.get(date_key, [])

            personnel_changes = [
                row for row in changes
                if row["change_type"] in ("joined", "left")
            ]

            rank_changes = [
                row for row in changes
                if row["change_type"] == "rank_changed"
            ]

            lines = [
                f"---{date_key}---",
                f"人员变动：{len(personnel_changes)}人",
                f"等级变动：{len(rank_changes)}人",
            ]

            # 人员变动详情
            for row in personnel_changes:
                name = row["name"] or "未知成员"
                member_id = row["member_id"]

                if member_id:
                    member_info = f"{name}（ID: {member_id}）"
                else:
                    member_info = name

                if row["change_type"] == "joined":
                    lines.append(f"{member_info} 加入骑空团")
                else:
                    lines.append(f"{member_info} 离开骑空团")

            # 等级变化详情
            for row in rank_changes:
                name = row["name"] or "未知成员"
                old_rank = format_rank(row["old_rank"])
                new_rank = format_rank(row["new_rank"])

                lines.append(
                    f"{name} {old_rank} → {new_rank}"
                )

            # 读取该日期最后一个快照中的成员登录时间
            snapshot_id = daily_snapshots[date_key]["id"]

            members = conn.execute("""
                SELECT member_id, name, last_login
                FROM snapshot_members
                WHERE snapshot_id = ?
                ORDER BY name
            """, (snapshot_id,)).fetchall()

            inactive_members = []

            for member in members:
                inactive_days = get_inactive_days(
                    member["last_login"]
                )

                # 14 天不算，15 天起才列出
                if (
                    inactive_days is not None
                    and inactive_days > INACTIVE_DAYS
                ):
                    inactive_members.append(
                        (member, inactive_days)
                    )

            # 只有存在符合条件的成员时，才添加该章节
            if inactive_members:
                lines.append("")
                lines.append("超过14天未登录：")

                for member, inactive_days in inactive_members:
                    name = member["name"] or "未知成员"
                    member_id = member["member_id"]

                    if member_id:
                        member_info = f"{name}（ID: {member_id}）"
                    else:
                        member_info = name

                    lines.append(
                        f"{member_info}上次登录：{inactive_days}日前"
                    )

            output_path = (
                OUTPUT_DIR
                / f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:]}.txt"
            )

            output_path.write_text(
                "\n".join(lines) + "\n",
                encoding="utf-8"
            )

            print(f"已生成：{output_path.name}")

    finally:
        conn.close()

    print("每日变动报告生成完成。")


if __name__ == "__main__":
    main()
