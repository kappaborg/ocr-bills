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
    ("CNY", "¥"),   # shared ¥ — CNY detected via language context
    ("INR", "₹"),
    ("KRW", "₩"),
    ("RUB", "₽"),
    ("TRY", "₺"),
    ("BRL", "R$"),
    ("CAD", "CA$"),
    ("AUD", "A$"),
    ("CHF", "CHF"),
    ("SGD", "S$"),
    ("HKD", "HK$"),
    ("TWD", "NT$"),
    ("PHP", "₱"),
    ("VND", "₫"),
    ("THB", "฿"),
    ("ILS", "₪"),
    ("UAH", "₴"),
    ("GEL", "₾"),
    ("AMD", "֏"),
    ("AZN", "₼"),
    ("KZT", "₸"),
    ("NGN", "₦"),
    ("MYR", "RM"),
    ("IDR", "Rp"),
    ("ZAR", "R"),
    ("PLN", "zł"),
    ("HUF", "Ft"),
]

_CURRENCY_CODES = {
    "USD", "EUR", "GBP", "JPY", "CNY", "INR", "KRW", "RUB", "TRY",
    "BRL", "CAD", "AUD", "CHF", "SEK", "NOK", "DKK", "BAM",
    # European
    "RSD", "HRK", "MKD", "ALL", "BGN", "HUF", "RON", "PLN", "CZK",
    "MDL", "GEL", "AMD", "AZN",
    # Middle East / Africa
    "AED", "SAR", "QAR", "KWD", "BHD", "OMR", "JOD", "EGP", "MAD",
    "DZD", "TND", "ILS", "TRY", "IRR", "IQD", "LBP",
    "ZAR", "NGN", "GHS", "KES", "ETB", "TZS", "UGX", "XOF", "XAF",
    # Asia-Pacific
    "SGD", "HKD", "TWD", "THB", "IDR", "MYR", "PHP", "VND", "KHR",
    "MMK", "LAK", "BDT", "LKR", "NPR", "PKR", "MNT", "KZT", "UZS",
    "KGS", "TJS", "TMT",
    # Americas
    "MXN", "ARS", "CLP", "COP", "PEN", "BOB", "PYG", "UYU",
    # Other
    "NZD", "UAH",
}

# Keywords that must never become items (totals, taxes, fiscal IDs, payment lines, discounts)
_EXCLUDE_LINE_KEYWORDS = {
    # Fiscal IDs
    "JIB", "PIB", "IBF", "RAC", "FISKAL",
    # Tax/VAT
    "VE", "VA", "OSN", "PDU", "PDV", "POV", "POREZ", "TAX", "VAT", "MWST", "TVA", "IVA", "GST", "KDV",
    # Totals / payment — Latin/Cyrillic
    "UKUPNO", "UPLACENO", "UPLATENO", "GOTOVINA", "POVRAT",
    "TOTAL", "TOIAL", "CHANGE", "CASH", "CARD",
    "PLAĆANJE", "PLACANJE", "PLATITI", "ZA PLATI", "IZNOS",
    "SVEUKUPNO", "SUBTOTAL", "PODRACUN", "PODRAČUN",
    # German
    "GESAMT", "SUMME", "BETRAG", "GESAMTBETRAG", "ZAHLBETRAG", "ZWISCHENSUMME",
    # French
    "MONTANT", "PAYER", "SOUS-TOTAL",
    # Spanish / Italian
    "IMPORTE", "TOTALE", "SUBTOTALE",
    # Dutch
    "TOTAAL", "BEDRAG",
    # Scandinavian
    "SUMMA", "BELOPP",
    # Polish
    "RAZEM", "KWOTA",
    # Turkish
    "TOPLAM", "TUTAR",
    # Discounts
    "RABAT", "POPUST", "DISCOUNT", "SCONTO", "REMISE", "RABATT",
    # Copy / receipt type markers
    "KOPIJA", "DUPLICATE",
    # Russian / Cyrillic
    "ИТОГО", "ОПЛАТЕ", "ВСЕГО", "СУММА", "РАЗОМ", "УСЬОГО",
    # Ukrainian
    "СПЛАТИ",
    # Bulgarian
    "ОБЩО",
}

