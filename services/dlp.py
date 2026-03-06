import pymupdf as fitz  # PyMuPDF
import re
import os

from services import logging

# ========= POLA REGEX INFORMASI SENSITIF =========
sensitive_patterns = [
    r'\b[\w\.-]+@[\w\.-]+\.\w{2,4}\b',               # Email
    r'\b08\d{8,13}\b',                               # No HP
    r'\b\d{16}\b',                                   # NIK (juga bisa STR dokter)
    r'\b\d{13}\b',                                   # No Peserta BPJS
    r'\b\d{4}-\d{2}-\d{2}\b',                        # Tanggal lahir (yyyy-mm-dd)
    r'\b\d{2}-\d{2}-\d{4}\b',                        # Tanggal lahir (dd-mm-yyyy)
    r'\b\d{4}/\d{2}/\d{2}/\d{6}\b',                  # No Rawat (YYYY/MM/DD/XXXXXX)
    r'\b\d{6}\b',                                    # No RM (bisa angka 6 digit lainnya juga)
    r'\bdr\.?\s?[A-Z][a-z]+(?:\s[A-Z][a-z]+)?\b',    # Nama dokter
]

# ========= FUNGSI PENCARIAN =========
def is_sensitive(text):
    return any(re.search(pattern, text) for pattern in sensitive_patterns)

# ========= FUNGSI UTAMA UNTUK SENSOR PDF =========
def sensor_pdf(input_path, output_path="output_disensor.pdf"):
    if not os.path.exists(input_path):
        print(f"❌ File tidak ditemukan: {input_path}")
        return

    doc = fitz.open(input_path)
    total_sensored = 0

    for page_num, page in enumerate(doc, 1):
        words = page.get_text("words")
        for w in words:
            x0, y0, x1, y1, word = w[:5]
            if is_sensitive(word):
                rect = fitz.Rect(x0, y0, x1, y1)
                page.draw_rect(rect, color=(0, 0, 0), fill=(0, 0, 0))
                total_sensored += 1
        print(f"✅ Halaman {page_num} selesai, {total_sensored} total bagian disensor")

    doc.save(output_path)
    doc.close()
    print(f"🎉 File berhasil disensor dan disimpan sebagai: {output_path}")

