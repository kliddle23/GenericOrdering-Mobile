"""Validate mobile edit requests against fictional records only.

No OneDrive access, no SQLite writes, no production database access.
The production import processor is intentionally NOT implemented.
"""
from copy import deepcopy
import json
import unittest

EDITABLE = {"description", "colour", "size", "qty", "notes"}
MAX_LENGTH = {"description": 500, "colour": 100, "size": 100, "qty": 32, "notes": 500}

class EditConflict(Exception):
    pass

class InvalidEdit(Exception):
    pass

def validate_and_apply_in_memory(request, order):
    """Apply only after every requested field passes precondition checks."""
    if not isinstance(request, dict) or request.get("schema_version") != 1:
        raise InvalidEdit("Unsupported request schema")
    if request.get("request_type") != "update_order_lines":
        raise InvalidEdit("Unsupported request type")
    if type(request.get("order_id")) is not int or request["order_id"] != order["id"]:
        raise InvalidEdit("Invalid order identifier")
    if request.get("expected_updated_at") != order.get("updated_at"):
        raise EditConflict("Order changed since the snapshot")
    changes = request.get("changes")
    if not isinstance(changes, list) or not 0 < len(changes) <= 100:
        raise InvalidEdit("Expected 1–100 changes")
    result = deepcopy(order)
    seen = set()
    for change in changes:
        if not isinstance(change, dict):
            raise InvalidEdit("Invalid change")
        line_id, field = change.get("line_id"), change.get("field")
        if type(line_id) is not int or field not in EDITABLE:
            raise InvalidEdit("Unknown line or field")
        if (line_id, field) in seen:
            raise InvalidEdit("Duplicate field edit")
        seen.add((line_id, field))
        line = next((x for x in result["lines"] if x["id"] == line_id), None)
        if line is None:
            raise EditConflict("Order line no longer exists")
        expected, value = change.get("expected"), change.get("value")
        if not isinstance(expected, str) or not isinstance(value, str):
            raise InvalidEdit("Expected and replacement values must be text")
        if len(value) > MAX_LENGTH[field]:
            raise InvalidEdit("Value too long")
        if str(line.get(field) or "") != expected:
            raise EditConflict("Line field has changed")
        if field == "qty":
            from decimal import Decimal, InvalidOperation
            try:
                quantity = Decimal(value)
            except InvalidOperation:
                raise InvalidEdit("Invalid quantity")
            if not quantity.is_finite() or not 0 < quantity <= 99999999:
                raise InvalidEdit("Invalid quantity")
            if quantity.as_tuple().exponent < -3:
                raise InvalidEdit("Too many decimal places")
        line[field] = value
    return result

class Tests(unittest.TestCase):
    def setUp(self):
        self.order = {"id": 1, "updated_at": "demo-v1",
                      "lines": [{"id": 3, "qty": "1", "description": "Demo"}]}
        self.request = {"schema_version": 1, "request_type": "update_order_lines",
                        "request_id": "fictional", "order_id": 1,
                        "expected_updated_at": "demo-v1",
                        "changes": [{"line_id": 3, "field": "qty", "expected": "1", "value": "2"}]}

    def test_valid(self):
        result = validate_and_apply_in_memory(self.request, self.order)
        self.assertEqual(result["lines"][0]["qty"], "2")
        self.assertEqual(self.order["lines"][0]["qty"], "1")

    def test_stale_order(self):
        self.order["updated_at"] = "demo-v2"
        with self.assertRaises(EditConflict):
            validate_and_apply_in_memory(self.request, self.order)

    def test_field_conflict(self):
        self.order["lines"][0]["qty"] = "5"
        with self.assertRaises(EditConflict):
            validate_and_apply_in_memory(self.request, self.order)

    def test_forbidden_field(self):
        self.request["changes"][0]["field"] = "cost"
        with self.assertRaises(InvalidEdit):
            validate_and_apply_in_memory(self.request, self.order)

    def test_invalid_qty(self):
        self.request["changes"][0]["value"] = "-10"
        with self.assertRaises(InvalidEdit):
            validate_and_apply_in_memory(self.request, self.order)

if __name__ == "__main__":
    unittest.main()
