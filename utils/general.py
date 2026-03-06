from fastapi import Response, UploadFile
from datetime import datetime
import os
import pytz

MAX_RAG_INPUT_CONTEXT=os.getenv("MAX_RAG_INPUT_CONTEXT", 780882)

# Fungsi untuk mendapatkan waktu saat ini dalam format Y-m-d H:i:s
def getCurrentDateTime() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Fungsi untuk mendapatkan waktu saat ini dalam format Y-m-d
def getCurrentDate() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def directLink(linkDirect):
    response = Response(status_code=302)
    response.headers["Location"] = linkDirect 
    return response

def convertStringDateTimeToDateTime(datetimeInput):
    input_time = datetime.strptime(str(datetimeInput), "%Y-%m-%d %H:%M:%S")

    input_time_str_formatted = input_time.strftime("%Y-%m-%d %H:%M:%S")

    return input_time_str_formatted

def utcToLocal(utc_dt):
    utc_datetime = datetime.strptime(utc_dt, '%Y-%m-%d %H:%M:%S')
    utc_zone = pytz.utc
    local_zone = pytz.timezone('Asia/Jakarta')
    local_datetime = utc_zone.localize(utc_datetime).astimezone(local_zone)
    
    return local_datetime

def is_pdf(file: UploadFile):
    if not file.filename.lower().endswith(".pdf"):
        return False
    if file.content_type != "application/pdf":
        return False
    return True

def truncate_text(text: str, max_length: int = int(MAX_RAG_INPUT_CONTEXT), marker: str = "... [KONTEN REFERENSI TERPOTONG KARENA TERLALU PANJANG] ...") -> str:
    """
    Memotong teks di bagian tengah jika melebihi panjang maksimum.

    Args:
        text: String input yang akan dipotong.
        max_length: Panjang maksimum yang diizinkan untuk string.
        marker: String yang akan disisipkan di tengah teks yang dipotong.

    Returns:
        String yang telah dipotong, atau string asli jika panjangnya tidak melebihi batas.
    """
    if len(text.split()) <= max_length:
        return text

    # Menggunakan integer division (//) yang setara dengan Math.floor()
    half = max_length // 2
    
    # Menggunakan f-string untuk interpolasi dan slicing untuk memotong string
    return f"{text[:half]}\n\n{marker}\n\n{text[-half:]}"