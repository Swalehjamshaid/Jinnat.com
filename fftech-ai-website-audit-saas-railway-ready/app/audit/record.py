# app/audit/record.py
import json
import os

RECORD_FILE = "audit_records.json"

def save_audit_record(url: str, data: dict):
    """
    Save audit results to a local JSON file
    """
    records = {}
    if os.path.exists(RECORD_FILE):
        try:
            with open(RECORD_FILE, "r") as f:
                records = json.load(f)
        except json.JSONDecodeError:
            records = {}

    records[url] = data

    with open(RECORD_FILE, "w") as f:
        json.dump(records, f, indent=2)
