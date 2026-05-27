import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_plan
from app.api.routes.fx import get_rates
from app.db.models import Category, Receipt, ReceiptItem, ReceiptStatus
from app.schemas.transactions import TransactionOut, TransactionsListResponse


router = APIRouter()


def _build_query(db, user, from_date, to_date, category_id, store):
    q = (
        db.query(Receipt, ReceiptItem, Category)
        .join(ReceiptItem, ReceiptItem.receipt_id == Receipt.id)
        .outerjoin(Category, Category.id == ReceiptItem.category_id)
        .filter(Receipt.user_id == user.id)
        .filter(Receipt.processing_status == ReceiptStatus.confirmed.value)
    )
    if from_date is not None:
        q = q.filter(Receipt.receipt_date >= from_date)
    if to_date is not None:
        q = q.filter(Receipt.receipt_date <= to_date)
    if category_id is not None:
        q = q.filter(ReceiptItem.category_id == category_id)
    if store:
        q = q.filter(Receipt.store_name.ilike(f"%{store}%"))
    return q.order_by(Receipt.receipt_date.desc().nullslast(), Receipt.id.desc())


@router.get("", response_model=TransactionsListResponse)
def list_transactions(
    from_date: Optional[datetime] = Query(default=None),
    to_date: Optional[datetime] = Query(default=None),
    category_id: Optional[int] = Query(default=None),
    store: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    rows = _build_query(db, user, from_date, to_date, category_id, store).limit(500).all()

    results: list[TransactionOut] = []
    for receipt, item, category in rows:
        results.append(
            TransactionOut(
                id=item.id,
                receipt_id=receipt.id,
                date=receipt.receipt_date,
                store_name=receipt.store_name,
                item_name=item.item_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                item_price=item.item_price,
                currency=receipt.currency,
                category_id=category.id if category else None,
                category_name=category.name if category else None,
            )
        )

    return {"results": results}


# Accountant-shaped exports. Each writer takes (writer, row) and emits a CSV row.
# Receipt purchases are expenses, so amounts are negative in formats that use
# signed totals (QuickBooks/Xero treat the receipt-importing user as the spender).
def _row_generic(writer, receipt, item, category):
    writer.writerow([
        receipt.receipt_date.strftime("%Y-%m-%d") if receipt.receipt_date else "",
        receipt.store_name or "",
        item.item_name,
        category.name if category else "Uncategorized",
        f"{item.item_price:.2f}",
        receipt.currency or "",
    ])


def _row_quickbooks(writer, receipt, item, category):
    """QuickBooks 3-column bank-statement CSV: Date, Description, Amount (negative = spend)."""
    date_str = receipt.receipt_date.strftime("%m/%d/%Y") if receipt.receipt_date else ""
    description = (receipt.store_name or "Receipt") + " — " + item.item_name
    amount = -abs(float(item.item_price))
    writer.writerow([date_str, description, f"{amount:.2f}"])


def _row_xero(writer, receipt, item, category):
    """Xero bank-statement CSV: *Date, *Amount, Payee, Description, Reference."""
    date_str = receipt.receipt_date.strftime("%d/%m/%Y") if receipt.receipt_date else ""
    amount = -abs(float(item.item_price))
    writer.writerow([
        date_str,
        f"{amount:.2f}",
        receipt.store_name or "",
        item.item_name,
        category.name if category else "Uncategorized",
    ])


_FORMAT_WRITERS = {
    "generic":    (["date", "merchant", "item", "category", "price", "currency"], _row_generic),
    "quickbooks": (["Date", "Description", "Amount"],                              _row_quickbooks),
    "xero":       (["*Date", "*Amount", "Payee", "Description", "Reference"],      _row_xero),
}

_PREMIUM_FORMATS = {"quickbooks", "xero"}


@router.get("/export.csv")
def export_transactions_csv(
    from_date: Optional[datetime] = Query(default=None),
    to_date: Optional[datetime] = Query(default=None),
    category_id: Optional[int] = Query(default=None),
    store: Optional[str] = Query(default=None),
    format: str = Query(default="generic", description="generic | quickbooks | xero"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Export confirmed transactions as CSV.

    `format=generic` is free-tier. `quickbooks` and `xero` are Pro+ — they
    produce import-ready files for those accounting platforms.
    """
    fmt = (format or "generic").lower()
    if fmt not in _FORMAT_WRITERS:
        raise HTTPException(status_code=400, detail=f"Unknown format '{fmt}'. Valid: {sorted(_FORMAT_WRITERS)}")

    if fmt in _PREMIUM_FORMATS:
        from app.api.deps import get_user_plan
        plan = get_user_plan(user, db)
        if plan == "free":
            raise HTTPException(
                status_code=402,
                detail=f"CSV format '{fmt}' requires the pro plan.",
                headers={"X-Upgrade-Required": "pro"},
            )

    header, row_writer = _FORMAT_WRITERS[fmt]
    rows = _build_query(db, user, from_date, to_date, category_id, store).all()

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(header)
        yield buf.getvalue()

        for receipt, item, category in rows:
            buf.seek(0)
            buf.truncate(0)
            row_writer(writer, receipt, item, category)
            yield buf.getvalue()

    filename = {
        "generic":    "transactions.csv",
        "quickbooks": "transactions_quickbooks.csv",
        "xero":       "transactions_xero.csv",
    }[fmt]
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export.pdf", dependencies=[Depends(require_plan("pro"))])
def export_transactions_pdf(
    from_date: Optional[datetime] = Query(default=None),
    to_date: Optional[datetime] = Query(default=None),
    category_id: Optional[int] = Query(default=None),
    store: Optional[str] = Query(default=None),
    display_currency: str = Query(default="BAM", min_length=3, max_length=4),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Professional expense report PDF: header, summary by category, item table.
    All amounts converted to display_currency. Use for accounting / reimbursement.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    rates = get_rates()["rates"]
    to_ccy = display_currency.upper()
    to_rate = rates.get(to_ccy)

    def convert(amount: float, from_ccy: str | None) -> float:
        f = (from_ccy or to_ccy).upper()
        fr = rates.get(f)
        if fr is None or to_rate is None:
            return amount
        return amount / fr * to_rate

    rows = _build_query(db, user, from_date, to_date, category_id, store).all()
    if not rows:
        raise HTTPException(status_code=404, detail="No transactions match the filter")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="Expense Report",
    )

    styles = getSampleStyleSheet()
    h1 = styles["Heading1"]
    h2 = ParagraphStyle("h2-tight", parent=styles["Heading2"], spaceBefore=14)
    body = styles["BodyText"]
    small = ParagraphStyle("small", parent=body, fontSize=8, textColor=colors.grey)

    story = []
    story.append(Paragraph("Expense Report", h1))
    story.append(Paragraph(
        f"Account: {user.email} &middot; Generated: "
        f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} &middot; Display currency: {to_ccy}",
        small,
    ))
    rng = ""
    if from_date or to_date:
        rng = f"Range: {from_date.date() if from_date else '—'} to {to_date.date() if to_date else '—'}"
    if rng:
        story.append(Paragraph(rng, small))
    story.append(Spacer(1, 0.5 * cm))

    by_cat: dict[str, float] = {}
    by_store: dict[str, float] = {}
    grand_total = 0.0
    for receipt, item, category in rows:
        amt = convert(float(item.item_price), receipt.currency)
        grand_total += amt
        cat_name = (category.name if category else None) or "Uncategorized"
        by_cat[cat_name] = by_cat.get(cat_name, 0.0) + amt
        if receipt.store_name:
            by_store[receipt.store_name] = by_store.get(receipt.store_name, 0.0) + amt

    summary_data = [["Total", f"{grand_total:,.2f} {to_ccy}"]]
    for c, total in sorted(by_cat.items(), key=lambda kv: -kv[1]):
        summary_data.append([f"   {c}", f"{total:,.2f} {to_ccy}"])

    story.append(Paragraph("Summary by category", h2))
    summary_table = Table(summary_data, colWidths=[10 * cm, 5 * cm])
    summary_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.grey),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(summary_table)

    story.append(Paragraph("Top merchants", h2))
    store_data = [[s, f"{t:,.2f} {to_ccy}"] for s, t in sorted(by_store.items(), key=lambda kv: -kv[1])[:8]]
    if store_data:
        store_table = Table(store_data, colWidths=[10 * cm, 5 * cm])
        store_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(store_table)

    story.append(Paragraph("Transactions", h2))
    table_data = [["Date", "Merchant", "Item", "Category", "Amount"]]
    for receipt, item, category in rows:
        amt = convert(float(item.item_price), receipt.currency)
        date_str = receipt.receipt_date.strftime("%Y-%m-%d") if receipt.receipt_date else ""
        table_data.append([
            date_str,
            (receipt.store_name or "")[:24],
            (item.item_name or "")[:36],
            (category.name if category else "Uncategorized")[:18],
            f"{amt:,.2f}",
        ])
    tx_table = Table(
        table_data,
        colWidths=[2.2 * cm, 4 * cm, 5.5 * cm, 3.3 * cm, 2.5 * cm],
        repeatRows=1,
    )
    tx_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (4, 1), (4, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(tx_table)

    doc.build(story)
    pdf = buf.getvalue()
    buf.close()

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=expense_report.pdf"},
    )
