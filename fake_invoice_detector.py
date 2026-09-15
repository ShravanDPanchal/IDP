# Explainable Fake Invoice Detector Engine
import re
from typing import Dict, List, Any, Optional, Tuple
from fraud_rules import (
    parse_num,
    validate_date_string,
    validate_date_chronology,
    validate_tax_calculation,
    validate_totals_balance,
    validate_table_line_items,
    scan_suspicious_keywords,
    scan_suspicious_company_keywords,
    scan_dummy_contact_info,
    validate_gstin_format,
    verify_qr_cross_check,
    check_missing_mandatory_fields,
    MAX_REASONABLE_TAX_PERCENTAGE
)
from yolo_preview_utils import get_crop_text

_SEEN_INVOICE_NUMBERS = set()


def extract_structured_invoice_data(results: Dict[str, Any], crops: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    md_text = results.get('markdown', '') or ''
    raw_text = results.get('text', '') or ''
    parts = [md_text, raw_text]

    json_data = results.get('json')
    if isinstance(json_data, list):
        for block in json_data:
            if isinstance(block, dict):
                if block.get('text'):
                    parts.append(str(block.get('text', '')))
                if block.get('table_body'):
                    parts.append(str(block.get('table_body', '')))
                if block.get('html'):
                    parts.append(str(block.get('html', '')))

    # Also include all crop texts
    if crops:
        for c in crops:
            c_txt = get_crop_text(c)
            if c_txt:
                parts.append(c_txt)

    full_text = "\n".join(p for p in parts if p)
    clean_text = re.sub(r'<[^>]+>', ' ', full_text)
    clean_text = re.sub(r'[*_`]', ' ', clean_text)

    extracted = {
        'company_name': None,
        'customer_name': None,
        'invoice_number': None,
        'invoice_date': None,
        'due_date': None,
        'gstin': None,
        'subtotal': None,
        'tax_amount': None,
        'total_amount': None,
        'discount': None,
        'address': None,
        'raw_full_text': full_text
    }

    # 1. Invoice Number (fix partial capture by using explicit patterns & comprehensive blacklist)
    inv_num_patterns = [
        r'(?i)\b(?:invoice|inv|bill|receipt)\s*#\s*([A-Za-z0-9\-\/]{1,30})\b',
        r'(?i)\b(?:invoice|inv|bill|receipt|doc(?:ument)?)\s*(?:number|num|no|id|code)\s*[:#.\-|]\s*([A-Za-z0-9\-\/]{1,30})\b',
        r'(?i)\b(?:invoice|inv|bill|receipt)\s*(?:no|number|num|#|id)\b\s*[\n\r]+\s*([A-Za-z0-9\-\/]{1,30})\b',
        r'(?i)\b(?:invoice|inv|bill|receipt)\s*(?:number|num|no|id|code)\s+([A-Za-z0-9\-\/]{1,30})\b',
        r'(?i)\b(?:invoice|inv)\b(?!\s*(?:date|total|tax|amount|due|subtotal|table|summary|item|to|by|from|when|remitting|funds|please))\s*[:#.\-|]\s*([A-Za-z0-9\-\/]{1,30})\b'
    ]
    inv_blacklist = {
        'when', 'where', 'why', 'how', 'what', 'which', 'who', 'whom', 'whose', 'remitting',
        'payment', 'payments', 'here', 'there', 'above', 'below', 'mentioned', 'specified',
        'provided', 'indicated', 'shown', 'will', 'shall', 'must', 'should', 'can', 'could',
        'may', 'might', 'would', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have',
        'has', 'had', 'do', 'does', 'did', 'for', 'on', 'in', 'at', 'by', 'to', 'from',
        'with', 'without', 'within', 'about', 'against', 'between', 'into', 'through',
        'during', 'before', 'after', 'above', 'below', 'under', 'up', 'down', 'off', 'over',
        'again', 'further', 'then', 'once', 'and', 'but', 'if', 'or', 'because', 'as',
        'until', 'while', 'of', 'that', 'this', 'these', 'those', 'am', 'the', 'a', 'an',
        'please', 'quote', 'kindly', 'note', 'reference', 'refer', 'regarding', 'subject',
        'format', 'template', 'sample', 'copy', 'original', 'duplicate', 'date', 'due', 'tax',
        'bill', 'total', 'amount', 'item', 'subtotal', 'number', 'num', 'no', 'gstin', 'pan',
        'hsn', 'ber', 'er', 'id', 'code', 'inv', 'invoice', 'receipt'
    }
    for p in inv_num_patterns:
        for m in re.finditer(p, clean_text):
            val = m.group(1).strip()
            val = re.sub(r'^(?:number|num|no|id|code|#|ref)[:\s.-]*', '', val, flags=re.IGNORECASE).strip()
            if val and val.lower() not in inv_blacklist and len(val) >= 1:
                extracted['invoice_number'] = val
                break
        if extracted['invoice_number']:
            break

    # 2. Invoice Date
    date_match = re.search(
        r'(?i)\b(?:invoice\s*date|bill\s*date|date\s*of\s*issue|issue\s*date|dated|\bdate\b)[:\s\t\-|]*([0-9]{1,4}[/\.-][0-9]{1,2}[/\.-][0-9]{2,4}|[0-9]{4}[/\.-][0-9]{1,2}[/\.-][0-9]{1,2}|[a-zA-Z]{3,9}\s+[0-9]{1,2},?\s+[0-9]{4}|[0-9]{1,2}\s+[a-zA-Z]{3,9}\s+[0-9]{4})',
        clean_text
    )
    if date_match:
        extracted['invoice_date'] = date_match.group(1).strip()
    else:
        fallback_date = re.search(r'\b([0-9]{1,2}[/\.-][0-9]{1,2}[/\.-][0-9]{2,4})\b', clean_text)
        if fallback_date:
            extracted['invoice_date'] = fallback_date.group(1).strip()

    # 3. Due Date
    due_match = re.search(
        r'(?i)\b(?:due\s*date|payment\s*due|valid\s*until|due\s*by)[:\s\t\-|]*([0-9]{1,4}[/\.-][0-9]{1,2}[/\.-][0-9]{2,4}|[a-zA-Z]{3,9}\s+[0-9]{1,2},?\s+[0-9]{4}|[0-9]{1,2}\s+[a-zA-Z]{3,9}\s+[0-9]{4})',
        clean_text
    )
    if due_match:
        extracted['due_date'] = due_match.group(1).strip()

    # 4. GSTIN / Tax ID
    gstin_match = re.search(
        r'(?i)\b(?:gstin|gst\s*no|tax\s*id|vat\s*no|vat\s*reg)[:\s\t\-|]*([0-9A-Z]{10,18})\b',
        clean_text
    )
    if gstin_match:
        extracted['gstin'] = gstin_match.group(1).strip()

    # 5. Precise Totals Line-by-Line & Table Parser (Subtotal, Tax, Grand Total, Discount)
    for line in full_text.splitlines():
        l_clean = re.sub(r'[*_`#]', '', line).strip()
        if not l_clean:
            continue

        # A. Subtotal
        if re.search(r'(?i)\b(?:sub\s*total|subtotal|taxable\s*(?:value|amount)|net\s*amount|gross\s*amount)\b', l_clean):
            nums = [parse_num(n) for n in re.findall(r'[\$₹€£]?\s*([0-9,]+(?:\.[0-9]{1,2})?)', l_clean)]
            valid = [n for n in nums if n is not None and n > 0]
            if valid and extracted['subtotal'] is None:
                extracted['subtotal'] = valid[-1]

        # B. Tax Amount & Rate (Summary line, not service description like 'Tax Consulting' or 'Tax Filing')
        elif re.search(r'(?i)\b(?:sales\s*tax|total\s*tax|tax\s*amount|vat\s*amount|gst\s*amount|cgst|sgst|igst|\btax\b(?!\s*(?:filing|consult|audit|return|service|advis|plan|compliance|litigat|appeal|law|court|matter|retainer|code|rate)))\b', l_clean):
            if not re.search(r'(?i)\b(?:tax\s*invoice|income\s*tax|taxable|sub\s*total|subtotal|grand\s*total)\b', l_clean):
                line_no_pct = re.sub(r'[0-9]+(?:\.[0-9]+)?\s*%', '', l_clean)
                nums = [parse_num(n) for n in re.findall(r'[\$₹€£]?\s*([0-9,]+(?:\.[0-9]{1,2})?)', line_no_pct)]
                valid = [n for n in nums if n is not None and n >= 0]
                if valid:
                    extracted['tax_amount'] = valid[-1]

        # C. Grand Total / Invoice Total / Amount Due
        elif re.search(r'(?i)\b(?:grand\s*total|invoice\s*total|total\s*amount|amount\s*(?:due|payable)|net\s*payable|\btotal\b)\b', l_clean):
            if not re.search(r'(?i)\b(?:sub\s*total|subtotal|tax\s*rate|unit\s*price|line\s*total|words|terms|payable\s*to)\b', l_clean):
                nums = [parse_num(n) for n in re.findall(r'[\$₹€£]?\s*([0-9,]+(?:\.[0-9]{1,2})?)', l_clean)]
                valid = [n for n in nums if n is not None and n > 0]
                if valid and extracted['total_amount'] is None:
                    extracted['total_amount'] = valid[-1]

        # D. Discount
        elif re.search(r'(?i)\b(?:discount)\b', l_clean) and not re.search(r'(?i)\bearlypay\b', l_clean):
            nums = [parse_num(n) for n in re.findall(r'[\$₹€£]?\s*([0-9,]+(?:\.[0-9]{1,2})?)', l_clean)]
            valid = [n for n in nums if n is not None and n > 0]
            if valid and extracted['discount'] is None:
                extracted['discount'] = valid[-1]

    # Fallback to standard 15-char Indian GSTIN pattern if not found
    if not extracted['gstin']:
        gstin_std = re.search(r'\b(\d{2}[A-Z]{5}\d{4}[A-Z0-9]{4})\b', clean_text)
        if gstin_std:
            extracted['gstin'] = gstin_std.group(1).strip()

    # 6. Company Name / Seller and Customer / Buyer
    party_blacklist = [
        'terms', 'conditions', 'remitting', 'funds', 'overdue', 'interest', 'delayed', 'payments',
        'please pay', 'pay within', 'charged on', 'payment due', 'payment terms', 'bank details',
        'scan to pay', 'the date of invoice', 'from the date', 'extracted markdown', 'raw text',
        'structured json', 'decoded qr', 'document name', 'document content', 'original', 'duplicate',
        'billed to', 'billed by', 'bill to', 'bill by', 'sold to', 'sold by', 'ship to', 'ship by',
        'shipped to', 'invoiced to', 'place of supply', 'country of supply', 'bank & payment'
    ]

    def is_valid_party(cand: str) -> bool:
        if not cand or len(cand) < 2 or len(cand) > 75:
            return False
        cl = cand.lower().strip()
        if any(b in cl for b in party_blacklist):
            return False
        return True

    def sanitize_party(val: str) -> str:
        v = re.sub(r'[*_`#]', '', str(val)).strip(' \t\n\r:|-#')
        v = v.splitlines()[0].strip() if v else ''
        v = re.sub(r'^(?:name|company|firm|attn|to|by|m/s|mr|ms|dr)[:\s.-]*', '', v, flags=re.IGNORECASE).strip()
        v = re.sub(r'(?i)\b(?:gstin|pan|date|cin|ph|phone|email|state|pin|zip)[\s:0-9a-z]*$', '', v).strip(' ,;-')
        return v

    lines_raw = [ln.strip() for ln in clean_text.splitlines() if ln.strip()]

    # Step 1: Paired 2-column side-by-side OCR layout (Billed by \n Billed to \n Vendor \n Customer)
    for i in range(len(lines_raw) - 3):
        l0 = lines_raw[i].strip()
        l1 = lines_raw[i+1].strip()
        l2 = lines_raw[i+2].strip()
        l3 = lines_raw[i+3].strip()
        is_v_hdr = bool(re.search(r'(?i)^\s*(?:billed\s*by|bill\s*by|sold\s*by|issued\s*by|seller|vendor|supplier)\s*[:\s\-|]*$', l0))
        is_c_hdr = bool(re.search(r'(?i)^\s*(?:billed\s*to|bill\s*to|sold\s*to|ship\s*to|shipped\s*to|invoiced\s*to|buyer|customer|client)\s*[:\s\-|]*$', l1))
        if is_v_hdr and is_c_hdr:
            cand_v = sanitize_party(l2)
            cand_c = sanitize_party(l3)
            if is_valid_party(cand_v) and is_valid_party(cand_c):
                extracted['company_name'] = cand_v
                extracted['customer_name'] = cand_c
                break

    # Step 2: Same-line or single-column Vendor
    if not extracted['company_name']:
        for i, line in enumerate(lines_raw):
            m = re.search(r'(?i)\b(?:billed\s*by|bill\s*by|sold\s*by|issued\s*by|seller|vendor|supplier|company\s*name)\b[:\s\-|]+(.+)', line)
            if m:
                cand = sanitize_party(m.group(1))
                if is_valid_party(cand):
                    extracted['company_name'] = cand
                    break
            if re.match(r'(?i)^\s*(?:billed\s*by|bill\s*by|sold\s*by|issued\s*by|seller|vendor|supplier)\s*[:\s\-|]*$', line):
                if i + 1 < len(lines_raw):
                    cand = sanitize_party(lines_raw[i + 1])
                    if is_valid_party(cand):
                        extracted['company_name'] = cand
                        break

    if not extracted['company_name']:
        for line in lines_raw:
            m = re.search(r'(?i)^\s*from\s*[:\-]\s*(.+)', line)
            if m:
                cand = sanitize_party(m.group(1))
                if is_valid_party(cand):
                    extracted['company_name'] = cand
                    break

    if not extracted['company_name']:
        for line_str in lines_raw[:6]:
            cand = sanitize_party(line_str)
            if is_valid_party(cand) and not re.search(r'(?i)\b(?:invoice|tax|bill|receipt|date|due|phone|email|tel|http|www|page|original|duplicate|extracted|markdown|raw text)\b', cand):
                extracted['company_name'] = cand[:60]
                break

    # Step 3: Same-line or single-column Customer
    if not extracted['customer_name']:
        for i, line in enumerate(lines_raw):
            m = re.search(r'(?i)\b(?:billed\to|bill\s*to|sold\s*to|ship\s*to|shipped\s*to|invoiced\s*to|buyer|customer|client|recipient|consignee)\b[:\s\-|]+(.+)', line)
            if m:
                cand = sanitize_party(m.group(1))
                if is_valid_party(cand):
                    extracted['customer_name'] = cand
                    break
            if re.match(r'(?i)^\s*(?:billed\s*to|bill\s*to|sold\s*to|ship\s*to|shipped\s*to|invoiced\s*to|buyer|customer|client)\s*[:\s\-|]*$', line):
                if i + 1 < len(lines_raw):
                    cand = sanitize_party(lines_raw[i + 1])
                    if is_valid_party(cand):
                        extracted['customer_name'] = cand
                        break

    # 8. Address
    addr_match = re.search(
        r'(?i)(?:address|location|street|city)[:\s\t\-|]*([^\r\n|]{5,100})',
        clean_text
    )
    if addr_match:
        extracted['address'] = addr_match.group(1).strip()
    else:
        addr_parts = []
        for line in clean_text.splitlines():
            line_clean = line.strip()
            if not line_clean or len(line_clean) < 4:
                continue
            if re.search(r'(?i)\b(?:street|st\.|road|rd\.|avenue|ave|city|suite|block|floor|pin|zip|\d{5})\b', line_clean):
                if not re.search(r'(?i)\b(?:bill\s*to|invoice|date|reference|line\s*items?|subtotal|table|price|unit)\b', line_clean):
                    addr_parts.append(line_clean[:100])
        if addr_parts:
            extracted['address'] = ", ".join(addr_parts[:2])

    return extracted


def detect_invoice_fraud(
    results: Dict[str, Any],
    yolo_crops: Optional[List[Dict[str, Any]]] = None,
    register_duplicate: bool = True
) -> Dict[str, Any]:
    crops = list(yolo_crops or results.get('yolo_crops') or [])
    extracted = extract_structured_invoice_data(results, crops=crops)
    full_text = extracted.get('raw_full_text', '')

    annotated_crops = []
    for c in crops:
        c_copy = dict(c)
        c_copy['is_flagged'] = False
        c_copy['flag_reason'] = None
        c_copy['flag_title'] = None
        annotated_crops.append(c_copy)

    detected_issues = []
    field_table = []
    risk_points = 0

    def flag_crop_by_pattern(pattern: str, reason: str, title: str):
        pat_lower = pattern.lower().strip()
        if not pat_lower:
            return
        pat_num = parse_num(pattern)

        for c in annotated_crops:
            text = get_crop_text(c).lower().strip()
            if not text:
                continue

            # If pattern is a number, match exact numeric equality with any number in the crop
            if pat_num is not None:
                crop_nums = re.findall(r'[\$₹€£]?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)', text)
                for cn in crop_nums:
                    cn_val = parse_num(cn)
                    if cn_val is not None and abs(cn_val - pat_num) < 0.001:
                        c['is_flagged'] = True
                        c['flag_reason'] = reason
                        c['flag_title'] = title
                        break
            else:
                # Text pattern match (e.g. "Widget A", "Fake Street", "29/02/2026")
                if pat_lower in text:
                    c['is_flagged'] = True
                    c['flag_reason'] = reason
                    c['flag_title'] = title

    # -------------------------------------------------------------
    # 1. DATE CALENDAR VALIDATION
    # -------------------------------------------------------------
    date_val = extracted.get('invoice_date')
    if date_val:
        is_valid_date, date_reason = validate_date_string(date_val)
        if not is_valid_date:
            risk_points += 40
            detected_issues.append({
                'title': 'Invalid Date',
                'field': 'Invoice Date',
                'value': date_val,
                'reason': date_reason,
                'severity': 'CRITICAL'
            })
            field_table.append({
                'field': 'Invoice Date',
                'value': date_val,
                'status': 'FAILED',
                'reason': date_reason
            })
            flag_crop_by_pattern(date_val, date_reason, 'INVALID DATE')
        else:
            field_table.append({
                'field': 'Invoice Date',
                'value': date_val,
                'status': 'VALID',
                'reason': 'Calendar date format verified'
            })
    else:
        field_table.append({
            'field': 'Invoice Date',
            'value': 'Not Detected',
            'status': 'MISSING',
            'reason': 'Invoice date could not be located'
        })
        risk_points += 10

    # -------------------------------------------------------------
    # 2. DATE CHRONOLOGY CHECK (Due Date vs Invoice Date)
    # -------------------------------------------------------------
    due_val = extracted.get('due_date')
    if date_val and due_val:
        is_chrono_valid, chrono_reason = validate_date_chronology(date_val, due_val)
        if not is_chrono_valid:
            risk_points += 30
            detected_issues.append({
                'title': 'Timeline Impossibility',
                'field': 'Due Date',
                'value': f'Due: {due_val} | Inv: {date_val}',
                'reason': chrono_reason,
                'severity': 'HIGH'
            })
            field_table.append({
                'field': 'Due Date',
                'value': due_val,
                'status': 'FAILED',
                'reason': chrono_reason
            })
            flag_crop_by_pattern(due_val, chrono_reason, 'DUE DATE ANOMALY')
        else:
            field_table.append({
                'field': 'Due Date',
                'value': due_val,
                'status': 'VALID',
                'reason': 'Chronological due date valid'
            })

    # -------------------------------------------------------------
    # 3. LINE ITEMS ROW-BY-ROW ARITHMETIC VALIDATION (Qty * Price = Total)
    # -------------------------------------------------------------
    line_item_issues = validate_table_line_items(full_text)
    for l_issue in line_item_issues:
        risk_points += 35
        detected_issues.append(l_issue)
        field_table.append({
            'field': l_issue['field'],
            'value': l_issue['value'],
            'status': 'FAILED',
            'reason': l_issue['reason']
        })
        # Flag all components of this erroneous line item row in red (Item Name, Qty, Price, Total)
        tokens_to_flag = l_issue.get('tokens_to_flag', [l_issue['item_name'], str(l_issue['total'])])
        for tok in tokens_to_flag:
            flag_crop_by_pattern(str(tok), l_issue['reason'], 'LINE ITEM ERROR')

    # -------------------------------------------------------------
    # 4. SUBTOTAL CHECK
    # -------------------------------------------------------------
    subtotal = extracted.get('subtotal')
    if subtotal is not None:
        field_table.append({
            'field': 'Subtotal',
            'value': f'${subtotal:g}',
            'status': 'VALID',
            'reason': 'Subtotal detected'
        })
    else:
        field_table.append({
            'field': 'Subtotal',
            'value': 'Not Detected',
            'status': 'MISSING',
            'reason': 'Subtotal not explicitly specified'
        })

    # -------------------------------------------------------------
    # 5. TAX ANOMALY DETECTION
    # -------------------------------------------------------------
    tax_amount = extracted.get('tax_amount')

    if subtotal is not None and tax_amount is not None:
        is_valid_tax, tax_pct, tax_reason = validate_tax_calculation(subtotal, tax_amount)
        tax_disp = f'${tax_amount:g} ({tax_pct:.1f}%)' if tax_pct is not None else f'${tax_amount:g}'
        if not is_valid_tax:
            risk_points += 40
            detected_issues.append({
                'title': 'Tax Anomaly',
                'field': 'Tax Amount',
                'value': tax_disp,
                'reason': tax_reason,
                'severity': 'HIGH'
            })
            field_table.append({
                'field': 'Tax Amount',
                'value': tax_disp,
                'status': 'SUSPICIOUS',
                'reason': tax_reason
            })
            flag_crop_by_pattern(str(int(tax_amount) if tax_amount.is_integer() else tax_amount), tax_reason, 'TAX ANOMALY')
        else:
            field_table.append({
                'field': 'Tax Amount',
                'value': tax_disp,
                'status': 'VALID',
                'reason': 'Tax percentage within normal standard range'
            })
    elif tax_amount is not None:
        field_table.append({
            'field': 'Tax Amount',
            'value': f'${tax_amount:g}',
            'status': 'VALID',
            'reason': 'Tax detected'
        })
    else:
        field_table.append({
            'field': 'Tax Amount',
            'value': 'Not Detected',
            'status': 'MISSING',
            'reason': 'Tax breakdown not explicitly separated'
        })

    # -------------------------------------------------------------
    # 6. MATHEMATICAL CALCULATION CONSISTENCY (Subtotal + Tax = Total)
    # -------------------------------------------------------------
    total_amount = extracted.get('total_amount')
    if total_amount is not None:
        is_calc_valid, calc_reason = validate_totals_balance(
            subtotal, tax_amount, total_amount, extracted.get('discount', 0.0)
        )
        if not is_calc_valid:
            risk_points += 30
            detected_issues.append({
                'title': 'Calculation Inconsistency',
                'field': 'Total Amount',
                'value': f'${total_amount:g}',
                'reason': calc_reason,
                'severity': 'HIGH'
            })
            field_table.append({
                'field': 'Total Amount',
                'value': f'${total_amount:g}',
                'status': 'FAILED',
                'reason': calc_reason
            })
            flag_crop_by_pattern(str(int(total_amount) if total_amount.is_integer() else total_amount), calc_reason, 'CALCULATION ERROR')
        else:
            field_table.append({
                'field': 'Total Amount',
                'value': f'${total_amount:g}',
                'status': 'VALID',
                'reason': 'Sum totals mathematically consistent'
            })
    else:
        field_table.append({
            'field': 'Total Amount',
            'value': 'Not Detected',
            'status': 'MISSING',
            'reason': 'Total invoice balance missing'
        })
        risk_points += 15

    # -------------------------------------------------------------
    # 6. FAKE / SUSPICIOUS KEYWORDS IN TEXT OR CROPS
    # -------------------------------------------------------------
    suspicious_hits = scan_suspicious_keywords(full_text)
    seen_kw = set()
    for kw, snippet in suspicious_hits:
        if kw in seen_kw:
            continue
        seen_kw.add(kw)
        risk_points += 30

        reason = f"Suspicious keyword '{kw}' detected: '...{snippet}...'"
        # Classify severity based on the updated keyword set
        critical_kws = {'fake invoice', 'fake company', 'fake customer', 'fraudulent',
                        'forged document', 'not real', 'imaginary', 'fictitious'}
        detected_issues.append({
            'title': 'Suspicious Keyword',
            'field': 'Document Content',
            'value': snippet,
            'reason': reason,
            'severity': 'CRITICAL' if kw in critical_kws else 'HIGH'
        })
        flag_crop_by_pattern(kw, f"Suspicious keyword '{kw}' detected", 'SUSPICIOUS TEXT')

    # Direct per-crop keyword scanning (uses the same tight fraud-marker set)
    for c in annotated_crops:
        c_text = get_crop_text(c)
        c_hits = scan_suspicious_keywords(c_text)
        if c_hits:
            c['is_flagged'] = True
            c['flag_reason'] = f"Suspicious keyword '{c_hits[0][0]}' in {c['class_name']}"
            c['flag_title'] = 'SUSPICIOUS DATA'

    # -------------------------------------------------------------
    # 7. DUMMY / PLACEHOLDER CONTACT INFO (Emails, Phones, Domains)
    # -------------------------------------------------------------
    dummy_contacts = scan_dummy_contact_info(full_text)
    for c_type, c_val, c_reason in dummy_contacts:
        risk_points += 25
        detected_issues.append({
            'title': f'Placeholder {c_type}',
            'field': c_type,
            'value': c_val,
            'reason': c_reason,
            'severity': 'HIGH'
        })
        field_table.append({
            'field': c_type,
            'value': c_val,
            'status': 'FAILED',
            'reason': c_reason
        })
        flag_crop_by_pattern(c_val, c_reason, f'DUMMY {c_type.upper()}')

    # -------------------------------------------------------------
    # 8. COMPANY NAME & BUYER NAME VERIFICATION
    # -------------------------------------------------------------
    comp_val = extracted.get('company_name')
    if comp_val:
        comp_hits = scan_suspicious_company_keywords(comp_val)
        if comp_hits:
            field_table.append({
                'field': 'Company Name',
                'value': comp_val,
                'status': 'FAILED',
                'reason': f"Suspicious keyword '{comp_hits[0][0]}' detected in company name"
            })
            flag_crop_by_pattern(comp_val, f"Suspicious company keyword '{comp_hits[0][0]}'", 'FAKE COMPANY')
        else:
            field_table.append({
                'field': 'Company Name',
                'value': comp_val,
                'status': 'VALID',
                'reason': 'Company name present and verified'
            })
    else:
        field_table.append({
            'field': 'Company Name',
            'value': 'Not Detected',
            'status': 'MISSING',
            'reason': 'Seller / company name could not be identified'
        })
        risk_points += 10

    cust_val = extracted.get('customer_name')
    if cust_val:
        cust_hits = scan_suspicious_company_keywords(cust_val)
        if cust_hits:
            field_table.append({
                'field': 'Customer Name',
                'value': cust_val,
                'status': 'SUSPICIOUS',
                'reason': f"Suspicious keyword '{cust_hits[0][0]}' in customer name"
            })
            flag_crop_by_pattern(cust_val, f"Suspicious customer keyword '{cust_hits[0][0]}'", 'SUSPICIOUS CUSTOMER')
        else:
            field_table.append({
                'field': 'Customer Name',
                'value': cust_val,
                'status': 'VALID',
                'reason': 'Customer name present and verified'
            })

    # -------------------------------------------------------------
    # 9. ADDRESS VERIFICATION
    # -------------------------------------------------------------
    addr_val = extracted.get('address')
    if addr_val:
        addr_hits = scan_suspicious_company_keywords(addr_val)
        if addr_hits:
            field_table.append({
                'field': 'Address',
                'value': addr_val,
                'status': 'SUSPICIOUS',
                'reason': f"Suspicious keyword '{addr_hits[0][0]}' in address"
            })
            flag_crop_by_pattern(addr_val, f"Suspicious address keyword '{addr_hits[0][0]}'", 'SUSPICIOUS ADDRESS')
        else:
            field_table.append({
                'field': 'Address',
                'value': addr_val,
                'status': 'VALID',
                'reason': 'Billing address found'
            })
    else:
        field_table.append({
            'field': 'Address',
            'value': 'Not Detected',
            'status': 'MISSING',
            'reason': 'Billing address missing'
        })
        risk_points += 5

    # -------------------------------------------------------------
    # 10. QR CODE CROSS-VERIFICATION
    # -------------------------------------------------------------
    qr_codes = results.get('qr_codes', [])
    if qr_codes:
        qr_mismatches = verify_qr_cross_check(qr_codes, extracted)
        for q_issue in qr_mismatches:
            risk_points += 40
            detected_issues.append(q_issue)
            field_table.append({
                'field': q_issue['field'],
                'value': q_issue['value'],
                'status': 'FAILED',
                'reason': q_issue['reason']
            })

    # -------------------------------------------------------------
    # 11. DUPLICATE INVOICE NUMBER CHECK
    # -------------------------------------------------------------
    inv_num = extracted.get('invoice_number')
    if inv_num:
        if inv_num in _SEEN_INVOICE_NUMBERS:
            risk_points += 30
            reason = f'Invoice number {inv_num} was previously processed in this session (Potential duplicate / fraud replay)'
            detected_issues.append({
                'title': 'Duplicate Invoice Number',
                'field': 'Invoice Number',
                'value': inv_num,
                'reason': reason,
                'severity': 'HIGH'
            })
            field_table.append({
                'field': 'Invoice Number',
                'value': inv_num,
                'status': 'SUSPICIOUS',
                'reason': reason
            })
            flag_crop_by_pattern(inv_num, reason, 'DUPLICATE INVOICE')
        else:
            if register_duplicate:
                _SEEN_INVOICE_NUMBERS.add(inv_num)
            field_table.append({
                'field': 'Invoice Number',
                'value': inv_num,
                'status': 'VALID',
                'reason': 'Unique invoice identifier'
            })
    else:
        field_table.append({
            'field': 'Invoice Number',
            'value': 'Not Detected',
            'status': 'MISSING',
            'reason': 'Invoice number missing'
        })
        risk_points += 10

    # -------------------------------------------------------------
    # 12. FINAL RISK SCORE & VERDICT
    # -------------------------------------------------------------
    final_risk_score = min(100, max(0, risk_points))

    if final_risk_score >= 70:
        verdict = 'FAKE / HIGH RISK'
        status_color = '#EF4444'
    elif final_risk_score >= 31:
        verdict = 'SUSPICIOUS'
        status_color = '#F59E0B'
    else:
        verdict = 'REAL'
        status_color = '#10B981'

    return {
        'verdict': verdict,
        'risk_score': final_risk_score,
        'status_color': status_color,
        'detected_issues': detected_issues,
        'field_analysis_table': field_table,
        'extracted_fields': extracted,
        'annotated_crops': annotated_crops
    }