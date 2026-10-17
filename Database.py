
import json
import re
import sqlite3
from pathlib import Path
from datetime import datetime


# =========================
# 路径配置
# =========================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_FILE = DATA_DIR / "gbf_history.db"


# =========================
# 数据库初始化
# =========================

def init_database():
    """创建数据库和所需的数据表。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_time TEXT NOT NULL,
                source_file TEXT NOT NULL UNIQUE,
                member_count INTEGER NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshot_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER NOT NULL,
                member_id TEXT,
                name TEXT NOT NULL,
                rank INTEGER,
                last_login TEXT,
                FOREIGN KEY (snapshot_id)
                    REFERENCES snapshots(id)
                    ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_members_snapshot
            ON snapshot_members(snapshot_id)
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS member_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER NOT NULL,
                snapshot_time TEXT NOT NULL,
                change_type TEXT NOT NULL,
                member_id TEXT,
                name TEXT NOT NULL,
                old_rank INTEGER,
                new_rank INTEGER,
                FOREIGN KEY (snapshot_id)
                    REFERENCES snapshots(id)
                    ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_changes_time
            ON member_changes(snapshot_time)
        """)


# =========================
# 数据标准化
# =========================

def normalize_member_id(value):
    """将成员 ID 转为字符串；空 ID 保存为 None。"""
    if value is None:
        return None

    value = str(value).strip()
    return value if value else None


def normalize_rank(value):
    """将 Rank425、425 等格式统一转换为整数 425。"""
    if value is None:
        return None

    match = re.search(r"\d+", str(value))

    if not match:
        return None

    return int(match.group())


def get_snapshot_time(json_file):
    """优先从文件名读取采集时间。"""
    match = re.fullmatch(
        r"members_(\d{8}_\d{6})",
        json_file.stem
    )

    if match:
        try:
            return datetime.strptime(
                match.group(1),
                "%Y%m%d_%H%M%S"
            ).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass

    # 兼容不符合命名规则的 JSON 文件
    return datetime.fromtimestamp(
        json_file.stat().st_mtime
    ).strftime("%Y-%m-%d %H:%M:%S")


# =========================
# 读取 JSON
# =========================

def load_members(json_file):
    """读取实际采集格式：id、name、rank、last。"""
    with json_file.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("JSON 顶层格式错误：必须是成员列表。")

    if not data:
        raise ValueError("成员列表为空，取消导入，避免误判全员退出。")

    members = []

    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(
                f"第 {index} 条成员记录不是对象，取消导入。"
            )

        name = str(item.get("name") or "").strip()

        if not name:
            raise ValueError(
                f"第 {index} 条成员记录没有 name，取消导入。"
            )

        members.append({
            # 适配实际 JSON 字段
            "member_id": normalize_member_id(item.get("id")),
            "name": name,
            "rank": normalize_rank(item.get("rank")),
            "last_login": (
                str(item["last"])
                if item.get("last") is not None
                else None
            )
        })

    return members


# =========================
# 匹配前后两次采集的成员
# =========================

def match_members(previous, current):
    """
    优先按成员 ID 匹配。
    ID 缺失或无法匹配时，再按名字匹配。
    """
    previous_used = set()
    current_used = set()
    matched_pairs = []

    # 第一轮：按非空 ID 匹配
    current_id_map = {}

    for j, member in enumerate(current):
        member_id = member["member_id"]

        if member_id:
            current_id_map.setdefault(member_id, []).append(j)

    for i, old in enumerate(previous):
        member_id = old["member_id"]

        if not member_id:
            continue

        candidates = current_id_map.get(member_id, [])

        while candidates and candidates[0] in current_used:
            candidates.pop(0)

        if candidates:
            j = candidates.pop(0)
            matched_pairs.append((i, j))
            previous_used.add(i)
            current_used.add(j)

    # 第二轮：剩余记录按名字匹配
    current_name_map = {}

    for j, member in enumerate(current):
        if j not in current_used:
            current_name_map.setdefault(
                member["name"], []
            ).append(j)

    for i, old in enumerate(previous):
        if i in previous_used:
            continue

        candidates = current_name_map.get(old["name"], [])

        while candidates and candidates[0] in current_used:
            candidates.pop(0)

        if candidates:
            j = candidates.pop(0)
            matched_pairs.append((i, j))
            previous_used.add(i)
            current_used.add(j)

    return matched_pairs, previous_used, current_used


# =========================
# 检测成员变化
# =========================

