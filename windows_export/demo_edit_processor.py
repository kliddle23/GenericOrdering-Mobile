"""Offline-only prototype: apply fictional mobile edits to a disposable SQLite DB.

Never point this at the real generic_orders.db. No OneDrive or network access.
Run: python -m unittest discover -s windows_export -p 'test_demo_processor.py'
"""
import json
import sqlite3
from pathlib import Path
from test_edit_validation import validate_and_apply_in_memory, InvalidEdit, EditConflict

SCHEMA = """
CREATE TABLE orders (id INTEGER PRIMARY KEY, updated_at TEXT NOT NULL);
CREATE TABLE order_lines (id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL,
 description TEXT, colour TEXT, size TEXT, qty TEXT, notes TEXT);
CREATE TABLE processed_requests (request_id TEXT PRIMARY KEY, payload TEXT NOT NULL,
 outcome TEXT NOT NULL);
"""

def create_disposable_db(path):
    """Explicitly refuse to overwrite an existing database."""
    path = Path(path)
    if path.exists():
        raise FileExistsError("Refusing to overwrite existing database")
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)
        db.execute("INSERT INTO orders VALUES (1, 'demo-v1')")
        db.execute("INSERT INTO order_lines VALUES (3, 1, 'Demo gloves', 'Blue', 'M', '1', '')")

def apply_demo_request(db_path, request):
    """Transactional, idempotent edit against ONLY our identifiable demo schema."""
    if not isinstance(request, dict):
        raise InvalidEdit("Request must be an object")
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128 or request_id == "DEMO-NOT-SUBMITTED":
        raise InvalidEdit("A unique request ID is required")
    payload = json.dumps(request, sort_keys=True, separators=(",", ":"))
    db = sqlite3.connect(db_path, timeout=5, isolation_level=None)
    try:
        db.execute("BEGIN IMMEDIATE")
        required = {"orders", "order_lines", "processed_requests"}
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not required.issubset(tables):
            raise InvalidEdit("Not a disposable demo processor database")
        # Production Generic Ordering does not have this marker table.
        existing = db.execute("SELECT payload, outcome FROM processed_requests WHERE request_id=?", (request_id,)).fetchone()
        if existing:
            if existing[0] != payload:
                raise InvalidEdit("Request ID reused with different contents")
            db.commit()
            return "duplicate"
        row = db.execute("SELECT id, updated_at FROM orders WHERE id=?", (request.get("order_id"),)).fetchone()
        if not row:
            raise EditConflict("Order not found")
        lines = [dict(zip(("id","description","colour","size","qty","notes"), r)) for r in
                 db.execute("SELECT id,description,colour,size,qty,notes FROM order_lines WHERE order_id=?", (row[0],))]
        original = {"id": row[0], "updated_at": row[1], "lines": lines}
        updated = validate_and_apply_in_memory(request, original)
        for change in request["changes"]:
            line = next(l for l in updated["lines"] if l["id"] == change["line_id"])
            db.execute("UPDATE order_lines SET "+change["field"]+"=? WHERE id=? AND order_id=?",
                       (line[change["field"]], change["line_id"], row[0]))
        # Bump version to ensure stale requests are rejected.
        db.execute("UPDATE orders SET updated_at=? WHERE id=?", (request_id, row[0]))
        db.execute("INSERT INTO processed_requests VALUES (?,?,?)", (request_id, payload, "applied"))
        db.commit()
        return "applied"
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
