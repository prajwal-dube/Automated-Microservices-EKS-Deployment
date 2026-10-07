"""PostgreSQL at deployment; SQLite only for offline development and tests."""
import os
import sqlite3
import time
from contextlib import contextmanager

class Database:
    def __init__(self):
        self.sqlite_path = os.getenv("SQLITE_PATH")

    @contextmanager
    def connect(self):
        if self.sqlite_path:
            conn = sqlite3.connect(self.sqlite_path, timeout=5)
        else:
            import psycopg
            conn = psycopg.connect(
                host=os.getenv("DB_HOST", "postgres"),
                port=int(os.getenv("DB_PORT", "5432")),
                dbname=os.getenv("DB_NAME", "netops"),
                user=os.getenv("DB_USER", "netops"),
                password=os.environ["DB_PASSWORD"],
                connect_timeout=3,
                options="-c statement_timeout=5000",
            )
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def query(self, conn, sql, params=()):
        return conn.execute(sql if self.sqlite_path else sql.replace("?", "%s"), params)

    def migrate(self):
        with self.connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS observations (
                id TEXT PRIMARY KEY, target TEXT NOT NULL,
                latency_ms DOUBLE PRECISION NOT NULL,
                status_code INTEGER, healthy BOOLEAN NOT NULL,
                observed_at DOUBLE PRECISION NOT NULL
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_target_time ON observations(target, observed_at DESC)")

    def ready(self):
        with self.connect() as conn:
            conn.execute("SELECT id FROM observations LIMIT 1")

    def insert(self, item):
        with self.connect() as conn:
            self.query(conn, "INSERT INTO observations VALUES (?, ?, ?, ?, ?, ?)",
                (item["id"], item["target"], item["latency_ms"], item["status_code"], item["healthy"], item["observed_at"]))
            self.query(conn, "DELETE FROM observations WHERE observed_at < ?",
                (time.time() - int(os.getenv("RETENTION_DAYS", "7")) * 86400,))

    def latest(self):
        with self.connect() as conn:
            return conn.execute("""SELECT id, target, latency_ms, status_code, healthy, observed_at
                FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY target ORDER BY observed_at DESC, id DESC) AS rank
                FROM observations) AS ranked WHERE rank=1 ORDER BY target""").fetchall()

    def history(self, target, limit):
        with self.connect() as conn:
            return self.query(conn, """SELECT id, target, latency_ms, status_code, healthy, observed_at
                FROM observations WHERE target=? ORDER BY observed_at DESC, id DESC LIMIT ?""", (target, limit)).fetchall()
