import cv2
import numpy as np
from pyzbar.pyzbar import decode as pyzbar_decode
import zxingcpp
import requests
import json
import re
import base64
from typing import List, Dict, Any, Optional

_qreader_instance: Optional[Any] = None

def get_qreader_instance():
    """Lazy initialize QReader detector to prevent repeated model loading."""
    global _qreader_instance
    if _qreader_instance is None:
        try:
            from qreader import QReader
            _qreader_instance = QReader()
        except Exception:
            _qreader_instance = False
    return _qreader_instance if _qreader_instance is not False else None


def parse_qr_structured_text(content: str) -> Dict[str, Any]:
    """Parse structured data inside QR codes (such as GST certificates, e-invoices, vCards, JSON, or Base64/JWT)."""
    details: Dict[str, Any] = {"raw_content": content}
    text = content.strip()

    # 1. Check Base64 / JWT payload
    if len(text) > 30 and ("=" in text or text.count(".") == 2 or re.match(r"^[A-Za-z0-9+/=_-]+$", text)):
        try:
            b64_candidate = text.split(".")[1] if text.count(".") == 2 else text
            b64_candidate += "=" * (-len(b64_candidate) % 4)
            decoded_bytes = base64.b64decode(b64_candidate)
            decoded_str = decoded_bytes.decode("utf-8", errors="ignore")
            if decoded_str.startswith("{") and decoded_str.endswith("}"):
                details["base64_decoded_json"] = json.loads(decoded_str)
            elif len(decoded_str) > 5 and any(c.isalnum() for c in decoded_str):
                details["base64_decoded_text"] = decoded_str
        except Exception:
            pass

    # 2. Check JSON
    if text.startswith("{") and text.endswith("}"):
        try:
            details["json_data"] = json.loads(text)
            return details
        except Exception:
            pass

    # 3. Check pipe-separated, newline-separated, or comma-separated fields (common in GST certificates, e-invoices)
    field_map = {}
    delimiters = ["|", "\n", ","]
    used_delim = None
    for d in delimiters:
        if d in text:
            used_delim = d
            break

    if used_delim:
        parts = [p.strip() for p in text.split(used_delim) if p.strip()]
        for idx, part in enumerate(parts, 1):
            if ":" in part:
                k, v = part.split(":", 1)
                field_map[k.strip()] = v.strip()
            elif "=" in part:
                k, v = part.split("=", 1)
                field_map[k.strip()] = v.strip()
            else:
                field_map[f"Field_{idx}"] = part
        if field_map:
            details["parsed_fields"] = field_map

    # 4. Regex search for GSTIN pattern (e.g., 24ABBFK4301Q1ZC)
    gstin_match = re.search(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}\b", text)
    if gstin_match:
        details["detected_gstin"] = gstin_match.group(0)

    # PAN match
    pan_match = re.search(r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b", text)
    if pan_match and not gstin_match:
        details["detected_pan"] = pan_match.group(0)

    # Date match
    date_matches = re.findall(r"\b\d{2}[/-]\d{2}[/-]\d{4}\b", text)
    if date_matches:
        details["detected_dates"] = date_matches

    # PIN Code match
    pincode_match = re.search(r"\b[1-9][0-9]{5}\b", text)
    if pincode_match:
        details["detected_pin_code"] = pincode_match.group(0)

    return details


def _run_qr_detectors(cv_img: np.ndarray) -> List[Dict[str, str]]:
    """
    Runs multiple QR detection engines:
    1. zxing-cpp (C++ ZXing port - extremely accurate)
    2. QReader (YOLO-based QR detector + decoder)
    3. pyzbar
    4. OpenCV QRCodeDetector
    """
    results = []
    if cv_img is None or cv_img.size == 0:
        return results

    seen_contents = set()

    def add_result(cnt: str, engine_type: str = "QRCODE"):
        cnt_str = cnt.strip()
        if cnt_str and cnt_str not in seen_contents:
            seen_contents.add(cnt_str)
            results.append({"content": cnt_str, "type": engine_type})

    # Prepare padded version to guarantee quiet zone around QR code
    if len(cv_img.shape) == 2:
        padded_img = cv2.copyMakeBorder(cv_img, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255)
    else:
        padded_img = cv2.copyMakeBorder(cv_img, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=[255, 255, 255])

    images_to_test = [cv_img, padded_img]

    # Engine 1: zxing-cpp
    for img_variant in images_to_test:
        try:
            barcodes = zxingcpp.read_barcodes(img_variant)
            for b in barcodes:
                if b.is_valid and b.text:
                    fmt = str(b.format).split(".")[-1] if hasattr(b, "format") else "QRCODE"
                    add_result(b.text, fmt)
        except Exception:
            pass
        if results:
            return results

    # Engine 2: QReader (YOLO QR detector)
    qr_detector = get_qreader_instance()
    if qr_detector is not None:
        for img_variant in images_to_test:
            try:
                rgb_img = cv2.cvtColor(img_variant, cv2.COLOR_BGR2RGB) if len(img_variant.shape) == 3 else cv2.cvtColor(img_variant, cv2.COLOR_GRAY2RGB)
                decoded_qrs = qr_detector.detect_and_decode(image=rgb_img)
                if decoded_qrs:
                    for dq in decoded_qrs:
                        if dq:
                            add_result(dq, "QRCODE")
            except Exception:
                pass
            if results:
                return results

    # Engine 3: pyzbar
    for img_variant in images_to_test:
        try:
            pyzbar_res = pyzbar_decode(img_variant)
            for r in pyzbar_res:
                try:
                    txt = r.data.decode("utf-8", errors="ignore")
                    if txt:
                        add_result(txt, r.type or "QRCODE")
                except Exception:
                    pass
        except Exception:
            pass
        if results:
            return results

    # Engine 4: OpenCV QRCodeDetector
    try:
        detector = cv2.QRCodeDetector()
        for img_variant in images_to_test:
            retval, decoded_info, points, straight_qrcode = detector.detectAndDecodeMulti(img_variant)
            if retval:
                for info in decoded_info:
                    if info and info.strip():
                        add_result(info, "QRCODE")
            else:
                info, points, _ = detector.detectAndDecode(img_variant)
                if info and info.strip():
                    add_result(info, "QRCODE")
            if results:
                return results
    except Exception:
        pass

    return results


def decode_qr_from_cv2_image(img: np.ndarray) -> List[Dict[str, str]]:
    """
    Multi-stage QR extraction pipeline:
    Stage 1: Direct multi-engine decode (zxing-cpp, QReader, pyzbar, OpenCV)
    Stage 2: Multi-scale upscaling (1.5x, 2.0x, 3.0x, 4.0x) with quiet zone padding
    Stage 3: Image Preprocessing (Grayscale, CLAHE contrast enhancement, Sharpening, Otsu, Inverted Otsu, Adaptive Threshold)
    Stage 4: Contour / Square Candidate Region Cropping & padded candidate scanning
    """
    if img is None or img.size == 0:
        return []

    found_qrs = []
    seen_contents = set()

    def add_unique(items):
        for item in items:
            cnt = item["content"]
            if cnt not in seen_contents:
                seen_contents.add(cnt)
                found_qrs.append(item)

    # --- Stage 1: Direct multi-engine scan ---
    add_unique(_run_qr_detectors(img))
    if found_qrs:
        return found_qrs

    # --- Stage 2: Multi-scale upscaling ---
    h, w = img.shape[:2]
    for scale in [1.5, 2.0, 3.0, 4.0]:
        upscaled = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
        add_unique(_run_qr_detectors(upscaled))
        if found_qrs:
            return found_qrs

    # --- Stage 3: Image Preprocessing ---
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()

    # Contrast enhancement (CLAHE)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    gray_clahe = clahe.apply(gray)

    # Sharpening
    sharpen_kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
    gray_sharp = cv2.filter2D(gray, -1, sharpen_kernel)

    # Binarization thresholds
    _, thresh_otsu = cv2.threshold(gray_clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, thresh_otsu_inv = cv2.threshold(gray_clahe, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    thresh_adapt = cv2.adaptiveThreshold(gray_clahe, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 3)

    for preprocess_variant in [gray, gray_clahe, gray_sharp, thresh_otsu, thresh_otsu_inv, thresh_adapt]:
        add_unique(_run_qr_detectors(preprocess_variant))
        if found_qrs:
            return found_qrs

    # --- Stage 4: Contour Candidate Region Cropping ---
    try:
        contours, _ = cv2.findContours(thresh_adapt, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        h_img, w_img = gray.shape[:2]
        for cnt in contours:
            x, y, w_box, h_box = cv2.boundingRect(cnt)
            aspect_ratio = float(w_box) / h_box if h_box > 0 else 0

            if 30 <= w_box <= w_img * 0.7 and 30 <= h_box <= h_img * 0.7 and 0.5 <= aspect_ratio <= 1.8:
                pad = 30
                x1 = max(0, x - pad)
                y1 = max(0, y - pad)
                x2 = min(w_img, x + w_box + pad)
                y2 = min(h_img, y + h_box + pad)

                crop = img[y1:y2, x1:x2]
                if crop.size > 0:
                    add_unique(_run_qr_detectors(crop))
                    crop_2x = cv2.resize(crop, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
                    add_unique(_run_qr_detectors(crop_2x))
                    if found_qrs:
                        break
    except Exception:
        pass

    return found_qrs


def decode_qr_from_image_bytes(image_bytes: bytes) -> List[Dict[str, str]]:
    """Decode QR codes from raw image bytes (PNG/JPG)."""
    if not image_bytes:
        return []
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return []
    return decode_qr_from_cv2_image(img)


def decode_qr_from_pil(pil_image) -> List[Dict[str, str]]:
    """Decode QR codes from a PIL Image (used for PDF page renders)."""
    if pil_image is None:
        return []
    arr = np.array(pil_image.convert("RGB"))
    img = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    return decode_qr_from_cv2_image(img)


def extract_qr_from_pdf_bytes(pdf_bytes: bytes, max_pages: int = 20) -> List[Dict[str, Any]]:
    """
    Extracts QR codes from PDF files using a fast dual strategy:
    1. Direct PDF embedded image extraction (super fast ~10ms, extracts raw XObject image streams directly).
    2. Page rendering canvas scan (fallback for vector-rendered or scanned pages).
    """
    if not pdf_bytes:
        return []

    qr_results = []
    seen_key = set()

    def add_qr(qr_item, page_num):
        content = qr_item["content"]
        key = (content, page_num)
        if key not in seen_key:
            seen_key.add(key)
            item = dict(qr_item)
            item["page"] = page_num
            qr_results.append(item)

    # Strategy 1 (Fast-Path ~10ms): Direct PDF embedded image stream extraction (PyMuPDF / fitz)
    try:
        import pymupdf
        pdf_doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        pages_to_check = min(len(pdf_doc), max_pages)

        for page_idx in range(pages_to_check):
            page = pdf_doc[page_idx]
            page_num = page_idx + 1

            try:
                image_list = page.get_images(full=True)
                for img_info in image_list:
                    xref = img_info[0]
                    base_img = pdf_doc.extract_image(xref)
                    if base_img and "image" in base_img:
                        img_bytes = base_img["image"]
                        qrs_in_img = decode_qr_from_image_bytes(img_bytes)
                        for q in qrs_in_img:
                            add_qr(q, page_num)
            except Exception:
                pass

        # If embedded image extraction found QR codes, return immediately (super fast!)
        if qr_results:
            return qr_results

        # Strategy 2 (Fallback): Page canvas render scan (at 150 DPI)
        for page_idx in range(pages_to_check):
            page = pdf_doc[page_idx]
            page_num = page_idx + 1
            try:
                pix = page.get_pixmap(dpi=150)
                page_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
                if pix.n == 4:
                    page_np = cv2.cvtColor(page_np, cv2.COLOR_RGBA2BGR)
                elif pix.n == 3:
                    page_np = cv2.cvtColor(page_np, cv2.COLOR_RGB2BGR)

                qrs_in_page = decode_qr_from_cv2_image(page_np)
                for q in qrs_in_page:
                    add_qr(q, page_num)
            except Exception:
                pass

    except Exception:
        # Fallback to pypdfium2 if pymupdf fails
        try:
            import pypdfium2 as pdfium
            pdf_doc = pdfium.PdfDocument(pdf_bytes)
            pages_to_check = min(len(pdf_doc), max_pages)
            for i in range(pages_to_check):
                page = pdf_doc[i]
                bitmap = page.render(scale=2.0)
                pil_image = bitmap.to_pil()
                found = decode_qr_from_pil(pil_image)
                for f in found:
                    add_qr(f, i + 1)
        except Exception:
            pass

    return qr_results


def fetch_qr_details(content: str) -> Dict[str, Any]:
    """If QR content is a URL, fetch it and return status + preview. Otherwise parse structured data."""
    if content.startswith("http://") or content.startswith("https://"):
        try:
            resp = requests.get(content, timeout=5)
            return {
                "url": content,
                "status_code": resp.status_code,
                "content_type": resp.headers.get("Content-Type", ""),
                "preview": resp.text[:500] if "text" in resp.headers.get("Content-Type", "") else "(non-text content)"
            }
        except Exception as e:
            return {"url": content, "error": str(e)}

    return parse_qr_structured_text(content)

