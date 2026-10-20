"""Read-only SQLite snapshot exporter for Generic Ordering.
Run --demo first. Do not put database files or snapshots in GitHub.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile

def folder_from_onedrive():
    for key in ("OneDriveCommercial", "OneDriveConsumer", "OneDrive"):
        if os.environ.get(key):
            return Path(os.environ[key]) / "Orders" / "AutoOrders" / "GenericOrdering"
    raise RuntimeError("OneDrive folder not detected; specify --folder")

def export(db_path, output):
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    # SQLite URI read-only: never create or write to the existing database.
    with sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        orders = [dict(r) for r in db.execute("""
            SELECT id, supplier_name AS supplier, po, status,
                   created_date AS date, placed_date, updated_at
            FROM orders ORDER BY id DESC
        """)]
        lines = [dict(r) for r in db.execute("""
            SELECT id, order_id, line_no, code, description, colour, size,
                   qty, cost, customer, notes
            FROM order_lines ORDER BY order_id, line_no, id
        """)]
    lookup = {o["id"]: o for o in orders}
    for order in orders:
        order["lines"] = []
    for line in lines:
        parent = lookup.get(line.pop("order_id"))
        if parent is not None:
            parent["lines"].append(line)
    snapshot = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "generic-ordering-windows",
        "orders": orders
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".mobile_snapshot_", suffix=".tmp", dir=output.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return len(orders), len(lines)

def demo_db(path):
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE orders(id INTEGER PRIMARY KEY,supplier_name TEXT,po TEXT,status TEXT,
            created_date TEXT,placed_date TEXT,updated_at TEXT);
        CREATE TABLE order_lines(id INTEGER PRIMARY KEY,order_id INTEGER,line_no INTEGER,
            code TEXT,description TEXT,colour TEXT,size TEXT,qty TEXT,cost TEXT,
            customer TEXT,notes TEXT);
        INSERT INTO orders VALUES(1,'Demo Safety Supplies','AT12345','Placed',
            '14/10/2026','15/10/2026','2026-10-15T12:00:00');
        INSERT INTO orders VALUES(2,'Demo Workwear Ltd',NULL,'Active',
            '18/10/2026',NULL,'2026-10-18T09:00:00');
        INSERT INTO order_lines VALUES(1,1,1,'GLV-100','Nitrile gloves',
            'Blue','Medium','12','4.50','Demo customer','');
        INSERT INTO order_lines VALUES(2,2,1,'BOOT-45','Safety boots',
            'Black','9','2','34.00','Demo customer','');
        """)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--demo", action="store_true", help="Use fictional test data only")
    p.add_argument("--folder", type=Path, help="OneDrive GenericOrdering directory")
    p.add_argument("--db", type=Path, help="Explicit SQLite database file")
    p.add_argument("--output", type=Path, help="Explicit JSON output path")
    args = p.parse_args()
    if args.demo:
        root = Path(tempfile.mkdtemp(prefix="generic_ordering_demo_"))
        db_path = root / "generic_orders_demo.db"
        demo_db(db_path)
        output = args.output or root / "mobile_orders_snapshot.json"
    else:
        folder = args.folder or folder_from_onedrive()
        db_path = args.db or folder / "generic_orders.db"
        output = args.output or folder / "mobile_orders_snapshot.json"
    if db_path.resolve() == output.resolve():
        p.error("Output must not overwrite the SQLite database")
    orders, lines = export(db_path, output)
    print(f"Exported {orders} orders and {lines} lines to {output}")

if __name__ == "__main__":
    main()
