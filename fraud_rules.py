# Comprehensive Explainable Fraud Rules Engine
# Detects fraud across ALL invoice dimensions:
# 1. Date & Chronological Verification (Invalid calendar dates like 29/02/2026, future dates, Due Date < Invoice Date)
# 2. Line Items Multiplication & Sum Integrity (Qty * Unit Price = Line Total, sum(Line Totals) = Subtotal)
# 3. Tax Anomaly Detection (tax / subtotal ratio, absurd percentages like 150%, negative tax)
# 4. Mathematical Balance (Subtotal + Tax - Discount = Grand Total)
# 5. Suspicious Text & Dummy Identities (Fake company, dummy emails, dummy phones, Lorem Ipsum, placeholder keywords)
# 6. Tax ID / GSTIN / VAT Format Validation
# 7. QR Code Cross-Verification (QR contents vs document text mismatch)
# 8. Missing Mandatory Information (Seller, Buyer, Invoice ID, Date, Totals, Address)
# 9. Duplicate Invoice Tracking

import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

SUSPICIOUS_KEYWORDS = {
    # Only explicit, unambiguous fraud markers – nothing that appears in real notes/terms
    'fake invoice', 'not real', 'fake company', 'fake customer',
    'acme fake', 'xyz fake', 'dummy invoice', 'void invoice',
    'imaginary', 'fictitious', 'fraudulent', 'forged document',
    'john doe', 'jane doe', 'draft only', 'specimen copy',
    'this is a test invoice', 'test invoice', 'sample invoice',
}

# Scoped keywords – used only when checking company / vendor / customer NAME fields
# or product/service description fields (NOT applied to free-text notes/terms)
SUSPICIOUS_COMPANY_KEYWORDS = {
    'fake', 'dummy', 'test', 'sample', 'demo', 'mock', 'placeholder',
    'void', 'specimen', 'nowhere', 'unreal', 'lorem ipsum',
}

DUMMY_DOMAINS = {
    'example.com', 'test.com', 'sample.com', 'fake.com', 'domain.com',
    'mailinator.com', 'tempmail.com', 'placeholder.com', 'nowhere.com'
}

# Only perfectly sequential / all-same-digit dummy numbers; avoid real phone patterns
DUMMY_PHONES = {
    '0000000000', '1111111111', '2222222222', '3333333333',
    '4444444444', '5555555555', '6666666666', '7777777777',
    '8888888888', '0123456789',
}

MAX_REASONABLE_TAX_PERCENTAGE = 40.0


def parse_num(s: Any) -> Optional[float]:
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    clean = re.sub(r'[^0-9\.\-]', '', str(s).replace(',', '').strip())
    if not clean or clean in ['-', '.']:
        return None
    try:
        return float(clean)
    except ValueError:
        return None


def parse_date_object(date_str: str) -> Optional[datetime]:
    if not date_str or not date_str.strip():
        return None
    cleaned = date_str.strip()
    match = re.search(r'(\d{1,2})[/\.-](\d{1,2})[/\.-](\d{4})', cleaned)
    if match:
        p1, p2, yr = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            return datetime(year=yr, month=p2, day=p1)
        except ValueError:
            pass
        try:
            return datetime(year=yr, month=p1, day=p2)
        except ValueError:
            pass
    match_iso = re.search(r'(\d{4})[/\.-](\d{1,2})[/\.-](\d{1,2})', cleaned)
    if match_iso:
        yr, mo, dy = int(match_iso.group(1)), int(match_iso.group(2)), int(match_iso.group(3))
        try:
            return datetime(year=yr, month=mo, day=dy)
        except ValueError:
            pass
    return None