# Arabic-Indic and other non-ASCII numeral translation table → ASCII digits
_NUMERAL_TABLE = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩"   # Arabic-Indic
    "۰۱۲۳۴۵۶۷۸۹"   # Extended Arabic-Indic (Urdu/Farsi)
    "०१२३४५६७८९"   # Devanagari
    "๐๑๒๓๔๕๖๗๘๙"   # Thai
    "০১২৩৪৫৬৭৮৯"   # Bengali
    "૦૧૨૩૪૫૬૭૮૯"   # Gujarati
    "੦੧੨੩੪੫੬੭੮੯"   # Gurmukhi
    "၀၁၂၃၄၅၆၇၈၉"   # Myanmar
    "០១២៣៤៥៦៧៨៩",  # Khmer
    "0123456789" * 9,
)

# Tax rate line: "PDV 17%: 8.37", "VAT 8.5%", "17% PDV" — exclude from items
_TAX_RATE_LINE_RE = re.compile(
    r'\b(?:PDV|VAT|POREZ|TAX|OSN|MWS|TVA|IVA|GST|MWST|PDVO|ПОРЕЗ|KDV|HST|PST)\b[^%\n]*\d+[.,]?\d*\s*%'
    r'|\d+[.,]?\d*\s*%[^%\n]*\b(?:PDV|VAT|POREZ|TAX|OSN|KDV)\b',
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

# 4-column tabular: NAME  QTY  UNIT_PRICE  TOTAL  (2+ spaces or tab)
# Name starts with any Unicode letter (Arabic, CJK, Thai, Latin, Cyrillic, etc.)
_FOUR_COL_RE = re.compile(
    r'^(?P<name>[^\W\d_]'                         # first char: any Unicode letter
    r'[\w\s.\-_/()؀-ۿ฀-๿'    # body: Unicode word chars + common scripts
    r'一-鿿぀-ヿ가-퟿]*?)\s{2,}'
    r'(?P<qty>\d+(?:[.,]\d{1,3})?)\s+'
    r'(?P<unit>\d[\d.,]*)\s+'
    r'(?P<total>\d[\d.,]+)\s*[A-Za-z]?\s*$',
    re.UNICODE,
)

# Simple line-ends-in-price pattern (module-level for reuse)
_LINE_PRICE_PAT = re.compile(
    r'^(?P<name>.+?)\s+(?P<cur>[$€£¥₹₩₽₺₱₫฿₪₴₾₼₸₦]|[A-Z]{3})?\s*(?P<num>\d[\d\s.,]*)\s*(?:[A-Z*])?\s*$',
    flags=re.IGNORECASE,
)
_MONEY_DECIMAL_RE = re.compile(r'\d[\d\s]*[.,]\d{1,3}')

# Fiscal/tax keywords to skip in store-name detection
_STORE_SKIP_KW_RE = re.compile(
    r'\b(?:JIB|PIB|IBF|PDV|VAT|FISKAL|FISKALNI|RAČUN|RACUN|UKUPNO|UPLACENO|UPLAĆENO|GOTOVINA)\b',
    flags=re.IGNORECASE,
)


# Tax-amount line: matches lines like "UKUPNO PDV: 8.37", "PDV: 8.37", "VAT 1.25",
# "PDV 17% 8.37" — captures the final monetary amount, not the rate percent.
_TAX_AMOUNT_RE = re.compile(
    r'\b(?:UKUPNO\s+)?(?:PDV|VAT|POREZ|MWST|TVA|IVA|GST|KDV)\b'
    r'(?:[^\d\n%]{0,30}\d+(?:[.,]\d+)?\s*%)?'   # optional inline rate "17%"
    r'[^\n\d-]*?(?P<amount>\d{1,5}[.,]\d{2})',
    flags=re.IGNORECASE,
)


def extract_tax_amount(text: str) -> Optional[float]:
    """
    Detect the PDV/VAT amount paid on a receipt. Returns the largest plausible
    match (handles split rates like '17% PDV: 6.20 + 5% PDV: 0.50').

    Pre-normalizes whitespace + non-ASCII numerals so OCR variants like
    "PDV  17%   8.37" or Arabic-Indic digits still match.
    """
    if not text:
        return None
    # Collapse runs of whitespace (incl. non-breaking spaces) and translate
    # any non-ASCII numerals to ASCII so the regex below stays simple.
    normalized = text.translate(_NUMERAL_TABLE)
    normalized = re.sub(r"[ \t ]+", " ", normalized)

    best: Optional[float] = None
    for m in _TAX_AMOUNT_RE.finditer(normalized):
        s = m.group("amount").replace(",", ".")
        try:
            value = float(s)
        except ValueError:
            continue
        if 0.01 <= value <= 100_000:
            best = value if best is None else max(best, value)
    return best


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
    # Keep Unicode word chars, spaces, and common punctuation; strip everything else
    name = re.sub(r"[^\w\s&\-\.]", " ", name, flags=re.UNICODE)
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

    # UAE dirham
    if re.search(r"\bAED\b|\bد\.إ\b|درهم", t):
        return "AED"

    # Saudi riyal
    if re.search(r"\bSAR\b|\bر\.س\b|ريال", t):
        return "SAR"

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
    """
    for line in (text or "").splitlines()[:30]:
        line = line.strip()
        if not line:
            continue

        # Must have at least 3 characters that are letters in any script
        letter_chars = [ch for ch in line if re.match(r"[^\W\d_]", ch, re.UNICODE)]
        if len(letter_chars) < 3:
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

        words = re.findall(r"[^\W\d_]{2,}", line, re.UNICODE)
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

    Handles:
    - Western: '12.34', '12,34', '1,234.56', '1.234,56', '1 234,56'
    - Arabic-Indic, Extended Arabic-Indic, Devanagari, Thai, Bengali,
      Gujarati, Gurmukhi, Myanmar, Khmer numerals
    """
    if raw is None:
        return None

    s = str(raw).strip()
    if not s:
        return None

    # Normalize non-ASCII numerals to ASCII digits
    s = s.translate(_NUMERAL_TABLE)
    # Normalize Arabic decimal/thousands separators
    s = s.replace("٫", ".").replace("٬", ",")  # ٫ → .  ٬ → ,

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
    1. Scan for all "real total" keyword matches across 25+ languages and return the LAST one.
    2. Fall back to UPLACENO / GOTOVINA (cash paid) if no keyword total found.
    3. Last resort: single currency-symbol match.
    """
    # Normalize non-ASCII numerals first
    text_norm = (text or "").translate(_NUMERAL_TABLE)

    _N = r"(?P<num>\d[\d \t.,]*)"

    total_patterns = [
        # English
        rf"(?:Grand\s+Total|Total\s+Due|Amount\s+Due|Balance\s+Due|Net\s+Total|TOTAL)[ \t]*[:\-]?[ \t]*"
        rf"(?:[$€£¥₹₩₽₺₱₫฿₪₴₾₼₸₦]|[A-Z]{{3}})?[ \t]*{_N}\b",
        # BiH / Serbian / Croatian
        rf"(?:UKUPNO\s+ZA\s+PLATI(?:TI)?|UKUPNO\s+ZA\s+PLA[ĆC]ANJE|SVEUKUPNO)"
        rf"[ \t]*[:\-]?[ \t]*{_N}\b",
        rf"(?:UKUPNO|ZA\s+PLA[ĆC]ANJE|ZA\s+PLATI(?:TI)?|IZNOS)[^\n\r0-9]*{_N}\b",
        # Russian
        rf"(?:ИТОГО\s+К\s+ОПЛАТЕ|ИТОГО|К\s+ОПЛАТЕ|ВСЕГО|СУММА)[ \t]*[:\-]?[ \t]*{_N}\b",
        # Ukrainian
        rf"(?:РАЗОМ|ДО\s+СПЛАТИ|УСЬОГО|ЗАГАЛЬНА\s+СУМА)[ \t]*[:\-]?[ \t]*{_N}\b",
        # Bulgarian
        rf"(?:ОБЩО|ЗА\s+ПЛАЩАНЕ|СУМА)[ \t]*[:\-]?[ \t]*{_N}\b",
        # German
        rf"(?:GESAMTBETRAG|GESAMT|ZAHLBETRAG|ZU\s+ZAHLEN|SUMME|RECHNUNGSBETRAG|BETRAG)"
        rf"[ \t]*[:\-]?[ \t]*{_N}\b",
        # French
        rf"(?:MONTANT\s+TTC|TOTAL\s+TTC|NET\s+À\s+PAYER|TOTAL\s+À\s+PAYER|MONTANT\s+TOTAL|MONTANT)"
        rf"[ \t]*[:\-]?[ \t]*{_N}\b",
        # Spanish
        rf"(?:IMPORTE\s+TOTAL|TOTAL\s+A\s+PAGAR|TOTAL\s+GENERAL|IMPORTE)[ \t]*[:\-]?[ \t]*{_N}\b",
        # Italian
        rf"(?:TOTALE\s+COMPLESSIVO|TOTALE\s+GENERALE|IMPORTO\s+TOTALE|DA\s+PAGARE|TOTALE)"
        rf"[ \t]*[:\-]?[ \t]*{_N}\b",
        # Dutch
        rf"(?:TOTAAL\s+BEDRAG|TE\s+BETALEN|TOTAAL)[ \t]*[:\-]?[ \t]*{_N}\b",
        # Swedish / Norwegian / Danish
        rf"(?:ATT\s+BETALA|Å\s+BETALE|I\s+ALT|TOTALT|SUMMA|BELOPP)[ \t]*[:\-]?[ \t]*{_N}\b",
        # Finnish
        rf"(?:YHTEENSÄ|MAKSETTAVA\s+SUMMA|MAKSETTAVA)[ \t]*[:\-]?[ \t]*{_N}\b",
        # Polish
        rf"(?:DO\s+ZAP[ŁL]ATY|[ŁL]ĄCZNA\s+KWOTA|RAZEM)[ \t]*[:\-]?[ \t]*{_N}\b",
        # Czech / Slovak
        rf"(?:K\s+[ÚU]HRAD[ĚE]|CELKOV[AÁ]\s+[ČC][ÁA]STKA|CELKEM)[ \t]*[:\-]?[ \t]*{_N}\b",
        # Hungarian
        rf"(?:FIZETEND[OŐ]|V[EÉ]G[OÖ]SSZEG|[OÖ]SSZESEN)[ \t]*[:\-]?[ \t]*{_N}\b",
        # Romanian
        rf"(?:DE\s+PLAT[AĂ]|SUMA\s+TOTAL[AĂ]|TOTAL)[ \t]*[:\-]?[ \t]*{_N}\b",
        # Turkish
        rf"(?:GENEL\s+TOPLAM|[OÖ]DENECEK\s+TUTAR|TOPLAM\s+TUTAR|TOPLAM|TUTAR)[ \t]*[:\-]?[ \t]*{_N}\b",
        # Arabic (right-to-left; OCR may produce partial matches)
        rf"(?:المجموع\s+الكلي|الإجمالي|المبلغ\s+الإجمالي|المجموع|مجموع)[ \t]*[:\-]?[ \t]*{_N}\b",
        # Hebrew
        rf'(?:סה"כ\s+לתשלום|לתשלום|סה"כ|סכום)[ \t]*[:\-]?[ \t]*{_N}\b',
        # Greek
        rf"(?:ΣΥΝΟΛΟ\s+ΠΛΗΡΩΤΕΟ|ΠΛΗΡΩΤΕΟ|ΣΥΝΟΛΟ)[ \t]*[:\-]?[ \t]*{_N}\b",
        # Chinese Simplified
        rf"(?:应付金额|实付金额|结账金额|应付|总计|合计|小计)[ \t]*[:\-]?[ \t]*[¥￥]?{_N}\b",
        # Chinese Traditional / Hong Kong
        rf"(?:應付金額|實付金額|合計|總計|小計)[ \t]*[:\-]?[ \t]*[¥$]?{_N}\b",
        # Japanese
        rf"(?:お支払合計|お会計|ご請求額|合計金額|合計|小計)[ \t]*[:\-]?[ \t]*[¥￥]?{_N}\b",
        # Korean
        rf"(?:합계\s*금액|결제\s*금액|총\s*금액|합\s*계|총액)[ \t]*[:\-]?[ \t]*[₩]?{_N}\b",
        # Thai
        rf"(?:ยอดรวมทั้งสิ้น|ยอดชำระ|ยอดรวม|รวมทั้งสิ้น|รวม)[ \t]*[:\-]?[ \t]*[฿]?{_N}\b",
        # Vietnamese
        rf"(?:TỔNG\s+CỘNG|TỔNG\s+TIỀN|THÀNH\s+TIỀN|CỘNG)[ \t]*[:\-]?[ \t]*{_N}\b",
        # Indonesian / Malay
        rf"(?:TOTAL\s+BAYAR|JUMLAH\s+BAYAR|JUMLAH|TOTAL)[ \t]*[:\-]?[ \t]*{_N}\b",
        # OCR error variants of TOTAL
        rf"(?:T[O0]IAL|T0TAL)[ \t]*[:\-]?[ \t]*{_N}\b",
    ]

    all_vals: list[float] = []
    for pat in total_patterns:
        for m in re.finditer(pat, text_norm, flags=re.IGNORECASE | re.UNICODE):
            raw = m.group("num") if "num" in m.groupdict() else None
            if raw:
                val = parse_money_number(raw.strip())
                if val is not None and val > 0:
                    all_vals.append(val)

    if all_vals:
        return all_vals[-1]

    # Fallback: UPLACENO / GOTOVINA (cash tendered)
    for kw_pat in [
        rf"(?:UPLACENO|UPLAĆENO|GOTOVINA)[ \t]*[:\-]?[ \t]*{_N}\b",
        rf"(?:НАЛИЧНЫЕ|ОПЛАЧЕНО|ВНЕСЕНО)[ \t]*[:\-]?[ \t]*{_N}\b",
    ]:
        m = re.search(kw_pat, text_norm, flags=re.IGNORECASE)
        if m:
            val = parse_money_number(m.group("num").strip())
            if val and val > 0:
                return val

    # Single currency symbol/code fallback
    found = re.findall(
        r"(?:(?:\bUSD\b|\bEUR\b|\bGBP\b|\bBAM\b|\bRSD\b)|[$€£¥₹₩₽₺₱₫฿₪₴])\s*(\d[\d\s.,]*)",
        text_norm,
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
    B. Qty × Unit:   NAME  QTY×UNIT_PRICE  TOTAL
    C. 4-column:     NAME  QTY  UNIT_PRICE  TOTAL  (tabular)
    D. Name has size: HLJEB 0.5KG  1.20
    E. Tax lines, discounts, and payment lines are all excluded.
    """
    items: list[ParsedItem] = []

    # Normalize non-ASCII numerals in the text before parsing
    text_norm = (text or "").translate(_NUMERAL_TABLE)

    for raw_line in text_norm.splitlines():
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
            if n_money == 2:
                m = _LINE_PRICE_PAT.match(line)
                if m:
                    name_raw = m.group("name").strip()
                    # Require at least one letter (any script) in the name
                    if re.search(r"[^\W\d_]", name_raw, re.UNICODE):
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
        for raw_line in text_norm.splitlines():
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
