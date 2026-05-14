import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


_DATE_PATTERNS = [
    r"(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})",
    r"(?P<y>\d{4})[./\-](?P<m>\d{1,2})[./\-](?P<d>\d{1,2})",
    r"(?P<d>\d{1,2})[\/\-](?P<m>\d{1,2})[\/\-](?P<y>\d{4})",
    r"(?P<d>\d{1,2})[./\-](?P<m>\d{1,2})[./\-](?P<y>\d{4})",
    r"(?P<m>\d{1,2})[\/\-](?P<d>\d{1,2})[\/\-](?P<y>\d{4})",
]

_CURRENCY_SYMBOLS: list[tuple[str, str]] = [
    ("USD", "$"),
    ("EUR", "€"),
    ("BAM", "KM"),
    ("GBP", "£"),
    ("JPY", "¥"),
    ("INR", "₹"),
    ("KRW", "₩"),
    ("RUB", "₽"),
    ("TRY", "₺"),
    ("BRL", "R$"),
    ("CAD", "CA$"),
    ("AUD", "A$"),
    ("CHF", "CHF"),
]

_CURRENCY_CODES = {
    "USD", "EUR", "GBP", "JPY", "CNY", "INR", "KRW", "RUB", "TRY",
    "BRL", "CAD", "AUD", "CHF", "SEK", "NOK", "DKK", "BAM",
    # Balkan currencies
    "RSD",   # Serbian dinar
    "HRK",   # Croatian kuna (historical, still on older receipts)
    "MKD",   # Macedonian denar
    "ALL",   # Albanian lek
    "BGN",   # Bulgarian lev
    "HUF",   # Hungarian forint
    "RON",   # Romanian leu
    "PLN",   # Polish zloty
    "CZK",   # Czech koruna
}

# Keywords that must never become items (totals, taxes, fiscal IDs, payment lines, discounts)
_EXCLUDE_LINE_KEYWORDS = {
    # Fiscal IDs
    "JIB", "PIB", "IBF", "RAC", "FISKAL",
    # Tax/VAT
    "VE", "VA", "OSN", "PDU", "PDV", "POV", "POREZ", "TAX", "VAT",
    # Totals / payment
    "UKUPNO", "UPLACENO", "UPLATENO", "GOTOVINA", "POVRAT",
    "TOTAL", "TOIAL", "CHANGE", "CASH", "CARD",
    "PLAĆANJE", "PLACANJE", "PLATITI", "ZA PLATI", "IZNOS",
    "SVEUKUPNO", "SUBTOTAL", "PODRACUN", "PODRAČUN",
    # Discounts
    "RABAT", "POPUST", "DISCOUNT",
    # Copy / receipt type markers
    "KOPIJA", "DUPLICATE",
    # Russian totals
    "ИТОГО", "ОПЛАТЕ", "ВСЕГО", "СУММА",
}

# Tax rate line: "PDV 17%: 8.37", "VAT 8.5%", "17% PDV" — exclude from items
_TAX_RATE_LINE_RE = re.compile(
    r'\b(?:PDV|VAT|POREZ|TAX|OSN|MWS|TVA|IVA|GST|MWST|PDVO|ПОРЕЗ)\b[^%\n]*\d+[.,]?\d*\s*%'
    r'|\d+[.,]?\d*\s*%[^%\n]*\b(?:PDV|VAT|POREZ|TAX|OSN)\b',
    flags=re.IGNORECASE,
)

# QTY × UNIT → TOTAL  (e.g. "Mleko  2x1.50  3.00" or "DIZEL 30L × 1.57/L = 46.97")
_QTY_X_UNIT_RE = re.compile(
    r'^(?P<name>.+?)\s+'
    r'(?P<qty>\d+(?:[.,]\d+)?)\s*'
    r'[xX×\*]\s*'
    r'(?P<unit>\d[\d.,]+)'
    r'(?:\s*(?:KM|BAM|EUR|USD|GBP|RSD|HRK|DIN|MKD|/[^\s=\-→]{0,10})?)?'
    r'\s*(?:[=\-→≈]?\s*)?'
    r'(?P<total>\d[\d.,]*)\s*$',
    flags=re.IGNORECASE,
)