def validate_date_string(date_str: str) -> Tuple[bool, str]:
    if not date_str or not date_str.strip():
        return False, 'Date value is empty'

    cleaned = date_str.strip()
    match = re.search(r'(\d{1,2})[/\.-](\d{1,2})[/\.-](\d{4})', cleaned)
    if match:
        part1 = int(match.group(1))
        part2 = int(match.group(2))
        year = int(match.group(3))

        if year < 1990 or year > 2100:
            return False, f'Year {year} is outside acceptable invoice timeframe'

        try_dm = False
        try_md = False
        try:
            datetime(year=year, month=part2, day=part1)
            try_dm = True
        except ValueError:
            pass

        try:
            datetime(year=year, month=part1, day=part2)
            try_md = True
        except ValueError:
            pass

        if not try_dm and not try_md:
            if (part2 == 2 and part1 == 29) or (part1 == 2 and part2 == 29):
                return False, f'Invalid calendar date (29/02/{year} does not exist - {year} is not a leap year)'
            if part1 > 31 or part2 > 12:
                return False, f'Invalid date components (Day: {part1}, Month: {part2}, Year: {year})'
            return False, f'Invalid calendar date ({cleaned})'

        return True, 'Valid date'

    match_iso = re.search(r'(\d{4})[/\.-](\d{1,2})[/\.-](\d{1,2})', cleaned)
    if match_iso:
        year = int(match_iso.group(1))
        month = int(match_iso.group(2))
        day = int(match_iso.group(3))
        try:
            datetime(year=year, month=month, day=day)
            return True, 'Valid date'
        except ValueError as e:
            if month == 2 and day == 29:
                return False, f'Invalid calendar date (29/02/{year} does not exist - {year} is not a leap year)'
            return False, f'Invalid calendar date ({cleaned}): {str(e)}'

    return True, 'Date format verified'


def validate_date_chronology(invoice_date_str: Optional[str], due_date_str: Optional[str]) -> Tuple[bool, str]:
    if not invoice_date_str or not due_date_str:
        return True, 'Dates chronological check skipped'
    
    dt_inv = parse_date_object(invoice_date_str)
    dt_due = parse_date_object(due_date_str)

    if dt_inv and dt_due:
        if dt_due < dt_inv:
            return False, f'Chronological error: Due Date ({due_date_str}) occurs before Invoice Date ({invoice_date_str})'
    return True, 'Date chronology valid'


def validate_tax_calculation(subtotal: Optional[float], tax_amount: Optional[float]) -> Tuple[bool, Optional[float], str]:
    if subtotal is None or tax_amount is None:
        return True, None, 'Subtotal or tax amount not available for check'

    if subtotal <= 0:
        if tax_amount > 0:
            return False, None, f'Subtotal is ${subtotal:.2f} but tax is ${tax_amount:.2f} (Invalid tax on zero subtotal)'
        return True, 0.0, 'Zero subtotal'

    tax_percentage = (tax_amount / subtotal) * 100.0

    if tax_amount < 0:
        return False, tax_percentage, f'Negative tax amount (${tax_amount:.2f})'

    if tax_percentage > 100.0:
        return False, tax_percentage, f'Tax percentage ({tax_percentage:.1f}%) exceeds 100% of subtotal'

    if tax_percentage > MAX_REASONABLE_TAX_PERCENTAGE:
        return False, tax_percentage, f'Abnormal tax percentage ({tax_percentage:.1f}%) exceeds maximum standard rate of {MAX_REASONABLE_TAX_PERCENTAGE:.0f}%'

    return True, tax_percentage, f'Tax rate is normal ({tax_percentage:.1f}%)'


def validate_totals_balance(
    subtotal: Optional[float],
    tax_amount: Optional[float],
    total_amount: Optional[float],
    discount: Optional[float] = 0.0,
    tolerance: float = 2.0
) -> Tuple[bool, str]:
    if total_amount is None:
        return False, 'Total amount is missing'

    if subtotal is not None and tax_amount is not None:
        expected_total = subtotal + tax_amount - (discount or 0.0)
        diff = abs(expected_total - total_amount)
        if diff > tolerance:
            return False, (
                f'Calculation mismatch: Subtotal (${subtotal:.2f}) + Tax (${tax_amount:.2f}) '
                f'- Discount (${discount or 0.0:.2f}) = ${expected_total:.2f}, but Total is ${total_amount:.2f} '
                f'(Difference: ${diff:.2f})'
            )
        return True, f'Calculation verified: ${subtotal:.2f} + ${tax_amount:.2f} = ${total_amount:.2f}'

    if subtotal is not None and total_amount < subtotal:
        return False, f'Total amount (${total_amount:.2f}) cannot be less than subtotal (${subtotal:.2f})'

    return True, 'Totals verified'


