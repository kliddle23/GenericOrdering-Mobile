"""Optional Windows companion: refresh the private mobile JSON snapshot after DB changes.

Run independently of Generic Ordering. Does not modify the Windows application or SQLite.
Ctrl+C to stop. Do not commit JSON snapshots to a public repository.
"""
import argparse
import logging
import os
from pathlib import Path
import sqlite3
import sys
import time

from export_mobile_snapshot import export, folder_from_onedrive

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, help="GenericOrdering OneDrive folder")
    parser.add_argument("--interval", type=float, default=15, help="Poll interval in seconds (default 15)")
    parser.add_argument("--settle", type=float, default=10, help="Wait after last database change (default 10 seconds)")
    parser.add_argument("--once", action="store_true", help="Export once and exit")
    args = parser.parse_args()
    if args.interval < 2 or args.settle < 0:
        parser.error("Interval must be >= 2 seconds; settle must be >= 0")
    folder = args.folder or folder_from_onedrive()
    db_path = folder / "generic_orders.db"
    output = folder / "mobile_orders_snapshot.json"
    print("Watching:", db_path)
    print("Snapshot:", output)
    print("This helper reads SQLite only. Press Ctrl+C to stop.", flush=True)
    last_signature = None
    pending_since = None
    exported_signature = None
    while True:
        try:
            stat = db_path.stat()
            signature = (stat.st_mtime_ns, stat.st_size)
            if signature != last_signature:
                last_signature = signature
                pending_since = time.monotonic()
            if signature != exported_signature and (args.once or time.monotonic() - pending_since >= args.settle):
                try:
                    orders, lines = export(db_path, output)
                    exported_signature = signature
                    print(f"Snapshot refreshed: {orders} orders, {lines} lines ({time.strftime('%Y-%m-%d %H:%M:%S')})", flush=True)
                except (sqlite3.Error, OSError) as exc:
                    print(f"Export deferred (will retry): {exc}", file=sys.stderr, flush=True)
            if args.once:
                if signature != exported_signature:
                    raise RuntimeError("One-time export failed")
                return
        except FileNotFoundError:
            print("Database not found; waiting for OneDrive sync.", file=sys.stderr, flush=True)
            if args.once:
                raise
        time.sleep(args.interval)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
