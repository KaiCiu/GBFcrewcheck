#Report_Changes.py
import sqlite3
from collections import defaultdict
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "gbf_history.db"
OUTPUT_DIR = BASE_DIR / "data" / "changes"


def format_date(snapshot_time):
    """将数据库日期转换为 YYYYMMDD。"""
    return snapshot_time[:10].replace("-", "")


def format_rank(rank):
    """将等级格式化为 Rank 100。"""
    if rank is None:
        return "未知等级"
    return f"Rank {rank}"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not DB_PATH.exists():
        print(f"数据库不存在：{DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # 获取已有快照的所有日期，确保没有变化的日期也生成文件
        snapshots = conn.execute("""
            SELECT snapshot_time
            FROM snapshots
            ORDER BY snapshot_time
        """).fetchall()

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

        dates = sorted({
            format_date(row["snapshot_time"])
            for row in snapshots
        })

        for date_key in dates:
            changes = daily_changes.get(date_key, [])

            # 人员变动：加入 + 离开
            personnel_changes = [
                row for row in changes
                if row["change_type"] in ("joined", "left")
            ]

            # 等级变化
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

            output_path = OUTPUT_DIR / f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:]}.txt"
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
