import os
import re
import uuid
import time
import logging
import tempfile

import cv2
import numpy as np
import pytesseract
import pdfplumber

from paddleocr import PaddleOCR
from fastapi import UploadFile


# =========================================================
# LOGGER CONFIG
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("OCR_SERVICE")


# =========================================================
# OCR MODELS
# =========================================================

logger.info("Initializing PaddleOCR...")

paddle_ocr = None


def get_paddle_ocr():
    global paddle_ocr

    if paddle_ocr is None:
        try:
            print("🔵 Initializing PaddleOCR...")
            paddle_ocr = PaddleOCR(
                use_angle_cls=True,
                lang="en",
                show_log=False  # IMPORTANT FIX
            )
            print("🟢 PaddleOCR initialized successfully")

        except Exception as e:
            print(f"🔴 PaddleOCR init failed: {e}")
            paddle_ocr = None

    return paddle_ocr


# =========================================================
# CLEAN TEXT
# =========================================================

def _clean_text(text: str) -> str:

    if not text:
        return ""

    text = text.replace("\r", "\n")

    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text
    )

    return text.strip()


# =========================================================
# DESKEW IMAGE
# =========================================================

def _deskew(image: np.ndarray) -> np.ndarray:

    try:

        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY
        )

        coords = np.column_stack(
            np.where(gray > 0)
        )

        if len(coords) == 0:
            return image

        angle = cv2.minAreaRect(coords)[-1]

        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        (h, w) = image.shape[:2]

        center = (w // 2, h // 2)

        M = cv2.getRotationMatrix2D(
            center,
            angle,
            1.0
        )

        rotated = cv2.warpAffine(
            image,
            M,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )

        logger.info(
            f"Deskew applied with angle: {round(angle, 2)}"
        )

        return rotated

    except Exception as e:

        logger.warning(
            f"Deskew failed: {str(e)}"
        )

        return image


# =========================================================
# IMAGE ENHANCEMENT
# =========================================================

def _preprocess_for_ocr(
    img_bgr: np.ndarray
) -> np.ndarray:

    logger.info("Starting OCR preprocessing")

    img_bgr = _deskew(img_bgr)

    gray = cv2.cvtColor(
        img_bgr,
        cv2.COLOR_BGR2GRAY
    )

    # CLAHE contrast enhancement
    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8)
    )

    gray = clahe.apply(gray)

    # denoise
    gray = cv2.fastNlMeansDenoising(
        gray,
        None,
        10,
        7,
        21
    )

    # adaptive threshold
    bw = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        15
    )

    # morphology cleanup
    kernel = np.ones((1, 1), np.uint8)

    bw = cv2.morphologyEx(
        bw,
        cv2.MORPH_OPEN,
        kernel
    )

    bw = cv2.morphologyEx(
        bw,
        cv2.MORPH_CLOSE,
        kernel
    )

    logger.info("OCR preprocessing completed")

    return bw


# =========================================================
# PADDLE OCR
# =========================================================

def _ocr_paddle(
    image: np.ndarray
) -> str:

    if paddle_ocr is None:

        logger.warning(
            "PaddleOCR unavailable"
        )

        return ""

    try:

        logger.info(
            "Running PaddleOCR..."
        )

        start = time.time()

        result = paddle_ocr.ocr(
            image,
            cls=True
        )

        lines = []

        if result:

            logger.info(
                f"PaddleOCR detected blocks: {len(result)}"
            )

            for block in result:

                if not block:
                    continue

                for line in block:

                    try:

                        if len(line) < 2:
                            continue

                        text = line[1][0]

                        confidence = line[1][1]

                        logger.info(
                            f"Paddle Text: {text[:50]} | "
                            f"Conf: {round(confidence, 3)}"
                        )

                        if (
                            text and
                            confidence > 0.40
                        ):
                            lines.append(text)

                    except Exception:
                        continue

        final_text = _clean_text(
            "\n".join(lines)
        )

        logger.info(
            f"PaddleOCR completed in "
            f"{round(time.time() - start, 2)}s"
        )

        logger.info(
            f"PaddleOCR extracted "
            f"{len(final_text)} chars"
        )

        return final_text

    except Exception as e:

        logger.error(
            f"PaddleOCR failed: {str(e)}"
        )

        return ""


# =========================================================
# TESSERACT FALLBACK
# =========================================================