def _identify_table_columns(header_cells: List[str]) -> Dict[str, int]:
    """
    Given a list of header cell texts, return a dict mapping logical role -> column index.
    Works for ANY invoice format — recognises a broad range of single and multi-word column header names.
    Roles: 'item', 'qty', 'unit_price', 'line_total'
    """
    col_map: Dict[str, int] = {}
    for i, cell in enumerate(header_cells):
        cl = cell.lower().strip()

        # Item / description column
        if re.search(
            r'\b(item|description|desc|particulars|service|product|details|goods|work|'
            r'task|activity|narration|specification|name|title)\b', cl
        ) and 'item' not in col_map:
            col_map['item'] = i

        # Quantity column
        if re.search(
            r'\b(qty|quantity|units?|nos?\.?|count|pcs|pieces|hours?|hrs?|days?|'
            r'months?|sq\.?\s*ft|sq\.?\s*m)\b', cl
        ) and 'qty' not in col_map:
            col_map['qty'] = i

        # Unit price column (must be explicit — 'price', 'rate', 'unit price', etc.)
        if re.search(
            r'\b(rate|unit[\s\-]?price|unit[\s\-]?rate|price[\s\-]?per[\s\-]?unit|'
            r'per[\s\-]?unit|mrp|selling[\s\-]?price|list[\s\-]?price|cost|'
            r'unit[\s\-]?cost|price(?!\s*(?:total|amount|inc|excl|before)))\b', cl
        ) and 'unit_price' not in col_map:
            col_map['unit_price'] = i

        # Line total column (last "amount" column, excluding tax sub-columns)
        if re.search(
            r'\b(amount|total|line[\s\-]?total|net[\s\-]?amount|line[\s\-]?amount|'
            r'ext(?:ended)?[\s\-]?price|gross)\b', cl
        ) and 'line_total' not in col_map:
            # Exclude tax-specific headers
            if not re.search(
                r'\b(taxable|sub|grand|cgst|sgst|igst|gst|vat|tax|discount|'
                r'freight|shipping|surcharge)\b', cl
            ):
                col_map['line_total'] = i

    return col_map


def _is_header_row(cells: List[str]) -> bool:
    """
    Returns True if this row looks like a table header.
    Heuristic: at least 2 non-numeric text cells, matching header keywords or having no numbers.
    """
    if not cells or len(cells) < 2:
        return False
    row_text = ' '.join(cells).lower()
    has_hdr_kw = bool(re.search(r'\b(qty|quantity|description|desc|item|particulars|price|rate|amount|total|unit)\b', row_text))
    pure_numeric = sum(1 for c in cells if parse_num(c) is not None and re.match(r'^[\d,.\s₹$€£]+$', c.strip()))
    return has_hdr_kw or (len(cells) >= 2 and pure_numeric == 0)


