import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'data' / 'reposcout.db'


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        with con:
            yield con
    finally:
        con.close()


def init():
    with connect() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, created TEXT, status TEXT, request TEXT, result TEXT, error TEXT);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, created TEXT, kind TEXT, payload TEXT);
        CREATE INDEX IF NOT EXISTS events_task ON events(task_id,id);
        CREATE TABLE IF NOT EXISTS checkpoints(task_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated TEXT NOT NULL);
        ''')
        con.execute("UPDATE tasks SET status='interrupted', error='服务重启，任务已中断；可重新创建任务。' WHERE status IN ('queued','running')")


def create(request):
    ident = uuid4().hex
    with connect() as con:
        con.execute('INSERT INTO tasks VALUES(?,?,?,?,?,?)', (ident, now(), 'queued', json.dumps(request, ensure_ascii=False), None, None))
    return ident


def get(ident):
    with connect() as con:
        row = con.execute('SELECT * FROM tasks WHERE id=?', (ident,)).fetchone()
    if row is None:
        return None
    item = dict(row)
    for key in ('request','result'):
        item[key] = json.loads(item[key]) if item[key] else None
    return item


def recent():
    with connect() as con:
        return [dict(r) for r in con.execute('SELECT id,created,status FROM tasks ORDER BY created DESC LIMIT 40')]


def checkpoint(ident, payload):
    with connect() as con:
        con.execute('INSERT OR REPLACE INTO checkpoints VALUES(?,?,?)', (ident, json.dumps(payload, ensure_ascii=False), now()))


def load_checkpoint(ident):
    with connect() as con:
        row = con.execute('SELECT payload FROM checkpoints WHERE task_id=?', (ident,)).fetchone()
    return json.loads(row['payload']) if row else None


def claim(ident):
    with connect() as con:
        return con.execute("UPDATE tasks SET status='running' WHERE id=? AND status='queued'", (ident,)).rowcount == 1


def finish(ident, status, result=None, error=None):
    with connect() as con:
        return con.execute("UPDATE tasks SET status=?,result=?,error=? WHERE id=? AND status='running'", (status, json.dumps(result, ensure_ascii=False) if result else None, error, ident)).rowcount == 1


def cancel(ident):
    with connect() as con:
        return con.execute("UPDATE tasks SET status='cancelled' WHERE id=? AND status IN ('queued','running')", (ident,)).rowcount == 1


def event(ident, kind, payload):
    with connect() as con:
        con.execute('INSERT INTO events(task_id,created,kind,payload) VALUES(?,?,?,?)', (ident, now(), kind, json.dumps(payload, ensure_ascii=False)))


def events(ident, after=0):
    with connect() as con:
        rows = con.execute('SELECT * FROM events WHERE task_id=? AND id>? ORDER BY id LIMIT 200', (ident, after)).fetchall()
    return [{**dict(r), 'payload': json.loads(r['payload'])} for r in rows]