def _ocr_tesseract(
    image_bw: np.ndarray
) -> str:

    logger.info(
        "Running Tesseract fallback..."
    )

    configs = [
        "--oem 3 --psm 6",
        "--oem 3 --psm 4",
        "--oem 3 --psm 11",
    ]

    best_text = ""

    for cfg in configs:

        try:

            start = time.time()

            txt = pytesseract.image_to_string(
                image_bw,
                config=cfg
            ) or ""

            txt = _clean_text(txt)

            logger.info(
                f"Tesseract config [{cfg}] "
                f"returned {len(txt)} chars "
                f"in {round(time.time() - start, 2)}s"
            )

            if len(txt) > len(best_text):
                best_text = txt

        except Exception as e:

            logger.warning(
                f"Tesseract failed "
                f"for config {cfg}: {str(e)}"
            )

    logger.info(
        f"Tesseract selected result length: "
        f"{len(best_text)}"
    )

    return best_text


# =========================================================
# HYBRID OCR
# =========================================================

def _hybrid_ocr(
    image_bgr: np.ndarray
) -> str:

    logger.info(
        "Starting hybrid OCR pipeline"
    )

    processed = _preprocess_for_ocr(
        image_bgr
    )

    # PaddleOCR
    paddle_text = _ocr_paddle(
        processed
    )

    # Tesseract
    tesseract_text = _ocr_tesseract(
        processed
    )

    logger.info(
        f"Paddle length: {len(paddle_text)} | "
        f"Tesseract length: {len(tesseract_text)}"
    )

    # choose best
    if len(paddle_text) >= len(tesseract_text):

        logger.info(
            "Selected PaddleOCR output"
        )

        best = paddle_text

    else:

        logger.info(
            "Selected Tesseract output"
        )

        best = tesseract_text

    final = _clean_text(best)

    logger.info(
        f"Final OCR text length: {len(final)}"
    )

    return final


# =========================================================
# PDF EXTRACTION
# =========================================================

async def extract_text_from_pdf(
    file: UploadFile
) -> str:

    logger.info(
        f"Processing PDF: {file.filename}"
    )

    content = await file.read()

    text_parts = []

    temp_dir = tempfile.gettempdir()

    tmp_pdf_path = os.path.join(
        temp_dir,
        f"{uuid.uuid4().hex}.pdf"
    )

    try:

        with open(tmp_pdf_path, "wb") as f:
            f.write(content)

        with pdfplumber.open(tmp_pdf_path) as pdf:

            logger.info(
                f"PDF pages detected: {len(pdf.pages)}"
            )

            for idx, page in enumerate(pdf.pages):

                logger.info(
                    f"Processing page {idx + 1}"
                )

                # =====================================
                # DIRECT TEXT EXTRACTION
                # =====================================

                direct_text = (
                    page.extract_text() or ""
                ).strip()

                if len(direct_text) > 30:

                    logger.info(
                        f"Typed text detected "
                        f"on page {idx + 1}"
                    )

                    text_parts.append(
                        _clean_text(direct_text)
                    )

                    continue

                logger.info(
                    f"OCR fallback triggered "
                    f"for page {idx + 1}"
                )

                # =====================================
                # OCR FALLBACK
                # =====================================

                try:

                    pil_img = page.to_image(
                        resolution=350
                    ).original

                    page_bgr = cv2.cvtColor(
                        np.array(pil_img),
                        cv2.COLOR_RGB2BGR
                    )

                    ocr_text = _hybrid_ocr(
                        page_bgr
                    )

                    text_parts.append(ocr_text)

                except Exception as e:

                    logger.error(
                        f"Page OCR failed: {str(e)}"
                    )

                    text_parts.append("")

        final_text = "\n\n".join(
            [
                t for t in text_parts
                if t.strip()
            ]
        )

        logger.info(
            f"PDF extraction completed. "
            f"Total chars: {len(final_text)}"
        )

        return _clean_text(final_text)

    finally:

        if os.path.exists(tmp_pdf_path):

            os.remove(tmp_pdf_path)

            logger.info(
                "Temporary PDF removed"
            )


# =========================================================
# IMAGE EXTRACTION
# =========================================================

async def extract_text_from_image(
    file: UploadFile
) -> str:

    logger.info(
        f"Processing image: {file.filename}"
    )

    content = await file.read()

    arr = np.frombuffer(
        content,
        np.uint8
    )

    img = cv2.imdecode(
        arr,
        cv2.IMREAD_COLOR
    )

    if img is None:

        logger.error(
            "Failed to decode image"
        )

        return ""

    logger.info(
        f"Image shape: {img.shape}"
    )

    text = _hybrid_ocr(img)

    logger.info(
        f"Image OCR completed. "
        f"Extracted chars: {len(text)}"
    )

    return _clean_text(text)