def _infer_column_roles_from_data(data_rows: List[List[str]]) -> Optional[Tuple[int, int, int]]:
    """
    Data-pattern inference: scan all data rows to find which column triplet (qi, pi, ti)
    satisfies data[qi] × data[pi] ≈ data[ti] for a majority of rows.
    """
    if not data_rows:
        return None

    candidates: Dict[Tuple[int, int, int], int] = {}
    for row in data_rows:
        nums = {}
        for ci, cell in enumerate(row):
            v = parse_num(cell)
            if v is not None and v > 0:
                nums[ci] = v
        if len(nums) < 3:
            continue
        col_indices = sorted(nums.keys())
        for qi in col_indices:
            for pi in col_indices:
                if pi == qi:
                    continue
                for ti in col_indices:
                    if ti == qi or ti == pi:
                        continue
                    q, p, t = nums[qi], nums[pi], nums[ti]
                    if t < 1:
                        continue
                    exp = q * p
                    if exp > 0 and abs(exp - t) <= max(1.0, t * 0.03):
                        key = (qi, pi, ti)
                        candidates[key] = candidates.get(key, 0) + 1

    if not candidates:
        return None

    best_triplet = max(candidates, key=lambda k: candidates[k])
    best_count = candidates[best_triplet]
    min_rows = max(2, len(data_rows) * 0.5)

    if best_count >= min_rows:
        return best_triplet
    return None