# 4-column tabular: NAME  QTY  UNIT_PRICE  TOTAL  (separated by 2+ spaces or tab)
# Optional trailing single tax-class letter (A/B on BiH receipts)
_FOUR_COL_RE = re.compile(
    r'^(?P<name>[A-Za-zÀ-ɏЀ-ӿ]'
    r'[A-Za-zÀ-ɏЀ-ӿ0-9\s\.\-\_\/\(\)]*?)\s{2,}'
    r'(?P<qty>\d+(?:[.,]\d{1,3})?)\s+'
    r'(?P<unit>\d[\d.,]*)\s+'
    r'(?P<total>\d[\d.,]+)\s*[A-Za-z]?\s*$',
)

# Simple line-ends-in-price pattern (module-level for reuse)
_LINE_PRICE_PAT = re.compile(
    r'^(?P<name>.+?)\s+(?P<cur>[$€£¥₹₩₽₺]|[A-Z]{3})?\s*(?P<num>\d[\d\s.,]*)\s*(?:[A-Z*])?\s*$',
    flags=re.IGNORECASE,
)
_MONEY_DECIMAL_RE = re.compile(r'\d[\d\s]*[.,]\d{1,3}')

# Fiscal/tax keywords to skip in store-name detection
_STORE_SKIP_KW_RE = re.compile(
    r'\b(?:JIB|PIB|IBF|PDV|VAT|FISKAL|FISKALNI|RAČUN|RACUN|UKUPNO|UPLACENO|UPLAĆENO|GOTOVINA)\b',
    flags=re.IGNORECASE,
)


@dataclass
class ParsedItem:
    item_name: str
    quantity: Optional[float]
    unit_price: Optional[float]
    item_price: float
    confidence_score: float = 0.5


