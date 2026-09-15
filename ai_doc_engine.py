"""
Python-side Document AI Grounding Engine for IDP Assistant.
Supports:
1. Local Ollama LLM (Qwen2.5 / Llama3 / Mistral) for 100% offline, private, deep document reasoning
2. Google Gemini API requests (Gemini 1.5 Flash) via API key
3. Intelligent local extraction fallback across Markdown, JSON, QR codes, and Fraud detection
"""

import json
import re
import os
import requests
from typing import Dict, Any, Optional, Tuple


import shutil

def ensure_ollama_running():
    """Starts Ollama daemon in background only if ollama binary is installed on system."""
    try:
        res = requests.get("http://localhost:11434/api/tags", timeout=0.3)
        if res.status_code == 200:
            return
    except Exception:
        pass
    if shutil.which("ollama"):
        try:
            import subprocess
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
        except Exception:
            pass


def get_available_ollama_model() -> Optional[str]:
    """Checks if Ollama is running locally and returns the best available model with fast timeout."""
    try:
        res = requests.get("http://localhost:11434/api/tags", timeout=0.4)
        if res.status_code == 200:
            models = [m.get("name", "") for m in res.json().get("models", [])]
            if models:
                # Priority preference list
                for pref in ["qwen2.5:3b", "qwen2.5", "llama3.2", "llama3.1", "llama3", "mistral", "phi3", "gemma2"]:
                    for m in models:
                        if pref in m.lower():
                            return m
                return models[0]
    except Exception:
        pass
    return None


def ask_document_ai(
    query: str,
    document_data: Optional[Dict[str, Any]] = None,
    document_name: str = "",
    api_key: str = ""
) -> Tuple[str, list]:
    """
    Answers user questions strictly based on the extracted document data.
    Returns (answer_text, suggestion_chips).
    """
    trimmed_query = (query or "").strip()
    if not trimmed_query:
        return (
            "👋 **Hello! I'm your Intelligent Document Processing (IDP) Assistant.**\n\nAsk me any question about your uploaded document!",
            ["💰 Invoice Total", "🔢 Invoice Number", "📅 Invoice Date", "🏢 Vendor & Customer"]
        )

    doc_text = ""
    if document_data:
        parts = []
        if document_data.get("file_name") or document_name:
            parts.append(f"Document Name: {document_data.get('file_name') or document_name}")
        if document_data.get("markdown"):
            parts.append(f"--- Extracted Markdown ---\n{document_data['markdown']}")
        if document_data.get("text") and document_data.get("text") != document_data.get("markdown"):
            parts.append(f"--- Raw Text ---\n{document_data['text']}")
        if document_data.get("qr_codes"):
            parts.append(f"--- Decoded QR Codes ---\n{json.dumps(document_data['qr_codes'], indent=2)}")
        if document_data.get("json"):
            parts.append(f"--- Structured JSON Content ---\n{json.dumps(document_data['json'], indent=2)}")
        if document_data.get("fraud_report"):
            parts.append(f"--- Fraud Analysis Report ---\n{json.dumps(document_data['fraud_report'], indent=2)}")
        doc_text = "\n\n".join(parts)

    system_prompt = f"""You are an expert Intelligent Document Processing (IDP) & Forensic Accounting AI Assistant called Reeva AI.
Analyze the following extracted document content and answer the user's question accurately, directly, and concisely.
--- DOCUMENT CONTENT ---
{doc_text if doc_text else "No document currently loaded."}
--- END DOCUMENT CONTENT ---

CRITICAL RESPONSE RULES:
1. STRICTLY TARGETED & CONCISE ANSWERS:
   - Answer ONLY the specific question asked by the user. Do NOT output unsolicited calculations, extra item tables, or full invoice breakdowns unless the user specifically requests a full breakdown or summary.
   - If the user asks about the date (e.g. 'is date fake or legit'), answer ONLY about the date in 1-2 clear sentences. Do not perform or dump arithmetic calculations.
   - If the user asks about a vendor, person, address, or GSTIN, provide ONLY that requested information.
   - If the user points out a math discrepancy (e.g. 5 x 50 is 250, but doc says 2500), confirm whether their math is correct and explain that specific calculation error directly in 2-3 sentences.
2. ACCURATE MATH (Only when calculations are asked):
   - Line Total = Quantity × Unit Price (e.g. 5 × $50 = $250). If the document states $2500, state that the document contains an arithmetic error / overcharge for that item.
3. CONCISE & PROFESSIONAL:
   - Keep answers clean, direct, and well-formatted with markdown. Avoid repetitive text or unsolicited tangents."""

    # 1. Try Local Ollama LLM (Qwen2.5 / Llama3)
    ollama_model = get_available_ollama_model()
    if ollama_model and doc_text:
        try:
            payload = {
                "model": ollama_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": trimmed_query}
                ],
                "stream": False,
                "options": {
                    "temperature": 0.15,
                    "top_p": 0.9
                }
            }
            res = requests.post("http://localhost:11434/api/chat", json=payload, timeout=25)
            if res.status_code == 200:
                answer = res.json().get("message", {}).get("content", "").strip()
                if answer:
                    return (
                        answer,
                        ["💰 Invoice Total", "🔢 Invoice Number", "🧾 GST & Tax Details", "🛡️ Fraud Check"]
                    )
        except Exception:
            pass

    # 2. Try Google Gemini API if key is supplied
    effective_key = (api_key or os.getenv("GEMINI_API_KEY") or "").strip()
    if effective_key and doc_text:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={effective_key}"
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": f"{system_prompt}\n\nUser Question: {trimmed_query}"}]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 1024
                }
            }
            res = requests.post(url, json=payload, timeout=12)
            if res.status_code == 200:
                data = res.json()
                reply = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                if reply.strip():
                    return reply.strip(), ["💰 Invoice Total", "🔢 Invoice Number", "🧾 GST & Tax Details", "📋 Line Items"]
        except Exception:
            pass

    # 3. High-Precision Local IDP Fallback Engine
    return local_extract_idp_answer(trimmed_query, doc_text, document_data)


def clean_val(val: str) -> str:
    """Cleans extracted value string by removing HTML tags, extra markdown formatting, and punctuation."""
    if not val:
        return ""
    v = re.sub(r"<[^>]+>", " ", str(val))
    v = re.sub(r"[*_`#]", "", v).strip(" \t\n\r:|-#")
    return re.sub(r"\s+", " ", v).strip()