def validate_table_line_items(text: str) -> List[Dict[str, Any]]:
    """
    Format-agnostic line item math validator for ANY invoice format:
    - Invoices with Qty × Unit Price = Total
    - Invoices without Qty (Services, Subscriptions, Fixed-Fee items)
    - HTML tables, Markdown pipe tables, and Plain-text space-aligned tables
    """
    issues: List[Dict[str, Any]] = []
    seen_items: set = set()

    # Determine primary currency symbol in document
    currency = '$' if '$' in text else ('₹' if '₹' in text or 'rs' in text.lower() or 'inr' in text.lower() else ('€' if '€' in text else '£'))

    SKIP_ROW_PATTERN = re.compile(
        r'(?i)\b(subtotal|sub\s*total|tax\s*total|grand\s*total|invoice\s*total|total\s*amount|'
        r'balance\s*due|amount\s*due|taxable|cgst|sgst|igst|vat|discount|'
        r'freight|shipping|surcharge|terms\s*&\s*conditions|payment\s*due)\b'
    )
    HEADER_PATTERN = re.compile(r'(?i)\b(qty|quantity|description|item|unit\s*price|rate|amount|total)\b')

    def _check_row(iname: str, q: Optional[float], p: Optional[float], t: Optional[float]) -> Optional[Dict]:
        """Validate row math: only flags if explicit Qty and Unit Price fail to equal Line Total."""
        if not iname or len(iname.strip()) < 2:
            return None
        clean_name = iname.strip(' \t\n\r|:-#*`')
        if clean_name in seen_items:
            return None
        if SKIP_ROW_PATTERN.search(clean_name) or HEADER_PATTERN.fullmatch(clean_name.lower()):
            return None
        
        # If no quantity or no unit price (e.g. fixed fee/service invoice), there is NO multiplication mismatch
        if q is None or p is None or t is None:
            return None
        if q <= 0 or p <= 0 or t <= 0:
            return None
        
        # Check calculation with standard currency rounding tolerance
        exp = round(q * p, 2)
        diff = abs(exp - t)
        tol = max(1.0, t * 0.02)  # 2% or $1.00 tolerance
        
        if diff > tol:
            seen_items.add(clean_name)
            return {
                'title': 'Line Item Calculation Error',
                'field': f'Line Item: {clean_name}',
                'value': f'Qty: {q:g} × Price: {currency}{p:,.2f} = Expected {currency}{exp:,.2f} vs Actual {currency}{t:,.2f}',
                'reason': (
                    f'{clean_name}: Qty ({q:g}) × Unit Price ({currency}{p:,.2f}) = {currency}{exp:,.2f}, '
                    f'but Line Total is {currency}{t:,.2f} (Mismatch: {currency}{diff:,.2f})'
                ),
                'severity': 'CRITICAL',
                'item_name': clean_name, 'qty': q, 'price': p, 'total': t, 'expected': exp,
                'tokens_to_flag': [
                    clean_name, f'{q:g}', f'{p:.2f}', f'{t:.2f}',
                    str(int(t) if float(t).is_integer() else t)
                ]
            }
        return None

    def _process_table_rows(all_rows: List[List[str]]):
        if not all_rows:
            return

        # Pass 1: Header-guided
        col_map: Dict[str, int] = {}
        data_start = 0
        for ri, row_cells in enumerate(all_rows[:4]):
            if _is_header_row(row_cells):
                col_map = _identify_table_columns(row_cells)
                data_start = ri + 1
                break

        if 'qty' in col_map and 'unit_price' in col_map:
            lt_col = col_map.get('line_total')
            item_col = col_map.get('item', 0)
            for row_cells in all_rows[data_start:]:
                needed = max(col_map.get('qty', 0), col_map.get('unit_price', 0),
                             lt_col if lt_col is not None else 0)
                if len(row_cells) <= needed:
                    continue
                iname = row_cells[item_col] if item_col < len(row_cells) else ''
                if SKIP_ROW_PATTERN.search(iname):
                    continue
                q = parse_num(row_cells[col_map['qty']])
                p = parse_num(row_cells[col_map['unit_price']])
                t = parse_num(row_cells[lt_col]) if lt_col is not None else None
                issue = _check_row(iname, q, p, t)
                if issue:
                    issues.append(issue)
            return

        # Pass 2: Data-pattern inference
        data_rows = all_rows[data_start:]
        candidate_rows = [
            r for r in data_rows
            if r and not SKIP_ROW_PATTERN.search(' '.join(r))
        ]
        triplet = _infer_column_roles_from_data(candidate_rows)
        if triplet is None:
            return

        qi, pi, ti = triplet
        item_col = 0 if qi != 0 else (1 if len(candidate_rows[0]) > 1 else 0)
        for row_cells in candidate_rows:
            needed = max(qi, pi, ti)
            if len(row_cells) <= needed:
                continue
            iname = row_cells[item_col] if item_col < len(row_cells) else ''
            if SKIP_ROW_PATTERN.search(iname):
                continue
            q = parse_num(row_cells[qi])
            p = parse_num(row_cells[pi])
            t = parse_num(row_cells[ti])
            issue = _check_row(iname, q, p, t)
            if issue:
                issues.append(issue)

    # 1. HTML Tables
    html_tables = re.findall(r'<table[^>]*>(.*?)</table>', text, re.DOTALL | re.IGNORECASE)
    for tbl in html_tables:
        rows_raw = re.findall(r'<tr[^>]*>(.*?)</tr>', tbl, re.DOTALL | re.IGNORECASE)
        all_rows: List[List[str]] = []
        for row in rows_raw:
            raw_cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL | re.IGNORECASE)
            cells = [re.sub(r'<[^>]+>', '', c).strip() for c in raw_cells]
            cells = [c for c in cells if c and not set(c).issubset({'-', ':', '|', ' '})]
            if cells:
                all_rows.append(cells)
        _process_table_rows(all_rows)

    # 2. Markdown Pipe Tables
    lines = text.splitlines()
    current_pipe_block: List[List[str]] = []

    def _flush_pipe_block():
        if current_pipe_block:
            _process_table_rows(current_pipe_block)
        current_pipe_block.clear()

    in_pipe = False
    for line in lines:
        line_s = line.strip()
        if not line_s or line_s.startswith(('<table', '<tr', '<td', '</table>', '</tr>')):
            if in_pipe:
                _flush_pipe_block()
                in_pipe = False
            continue
        if '|' in line_s and set(re.sub(r'[|:\- ]', '', line_s)).issubset({''}):
            continue

        if '|' in line_s:
            cells = [c.strip() for c in line_s.split('|') if c.strip()]
            cells = [c for c in cells if not set(c).issubset({'-', ':', ' '})]
            if cells:
                current_pipe_block.append(cells)
                in_pipe = True
        else:
            if in_pipe:
                _flush_pipe_block()
                in_pipe = False

    if in_pipe:
        _flush_pipe_block()

    # 3. Direct Plain-Text Line Item Patterns (Safe Line-by-Line Grammar Parsing)
    for line in lines:
        line_s = line.strip()
        if not line_s or '|' in line_s or line_s.startswith(('<', '---', '===')):
            continue
        if SKIP_ROW_PATTERN.search(line_s):
            continue

        # Pattern 1: [Index/Qty] [Description] [Unit Price] [Amount]
        # e.g.: "1   Front and rear brake cables   100.00   100.00"
        m1 = re.match(r'^([0-9]{1,4})\s+(.+?)\s+[\$₹€£]?([0-9,]+(?:\.[0-9]{2})?)\s+[\$₹€£]?([0-9,]+(?:\.[0-9]{2})?)$', line_s)
        if m1:
            q_val = parse_num(m1.group(1))
            item_val = m1.group(2).strip()
            p_val = parse_num(m1.group(3))
            t_val = parse_num(m1.group(4))
            issue = _check_row(item_val, q_val, p_val, t_val)
            if issue:
                issues.append(issue)
            continue

        # Pattern 2: [Description] [Qty] [Unit Price] [Amount]
        # e.g.: "Front brake cables   2   50.00   100.00"
        m2 = re.match(r'^([A-Za-z][A-Za-z0-9\s,._\-\/]{2,50})\s+([0-9]{1,4})\s+[\$₹€£]?([0-9,]+(?:\.[0-9]{2})?)\s+[\$₹€£]?([0-9,]+(?:\.[0-9]{2})?)$', line_s)
        if m2:
            item_val = m2.group(1).strip()
            q_val = parse_num(m2.group(2))
            p_val = parse_num(m2.group(3))
            t_val = parse_num(m2.group(4))
            issue = _check_row(item_val, q_val, p_val, t_val)
            if issue:
                issues.append(issue)
            continue

    return issues




