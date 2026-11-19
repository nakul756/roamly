"""A SQLite connection that is safe to share between FastAPI's worker threads.
Every statement runs under one lock and write statements are committed immediately.
`execute()` returns an object with fetchone(), fetchall() and lastrowid, like a normal cursor."""
import sqlite3
import threading


class _Result:
    def __init__(self, rows, lastrowid, rowcount):
        self.rows, self.lastrowid, self.rowcount = rows, lastrowid, rowcount

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class SafeCon:
    def __init__(self, path):
        self._c = sqlite3.connect(path, check_same_thread=False)
        self._l = threading.RLock()
        self._c.execute("PRAGMA journal_mode=WAL")

    def execute(self, sql, args=()):
        with self._l:
            cur = self._c.execute(sql, args)
            rows = cur.fetchall() if cur.description else []
            if not sql.lstrip().upper().startswith("SELECT"):
                self._c.commit()
            return _Result(rows, cur.lastrowid, cur.rowcount)

    def commit(self):   # kept so older code that calls commit() still works
        pass

    def add_column(self, table, column, decl):
        """ALTER TABLE ... ADD COLUMN, ignored if the column already exists (simple migration)."""
        with self._l:
            have = [r[1] for r in self._c.execute(f"PRAGMA table_info({table})").fetchall()]
            if column not in have:
                self._c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
                self._c.commit()
