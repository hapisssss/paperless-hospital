import os
import json
import types
import fitz  # PyMuPDF
import numpy as np
from google import genai
from google.genai import types
from typing import List, Dict, Any
from collections import defaultdict
import logging
import chromadb
from services.extraction import extract_structured_pdf

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# The genai library will automatically use the project and location from the environment
# when making calls, assuming the environment is set up correctly (e.g., via gcloud auth).
# We'll assume the environment variables are loaded from the main application entry point.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-004")
client = genai.Client(
    vertexai=True,
    project="diarization-ai",
    location="us-central1",
)

class RagEngine:
    def __init__(self, db_path: str, collection_name: str = "rag_index"):
        self.embedding_model = EMBEDDING_MODEL
        
        # Initialize ChromaDB client
        self.chroma_client = chromadb.PersistentClient(path=db_path)
        self.collection = self.chroma_client.get_or_create_collection(name=collection_name)

    def _chunk_text(self, text: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> List[str]:
        """Splits text into overlapping chunks."""
        if not text:
            return []
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - chunk_overlap
        return chunks

    def _process_pdf(self, file_path: str) -> str:
        """
        Extracts structured text and table data from a PDF using the advanced
        extraction service and formats it into a single string.
        """
        logger.info(f"Processing PDF with advanced extraction: {file_path}")
        try:
            structured_data = extract_structured_pdf(file_path)
            if not structured_data:
                logger.warning(f"Advanced extraction returned no data for {file_path}.")
                return ""

            full_text = []
            for page_data in structured_data:
                page_num = page_data.get("page", "N/A")
                full_text.append(f"\n--- Page {page_num} ---\n")
                
                content_blocks = page_data.get("content", [])
                for block in content_blocks:
                    block_type = block.get("type", "unknown")
                    content = block.get("content", "")
                    
                    if block_type == "table":
                        full_text.append("\n[TABLE START]\n")
                        full_text.append(content)
                        full_text.append("\n[TABLE END]\n")
                    else: # text
                        full_text.append(content)
                full_text.append("\n")

            return "\n".join(full_text)
        except Exception as e:
            logger.error(f"Error during advanced PDF processing for {file_path}: {e}")
            return ""

    def create_index(self, pdf_files: List[str]):
        """
        Creates and saves a searchable index from a list of PDF file paths into ChromaDB.
        Handles embedding limits by batching requests.
        """
        logger.info("Starting to create RAG index in ChromaDB...")
        
        if not pdf_files:
            logger.warning("No PDF files provided to index.")
            return {"message": "No PDF files found to index."}

        all_chunks = []
        indexed_files = []
        for file_path in pdf_files:
            file_name = os.path.basename(file_path)
            logger.info(f"Processing file: {file_path}")
            text = self._process_pdf(file_path)
            
            chunks = self._chunk_text(text)
            
            if not chunks:
                logger.warning(f"No text extracted from {file_name}. Skipping.")
                continue

            indexed_files.append(file_name)
            for i, chunk_text in enumerate(chunks):
                all_chunks.append({
                    "text": chunk_text,
                    "source": file_name,
                    "chunk_id": i
                })

        if not all_chunks:
            logger.error("No text could be extracted from the provided PDF files.")
            return {"message": "Failed to extract any text from the PDF files."}

        logger.info(f"Generating embeddings for {len(all_chunks)} chunks...")
        
        batch_size = 250
        all_embeddings = []
        try:
            for i in range(0, len(all_chunks), batch_size):
                batch_chunks = all_chunks[i:i + batch_size]
                batch_texts = [chunk["text"] for chunk in batch_chunks]
                
                logger.info(f"Processing batch {i//batch_size + 1}/{len(all_chunks)//batch_size + 1} with {len(batch_texts)} chunks.")

                result = client.models.embed_content(
                    model=f"gemini-embedding-001",
                    contents=batch_texts,
                    config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
                )
                all_embeddings.extend(result.embeddings)
        except Exception as e:
            logger.error(f"Failed to generate embeddings for a batch: {e}")
            return {"message": f"Error during embedding generation: {e}"}

        if len(all_embeddings) != len(all_chunks):
            logger.error("Mismatch between number of chunks and embeddings generated.")
            return {"message": "Failed to generate embeddings for all chunks due to a mismatch."}

        logger.info(f"Adding {len(all_chunks)} documents to ChromaDB collection '{self.collection.name}'...")
        try:
            # Prepare data for ChromaDB
            documents_to_add = [chunk['text'] for chunk in all_chunks]
            metadatas_to_add = [{'source': chunk['source'], 'chunk_id': str(chunk['chunk_id'])} for chunk in all_chunks]
            ids_to_add = [f"{chunk['source']}-{chunk['chunk_id']}-{i}" for i, chunk in enumerate(all_chunks)]
            embeddings_to_add = [emb.values for emb in all_embeddings]

            self.collection.add(
                embeddings=embeddings_to_add,
                documents=documents_to_add,
                metadatas=metadatas_to_add,
                ids=ids_to_add
            )
        except Exception as e:
            logger.error(f"Failed to add documents to ChromaDB: {e}")
            return {"message": f"Error during adding to ChromaDB: {e}"}
            
        logger.info("Index creation in ChromaDB complete.")
        return {"message": "Index created successfully in ChromaDB.", "indexed_files": indexed_files, "total_chunks": len(all_chunks)}

    def get_indexed_metadata(self, include_documents: bool = False):
        """
        Retrieves metadata and optionally the document content from ChromaDB.
        """
        logger.info(f"Fetching data from ChromaDB collection '{self.collection.name}'")
        
        include_payload = ["metadatas"]
        if include_documents:
            include_payload.append("documents")

        try:
            results = self.collection.get(include=include_payload)
            
            if not results or not results['ids']:
                return {"message": "No documents have been indexed yet.", "files": []}

            documents_map = {}
            if include_documents and results.get('documents'):
                documents_map = dict(zip(results['ids'], results['documents']))

            indexed_files = defaultdict(lambda: {'chunks_indexed': 0, 'documents': []})
            
            for i, meta in enumerate(results['metadatas']):
                source = meta.get('source', 'unknown_source')
                doc_id = results['ids'][i]

                indexed_files[source]['chunks_indexed'] += 1
                
                if include_documents:
                    chunk_content = documents_map.get(doc_id, "[Content not found]")
                    indexed_files[source]['documents'].append({
                        'chunk_id': meta.get('chunk_id', 'N/A'),
                        'content': chunk_content
                    })

            summary = []
            for filename, data in indexed_files.items():
                file_summary = {
                    "filename": filename, 
                    "chunks_indexed": data['chunks_indexed']
                }
                if include_documents:
                    file_summary['documents'] = data['documents']
                summary.append(file_summary)

            return {
                "message": f"Found metadata for {len(summary)} files.",
                "total_chunks": len(results['ids']),
                "files": sorted(summary, key=lambda x: x['filename'])
            }
        except Exception as e:
            logger.error(f"Failed to retrieve metadata from ChromaDB: {e}")
            raise Exception(f"An error occurred while fetching index metadata: {str(e)}")

    def query(self, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Queries the RAG engine using ChromaDB to get relevant context."""
        logger.info(f"Performing query via ChromaDB: '{query_text}'")
        
        if self.collection.count() == 0:
            logger.warning("ChromaDB collection is empty. Cannot perform query.")
            return []

        try:
            query_result = client.models.embed_content(
                model=f"gemini-embedding-001",
                contents=[query_text],
                config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY")
            )
            query_embedding = query_result.embeddings[0].values
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            raise
            
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, self.collection.count()) # Ensure n_results is not greater than the number of items
            )
        except Exception as e:
            logger.error(f"Failed to query ChromaDB: {e}")
            return []

        similar_chunks = []
        if results and results['documents']:
            documents = results['documents'][0]
            metadatas = results['metadatas'][0]
            for doc, meta in zip(documents, metadatas):
                similar_chunks.append({
                    'text': doc,
                    'source': meta.get('source', 'unknown')
                })
        
        logger.info(f"Found {len(similar_chunks)} relevant chunks from ChromaDB.")
        return similar_chunks

    def generatePromptVerifikasiKlaimBpjs(self, context: str = "", query_text: str = ""):
        """
            Menggabungkan prompt dan konteks untuk analisis klaim BPJS.
        """

        prompt_template = f"""
Anda adalah asisten AI yang ahli dalam menganalisis dokumen klaim BPJS dan memverifikasi administrasi klaim. Tugas Anda adalah memeriksa setiap halaman dokumen klaim, menganalisisnya secara mendalam, dan memberikan rekomendasi yang akurat. **Diagnosis utama pada ICD-10 menjadi acuan utama dalam semua pemeriksaan Anda.** Anda harus menjawab secara **konsisten** untuk setiap klaim yang diberikan.

Berikut adalah panduan dan kriteria analisis yang harus Anda ikuti:

### 1. Verifikasi Prosedur dan Kesesuaian Klaim:
- Periksa apakah prosedur dan pemeriksaan medis yang diajukan sesuai dengan ketentuan BPJS Kesehatan.
- Identifikasi dan analisis ketidaksesuaian dalam klaim (dokumen, prosedur, cakupan layanan).
- Berikan rekomendasi perbaikan yang diperlukan berdasarkan **kode ICD-10 (diagnosis)** dan **ICD-9-CM (prosedur)** agar klaim sesuai.
- Jika kode ICD tertentu memerlukan dokumen penunjang, sebutkan secara spesifik dokumen apa yang harus dilengkapi.
- Analisis diagnosis utama dan tindakan untuk dijadikan kode ICD-10 dan ICD-9 jika tidak ditemukan.

### 2. Pemeriksaan Akurasi Klaim Klinis dan Administratif:
- **Lama Rawat Inap:** Bandingkan lama rawat inap dengan diagnosis dan prosedur. Apakah wajar dan sesuai standar klinis?
- **Tingkat Layanan:** Apakah pasien dirawat di tingkat layanan yang lebih tinggi dari yang dibutuhkan?
- **Justifikasi Medis:** Apakah ada perpanjangan masa rawat inap tanpa justifikasi medis yang jelas dalam rekam medis?
- **Kesesuaian Kode:** Apakah pengkodean diagnosis dan prosedur sesuai dengan pedoman ICD-10 dan ICD-9-CM versi terbaru BPJS Kesehatan?
- **Pedoman Khusus:** Periksa apakah ada Berita Acara Kesepakatan (BAK) atau pedoman khusus dari BPJS yang relevan. Apakah klaim mematuhinya?
- **Kompetensi FKTP:** Apakah ada kode diagnosis atau prosedur yang seharusnya menjadi kompetensi Fasilitas Kesehatan Tingkat Pertama (FKTP)?
- **Kombinasi Kode Tidak Biasa:** Identifikasi kombinasi kode diagnosis dan prosedur yang tidak biasa. Apakah kombinasi ini dapat dijelaskan secara medis?
- **Potensi Upcoding:** Apakah ada pola klaim dari dokter/unit tertentu yang menunjukkan potensi _upcoding_ (menggunakan kode tarif lebih tinggi)?
- **Perbandingan Biaya:** Bandingkan biaya klaim dengan biaya rata-rata kasus serupa. Apakah ada perbedaan signifikan?
- **Kunjungan Berulang:** Apakah kunjungan kontrol ulang dikodekan sebagai kunjungan pertama?
- **Diagnosis Komplikasi:** Apakah ada klaim untuk hipertensi dengan komplikasi padahal catatan medis hanya menunjukkan hipertensi esensial tanpa komplikasi?
- **Kombinasi Kode Tepat:** Apakah ada klaim terpisah untuk pneumonia dan PPOK, padahal ada kode kombinasi yang lebih tepat (J44.0)?
- **Prosedur Berbiaya Tinggi:** Apakah ada klaim prosedur berbiaya tinggi untuk kondisi yang biasanya memerlukan perawatan kurang intensif?

### 3. Kelengkapan dan Analisis Berkas:
- **Kelengkapan Halaman:** Periksa setiap halaman berkas. Tandai sebagai **"berkas tidak lengkap"** jika ada halaman tanpa isi pemeriksaan medis.
- **Kebutuhan Dokumen Penunjang:** Berdasarkan diagnosis pasien, periksa apakah rekam medis memerlukan dokumen penunjang (Laboratorium, Radiologi, dll.).
- **Dokumen yang Diperlukan BPJS:** Verifikasi kelengkapan dokumen yang biasa diminta BPJS, meliputi:
    - SEP (Surat Eligibilitas Peserta)
    - Resume Medis
    - Diagnosa dan Tindakan
    - SOAP (Subjektif, Objektif, Asesmen, Plan)
    - Billing
    - Triase (pastikan pasien dari IGD terlebih dahulu, jika dari IGD maka document ini wajib ada)
    - Hasil Penunjang (Radiologi, Fisioterapi, Laboratorium, dll. pastikan analisis sesuai dengan diagnosis utama yang mewajibkan penunjang tertentu)
    - Billing INACBG
    - Laporan Operasi (jika pasien dioperasi selama perawatan maka dokumen ini wajib ada)
- **Status Pasien:** Periksa apakah pasien rawat jalan atau rawat inap dan sesuaikan dengan regulasi yang berlaku.

### 4. Analisis Berdasarkan Aturan:
- Analisis klaim berdasarkan **aturan klinis**, **Berita Acara Kesepakatan (BAK)**, **Permenkes**, dan **panduan coding medis**.

### Output:
Berdasarkan konteks dokumen internal di bawah ini, berikan analisis yang terstruktur, akurat, dan **konsisten**. Jika informasi tidak ditemukan dalam konteks anda dapat mengombinasikan dengan informasi yang kamu punya dan valid, jika tidak ada maka nyatakan dengan jelas bahwa informasi tersebut tidak ada.

Berikut konteks dokumen:
{context}

Pertanyaan pengguna:
{query_text}

Buat analisis yang terstruktur, akurat dan konsisten.
"""
        return prompt_template
