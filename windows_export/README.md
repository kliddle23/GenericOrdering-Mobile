# Windows export companion (v0.2 test)

This folder contains a **standalone, read-only** export tool. It does not change the production Generic Ordering Python program, its SQLite schema, or any orders.

## First test (fictional data only)

On Windows, download `export_mobile_snapshot.py` and run:

```powershell
py export_mobile_snapshot.py --demo
```

This creates a temporary fictional SQLite database and a JSON snapshot in your Windows temporary directory. No production files are accessed.

## Optional test against a COPY of your database

**Do not run against your live database yet.** Make a separate test copy of `generic_orders.db` only after closing Generic Ordering and allowing OneDrive to finish syncing.

```powershell
py export_mobile_snapshot.py --db "C:\\Test\\generic_orders.db" --output "C:\\Test\\mobile_orders_snapshot.json"
```

Inspect the output privately. It contains business data, including customer/job names, descriptions, notes and prices; **never commit it to GitHub**.

## Later production use (not enabled yet)

After testing, the standalone script can export `mobile_orders_snapshot.json` to `OneDrive/Orders/AutoOrders/GenericOrdering/`. The iPhone then uses Microsoft Graph to fetch this file after Entra sign-in. The SQLite file itself is never sent to the phone.

Snapshots are read-only copies, not live database views. Changes are not visible on iPhone until the next successful export and OneDrive sync. We will add a separate safe import mechanism before enabling mobile editing.

## Data contract

```json
{
  "schema_version": 1,
  "generated_at": "2026-10-20T08:00:00+00:00",
  "source": "generic-ordering-windows",
  "orders": [
    {
      "id": 1, "supplier": "Demo Supplier", "po": "AT12345",
      "status": "Placed", "date": "14/10/2026",
      "placed_date": "15/10/2026", "updated_at": "2026-10-15T12:00:00",
      "lines": [
        {"id": 1, "line_no": 1, "code": "GLV-100",
         "description": "Demo gloves", "colour": "Blue", "size": "Medium",
         "qty": "12", "cost": "4.50", "customer": "Demo customer", "notes": ""}
      ]
    }
  ]
}
```

The mobile interface does not store the exported snapshot in GitHub or browser local storage. Browser memory holds it during the session.

**Important:** The export is currently manually triggered, not automatic. The live Windows app remains unchanged.
