import os
import pdfplumber
import camelot
import pandas as pd
import pytesseract
from typing import List

# ==============================================================================
# --- KONFIGURASI UTAMA ---
#
# VVV UBAH TIGA BARIS DI BAWAH INI SESUAI KOMPUTER ANDA VVV
#
# 1. Path ke Tesseract-OCR executable
pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_EXECUTABLE")
# ==============================================================================

# ==============================================================================
# DEFINISI FUNGSI INTI
# ==============================================================================

def _generate_text_report_for_pdf(pdf_path: str, ocr_threshold: int, flavor: str, alignment: str) -> str:
    """Fungsi internal untuk memproses satu file PDF dan mengembalikan laporannya sebagai string."""
    report_lines: List[str] = []
    file_name = os.path.basename(pdf_path)
    
    report_lines.append(f"# Laporan Ekstraksi Dokumen: {file_name}")
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            report_lines.append(f"\n**Total Halaman:** {total_pages}\n")
            
            for i, page in enumerate(pdf.pages):
                page_num = i + 1
                report_lines.append(f"\n---\n\n## Halaman {page_num}\n")
                
                base_text = page.extract_text(x_tolerance=2) or ""
                
                if len(base_text.strip()) < ocr_threshold:
                    report_lines.append("**Tipe Ekstraksi:** OCR\n")
                    try:
                        page_image = page.to_image(resolution=300).original
                        ocr_text = pytesseract.image_to_string(page_image, lang='ind')
                        report_lines.append("```text\n" + ocr_text.strip() + "\n```")
                    except Exception as e:
                        report_lines.append(f"**Gagal OCR:** `{e}`")
                else:
                    report_lines.append("**Tipe Ekstraksi:** Digital\n")
                    report_lines.append(base_text.strip())
                    try:
                        camelot_tables = camelot.read_pdf(pdf_path, pages=str(page_num), flavor=flavor, suppress_stdout=True)
                        if camelot_tables.n > 0:
                            report_lines.append("\n\n### Tabel Ditemukan\n")
                            for table_index, table in enumerate(camelot_tables):
                                table_string = table.df.to_string(justify=alignment)
                                report_lines.append(f"**Tabel {table_index + 1}:**\n```\n{table_string}\n```")
                    except Exception as e:
                        print(f"   -> Peringatan: Gagal memproses tabel di halaman {page_num} file {file_name}. Error: {e}")
                
        return "\n".join(report_lines)
    except Exception as e:
        return f"# GAGAL TOTAL memproses file {file_name}\n\nError: `{e}`"

def proses_folder_pdf(
    input_folder_path: str,
    output_folder_path: str,
    ocr_threshold: int = 100,
    camelot_flavor: str = 'stream',
    table_alignment: str = 'left'
) -> str:
    """
    Memproses semua PDF, menyimpan setiap hasil ke folder output .md, dan menggabungkan semua ke satu string.
    """
    if not os.path.isdir(input_folder_path):
        error_message = f"❌ ERROR: Path folder INPUT tidak ditemukan: '{input_folder_path}'"
        print(error_message)
        return error_message

    # Gunakan path output dan buat jika belum ada ---
    os.makedirs(output_folder_path, exist_ok=True)
    print(f"File .md akan disimpan di: {output_folder_path}")
    
    pdf_files_to_process = [f for f in os.listdir(input_folder_path) if f.lower().endswith('.pdf')]

    if not pdf_files_to_process:
        warning_message = f"⚠️ Tidak ada file PDF ditemukan di folder '{input_folder_path}'."
        print(warning_message)
        return warning_message

    print(f"🚀 Memulai pemrosesan batch untuk {len(pdf_files_to_process)} file PDF...")
    
    file_reports = []
    for filename in pdf_files_to_process:
        full_path = os.path.join(input_folder_path, filename)
        print(f"\n🔄 Memproses: {filename}...")
        
        pdf_report = _generate_text_report_for_pdf(full_path, ocr_threshold, camelot_flavor, table_alignment)
        
        if pdf_report:
            file_reports.append(pdf_report)
            
            # Simpan ke folder output yang ditentukan ---
            try:
                md_filename = os.path.splitext(filename)[0] + '.md'
                md_output_path = os.path.join(output_folder_path, md_filename)
                with open(md_output_path, 'w', encoding='utf-8') as f:
                    f.write(pdf_report)
                print(f"✅ Laporan untuk '{filename}' telah disimpan ke: {md_output_path}")
            except Exception as e:
                print(f"   -> ❌ Gagal menyimpan file .md untuk '{filename}'. Error: {e}")
            
    print("\n\n🎉🎉🎉 Semua file telah berhasil diproses! 🎉🎉🎉")
    
    return "\n\n---\n\n".join(file_reports)


# ==============================================================================
# --- EKSEKUSI LANGSUNG ---
# ==============================================================================

# 1. Path ke folder yang berisi semua file PDF Anda
# PATH_FOLDER_INPUT = r"D:\QERJA\SERVICE AI\checking-klaim\input_file"

# 2. Path ke folder tempat Anda ingin menyimpan semua file .md hasil ekstraksi
# PATH_FOLDER_OUTPUT = r"D:\QERJA\SERVICE AI\checking-klaim\output_file"

# Panggil fungsi utama dengan path input dan output ---
# hasil_laporan_lengkap = proses_folder_pdf(
#     input_folder_path=PATH_FOLDER_INPUT,
#     output_folder_path=PATH_FOLDER_OUTPUT
# )

# Tampilkan hasil akhir gabungan di layar/terminal
# print("\n============================================================")
# print("HASIL AKHIR GABUNGAN (TERSIPAN DI VARIABEL DI BAWAH INI)")
# print("============================================================")
"""aktifkan dibawah ini untuk preview hasil di terminal"""
# print(hasil_laporan_lengkap)

# print("\n\n✅ Proses Selesai. Hasil gabungan kini tersedia di variabel `hasil_laporan_lengkap`.")