def detect_changes(
    conn,
    snapshot_id,
    snapshot_time,
    previous_id,
    current
):
    """比较本次采集与前一次采集，并保存变化记录。"""

    if previous_id is None:
        print("这是第一份历史快照，暂时无法比较成员变化。")
        return

    rows = conn.execute("""
        SELECT member_id, name, rank
        FROM snapshot_members
        WHERE snapshot_id = ?
    """, (previous_id,)).fetchall()

    previous = [
        {
            "member_id": row[0],
            "name": row[1],
            "rank": row[2]
        }
        for row in rows
    ]

    matched, previous_used, current_used = match_members(
        previous, current
    )

    changes = []

    # 等级变化
    for i, j in matched:
        old = previous[i]
        new = current[j]

        # 只有新旧等级都有效时才比较
        if (
            old["rank"] is not None
            and new["rank"] is not None
            and old["rank"] != new["rank"]
        ):
            changes.append((
                "rank_changed",
                new["member_id"] or old["member_id"],
                new["name"],
                old["rank"],
                new["rank"]
            ))

    # 新加入的成员
    for j, member in enumerate(current):
        if j not in current_used:
            changes.append((
                "joined",
                member["member_id"],
                member["name"],
                None,
                member["rank"]
            ))

    # 离开的成员
    for i, member in enumerate(previous):
        if i not in previous_used:
            changes.append((
                "left",
                member["member_id"],
                member["name"],
                member["rank"],
                None
            ))

    conn.executemany("""
        INSERT INTO member_changes (
            snapshot_id,
            snapshot_time,
            change_type,
            member_id,
            name,
            old_rank,
            new_rank
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        (
            snapshot_id,
            snapshot_time,
            change_type,
            member_id,
            name,
            old_rank,
            new_rank
        )
        for (
            change_type,
            member_id,
            name,
            old_rank,
            new_rank
        ) in changes
    ])

    print(f"成员变化：发现 {len(changes)} 条记录。")

    for change_type, member_id, name, old_rank, new_rank in changes:
        id_text = f"（ID: {member_id}）" if member_id else ""

        if change_type == "rank_changed":
            print(
                f"[等级变化] {name}{id_text}："
                f"{old_rank} → {new_rank}"
            )
        elif change_type == "joined":
            print(f"[新增成员] {name}{id_text}")
        elif change_type == "left":
            print(f"[退出成员] {name}{id_text}")


# =========================
# 导入单个 JSON 快照
# =========================

def import_json(json_file):
    """导入单个快照；重复文件自动跳过。"""
    current = load_members(json_file)
    snapshot_time = get_snapshot_time(json_file)

    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        existing = conn.execute("""
            SELECT id
            FROM snapshots
            WHERE source_file = ?
        """, (json_file.name,)).fetchone()

        if existing:
            print(f"[跳过] 文件已经导入：{json_file.name}")
            return

        # 选择时间不晚于本次快照的最近一份已导入快照
        previous_row = conn.execute("""
            SELECT id
            FROM snapshots
            WHERE snapshot_time <= ?
            ORDER BY snapshot_time DESC, id DESC
            LIMIT 1
        """, (snapshot_time,)).fetchone()

        previous_id = previous_row[0] if previous_row else None

        cursor = conn.execute("""
            INSERT INTO snapshots (
                snapshot_time,
                source_file,
                member_count
            )
            VALUES (?, ?, ?)
        """, (
            snapshot_time,
            json_file.name,
            len(current)
        ))

        snapshot_id = cursor.lastrowid

        conn.executemany("""
            INSERT INTO snapshot_members (
                snapshot_id,
                member_id,
                name,
                rank,
                last_login
            )
            VALUES (?, ?, ?, ?, ?)
        """, [
            (
                snapshot_id,
                member["member_id"],
                member["name"],
                member["rank"],
                member["last_login"]
            )
            for member in current
        ])

        detect_changes(
            conn,
            snapshot_id,
            snapshot_time,
            previous_id,
            current
        )

    print(
        f"[导入成功] {json_file.name}："
        f"{len(current)} 人，采集时间 {snapshot_time}"
    )


# =========================
# 显示历史快照
# =========================

def show_history():
    """显示所有已导入的快照。"""
    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute("""
            SELECT snapshot_time, source_file, member_count
            FROM snapshots
            ORDER BY snapshot_time, id
        """).fetchall()

    print("\n========== 历史快照 ==========")

    if not rows:
        print("数据库中没有快照记录。")
        return

    for snapshot_time, source_file, member_count in rows:
        print(
            f"{snapshot_time}：{member_count} 人 "
            f"（{source_file}）"
        )

    print(f"共 {len(rows)} 份快照。")


# =========================
# 显示变化记录
# =========================

def show_changes():
    """显示已经保存的成员变化。"""
    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute("""
            SELECT
                snapshot_time,
                change_type,
                member_id,
                name,
                old_rank,
                new_rank
            FROM member_changes
            ORDER BY snapshot_time, id
        """).fetchall()

    print("\n========== 成员变化 ==========")

    if not rows:
        print("目前没有成员变化记录。")
        return

    for time, change_type, member_id, name, old_rank, new_rank in rows:
        id_text = f"（ID: {member_id}）" if member_id else ""

        if change_type == "rank_changed":
            print(
                f"{time} [等级变化] {name}{id_text}："
                f"{old_rank} → {new_rank}"
            )
        elif change_type == "joined":
            print(f"{time} [新增成员] {name}{id_text}")
        elif change_type == "left":
            print(f"{time} [退出成员] {name}{id_text}")


# =========================
# 主程序
# =========================

def main():
    init_database()

    json_files = sorted(
        DATA_DIR.glob("members_*.json"),
        key=lambda path: (get_snapshot_time(path), path.name)
    )

    if not json_files:
        print("找不到成员 JSON 文件，请先运行 Collect_Members.py。")
        return

    print(f"找到 {len(json_files)} 个 JSON 文件，开始按时间顺序导入。")

    success_count = 0
    skipped_count = 0
    failed_count = 0

    for json_file in json_files:
        try:
            with sqlite3.connect(DB_FILE) as conn:
                already_imported = conn.execute("""
                    SELECT 1
                    FROM snapshots
                    WHERE source_file = ?
                """, (json_file.name,)).fetchone()

            if already_imported:
                print(f"[跳过] {json_file.name}")
                skipped_count += 1
                continue

            import_json(json_file)
            success_count += 1

        except (OSError, json.JSONDecodeError, ValueError, sqlite3.Error) as exc:
            print(f"[失败] {json_file.name}：{exc}")
            failed_count += 1

    print("\n========== 导入汇总 ==========")
    print(f"本次成功导入：{success_count} 份")
    print(f"已存在而跳过：{skipped_count} 份")
    print(f"导入失败：{failed_count} 份")

    show_history()
    show_changes()

    print(f"\n数据库位置：{DB_FILE}")


if __name__ == "__main__":
    main()