def extract_invoice_number_field(text: str) -> Optional[str]:
    """Extracts the invoice number with high confidence without capturing English prepositions or keywords like 'when' or 'ber'."""
    clean_text = re.sub(r"<[^>]+>", " ", text)
    clean_text = re.sub(r"[*_`]", " ", clean_text)
    
    english_words_blacklist = {
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

    patterns = [
        # Explicit 'Invoice #' (e.g. Invoice# 004 or Inv # 123)
        r"(?i)\b(?:invoice|inv|bill|receipt)\s*#\s*([A-Za-z0-9\-\/]{1,30})\b",
        # Explicit 'Invoice Number / No' with colon/dash/pipe (e.g. Invoice Number: 004)
        r"(?i)\b(?:invoice|inv|bill|receipt|doc(?:ument)?)\s*(?:number|num|no|id|code)\s*[:#.\-|]\s*([A-Za-z0-9\-\/]{1,30})\b",
        # Multi-line: 'Invoice No' on one line, value on next
        r"(?i)\b(?:invoice|inv|bill|receipt)\s*(?:no|number|num|#|id)\b\s*[\n\r]+\s*([A-Za-z0-9\-\/]{1,30})\b",
        # Space separated: 'Invoice No 004' (must not be an English sentence word)
        r"(?i)\b(?:invoice|inv|bill|receipt)\s*(?:number|num|no|id|code)\s+([A-Za-z0-9\-\/]{1,30})\b",
        # Fallback 'Invoice: 004'
        r"(?i)\b(?:invoice|inv)\b(?!\s*(?:date|total|tax|amount|due|subtotal|table|summary|item|to|by|from|when|remitting|funds|please))\s*[:#.\-|]\s*([A-Za-z0-9\-\/]{1,30})\b"
    ]
    for p in patterns:
        for m in re.finditer(p, clean_text):
            val = m.group(1).strip()
            val = re.sub(r"^(?:number|num|no|id|code|#|ref)[:\s.-]*", "", val, flags=re.IGNORECASE).strip()
            if val and val.lower() not in english_words_blacklist and len(val) >= 1:
                return val
    return None


def extract_dates_fields(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Extracts invoice date and payment due date cleanly."""
    inv_date, due_date = None, None
    clean_text = re.sub(r"<[^>]+>", " ", text)

    date_pattern = r"([0-9]{1,4}[/\.-][0-9]{1,2}[/\.-][0-9]{2,4}|[a-zA-Z]{3,9}\s+[0-9]{1,2},?\s+[0-9]{4}|[0-9]{1,2}\s+[a-zA-Z]{3,9}\s+[0-9]{4})"
    
    date_m = re.search(r"(?i)\b(?:invoice\s*date|bill\s*date|date\s*of\s*issue|issue\s*date|dated|\bdate\b)[:\s\t\-|]*" + date_pattern, clean_text)
    if date_m:
        inv_date = date_m.group(1).strip()
    else:
        fallback_date = re.search(r"\b([0-9]{1,2}[/\.-][0-9]{1,2}[/\.-][0-9]{2,4})\b", clean_text)
        if fallback_date:
            inv_date = fallback_date.group(1).strip()

    due_m = re.search(r"(?i)\b(?:due\s*date|payment\s*due|valid\s*until|due\s*by|pay\s*by)[:\s\t\-|]*" + date_pattern, clean_text)
    if due_m:
        due_date = due_m.group(1).strip()

    return inv_date, due_date


def is_party_label(text: str) -> bool:
    """Checks if a string is a party header label rather than a company/customer name."""
    if not text:
        return False
    cl = text.lower().strip()
    return bool(re.search(r"^\s*(?:billed\s*(?:to|by)|bill\s*(?:to|by)|sold\s*(?:to|by)|ship\s*(?:to|by)|shipped\s*to|invoiced\s*to|buyer|seller|vendor|supplier|customer|client|place\s*of\s*supply|country\s*of\s*supply|terms\s*and\s*conditions|bank\s*&\s*payment)\b", cl))


def extract_parties_fields(text: str) -> Dict[str, Optional[str]]:
    """Extracts Vendor/Seller and Customer/Buyer information accurately across single and multi-column layouts."""
    clean_text = re.sub(r"<[^>]+>", "\n", text)
    lines = [
        ln.strip() for ln in clean_text.splitlines()
        if ln.strip() and not ln.strip().startswith(("---", "===", "###", "```"))
    ]

    vendor, customer, email, phone = None, None, None, None
    vendor_addr, customer_addr = None, None

    def is_valid_name(cand: str) -> bool:
        if not cand or len(cand) < 2 or len(cand) > 75:
            return False
        cl = cand.lower().strip()
        if is_party_label(cl):
            return False
        exact_bad = {'date', 'invoice', 'due', 'total', 'tax', 'subtotal', 'terms', 'within', 'gstin', 'pan', 'the date', 'extracted markdown', 'markdown', 'raw text', 'structured json', 'decoded qr', 'document name', 'document content', 'original', 'duplicate'}
        if cl in exact_bad:
            return False
        bad_phrases = [
            r"\b(?:terms\s*and\s*conditions|remitting\s*funds|overdue\s*interest|delayed\s*payments|please\s*pay|pay\s*within|charged\s*on)\b",
            r"\b(?:payment\s*(?:due|terms|method|mode|status|details)|bank\s*details|scan\s*to\s*pay)\b",
            r"\b(?:the\s*date\s*of\s*invoice|from\s*the\s*date)\b",
            r"\b(?:extracted\s*markdown|raw\s*text|structured\s*json)\b"
        ]
        if any(re.search(p, cl) for p in bad_phrases):
            return False
        return True

    def sanitize_party_name(val: str) -> str:
        v = clean_val(val)
        if not v:
            return ""
        lines_v = v.splitlines()
        v = lines_v[0].strip() if lines_v else ""
        v = re.sub(r"^(?:name|company|firm|attn|to|by|m/s|mr|ms|dr)[:\s.-]*", "", v, flags=re.IGNORECASE).strip()
        v = re.sub(r"(?i)\b(?:gstin|pan|date|cin|ph|phone|email|state|pin|zip)[\s:0-9a-z]*$", "", v).strip(" ,;-")
        return v

    # Step 1: Paired 2-column side-by-side OCR layout (Billed by \n Billed to \n Vendor \n Customer)
    for i in range(len(lines) - 3):
        l0 = lines[i].strip()
        l1 = lines[i+1].strip()
        l2 = lines[i+2].strip()
        l3 = lines[i+3].strip()
        is_v_hdr = bool(re.search(r"(?i)^\s*(?:billed\s*by|bill\s*by|sold\s*by|issued\s*by|seller|vendor|supplier)\s*[:\s\-|]*$", l0))
        is_c_hdr = bool(re.search(r"(?i)^\s*(?:billed\s*to|bill\s*to|sold\s*to|ship\s*to|shipped\s*to|invoiced\s*to|buyer|customer|client)\s*[:\s\-|]*$", l1))
        if is_v_hdr and is_c_hdr:
            cand_v = sanitize_party_name(l2)
            cand_c = sanitize_party_name(l3)
            if is_valid_name(cand_v) and is_valid_name(cand_c):
                vendor = cand_v
                customer = cand_c
                if i + 4 < len(lines) and is_valid_name(sanitize_party_name(lines[i+4])) and not is_party_label(lines[i+4]):
                    vendor_addr = clean_val(lines[i+4])
                if i + 5 < len(lines) and is_valid_name(sanitize_party_name(lines[i+5])) and not is_party_label(lines[i+5]):
                    customer_addr = clean_val(lines[i+5])
                break

    # Step 2: Same-line or single-column Vendor
    if not vendor:
        for i, line in enumerate(lines):
            m = re.search(r"(?i)\b(?:billed\s*by|bill\s*by|sold\s*by|issued\s*by|seller|vendor|supplier|company\s*name)\b[:\s\-|]+(.+)", line)
            if m:
                cand = sanitize_party_name(m.group(1))
                if is_valid_name(cand):
                    vendor = cand
                    if i + 1 < len(lines) and is_valid_name(sanitize_party_name(lines[i + 1])) and not is_party_label(lines[i + 1]):
                        vendor_addr = clean_val(lines[i + 1])
                    break
            if re.search(r"(?i)^\s*(?:billed\s*by|bill\s*by|sold\s*by|issued\s*by|seller|vendor|supplier)\s*[:\s\-|]*$", line):
                if i + 1 < len(lines):
                    cand = sanitize_party_name(lines[i + 1])
                    if is_valid_name(cand):
                        vendor = cand
                        if i + 2 < len(lines) and is_valid_name(sanitize_party_name(lines[i + 2])) and not is_party_label(lines[i + 2]):
                            vendor_addr = clean_val(lines[i + 2])
                        break

    # Secondary Vendor check: strict 'From:'
    if not vendor:
        for i, line in enumerate(lines):
            m = re.search(r"(?i)^\s*from\s*[:\-]\s*(.+)", line)
            if m:
                cand = sanitize_party_name(m.group(1))
                if is_valid_name(cand):
                    vendor = cand
                    break

    # Step 3: Same-line or single-column Customer
    if not customer:
        for i, line in enumerate(lines):
            m = re.search(r"(?i)\b(?:billed\s*to|bill\s*to|sold\s*to|ship\s*to|shipped\s*to|invoiced\s*to|buyer|customer|client|recipient|consignee|empfanger)\b[:\s\-|]+(.+)", line)
            if m:
                cand = sanitize_party_name(m.group(1))
                if is_valid_name(cand):
                    customer = cand
                    if i + 1 < len(lines) and is_valid_name(sanitize_party_name(lines[i + 1])) and not is_party_label(lines[i + 1]):
                        customer_addr = clean_val(lines[i + 1])
                    break
            if re.search(r"(?i)^\s*(?:billed\s*to|bill\s*to|sold\s*to|ship\s*to|shipped\s*to|invoiced\s*to|buyer|customer|client|recipient|consignee|empfanger)\s*[:\s\-|]*$", line):
                if i + 1 < len(lines):
                    cand = sanitize_party_name(lines[i + 1])
                    if is_valid_name(cand):
                        customer = cand
                        if i + 2 < len(lines) and is_valid_name(sanitize_party_name(lines[i + 2])) and not is_party_label(lines[i + 2]):
                            customer_addr = clean_val(lines[i + 2])
                        break

    # Step 4: Header fallback for Vendor (first non-label line at top)
    if not vendor:
        for i in range(min(len(lines), 6)):
            cand = sanitize_party_name(lines[i])
            if is_valid_name(cand) and not re.search(r"(?i)\b(?:invoice|tax|bill|receipt|date|due|phone|email|tel|http|www|page|original|duplicate|extracted|markdown|raw text)\b", cand):
                vendor = cand
                if i + 1 < len(lines) and is_valid_name(sanitize_party_name(lines[i + 1])) and not is_party_label(lines[i + 1]):
                    vendor_addr = clean_val(lines[i + 1])
                break

    # 3. Clean Contact Email
    email_m = re.search(r"\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.(?:com|in|org|net|co|io|edu|gov|co\.in|org\.in|dev|ai|app|biz|info|de|fr|uk))\b", text, re.IGNORECASE)
    if email_m:
        email = email_m.group(1).strip()

    # 4. Clean Phone Number (Avoid bank account numbers)
    phone_m = re.search(r"(?i)\b(?:phone|call|tel|mobile|cell|contact|ph)\b[\s:.\-on]*(\+?[0-9\s\-()]{7,20})", text)
    if phone_m:
        cand = re.sub(r"[^0-9+]", "", phone_m.group(1).strip())
        if len(cand) >= 7:
            phone = cand
    if not phone:
        phone_m2 = re.search(r"\+91[\s\-]?[6-9]\d{9}|\+\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|\+\d{2,3}\s*\d{2,4}\s*\d{4,8}", text)
        if phone_m2:
            phone = phone_m2.group(0).strip()

    return {
        'vendor': vendor,
        'vendor_addr': vendor_addr,
        'customer': customer,
        'customer_addr': customer_addr,
        'email': email,
        'phone': phone
    }


def extract_financial_breakdown_field(doc_text: str) -> str:
    """Extracts Subtotal, Discount, Taxable Amount, Individual Taxes (CGST, SGST, IGST, VAT), and Grand Total accurately."""
    clean_lines = [l.strip() for l in doc_text.splitlines() if l.strip()]
    subtotal = None
    taxable = None
    discount = None
    cgst = None
    sgst = None
    igst = None
    tax_total = None
    grand_total = None

    for line in clean_lines:
        l = line.replace('*', '').replace('`', '').strip()
        if re.search(r'(?i)\b(?:sub\s*total|subtotal|gross\s*amount)\b', l):
            amounts = [a.strip() for a in re.findall(r'([₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)', l) if re.search(r'\d', a)]
            if amounts:
                subtotal = amounts[-1]
        elif re.search(r'(?i)\b(?:taxable\s*amount|taxable\s*value|net\s*taxable|net\s*amount)\b', l):
            amounts = [a.strip() for a in re.findall(r'([₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)', l) if re.search(r'\d', a)]
            if amounts:
                taxable = amounts[-1]
        elif re.search(r'(?i)\b(?:discount)\b', l) and not re.search(r'(?i)\bearlypay\b', l):
            amounts = [a.strip() for a in re.findall(r'(-?[₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)', l) if re.search(r'\d', a)]
            pct = re.search(r'(\d+%)', l)
            if pct and len(amounts) >= 2:
                discount = f'{pct.group(1)} ({amounts[-1]})'
            elif amounts:
                discount = amounts[-1]
        elif re.search(r'(?i)\bcgst\b', l):
            amounts = [a.strip() for a in re.findall(r'([₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)', l) if re.search(r'\d', a)]
            if amounts:
                cgst = amounts[-1]
        elif re.search(r'(?i)\bsgst\b', l):
            amounts = [a.strip() for a in re.findall(r'([₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)', l) if re.search(r'\d', a)]
            if amounts:
                sgst = amounts[-1]
        elif re.search(r'(?i)\bigst\b', l):
            amounts = [a.strip() for a in re.findall(r'([₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)', l) if re.search(r'\d', a)]
            if amounts:
                igst = amounts[-1]
        elif re.search(r'(?i)\b(?:total\s*tax|tax\s*amount|vat\s*amount|vat\s*\(|sales\s*tax)\b', l):
            amounts = [a.strip() for a in re.findall(r'([₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)', l) if re.search(r'\d', a)]
            if amounts:
                tax_total = amounts[-1]
        elif re.search(r'(?i)\b(?:grand\s*total|invoice\s*total|total\s*amount|balance\s*due|net\s*payable|\btotal\b)\b', l):
            if not re.search(r'(?i)\b(?:sub\s*total|subtotal|tax\s*rate|unit\s*price|line\s*total|words|earlypay)\b', l):
                amounts = [a.strip() for a in re.findall(r'([₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)', l) if re.search(r'\d', a)]
                if amounts:
                    grand_total = amounts[-1]

    rows = []
    if subtotal:
        rows.append(f'• **Subtotal / Gross Amount:** `{subtotal}`')
    if discount:
        rows.append(f'• **Discount:** `{discount}`')
    if taxable:
        rows.append(f'• **Taxable Amount:** `{taxable}`')
    if cgst and sgst:
        rows.append(f'• **Taxes (CGST + SGST):** `CGST: {cgst} | SGST: {sgst}`')
    elif cgst:
        rows.append(f'• **CGST:** `{cgst}`')
    elif sgst:
        rows.append(f'• **SGST:** `{sgst}`')
    elif igst:
        rows.append(f'• **IGST:** `{igst}`')
    elif tax_total:
        rows.append(f'• **Tax Amount:** `{tax_total}`')
    if grand_total:
        rows.append(f'• **Grand Total:** `{grand_total}`')

    if rows:
        return "💰 **Financial Breakdown Extracted from Document:**\n\n" + "\n".join(rows)
    return "No financial breakdown or totals detected in this document."


def extract_gst_tax_details_field(doc_text: str) -> str:
    """Extracts, deduplicates, and formats GSTIN, PAN, European/UK VAT, Australian ABN, and Tax IDs cleanly."""
    clean_text = re.sub(r"<[^>]+>", " ", doc_text)

    # 1. Deduplicated 15-char Indian GSTINs
    raw_gstins = re.findall(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z0-9]{4})\b", clean_text, re.IGNORECASE)
    seen_gstin = set()
    gstins = []
    for g in raw_gstins:
        gu = g.upper()
        if gu not in seen_gstin:
            seen_gstin.add(gu)
            gstins.append(gu)

    # 2. Extract PANs (10-char alphanumeric)
    raw_pans = re.findall(r"\b([A-Z]{5}\d{4}[A-Z])\b", clean_text, re.IGNORECASE)
    seen_pan = set()
    standalone_pans = []
    gstin_pans = {g[2:12] for g in gstins}

    for p in raw_pans:
        pu = p.upper()
        if pu not in seen_pan:
            seen_pan.add(pu)
            if pu not in gstin_pans:
                standalone_pans.append(pu)

    rows = []
    seller_gstin = None
    buyer_gstin = None

    # Contextual check for Seller vs Buyer GSTIN
    seller_block_m = re.search(r"(?i)(?:billed\s*by|seller|vendor|supplier|from)[\s\S]{1,300}?(\d{2}[A-Z]{5}\d{4}[A-Z0-9]{4})\b", clean_text)
    if seller_block_m:
        seller_gstin = seller_block_m.group(1).upper()

    buyer_block_m = re.search(r"(?i)(?:billed\s*to|buyer|customer|client|ship\s*to)[\s\S]{1,300}?(\d{2}[A-Z]{5}\d{4}[A-Z0-9]{4})\b", clean_text)
    if buyer_block_m:
        buyer_gstin = buyer_block_m.group(1).upper()

    if seller_gstin and buyer_gstin and seller_gstin != buyer_gstin:
        rows.append(f"• **Seller / Vendor GSTIN:** `{seller_gstin}` (PAN: `{seller_gstin[2:12]}`)")
        rows.append(f"• **Buyer / Customer GSTIN:** `{buyer_gstin}` (PAN: `{buyer_gstin[2:12]}`)")
        for g in gstins:
            if g != seller_gstin and g != buyer_gstin:
                rows.append(f"• **GSTIN:** `{g}` (PAN: `{g[2:12]}`)")
    else:
        for g in gstins:
            rows.append(f"• **GSTIN / GST Number:** `{g}` (PAN: `{g[2:12]}`)")

    for p in standalone_pans:
        rows.append(f"• **PAN Number:** `{p}`")

    # 3. European / UK VAT Numbers (e.g. DE123456789, FR987654321, GB123456789)
    eu_vat_matches = re.findall(r"\b(?:AT|BE|BG|CY|CZ|DE|DK|EE|EL|ES|FI|FR|GB|GR|HR|HU|IE|IT|LT|LU|LV|MT|NL|PL|PT|RO|SE|SI|SK|CHE)\s?[0-9A-Z]{8,12}\b", clean_text)
    seen_vats = set()
    for v in eu_vat_matches:
        v_clean = re.sub(r"\s+", "", v).upper()
        if v_clean not in seen_vats and v_clean not in seen_gstin and v_clean not in seen_pan:
            seen_vats.add(v_clean)
            rows.append(f"• **VAT / Tax Registration ID:** `{v_clean}`")

    # 4. Explicit VAT, ABN, CIN, TIN, Tax ID label matches
    tax_id_matches = re.findall(r"(?i)\b(?:vat\s*(?:id|no|number|reg)?|ust-idnr|tva|abn|acn|tax\s*(?:id|no|number|reg)?|cin|tin)\b[:\s\-|]*([A-Z0-9\s\-]{5,25})\b", clean_text)
    seen_tax_ids = set()
    for tid in tax_id_matches:
        t_clean = tid.strip().upper()
        if t_clean not in seen_tax_ids and t_clean not in seen_gstin and t_clean not in seen_pan and t_clean not in seen_vats:
            if len(t_clean) >= 5 and not re.search(r"(?i)\b(?:invoice|total|amount|subtotal)\b", t_clean):
                seen_tax_ids.add(t_clean)
                rows.append(f"• **Tax / Registration ID:** `{t_clean}`")

    if rows:
        return "🧾 **GST & Tax Registration Details:**\n\n" + "\n".join(rows)
    return "No GSTIN, PAN, or Tax registration numbers detected in this document."


def local_extract_idp_answer(query: str, doc_text: str, document_data: Optional[Dict[str, Any]]) -> Tuple[str, list]:
    q_lower = query.lower().strip()

    # 1. Identity & Introduction Queries
    if re.search(r"^(who are (you|u|r u)|who r u|what is your name|who made you|what are you)\b", q_lower):
        return (
            "👋 I’m **Reeva AI**, the Intelligent Document Processing (IDP) Assistant built by **Reeva Dev**!\n\nI specialize in analyzing, extracting, and inspecting your documents, invoices, receipts, and forms using advanced OCR, YOLO layout segmentation, and Explainable AI fraud detection.",
            ["✨ What can you do?", "📁 Supported Formats", "🚀 How to upload"]
        )

    # 2. Capability & Feature Queries
    if re.search(r"^(what (can|did|do) (you|u) do|what are your (features|capabilities)|how can you help|what else can you do)\b", q_lower) or re.search(r"what (can|did|do) (you|u) do", q_lower):
        return (
            "✨ **Here is everything I can do for you:**\n\n• 📄 **Document Extraction:** Parse text, structured markdown, and JSON tables from PDFs, images, DOCX, and XLSX.\n• 💰 **Financial Breakdown:** Extract and verify Subtotals, Tax/GST/VAT, and Grand Totals.\n• 🔢 **Invoice Details:** Extract Invoice Numbers, Issue Dates, Due Dates, and Reference IDs.\n• 🏢 **Parties & Contacts:** Identify Vendor/Issuer details, Customer/Billed To info, and email addresses.\n• 🛡️ **Explainable AI Fraud Inspection:** Detect layout tampering, arithmetic discrepancies, and calculate risk scores.\n• 📱 **QR & Barcode Decoding:** Decode scannable payloads and UPI payment links.\n• 🔊 **Voice Speech & Audio:** Read responses aloud and accept microphone voice input.\n\n*Upload a document on the homepage to start asking questions about it!*",
            ["💰 Invoice Total", "🔢 Invoice Number", "🛡️ Fraud Check", "📁 Supported Formats"]
        )

    # 3. Greeting Queries
    if re.search(r"^(hi|hello|hey|hola|greetings|good morning|good afternoon|good evening)\b", q_lower):
        return (
            "👋 **Hello!** How can I assist you with your document processing or questions today?",
            ["✨ What can you do?", "🚀 How to upload documents", "📁 Supported Formats"]
        )

    # 4. Help & Instructions Queries
    if re.search(r"^(how to (use|upload|process)|help|how does (it|this) work|instructions)\b", q_lower):
        return (
            "🚀 **How to Use IDP:**\n\n1. **Upload Documents:** Drag and drop your PDF or image into the upload box at the top.\n2. **Convert:** Click **🚀 Convert & Process Documents** to run OCR, YOLO layout analysis, and fraud checks.\n3. **Inspect Tabs:** Review the extracted Markdown, Tables, JSON, YOLO Layout Crops, and Fraud overlays.\n4. **Ask Reeva AI:** Ask me any specific question about amounts, dates, or items here in the chat (or click 🎙️ to speak)!",
            ["📁 Supported Formats", "🛡️ Fraud Detection Info", "✨ What can you do?"]
        )

    # 5. Supported Formats
    if re.search(r"\b(supported formats|what formats|file types|formats supported)\b", q_lower):
        return (
            "📁 **Supported Document Formats:**\n\n• 📄 **PDFs:** Scanned and digital multi-page PDFs\n• 🖼️ **Images:** PNG, JPG, JPEG, TIFF, WEBP\n• 📊 **Office Documents:** DOCX, PPTX, XLSX",
            ["🚀 How to upload", "✨ What can you do?", "🛡️ Fraud Check"]
        )

    if not doc_text.strip():
        return (
            "👋 **No document content is currently loaded.**\n\nPlease drag and drop a PDF or image invoice into the upload box above and click **Convert & Process Documents** to analyze it!",
            ["🚀 How to upload documents", "📁 Supported Formats", "✨ What can you do?"]
        )

def html_table_to_markdown(html_str: str) -> str:
    """Converts HTML table tags into clean GitHub-flavored Markdown tables."""
    if "<table" not in html_str.lower():
        return ""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_str, "html.parser")
        tables = soup.find_all("table")
        if not tables:
            return ""
        
        md_tables = []
        for table in tables:
            rows = table.find_all("tr")
            if not rows:
                continue
            parsed_rows = []
            for r in rows:
                cells = r.find_all(["th", "td"])
                cell_texts = [re.sub(r'\s+', ' ', c.get_text()).strip() for c in cells]
                if any(cell_texts):
                    parsed_rows.append(cell_texts)
            if not parsed_rows:
                continue
            max_cols = max(len(r) for r in parsed_rows)
            padded = [r + [''] * (max_cols - len(r)) for r in parsed_rows]
            header = padded[0]
            separator = ['---'] * max_cols
            md_lines = [
                "| " + " | ".join(header) + " |",
                "| " + " | ".join(separator) + " |"
            ]
            for data_row in padded[1:]:
                md_lines.append("| " + " | ".join(data_row) + " |")
            md_tables.append("\n".join(md_lines))
        return "\n\n".join(md_tables)
    except Exception:
        return ""


def extract_amount_in_words(text: str) -> Optional[str]:
    """Extracts total amount written in words."""
    m = re.search(r"(?i)\b(?:amount\s*in\s*words|total\s*in\s*words|invoice\s*total\s*\(in\s*words\)|in\s*words)[:\s\t\-|]*[\r\n]*([A-Za-z\s\-]+(?:rupees|dollars|cents|euros|pounds|only|paisa|aud|cad|inr|usd))\b", text)
    if m:
        return m.group(1).strip()
    return None


def extract_terms_and_notes(text: str) -> Optional[str]:
    """Extracts terms & conditions, early payment discounts, and additional notes."""
    terms = []
    t_match = re.search(r"(?i)(?:terms\s*and\s*conditions|terms\s*&\s*conditions|payment\s*terms)[\s:.\-|]*[\r\n]+([\s\S]{1,400}?)(?:\n\s*\n|additional\s*notes|bank|\Z)", text)
    if t_match:
        terms.append(f"📜 **Terms & Conditions:**\n{t_match.group(1).strip()}")
    
    early_pay = re.findall(r"(?i)\b(?:earlypay|early\s*payment|early\s*bird)\b[^\n]+", text)
    if early_pay:
        terms.append("⚡ **Early Payment Benefit:**\n" + "\n".join(f"• {e.strip()}" for e in early_pay))
        
    notes_match = re.search(r"(?i)(?:additional\s*notes|notes|remarks)[\s:.\-|]*[\r\n]+([\s\S]{1,300}?)(?:\n\s*\n|for\s*any\s*enquiries|\Z)", text)
    if notes_match:
        terms.append(f"📝 **Additional Notes:**\n{notes_match.group(1).strip()}")
        
    return "\n\n".join(terms) if terms else None


def extract_place_of_supply(text: str) -> Optional[str]:
    """Extracts Place of Supply, Country of Supply, or Shipping Location."""
    rows = []
    pos_m = re.search(r"(?i)\b(?:place\s*of\s*supply|pos)\b[:\s\t\-|]*([^\r\n]{2,40})", text)
    if pos_m:
        val = clean_val(pos_m.group(1))
        if val: rows.append(f"• **Place of Supply:** `{val}`")
    cos_m = re.search(r"(?i)\b(?:country\s*of\s*supply|country)\b[:\s\t\-|]*([^\r\n]{2,40})", text)
    if cos_m:
        val = clean_val(cos_m.group(1))
        if val: rows.append(f"• **Country of Supply:** `{val}`")
    return "\n".join(rows) if rows else None


def local_extract_idp_answer(query: str, doc_text: str, document_data: Optional[Dict[str, Any]]) -> Tuple[str, list]:
    q_lower = query.lower().strip()

    # 1. Identity & Introduction Queries
    if re.search(r"^(who are (you|u|r u)|who r u|what is your name|who made you|what are you)\b", q_lower):
        return (
            "👋 I’m **Reeva AI**, the Intelligent Document Processing (IDP) Assistant built by **Reeva Dev**!\n\nI specialize in analyzing, extracting, and inspecting your documents, invoices, receipts, and forms using advanced OCR, YOLO layout segmentation, and Explainable AI fraud detection.",
            ["✨ What can you do?", "📁 Supported Formats", "🚀 How to upload"]
        )

    # 2. Capability & Feature Queries
    if re.search(r"^(what (can|did|do) (you|u) do|what are your (features|capabilities)|how can you help|what else can you do)\b", q_lower) or re.search(r"what (can|did|do) (you|u) do", q_lower):
        return (
            "✨ **Here is everything I can do for you:**\n\n• 📄 **Document Extraction:** Parse text, structured markdown, and JSON tables from PDFs, images, DOCX, and XLSX.\n• 💰 **Financial Breakdown:** Extract and verify Subtotals, Tax/GST/VAT, and Grand Totals.\n• 🔢 **Invoice Details:** Extract Invoice Numbers, Issue Dates, Due Dates, and Reference IDs.\n• 🏢 **Parties & Contacts:** Identify Vendor/Issuer details, Customer/Billed To info, and email addresses.\n• 🛡️ **Explainable AI Fraud Inspection:** Detect layout tampering, arithmetic discrepancies, and calculate risk scores.\n• 📱 **QR & Barcode Decoding:** Decode scannable payloads and UPI payment links.\n• 🔊 **Voice Speech & Audio:** Read responses aloud and accept microphone voice input.\n\n*Upload a document on the homepage to start asking questions about it!*",
            ["💰 Invoice Total", "🔢 Invoice Number", "🛡️ Fraud Check", "📁 Supported Formats"]
        )

    # 3. Greeting Queries
    if re.search(r"^(hi|hello|hey|hola|greetings|good morning|good afternoon|good evening)\b", q_lower):
        return (
            "👋 **Hello!** How can I assist you with your document processing or questions today?",
            ["✨ What can you do?", "🚀 How to upload documents", "📁 Supported Formats"]
        )

    # 4. Help & Instructions Queries
    if re.search(r"^(how to (use|upload|process)|help|how does (it|this) work|instructions)\b", q_lower):
        return (
            "🚀 **How to Use IDP:**\n\n1. **Upload Documents:** Drag and drop your PDF or image into the upload box at the top.\n2. **Convert:** Click **🚀 Convert & Process Documents** to run OCR, YOLO layout analysis, and fraud checks.\n3. **Inspect Tabs:** Review the extracted Markdown, Tables, JSON, YOLO Layout Crops, and Fraud overlays.\n4. **Ask Reeva AI:** Ask me any specific question about amounts, dates, or items here in the chat (or click 🎙️ to speak)!",
            ["📁 Supported Formats", "🛡️ Fraud Detection Info", "✨ What can you do?"]
        )

    # 5. Supported Formats
    if re.search(r"\b(supported formats|what formats|file types|formats supported)\b", q_lower):
        return (
            "📁 **Supported Document Formats:**\n\n• 📄 **PDFs:** Scanned and digital multi-page PDFs\n• 🖼️ **Images:** PNG, JPG, JPEG, TIFF, WEBP\n• 📊 **Office Documents:** DOCX, PPTX, XLSX",
            ["🚀 How to upload", "✨ What can you do?", "🛡️ Fraud Check"]
        )

    if not doc_text.strip():
        return (
            "👋 **No document content is currently loaded.**\n\nPlease drag and drop a PDF or image invoice into the upload box above and click **Convert & Process Documents** to analyze it!",
            ["🚀 How to upload documents", "📁 Supported Formats", "✨ What can you do?"]
        )

    # A. Tax ID / GSTIN / PAN / VAT Registration Numbers
    if re.search(r"\b(gst|gstin|gst no|gst number|tax id|tax no|tax number|pan|pan card|pan no|vat|vat no|vat number|tin|cin|registration no|reg no)\b", q_lower):
        res = extract_gst_tax_details_field(doc_text)
        return (
            res,
            ["💰 Invoice Total", "🔢 Invoice Number", "🏢 Vendor Details"]
        )

    # B. Bank & Payment Information
    if re.search(r"\b(bank|account|account number|a\/c|ifsc|iban|swift|upi|payment method|payment mode)\b", q_lower):
        bank_lines = []
        clean_text = re.sub(r"<[^>]+>", "\n", doc_text)
        for line in clean_text.split("\n"):
            clean_l = clean_val(line)
            if not clean_l or len(clean_l) < 3:
                continue
            if re.search(r"\b(?:bank|account|a\/c|ifsc|iban|swift|upi|branch|savings|current)\b", clean_l, re.IGNORECASE):
                if not re.search(r"\b(?:terms|condition|please pay|charged on)\b", clean_l, re.IGNORECASE):
                    bank_lines.append(f"• {clean_l}")

        if bank_lines:
            unique_bank = list(dict.fromkeys(bank_lines))
            return (
                "🏦 **Bank & Payment Details:**\n\n" + "\n".join(unique_bank[:8]),
                ["💰 Invoice Total", "🔢 Invoice Number", "🏢 Vendor Info"]
            )

    # C. PO / Order / Quotation Number
    if re.search(r"\b(po number|po no|purchase order|order number|order no|quote number|job number|quotation|proforma)\b", q_lower):
        po_m = re.search(r"(?:p\.?o\.?\s*(?:no|num|number|#)|purchase\s*order|order\s*(?:no|number|#)|quotation\s*(?:no|number|#)?)[\s*:#.-]*([A-Za-z0-9\/-]{2,30})", doc_text, re.IGNORECASE)
        if po_m:
            return (
                f"📦 **Order / Reference Information:**\n\n• **Order / Reference Number:** `{clean_val(po_m.group(1))}`",
                ["💰 Total Amount", "🔢 Invoice Number", "📅 Dates"]
            )

    # D. Total in Words / Amount in Words
    if re.search(r"\b(in words|amount in words|total in words|words)\b", q_lower):
        words = extract_amount_in_words(doc_text)
        if words:
            return (
                f"🔤 **Amount in Words:**\n\n• `{words}`",
                ["💰 Numeric Total", "🔢 Invoice Number", "🏢 Vendor Details"]
            )

    # E. Terms & Conditions / Notes / Early Payment Discount
    if re.search(r"\b(terms|condition|conditions|policy|late fee|overdue interest|early pay|earlypay|notes|additional notes|remarks)\b", q_lower):
        terms_text = extract_terms_and_notes(doc_text)
        if terms_text:
            return (
                terms_text,
                ["💰 Invoice Total", "📅 Due Date", "🏦 Bank Details"]
            )

    # F. Place of Supply / Country / Shipping Location
    if re.search(r"\b(place of supply|country of supply|pos|shipping address|ship to|delivery location|dispatch)\b", q_lower):
        pos_text = extract_place_of_supply(doc_text)
        if pos_text:
            return (
                "📍 **Supply & Delivery Details:**\n\n" + pos_text,
                ["🏢 Vendor & Customer", "💰 Invoice Total", "🧾 GST Details"]
            )

    # Specific Query Identifiers
    is_inv_query = bool(re.search(r"\b(invoice number|invoice no|inv no|invoice #|invoice id|reference number|bill number|receipt number|document number)\b", q_lower))
    is_date_query = bool(re.search(r"\b(due date|invoice date|billing date|issue date|date of issue|when was|pay by)\b", q_lower))

    # G. Invoice Number & Date Combined Extraction
    if is_inv_query or is_date_query:
        inv_num = extract_invoice_number_field(doc_text)
        inv_date, due_date = extract_dates_fields(doc_text)

        inv_rows = []
        if inv_num and is_inv_query:
            inv_rows.append(f"• **Invoice Number:** `{inv_num}`")
        if inv_date and (is_date_query or "date" in q_lower):
            inv_rows.append(f"• **Invoice Date:** `{inv_date}`")
        if due_date and (is_date_query or "due" in q_lower or "date" in q_lower):
            inv_rows.append(f"• **Due Date:** `{due_date}`")

        # If user asked for invoice number and we have both number and dates, present complete invoice info
        if is_inv_query and inv_num:
            if inv_date and not any("Invoice Date" in r for r in inv_rows):
                inv_rows.append(f"• **Invoice Date:** `{inv_date}`")
            if due_date and not any("Due Date" in r for r in inv_rows):
                inv_rows.append(f"• **Due Date:** `{due_date}`")

        if inv_rows:
            return (
                "🔢 **Invoice Information:**\n\n" + "\n".join(inv_rows),
                ["📅 Invoice Dates", "💰 Invoice Total", "🏢 Vendor & Customer"]
            )

    # H. Vendor / Customer / Supplier / Parties
    if re.search(r"\b(vendor|seller|supplier|company|billed to|customer|buyer|client|who issued|parties|who is)\b", q_lower):
        parties = extract_parties_fields(doc_text)
        rows = []
        if parties.get('vendor'):
            rows.append(f"• **Vendor / Seller:** `{parties['vendor']}`")
            if parties.get('vendor_addr'):
                rows.append(f"  *Address:* {parties['vendor_addr']}")
        if parties.get('customer'):
            rows.append(f"• **Customer / Billed To:** `{parties['customer']}`")
            if parties.get('customer_addr'):
                rows.append(f"  *Address:* {parties['customer_addr']}")
        if parties.get('email'):
            rows.append(f"• **Contact Email:** `{parties['email']}`")
        if parties.get('phone'):
            rows.append(f"• **Contact Phone:** `{parties['phone']}`")

        if rows:
            return (
                "🏢 **Parties Information:**\n\n" + "\n".join(rows),
                ["💰 Invoice Total", "🔢 Invoice Number", "🧾 GST & Tax Details"]
            )

    # I. Financial / Total / Tax / Amount
    if re.search(r"\b(total|amount|grand total|subtotal|tax|gst|vat|price|cost|how much|balance due|net amount|net payable)\b", q_lower):
        fin_text = extract_financial_breakdown_field(doc_text)
        if "•" in fin_text:
            return (
                fin_text,
                ["🔢 Invoice Number & Date", "🏢 Vendor Details", "🛡️ Fraud Check", "📋 Line Items"]
            )

    # J. Fraud / Legitimacy
    if re.search(r"\b(fraud|fake|suspicious|valid|risk|tampered|anomaly|legit)\b", q_lower):
        if document_data and document_data.get("fraud_report"):
            fr = document_data["fraud_report"]
            verdict = fr.get("verdict", "LEGITIMATE / LOW RISK")
            risk = fr.get("risk_score", 0)
            return (
                f"🛡️ **Explainable AI Fraud Inspection:**\n\n• **Verdict:** **{verdict}**\n• **Risk Score:** `{risk}%`\n\nSee the **Fraud Detection** tab for field-level overlays.",
                ["💰 Verify Totals", "🔢 Invoice Number", "📅 Dates"]
            )
        return (
            "🛡️ **Fraud Status:** Arithmetic consistency and visual layout checks are active. Check the **Fraud Detection** tab to view flagged bounding boxes.",
            ["💰 What is the total?", "🔢 Invoice Number"]
        )

    # K. QR Codes
    if re.search(r"\b(qr|qr code|barcode|scannable)\b", q_lower):
        if document_data and document_data.get("qr_codes"):
            qr_lines = [f"**QR #{i+1}:** `{q.get('content', 'Decoded')}`" for i, q in enumerate(document_data["qr_codes"])]
            return (
                "📱 **QR Codes Found in Document:**\n\n" + "\n".join(qr_lines),
                ["💰 Invoice Total", "🛡️ Fraud Check", "🔢 Invoice Number"]
            )
        return (
            "📱 **QR Code Status:** No QR codes were detected in the current document.",
            ["💰 Invoice Total", "📅 Dates", "🛡️ Fraud Check"]
        )

    # L. Items / Table / Products / Services
    if re.search(r"\b(items|line items|products|services|table|breakdown|quantities|quantity|qty|rate|hsn|description)\b", q_lower):
        # 1. Check for HTML tables
        html_md = html_table_to_markdown(doc_text)
        if html_md:
            return (
                "📋 **Extracted Line Items / Table:**\n\n" + html_md,
                ["💰 Grand Total", "📅 Invoice Date", "🏢 Vendor Info"]
            )
        # 2. Check for markdown table lines
        table_lines = [clean_val(l) for l in doc_text.split("\n") if "|" in l and not l.startswith("<")]
        if len(table_lines) >= 2:
            return (
                "📋 **Extracted Line Items / Table:**\n\n" + "\n".join(table_lines[:15]),
                ["💰 Grand Total", "📅 Invoice Date", "🏢 Vendor Info"]
            )

    # M. Summary
    if re.search(r"\b(summary|summarize|what is this|overview|explain)\b", q_lower):
        inv_num = extract_invoice_number_field(doc_text)
        inv_date, _ = extract_dates_fields(doc_text)
        parties = extract_parties_fields(doc_text)
        summary_bullets = []
        if inv_num: summary_bullets.append(f"• **Invoice Number:** `{inv_num}`")
        if inv_date: summary_bullets.append(f"• **Date:** `{inv_date}`")
        if parties.get('vendor'): summary_bullets.append(f"• **Vendor:** `{parties['vendor']}`")
        if parties.get('customer'): summary_bullets.append(f"• **Customer:** `{parties['customer']}`")
        
        if summary_bullets:
            return (
                "📄 **Document Summary:**\n\n" + "\n".join(summary_bullets),
                ["💰 Invoice Total", "🔢 Invoice Number", "📅 Invoice Date"]
            )

    # N. Universal Line-by-Line Keyword & Field Finder
    stop_words = {'provide', 'give', 'tell', 'show', 'find', 'what', 'is', 'the', 'of', 'for', 'in', 'this', 'document', 'file', 'please', 'me', 'can', 'you', 'number', 'details'}
    keywords = [w for w in re.split(r'[^a-zA-Z0-9]+', q_lower) if len(w) >= 2 and w not in stop_words]
    if keywords:
        matching_lines = []
        clean_text = re.sub(r"<[^>]+>", "\n", doc_text)
        for line in clean_text.split("\n"):
            clean_l = clean_val(line)
            if not clean_l or len(clean_l) < 3 or clean_l.startswith("<"):
                continue
            l_lower = clean_l.lower()
            if any(k in l_lower for k in keywords):
                matching_lines.append(f"• {clean_l}")

        if matching_lines:
            unique_matches = list(dict.fromkeys(matching_lines))
            return (
                "🔍 **Matching Document Content:**\n\n" + "\n".join(unique_matches[:8]),
                ["💰 Total Amount", "🔢 Invoice Number", "📅 Document Dates"]
            )

    # O. Paragraph keyword matching
    clean_text = re.sub(r"<[^>]+>", "\n", doc_text)
    paras = [clean_val(p) for p in clean_text.split("\n\n") if len(clean_val(p)) > 15]
    tokens = [w for w in q_lower.split() if len(w) >= 3]
    best_p, best_score = "", 0
    for p in paras:
        score = sum(1 for t in tokens if t in p.lower())
        if score > best_score:
            best_score = score
            best_p = p

    if best_p and best_score >= 1:
        return (
            f"🔍 **Information Found in Document:**\n\n{best_p}",
            ["💰 Total Amount", "🔢 Invoice Number", "📅 Document Dates"]
        )

    return (
        f"I searched the document for **\"{query}\"**, but couldn't find an exact match.\n\nYou can ask about:\n• 💰 **Invoice Total & Tax**\n• 🔢 **Invoice Number & Dates**\n• 🏢 **Vendor & Customer**\n• 📋 **Line Items & Services**\n• 🏦 **Bank & Payment Details**\n• 🛡️ **Fraud & Risk**",
        ["💰 Invoice Total", "🔢 Invoice Number", "📅 Invoice Date", "🛡️ Fraud Check"]
    )

