"""Compress all PDFs to image-based PDFs at JPEG quality 60.

Each page is rendered at 150 DPI, saved as JPEG quality 60,
then reassembled into a new PDF. Only replaces the original
when the compressed version is smaller. Text remains readable
at 150 DPI.
"""

import fitz  # PyMuPDF
import os
import sys
import io
from PIL import Image

PDF_DIR = os.path.join(os.path.dirname(__file__), "pdfs")
DPI = 150
JPEG_QUALITY = 60


def compress_pdf(filepath: str) -> tuple[str, int, int]:
    """Compress a single PDF.

    Returns (status, old_size, new_size).
    status: 'compressed', 'kept_original', 'error'
    """
    old_size = os.path.getsize(filepath)

    try:
        doc = fitz.open(filepath)
    except Exception:
        return "error", old_size, old_size

    if doc.page_count == 0:
        doc.close()
        return "error", old_size, old_size

    new_doc = fitz.open()
    zoom = DPI / 72
    mat = fitz.Matrix(zoom, zoom)

    for page in doc:
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY)
        buf.seek(0)
        img_bytes = buf.read()

        img_doc = fitz.open(stream=img_bytes, filetype="jpeg")
        rect = img_doc[0].rect
        new_page = new_doc.new_page(width=rect.width, height=rect.height)
        new_page.insert_image(rect, stream=img_bytes)
        img_doc.close()

    tmp_path = filepath + ".tmp"
    new_doc.save(tmp_path, garbage=4, deflate=True)
    new_doc.close()
    doc.close()

    new_size = os.path.getsize(tmp_path)

    if new_size < old_size:
        os.replace(tmp_path, filepath)
        return "compressed", old_size, new_size
    else:
        os.remove(tmp_path)
        return "kept_original", old_size, old_size


def main():
    pdf_files = sorted(
        f for f in os.listdir(PDF_DIR) if f.lower().endswith(".pdf")
    )
    total = len(pdf_files)
    print(f"Compressing {total} PDFs at JPEG quality {JPEG_QUALITY}, {DPI} DPI")
    print(f"Only replacing when compressed version is smaller.")
    print(f"Directory: {PDF_DIR}\n")

    total_old = 0
    total_new = 0
    compressed_count = 0
    kept_count = 0
    failed = []

    for i, fname in enumerate(pdf_files, 1):
        filepath = os.path.join(PDF_DIR, fname)
        status, old_sz, new_sz = compress_pdf(filepath)

        total_old += old_sz
        total_new += new_sz

        if status == "compressed":
            compressed_count += 1
            ratio = new_sz / old_sz * 100 if old_sz > 0 else 100
            print(
                f"[{i}/{total}] COMPRESSED: {fname[:55]}... "
                f"{old_sz // 1024}KB -> {new_sz // 1024}KB ({ratio:.0f}%)"
            )
        elif status == "kept_original":
            kept_count += 1
            print(f"[{i}/{total}] KEPT: {fname[:55]}... ({old_sz // 1024}KB)")
        else:
            failed.append(fname)
            print(f"[{i}/{total}] ERROR: {fname}")

        sys.stdout.flush()

    print(f"\n=== DONE ===")
    print(f"Total: {total_old / 1024 / 1024:.0f}MB -> {total_new / 1024 / 1024:.0f}MB")
    print(f"Saved: {(total_old - total_new) / 1024 / 1024:.0f}MB")
    print(f"Compressed: {compressed_count}, Kept original: {kept_count}")
    if failed:
        print(f"Failed: {len(failed)} files")
        for f in failed:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
