"""SQLite 발행 기록 관리"""
import sqlite3
import os
from datetime import date


DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "publish_history.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS publish_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                publish_date TEXT NOT NULL,
                org TEXT,
                keyword TEXT,
                title TEXT,
                search_volume INTEGER,
                blog_url TEXT,
                blog_status TEXT DEFAULT 'pending',
                insta_status TEXT DEFAULT 'pending',
                landing_url TEXT,
                category TEXT,
                memo TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def count_today_published() -> int:
    today = date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM publish_history WHERE publish_date = ? AND blog_status = 'success'",
            (today,)
        ).fetchone()
        return row[0] if row else 0


def insert_record(record: dict) -> int:
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO publish_history
            (publish_date, org, keyword, title, search_volume, blog_url,
             blog_status, insta_status, landing_url, category, memo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.get("publish_date", date.today().isoformat()),
            record.get("org", ""),
            record.get("keyword", ""),
            record.get("title", ""),
            record.get("search_volume"),
            record.get("blog_url", ""),
            record.get("blog_status", "pending"),
            record.get("insta_status", "pending"),
            record.get("landing_url", ""),
            record.get("category", ""),
            record.get("memo", ""),
        ))
        conn.commit()
        return cur.lastrowid


def update_status(record_id: int, blog_status: str = None, insta_status: str = None, blog_url: str = None):
    parts = []
    values = []
    if blog_status:
        parts.append("blog_status = ?")
        values.append(blog_status)
    if insta_status:
        parts.append("insta_status = ?")
        values.append(insta_status)
    if blog_url:
        parts.append("blog_url = ?")
        values.append(blog_url)
    if not parts:
        return
    values.append(record_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE publish_history SET {', '.join(parts)} WHERE id = ?", values)
        conn.commit()


def fetch_all(org_filter: str = None, date_from: str = None, date_to: str = None) -> list:
    query = "SELECT * FROM publish_history WHERE 1=1"
    params = []
    if org_filter and org_filter != "전체":
        query += " AND org = ?"
        params.append(org_filter)
    if date_from:
        query += " AND publish_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND publish_date <= ?"
        params.append(date_to)
    query += " ORDER BY publish_date DESC, id DESC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def update_memo(record_id: int, memo: str):
    with get_conn() as conn:
        conn.execute("UPDATE publish_history SET memo = ? WHERE id = ?", (memo, record_id))
        conn.commit()
