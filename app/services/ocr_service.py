import os
import re
import uuid
import tempfile
import cv2
import numpy as np
import pytesseract
import pdfplumber
from fastapi import UploadFile


def _clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)      # collapse spaces
    text = re.sub(r"\n{3,}", "\n\n", text)   # collapse extra new lines
    return text.strip()


def _preprocess_for_ocr(img_bgr: np.ndarray) -> np.ndarray:
    # grayscale
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # denoise while preserving edges
    gray = cv2.bilateralFilter(gray, 9, 75, 75)

    # adaptive threshold (better for uneven lighting)
    bw = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        15
    )

    # optional morphology to reduce tiny noise
    kernel = np.ones((1, 1), np.uint8)
    bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel, iterations=1)
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, kernel, iterations=1)

    return bw


def _ocr_tesseract_with_fallbacks(image_bw: np.ndarray) -> str:
    # Try multiple page segmentation modes, choose best by length
    configs = [
        "--oem 3 --psm 6",   # uniform block
        "--oem 3 --psm 4",   # single column
        "--oem 3 --psm 11",  # sparse text
    ]

    best_text = ""
    for cfg in configs:
        txt = pytesseract.image_to_string(image_bw, config=cfg) or ""
        txt = _clean_text(txt)
        if len(txt) > len(best_text):
            best_text = txt
    return best_text


async def extract_text_from_pdf(file: UploadFile) -> str:
    """
    1) Try direct text extraction from PDF.
    2) If page has no selectable text, convert page to image and OCR it.
    """
    content = await file.read()
    text_parts = []

    # ✅ Cross-platform temp path (Windows/Linux/Render)
    temp_dir = tempfile.gettempdir()
    tmp_pdf_path = os.path.join(temp_dir, f"{uuid.uuid4().hex}.pdf")

    try:
        with open(tmp_pdf_path, "wb") as f:
            f.write(content)

        with pdfplumber.open(tmp_pdf_path) as pdf:
            for page in pdf.pages:
                # Direct text first (best for typed PDFs)
                direct_text = (page.extract_text() or "").strip()
                if direct_text:
                    text_parts.append(_clean_text(direct_text))
                    continue

                # Fallback OCR for scanned PDF pages
                try:
                    pil_img = page.to_image(resolution=300).original
                    page_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                    bw = _preprocess_for_ocr(page_bgr)
                    ocr_text = _ocr_tesseract_with_fallbacks(bw)
                    text_parts.append(ocr_text)
                except Exception:
                    text_parts.append("")

        return _clean_text("\n\n".join([t for t in text_parts if t]))

    finally:
        if os.path.exists(tmp_pdf_path):
            os.remove(tmp_pdf_path)


async def extract_text_from_image(file: UploadFile) -> str:
    content = await file.read()
    arr = np.frombuffer(content, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    if img is None:
        return ""

    bw = _preprocess_for_ocr(img)
    text = _ocr_tesseract_with_fallbacks(bw)
    return _clean_text(text)