"""
PDF processing service.

Converts PDF pages to images for display and analysis.
"""

import os
import asyncio
from typing import Optional

# Try to import PDF processing libraries
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    from pdf2image import convert_from_path
    HAS_PDF2IMAGE = True
except ImportError:
    HAS_PDF2IMAGE = False


UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")


async def process_pdf(file_id: str, pdf_path: str) -> dict:
    """
    Process a PDF file: extract pages as images.

    Args:
        file_id: Unique identifier for this upload
        pdf_path: Path to the PDF file

    Returns:
        dict with page count and image paths
    """
    upload_path = os.path.join(UPLOAD_DIR, file_id)
    os.makedirs(upload_path, exist_ok=True)

    if HAS_PYMUPDF:
        return await _process_with_pymupdf(pdf_path, upload_path)
    elif HAS_PDF2IMAGE:
        return await _process_with_pdf2image(pdf_path, upload_path)
    else:
        # Fallback: just note the PDF exists, frontend will use react-pdf
        return {
            "page_count": 1,
            "images": [],
            "note": "No PDF processing library available. Using frontend rendering."
        }


async def _process_with_pymupdf(pdf_path: str, output_dir: str) -> dict:
    """Process PDF using PyMuPDF (faster, no external dependencies)."""
    def _process():
        doc = fitz.open(pdf_path)
        images = []

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            # Render at 2x resolution for clarity
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)

            image_path = os.path.join(output_dir, f"page_{page_num + 1}.png")
            pix.save(image_path)
            images.append(image_path)

        doc.close()
        return {"page_count": len(images), "images": images}

    # Run in thread pool to not block async loop
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _process)


async def _process_with_pdf2image(pdf_path: str, output_dir: str) -> dict:
    """Process PDF using pdf2image (requires poppler)."""
    def _process():
        images = convert_from_path(pdf_path, dpi=200)
        image_paths = []

        for i, image in enumerate(images):
            image_path = os.path.join(output_dir, f"page_{i + 1}.png")
            image.save(image_path, "PNG")
            image_paths.append(image_path)

        return {"page_count": len(image_paths), "images": image_paths}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _process)


async def get_page_count(file_id: str) -> int:
    """Get the number of pages in a processed PDF."""
    upload_path = os.path.join(UPLOAD_DIR, file_id)

    # Count PNG files
    if os.path.exists(upload_path):
        png_files = [f for f in os.listdir(upload_path) if f.endswith('.png')]
        return len(png_files)

    return 0