def scan_suspicious_keywords(text: str) -> List[Tuple[str, str]]:
    """
    Scans for explicit fraud-marker keywords only.
    Uses exact substring matching for multi-word phrases to avoid word-boundary false positives.
    """
    if not text:
        return []

    found = []
    text_lower = text.lower()

    for kw in SUSPICIOUS_KEYWORDS:
        # Multi-word keywords: use exact substring search (no word boundary issues)
        if ' ' in kw:
            idx = text_lower.find(kw)
            while idx != -1:
                start = max(0, idx - 20)
                end = min(len(text), idx + len(kw) + 20)
                snippet = text[start:end].strip().replace('\r\n', ' ').replace('\n', ' ')
                found.append((kw, snippet))
                idx = text_lower.find(kw, idx + 1)
        else:
            # Single-word: use word boundary to prevent partial matches
            pattern = r'\b' + re.escape(kw) + r'\b'
            for m in re.finditer(pattern, text_lower):
                start = max(0, m.start() - 20)
                end = min(len(text), m.end() + 20)
                snippet = text[start:end].strip().replace('\r\n', ' ').replace('\n', ' ')
                found.append((kw, snippet))

    return found


def scan_suspicious_company_keywords(text: str) -> List[Tuple[str, str]]:
    """
    Scans company/customer name fields for words that suggest placeholder or dummy data.
    Uses the tighter SUSPICIOUS_COMPANY_KEYWORDS set to avoid false positives in body text.
    """
    if not text:
        return []

    found = []
    text_lower = text.lower()

    for kw in SUSPICIOUS_COMPANY_KEYWORDS:
        pattern = r'\b' + re.escape(kw) + r'\b'
        for m in re.finditer(pattern, text_lower):
            start = max(0, m.start() - 20)
            end = min(len(text), m.end() + 20)
            snippet = text[start:end].strip().replace('\r\n', ' ').replace('\n', ' ')
            found.append((kw, snippet))

    return found


