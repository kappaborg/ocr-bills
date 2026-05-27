"""
Bank statement reconciliation.

Accepts a CSV upload (date, merchant, amount) and matches each row against
the user's confirmed receipts. Match criteria:
  - amount within ±5% (default tolerance configurable per call)
  - date within ±2 calendar days
  - merchant substring (case-insensitive) — optional but improves score

Returns three lists: matched, unmatched_bank (no receipt), unmatched_receipts
(receipts not seen in the statement).
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_plan
from app.db.init_db import init_db
from app.db.models import Receipt, ReceiptStatus


router = APIRouter(dependencies=[Depends(require_plan("business"))])


def _parse_amount(s: str) -> Optional[float]:
    if s is None:
        return None
    s = s.strip().replace(",", ".").replace(" ", "")
    if not s:
        return None
    # Allow leading "-" or "(amount)" for debits.
    neg = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    s = s.lstrip("-").strip("()")
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def _parse_date(s: str) -> Optional[datetime]:
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


@router.post("/upload")
def reconcile_upload(
    file: UploadFile = File(...),
    amount_tolerance_pct: float = Query(default=5.0, ge=0.0, le=20.0),
    day_window: int = Query(default=2, ge=0, le=14),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    CSV format (header optional, comma or semicolon delimited):
        date,merchant,amount
        2026-05-12,KONZUM,32.45

    We accept absolute or negative amounts — debits are matched as positive
    receipt totals.
    """
    init_db(db)
    blob = file.file.read().decode("utf-8", errors="replace")

    # Sniff delimiter
    try:
        dialect = csv.Sniffer().sniff(blob[:2048], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(blob), dialect)
    rows = [r for r in reader if r and any(c.strip() for c in r)]
    if not rows:
        raise HTTPException(status_code=400, detail="Empty CSV")

    # Detect header by checking if any cell on row[0] is non-numeric.
    first = rows[0]
    has_header = any(_parse_amount(c) is None and _parse_date(c) is None for c in first[:3])
    data_rows = rows[1:] if has_header else rows

    bank_lines = []
    for idx, r in enumerate(data_rows):
        if len(r) < 3:
            continue
        d = _parse_date(r[0])
        merchant = (r[1] or "").strip()
        amount = _parse_amount(r[2])
        if d is None or amount is None:
            continue
        bank_lines.append({"row": idx + (2 if has_header else 1), "date": d, "merchant": merchant, "amount": abs(amount)})

    if not bank_lines:
        raise HTTPException(status_code=400, detail="No parseable rows. Expected columns: date, merchant, amount")

    receipts = (
        db.query(Receipt)
        .filter(Receipt.user_id == user.id)
        .filter(Receipt.processing_status == ReceiptStatus.confirmed.value)
        .filter(Receipt.total_amount.isnot(None))
        .filter(Receipt.receipt_date.isnot(None))
        .all()
    )

    matched: list[dict] = []
    unmatched_bank: list[dict] = []
    used_receipt_ids: set[int] = set()

    for bank in bank_lines:
        best: Optional[Receipt] = None
        best_score = -1.0
        for r in receipts:
            if r.id in used_receipt_ids:
                continue
            if abs((r.receipt_date - bank["date"]).days) > day_window:
                continue
            tol = max(0.01, bank["amount"] * (amount_tolerance_pct / 100.0))
            if abs(r.total_amount - bank["amount"]) > tol:
                continue
            score = 1.0
            day_diff = abs((r.receipt_date - bank["date"]).days)
            score -= 0.1 * day_diff
            if bank["merchant"] and r.store_name:
                if bank["merchant"].lower() in r.store_name.lower() or r.store_name.lower() in bank["merchant"].lower():
                    score += 0.5
            if score > best_score:
                best_score = score
                best = r
        if best is not None:
            used_receipt_ids.add(best.id)
            matched.append({
                "bank_row": bank["row"],
                "bank_date": bank["date"],
                "bank_merchant": bank["merchant"],
                "bank_amount": bank["amount"],
                "receipt_id": best.id,
                "receipt_store": best.store_name,
                "receipt_total": best.total_amount,
                "receipt_date": best.receipt_date,
                "score": round(best_score, 3),
            })
        else:
            unmatched_bank.append(bank)

    unmatched_receipts = [
        {
            "receipt_id": r.id,
            "store_name": r.store_name,
            "total_amount": r.total_amount,
            "currency": r.currency,
            "receipt_date": r.receipt_date,
        }
        for r in receipts
        if r.id not in used_receipt_ids
    ]

    return {
        "matched": matched,
        "unmatched_bank": unmatched_bank,
        "unmatched_receipts": unmatched_receipts,
        "stats": {
            "bank_rows": len(bank_lines),
            "matched": len(matched),
            "unmatched_bank": len(unmatched_bank),
            "unmatched_receipts": len(unmatched_receipts),
            "match_rate_pct": round(len(matched) / len(bank_lines) * 100.0, 1) if bank_lines else 0,
        },
    }
