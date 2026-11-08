"""Cross-process durable bounds for unattended growth, never a provider budget."""
import hashlib
import sqlite3
import time
from pathlib import Path


class GrowthBudget:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = self.connect()
        try:
            with db:
                db.execute('CREATE TABLE IF NOT EXISTS reservations(id INTEGER PRIMARY KEY, key TEXT, created REAL, status TEXT)')
        finally:
            db.close()

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def reserve(self, department, objective, now=None):
        now = time.time() if now is None else now
        key = hashlib.sha256((department + '\0' + objective).encode()).hexdigest()
        db = self.connect()
        try:
            with db:
                db.execute('BEGIN IMMEDIATE')
                if db.execute('SELECT COUNT(*) FROM reservations').fetchone()[0] >= 4096:
                    return None, 'Kayıt sınırı; yönetici incelemesi gerekli'
                if db.execute('SELECT COUNT(*) FROM reservations WHERE created>?', (now - 86400,)).fetchone()[0] >= 8:
                    return None, '24 saatlik sekiz otomatik görev sınırı'
                # A crash consumes its reservation too: restarting never resets limits.
                if db.execute('SELECT 1 FROM reservations WHERE key=? AND created>?', (key, now - 3600)).fetchone():
                    return None, 'Aynı hedef için bir saatlik bekleme'
                cursor = db.execute("INSERT INTO reservations(key,created,status) VALUES(?,?,'reserved')", (key, now))
                return cursor.lastrowid, None
        finally:
            db.close()

    def finish(self, ident, status):
        if status not in ('completed', 'blocked', 'failed'):
            raise ValueError('Invalid growth result')
        db = self.connect()
        try:
            with db:
                db.execute("UPDATE reservations SET status=? WHERE id=? AND status='reserved'", (status, ident))
        finally:
            db.close()