@dataclass
class ParsedReceipt:
    receipt_date: Optional[datetime]
    store_name: Optional[str]
    total_amount: Optional[float]
    currency: Optional[str]
    items: list[ParsedItem]
    raw_text_excerpt: str
    detected_language: Optional[str] = None


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _clean_item_name(name: str) -> str:
    """Normalize an OCR item name: remove bad punctuation and fold whitespace."""
    name = re.sub(r"['\"`{}\[\]\(\)\|]", " ", name)
    name = re.sub(r"[^0-9A-Za-zÀ-ɏЀ-ӿ\s&\-\.]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def detect_receipt_date(text: str) -> Optional[datetime]:
    for pat in _DATE_PATTERNS:
        m = re.search(pat, text)
        if not m:
            continue
        gd = m.groupdict()
        try:
            y = int(gd["y"])
            mth = int(gd["m"])
            d = int(gd["d"])
            return datetime(y, mth, d)
        except Exception:
            continue
    return None


def looks_like_bosnia_fiscal_receipt(text: str) -> bool:
    u = (text or "").upper()
    has_jib = bool(re.search(r"\bJIB\s*:", u)) or " JIB:" in u or u.startswith("JIB:")
    has_pib = bool(re.search(r"\bPIB\s*:", u)) or " PIB:" in u
    has_fiskal = "FISKAL" in u or "FISKALNI" in u
    has_racun = "RAČUN" in (text or "").upper() or "RACUN" in u or "RAČUN" in (text or "")
    has_ukupno = "UKUPNO" in u
    has_uplaceno = "UPLACENO" in u or "UPLAĆENO" in (text or "").upper()
    local_hint = any(
        x in u
        for x in (
            "SARAJEVO", "ILIDŽA", "ILIDZA", "MOSTAR", "TUZLA",
            "BANJA LUKA", "BIJELJINA", "ZENICA", "BOSNA", "HERCEGOVINA",
            " BIH", "BIH ",
        )
    )
    if has_jib and has_pib:
        return True
    if (has_fiskal or has_racun) and (has_ukupno or has_uplaceno) and local_hint:
        return True
    if has_ukupno and has_uplaceno and local_hint:
        return True
    return False


def detect_currency(text: str) -> Optional[str]:
    t = text or ""
    if looks_like_bosnia_fiscal_receipt(t):
        return "BAM"

    m = re.search(r"\b(" + "|".join(sorted(_CURRENCY_CODES)) + r")\b", t)
    if m:
        return m.group(1)

    # Turkish Lira: only when not a BiH fiscal receipt
    if re.search(r"\bTL\b", t, flags=re.IGNORECASE) and not looks_like_bosnia_fiscal_receipt(t):
        return "TRY"

    # Serbian dinar short forms (din, RSD) on Serbian receipts
    if re.search(r"\bDIN\b", t, flags=re.IGNORECASE) and not looks_like_bosnia_fiscal_receipt(t):
        return "RSD"

    for code, symbol in _CURRENCY_SYMBOLS:
        if not symbol:
            continue
        if symbol == "KM":
            if re.search(r"(?<![A-Z0-9])KM(?![A-Z0-9])", t, flags=re.IGNORECASE):
                return "BAM"
            continue
        if symbol in t:
            return code

    return None


def detect_store_name(text: str) -> Optional[str]:
    """
    Return the most likely store/company name from the receipt header.

    Skips:
    - Separator lines (dashes, equals, asterisks)
    - Purely numeric / fiscal-code lines
    - Lines containing fiscal/tax keywords (JIB, PIB, PDV, FISKAL, …)
    - Date / time lines
    - Phone-number-like lines
    - Lines starting with a digit followed by a word (street addresses)
    - Lines shorter than 3 alpha chars
    """
    for line in (text or "").splitlines()[:30]:
        line = line.strip()
        if not line:
            continue

        alpha_chars = [ch for ch in line if ch.isalpha()]
        if len(alpha_chars) < 3:
            continue

        # Separator / noise lines
        if re.match(r"^[\-\—\–\=\*\#\~\_\.\s]+$", line):
            continue
        if re.match(r"^[\-\—\–]+\s*\w{1,6}\s*$", line):
            continue

        # Purely numeric / fiscal-code lines
        if re.match(r"^[\d\s\-\.\,\:\/]+$", line):
            continue

        # Fiscal / tax keyword lines (JIB, PIB, PDV, FISKAL, UKUPNO, …)
        if _STORE_SKIP_KW_RE.search(line):
            continue

        # Date / time lines
        if detect_receipt_date(line) is not None:
            continue

        # Phone-number-like lines (digits, spaces, hyphens, parens)
        if re.match(r"^\+?\d[\d\s\-\(\)\.]{5,}$", line):
            continue

        # Address lines starting with a street number
        if re.match(r"^\d+\s+[A-Za-zÀ-ɏЀ-ӿ]", line):
            continue

        words = re.findall(r"[a-zA-ZÀ-ɏЀ-ӿ]{2,}", line)
        if not words:
            continue

        cleaned = line[:60]
        cleaned = re.sub(r"['\"`{}\[\]\(\)\|]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if len(cleaned) >= 3:
            return cleaned

    return None


def parse_money_number(raw: str) -> Optional[float]:
    """
    Convert locale-specific number strings to float.

    Handles: '12.34', '12,34', '1,234.56', '1.234,56', '1 234,56', '1 234.56'
    Also corrects common OCR artefacts like 'O' → '0' in numeric context.
    """
    if raw is None:
        return None

    s = str(raw).strip()
    if not s:
        return None

    # OCR artefact: letter O mistaken for digit 0
    s = re.sub(r'(?<=[,.\s\d])[Oo](?=[,.\s\d]|$)', '0', s)
    s = re.sub(r'^[Oo](?=\d)', '0', s)

    # Normalize whitespace separators (incl. non-breaking spaces)
    s = s.replace(" ", " ").replace(" ", " ")
    s = re.sub(r"\s+", "", s)

    # Keep only digits and separators
    s = re.sub(r"[^0-9,.\-]", "", s)
    if not s or s == "-" or s == ".":
        return None

    has_comma = "," in s
    has_dot = "." in s

    if has_comma and has_dot:
        last_comma = s.rfind(",")
        last_dot = s.rfind(".")
        decimal_sep = "," if last_comma > last_dot else "."
        thousand_sep = "." if decimal_sep == "," else ","
    elif has_comma:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            decimal_sep = ","
        else:
            decimal_sep = None
        thousand_sep = "," if decimal_sep is None else None
    elif has_dot:
        parts = s.split(".")
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            decimal_sep = "."
        else:
            decimal_sep = None
        thousand_sep = "." if decimal_sep is None else None
    else:
        decimal_sep = None
        thousand_sep = None

    if thousand_sep:
        s = s.replace(thousand_sep, "")
    if decimal_sep:
        s = s.replace(decimal_sep, ".")

    try:
        val = float(s)
    except Exception:
        return None
    return val


def extract_total_amount(text: str, currency: Optional[str]) -> Optional[float]:
    """
    Find the grand total amount from a receipt.

    Strategy:
    1. Scan for all "real total" keyword matches (UKUPNO, TOTAL, ИТОГО, etc.)
       and return the LAST one (grand total is always after subtotals).
    2. Fall back to UPLACENO / GOTOVINA (cash paid) if no keyword total found.
    3. Last resort: single currency-symbol match.
    """
    # Ordered by priority — UKUPNO ZA PLATITI > UKUPNO > TOTAL
    # We collect ALL numeric matches and return the last one.
    total_patterns = [
        # English
        r"(?:Grand\s+Total|Total\s+Due|Amount\s+Due|Balance\s+Due|TOTAL)[ \t]*[:\-]?[ \t]*"
        r"(?:[$€£¥₹₩₽₺]|[A-Z]{3})?[ \t]*(?P<num>\d[\d \t.,]*)\b",
        # BiH / Serbian / Croatian — extended form first (more specific)
        r"(?:UKUPNO\s+ZA\s+PLATI(?:TI)?|UKUPNO\s+ZA\s+PLA[ĆC]ANJE|SVEUKUPNO)"
        r"[ \t]*[:\-]?[ \t]*(?P<num>\d[\d \t.,]*)\b",
        r"(?:UKUPNO|ZA\s+PLA[ĆC]ANJE|ZA\s+PLATI(?:TI)?|IZNOS)[^\n\r0-9]*"
        r"(?P<num>\d[\d \t.,]*)\b",
        # Russian
        r"(?:ИТОГО\s+К\s+ОПЛАТЕ|ИТОГО|К\s+ОПЛАТЕ|ВСЕГО|СУММА)[ \t]*[:\-]?[ \t]*"
        r"(?P<num>\d[\d \t.,]*)\b",
        # OCR error variants of TOTAL
        r"(?:T[O0]IAL|T0TAL)[ \t]*[:\-]?[ \t]*(?P<num>\d[\d \t.,]*)\b",
    ]

    all_vals: list[float] = []
    for pat in total_patterns:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            raw = m.group("num") if "num" in m.groupdict() else None
            if raw:
                val = parse_money_number(raw.strip())
                if val is not None and val > 0:
                    all_vals.append(val)

    if all_vals:
        # Return the LAST match — grand total always appears after subtotals on a receipt
        return all_vals[-1]

    # Fallback: UPLACENO / GOTOVINA (cash tendered — equals total for exact-change receipts)
    for kw_pat in [
        r"(?:UPLACENO|UPLAĆENO|GOTOVINA)[ \t]*[:\-]?[ \t]*(?P<num>\d[\d \t.,]*)\b",
    ]:
        m = re.search(kw_pat, text, flags=re.IGNORECASE)
        if m:
            val = parse_money_number(m.group("num").strip())
            if val and val > 0:
                return val

    # Single currency symbol fallback
    found = re.findall(
        r"(?:(?:\bUSD\b|\bEUR\b|\bGBP\b|\bBAM\b|\bRSD\b)|[$€£])\s*(\d[\d\s.,]*)",
        text,
        flags=re.IGNORECASE,
    )
    if len(found) == 1:
        return parse_money_number(found[0])

    return None


def extract_items(text: str, currency: Optional[str]) -> list[ParsedItem]:
    """
    Multi-format item extractor.

    Handles:
    A. Simple:        NAME  PRICE
    B. Qty × Unit:   NAME  QTY×UNIT_PRICE  TOTAL      (e.g. "Mleko 2x1.50 3.00")
    C. 4-column:     NAME  QTY  UNIT_PRICE  TOTAL      (tabular supermarket format)
    D. Name has size: HLJEB 0.5KG  1.20                (one decimal in name, one is price)
    E. Tax lines, discounts, and payment lines are all excluded.
    """
    items: list[ParsedItem] = []

    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line_u = line.upper()

        # ── Skip non-item lines ──────────────────────────────────────────────
        if any(k in line_u for k in _EXCLUDE_LINE_KEYWORDS):
            continue
        if detect_receipt_date(line) is not None:
            continue
        if re.search(r"(?:TOTAL|AMOUNT DUE|CHANGE|CASH|CARD)\b", line, flags=re.IGNORECASE):
            continue
        # Skip tax rate lines: "PDV 17%: 8.37", "17% VAT", etc.
        if _TAX_RATE_LINE_RE.search(line):
            continue
        # Skip separator / decoration lines
        if re.match(r"^[\-\—\–\=\*\#\~\_\.\s]+$", line):
            continue
        # Skip standalone tax class indicators ("A", "B", "*")
        if re.match(r"^[A-Z\*]{1,2}\s*$", line):
            continue

        # ── Pattern B: QTY × UNIT → TOTAL ───────────────────────────────────
        m = _QTY_X_UNIT_RE.match(line)
        if m:
            name = _clean_item_name(m.group("name"))
            total = parse_money_number(m.group("total"))
            if name and len(name) >= 2 and total and 0 < total <= 10_000:
                items.append(
                    ParsedItem(
                        item_name=name,
                        quantity=parse_money_number(m.group("qty")),
                        unit_price=parse_money_number(m.group("unit")),
                        item_price=total,
                        confidence_score=0.82,
                    )
                )
                continue

        # ── Pattern C: 4-column tabular ─────────────────────────────────────
        m = _FOUR_COL_RE.match(line)
        if m:
            name = _clean_item_name(m.group("name"))
            qty = parse_money_number(m.group("qty"))
            unit = parse_money_number(m.group("unit"))
            total = parse_money_number(m.group("total"))
            if name and len(name) >= 2 and total and 0 < total <= 10_000:
                # Cross-check qty × unit ≈ total (within 5 % tolerance for rounding)
                conf = 0.75
                if qty and unit:
                    expected = qty * unit
                    if expected > 0 and abs(expected - total) / max(expected, total) < 0.06:
                        conf = 0.82
                items.append(
                    ParsedItem(
                        item_name=name,
                        quantity=qty,
                        unit_price=unit,
                        item_price=total,
                        confidence_score=conf,
                    )
                )
                continue

        # ── Patterns A / D: Simple line ending in a price ───────────────────
        n_money = len(_MONEY_DECIMAL_RE.findall(line))

        if n_money >= 2:
            # 2+ decimal numbers but no multi-column match.
            # Accept ONLY if exactly 2 money numbers and the line has meaningful text
            # (handles "HLJEB 0.5KG  1.20" where 0.5 is part of the product descriptor).
            if n_money == 2:
                m = _LINE_PRICE_PAT.match(line)
                if m:
                    name_raw = m.group("name").strip()
                    # Require at least one letter in the name portion
                    if re.search(r"[a-zA-ZÀ-ɏЀ-ӿ]", name_raw):
                        name = _clean_item_name(name_raw)
                        price = parse_money_number(m.group("num"))
                        if name and len(name) >= 2 and price and 0 < price <= 10_000:
                            items.append(
                                ParsedItem(
                                    item_name=name,
                                    quantity=None,
                                    unit_price=None,
                                    item_price=price,
                                    confidence_score=0.55,
                                )
                            )
            # 3+ money numbers that didn't match any pattern → likely a header/summary, skip.
            continue

        # Standard simple pattern: "Item name  12.34"
        m = _LINE_PRICE_PAT.match(line)
        if not m:
            continue
        name = _clean_item_name(m.group("name").strip())
        if not name or len(name) < 2:
            continue
        price = parse_money_number(m.group("num"))
        if price is None or price <= 0 or price > 10_000:
            continue
        if len(name) > 80:
            name = name[:80]

        items.append(
            ParsedItem(
                item_name=name,
                quantity=None,
                unit_price=None,
                item_price=price,
                confidence_score=0.62,
            )
        )

    # ── Fallback: lightweight token scan if nothing found ────────────────────
    if not items:
        token_pat = re.compile(r"(?P<name>.+?)\s+(?P<num>\d[\d\s.,]*)\b")
        for raw_line in (text or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            line_u_fb = line.upper()
            if any(k in line_u_fb for k in _EXCLUDE_LINE_KEYWORDS):
                continue
            if _TAX_RATE_LINE_RE.search(line):
                continue
            if detect_receipt_date(line) is not None:
                continue
            if re.search(r"(?:TOTAL|AMOUNT DUE|CHANGE|CASH|CARD)\b", line, flags=re.IGNORECASE):
                continue
            m = token_pat.search(line)
            if not m:
                continue
            name = _clean_item_name(m.group("name"))
            price = parse_money_number(m.group("num"))
            if price and 0 < price <= 10_000 and name and len(name) >= 2:
                items.append(
                    ParsedItem(
                        item_name=name[:80],
                        quantity=None,
                        unit_price=None,
                        item_price=price,
                        confidence_score=0.35,
                    )
                )

    # ── Deduplicate consecutive identical items (OCR noise) ──────────────────
    deduped: list[ParsedItem] = []
    prev = None
    for it in items:
        key = (it.item_name.lower(), round(it.item_price, 2))
        if prev == key:
            continue
        deduped.append(it)
        prev = key

    return deduped[:50]


def infer_primary_commodity(text: str, store_name: Optional[str]) -> str:
    t = text or ""
    for kw in ["PETROL", "DIZEL", "DIESEL", "BENZIN", "NAFTA", "GAS", "FUEL"]:
        if re.search(rf"\b{kw}\b", t, flags=re.IGNORECASE):
            return kw.capitalize()
    if store_name:
        return store_name[:40]
    return "Receipt total"


def parse_receipt(raw_text: str) -> ParsedReceipt:
    text = raw_text or ""
    currency = detect_currency(text)
    receipt_date = detect_receipt_date(text)
    store_name = detect_store_name(text)
    total_amount = extract_total_amount(text, currency)
    items = extract_items(text, currency)

    is_fuel_receipt = bool(
        re.search(r"\b(PETROL|DIZEL|DIESEL|BENZIN|NAFTA|GAS|FUEL)\b", text, flags=re.IGNORECASE)
        and re.search(r"\b(UKUPNO|UPLACENO|UPLATENO|TOTAL|TOIAL)\b", text, flags=re.IGNORECASE)
        and total_amount is not None
    )

    if is_fuel_receipt and total_amount is not None:
        commodity = infer_primary_commodity(text, store_name)
        items = [
            ParsedItem(
                item_name=commodity,
                quantity=None,
                unit_price=None,
                item_price=total_amount,
                confidence_score=0.25,
            )
        ]

    if not items and total_amount is not None:
        commodity = infer_primary_commodity(text, store_name)
        items = [
            ParsedItem(
                item_name=commodity,
                quantity=None,
                unit_price=None,
                item_price=total_amount,
                confidence_score=0.25,
            )
        ]

    excerpt = text[:800]

    return ParsedReceipt(
        receipt_date=receipt_date,
        store_name=store_name,
        total_amount=total_amount,
        currency=currency,
        items=items,
        raw_text_excerpt=excerpt,
    )
