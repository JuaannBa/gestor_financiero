import csv
import hashlib
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

DATE_FORMATS = [
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%d/%m/%y",
    "%m/%d/%Y",
]

INCOME_SYNONYMS = {"income", "ingreso", "ingresos", "in", "i"}
EXPENSE_SYNONYMS = {"expense", "gasto", "gastos", "out", "e", "cargo"}


CANDIDATE_DELIMITERS = [";", ",", "\t", "|"]

# Sniffer only flags a header when these heuristics agree: the first row shares the
# modal column count and carries more alphabetic tokens than the row after it.


def detect_header(sample: str, delimiter: str) -> bool:
    lines = [line for line in sample.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    first = next(csv.reader([lines[0]], delimiter=delimiter))
    second = next(csv.reader([lines[1]], delimiter=delimiter))
    if len(first) != len(second) or len(first) < 2:
        return False
    alpha = lambda cells: sum(any(ch.isalpha() for ch in c) for c in cells)  # noqa: E731
    return alpha(first) > alpha(second)


def detect_delimiter(sample: str) -> str:
    """Pick the delimiter that splits rows into the most consistent column counts.

    csv.Sniffer misfires on European amounts (decimal commas look like a delimiter),
    so we score candidates ourselves and prefer ';' on ties.
    """
    lines = [line for line in sample.splitlines() if line.strip()][:20]
    best = ","
    best_score = (-1, -1)
    for candidate in CANDIDATE_DELIMITERS:
        counts = [line.count(candidate) for line in lines]
        if not counts or counts[0] == 0:
            continue
        modal = max(set(counts), key=counts.count)
        score = (modal, counts.count(modal))
        if score > best_score:
            best_score = score
            best = candidate
    return best


def parse_csv(content: str, has_header: bool | None = None) -> dict:
    """Detect delimiter/header, return columns and a sample of raw rows."""
    sample = content[:4096]
    delimiter = detect_delimiter(sample)
    if has_header is None:
        has_header = detect_header(sample, delimiter)

    rows = [
        r
        for r in csv.reader(io.StringIO(content), delimiter=delimiter)
        if any(cell.strip() for cell in r)
    ]
    if not rows:
        raise ValueError("The file has no rows")

    if has_header:
        columns = [c.strip() or f"col{i}" for i, c in enumerate(rows[0])]
        data_rows = rows[1:]
    else:
        width = max(len(r) for r in rows)
        columns = [f"col{i}" for i in range(width)]
        data_rows = rows

    return {
        "delimiter": delimiter,
        "has_header": has_header,
        "columns": columns,
        "sample_rows": [r for r in data_rows[:20]],
        "total_rows": len(data_rows),
    }


def parse_amount(raw: str) -> Decimal:
    """Parse '1.234,56', '1,234.56', '(12.00)', '-5', '12,00 EUR' into Decimal."""
    s = raw.strip().replace("\u00a0", " ")
    for token in ("EUR", "USD", "GBP", "€", "$", "£"):
        s = s.replace(token, "")
    s = s.replace(" ", "")

    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    if s.startswith("-"):
        negative = True
        s = s[1:]
    elif s.startswith("+"):
        s = s[1:]
    if s.endswith("-"):  # trailing minus used by some banks
        negative = True
        s = s[:-1]

    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")  # 1.234,56
        else:
            s = s.replace(",", "")  # 1,234.56
    elif "," in s:
        head, _, tail = s.rpartition(",")
        if len(tail) == 2 and head.replace(".", "").replace("-", "").isdigit():
            s = f"{head}.{tail}"  # decimal comma: 12,34
        else:
            s = s.replace(",", "")  # thousands: 1,234
    elif "." in s:
        head, _, tail = s.rpartition(".")
        if len(tail) == 3 and head.replace("-", "").isdigit():
            s = s.replace(".", "")  # EU thousands: 1.234

    try:
        value = Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"Cannot parse amount: {raw!r}") from exc
    return -value if negative else value


def parse_date(raw: str, fmt: str | None = None) -> date:
    s = raw.strip()
    formats = [fmt] if fmt else DATE_FORMATS
    for f in formats:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {raw!r}")


def fingerprint(
    user_id: int, account_id: int, tx_date: date, amount: Decimal, payee: str, tx_type: str
) -> str:
    key = f"{user_id}|{account_id}|{tx_date.isoformat()}|{amount}|{payee.strip().lower()}|{tx_type}"
    return hashlib.sha256(key.encode()).hexdigest()


def resolve_column(value, columns: list[str]) -> int:
    """Mapping column value: int index or header name -> index."""
    if isinstance(value, int):
        idx = value
    else:
        try:
            idx = columns.index(str(value))
        except ValueError as exc:
            raise ValueError(f"Unknown column: {value!r}") from exc
    if not 0 <= idx < len(columns):
        raise ValueError(f"Column index out of range: {idx}")
    return idx


def parse_row(row: list[str], mapping: dict, columns: list[str], user_id: int) -> dict:
    """Turn one CSV row into transaction fields (raises ValueError with context)."""

    def cell(field: str) -> str:
        idx = mapping.get(field)
        if idx is None:
            return ""
        if idx >= len(row):
            raise ValueError(f"Missing column for {field}")
        return row[idx].strip()

    raw_date = cell("date")
    if not raw_date:
        raise ValueError("Date is empty")
    tx_date = parse_date(raw_date, mapping.get("date_format"))

    raw_amount = cell("amount")
    if not raw_amount:
        raise ValueError("Amount is empty")
    amount = parse_amount(raw_amount)

    raw_type = cell("type") if mapping.get("type") is not None else ""
    if raw_type:
        norm = raw_type.strip().lower()
        if norm in INCOME_SYNONYMS:
            tx_type = "income"
        elif norm in EXPENSE_SYNONYMS:
            tx_type = "expense"
        else:
            raise ValueError(f"Unknown type: {raw_type!r}")
    else:
        tx_type = "expense" if amount < 0 else "income"

    return {
        "date": tx_date,
        "amount": abs(amount),
        "type": tx_type,
        "payee": cell("payee"),
        "notes": cell("notes"),
        "category_name": cell("category") if mapping.get("category") is not None else "",
        "fingerprint": None,  # filled by caller once account is known
    }