def scan_dummy_contact_info(text: str) -> List[Tuple[str, str, str]]:
    if not text:
        return []

    findings = []

    # 1. Check Dummy Emails
    emails = re.findall(r'[a-zA-Z0-9_.+-]+@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', text)
    for domain in emails:
        if domain.lower() in DUMMY_DOMAINS:
            findings.append(('Email Domain', f'@{domain}', f'Placeholder/Dummy email domain detected (@{domain})'))

    # 2. Check Dummy Phones — extract individual phone numbers and match exactly
    # Extract phone-like tokens (groups of 7-15 digits, optionally prefixed with + or country code)
    phone_tokens = re.findall(r'(?<!\d)(\+?[0-9]{7,15})(?!\d)', re.sub(r'[\s\-.()\[\]]+', '', text))
    dummy_set = {re.sub(r'[^0-9+]', '', dp) for dp in DUMMY_PHONES}
    for pt in phone_tokens:
        pt_clean = re.sub(r'[^0-9+]', '', pt)
        # Match exact number or strip country code prefix and check again
        stripped = pt_clean.lstrip('+')
        # Remove leading country codes (91 for India, 1 for US)
        core10 = stripped[-10:] if len(stripped) >= 10 else stripped
        if pt_clean in dummy_set or stripped in dummy_set or core10 in dummy_set:
            findings.append(('Phone Number', pt, f'Sequential or dummy test phone number detected ({pt})'))

    return findings



def validate_gstin_format(gstin: str) -> Tuple[bool, str]:
    if not gstin or not gstin.strip():
        return True, 'No GSTIN provided'
    cleaned = re.sub(r'[^A-Za-z0-9]', '', gstin).upper()
    if len(cleaned) == 15:
        if re.match(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$', cleaned):
            return True, f'Valid GSTIN format ({cleaned})'
        else:
            return False, f'Malformed GSTIN structure ({cleaned}): does not conform to standard 15-character schema'
    elif len(cleaned) > 0:
        return False, f'Invalid GSTIN length ({len(cleaned)} chars instead of 15)'
    return True, 'Valid'


def verify_qr_cross_check(qr_codes: List[Dict[str, Any]], extracted_fields: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not qr_codes:
        return []

    mismatches = []
    for qr in qr_codes:
        details = qr.get('details', {})
        parsed = details.get('parsed_fields', {})

        qr_inv = parsed.get('irn') or parsed.get('doc_no') or parsed.get('invoice_no')
        doc_inv = extracted_fields.get('invoice_number')
        if qr_inv and doc_inv and str(qr_inv).strip().lower() != str(doc_inv).strip().lower():
            mismatches.append({
                'title': 'QR Code Data Mismatch',
                'field': 'Invoice Number vs QR',
                'value': f'Doc: {doc_inv} | QR: {qr_inv}',
                'reason': f'Document invoice number ({doc_inv}) does not match digital QR code payload ({qr_inv}) - High risk of tampering!',
                'severity': 'CRITICAL'
            })

        qr_gstin = details.get('detected_gstin') or parsed.get('seller_gstin')
        doc_gstin = extracted_fields.get('gstin')
        if qr_gstin and doc_gstin and str(qr_gstin).strip().upper() != str(doc_gstin).strip().upper():
            mismatches.append({
                'title': 'GSTIN QR Mismatch',
                'field': 'GSTIN vs QR',
                'value': f'Doc: {doc_gstin} | QR: {qr_gstin}',
                'reason': f'Document GSTIN ({doc_gstin}) does not match QR code GSTIN ({qr_gstin}) - Potential tax fraud!',
                'severity': 'CRITICAL'
            })

    return mismatches


def check_missing_mandatory_fields(extracted_fields: Dict[str, Any]) -> List[str]:
    mandatory = {
        'company_name': 'Company / Seller Name',
        'invoice_number': 'Invoice Number',
        'invoice_date': 'Invoice Date',
        'total_amount': 'Total Amount',
        'address': 'Address / Contact'
    }

    missing = []
    for key, label in mandatory.items():
        val = extracted_fields.get(key)
        if val is None or (isinstance(val, str) and not val.strip()):
            missing.append(label)
    return missing