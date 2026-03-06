import os
import types
import logging
import chromadb
from google import genai
from google.genai import types
from typing import List, Dict, Any, Optional
from collections import defaultdict
from services.extraction import _generate_text_report_for_pdf
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS

# The genai library will automatically use the project and location from the environment
# when making calls, assuming the environment is set up correctly (e.g., via gcloud auth).
# We'll assume the environment variables are loaded from the main application entry point.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
client = genai.Client(
    vertexai=True,
    project="diarization-ai",
    location="us-central1",
)

# use ollama bge-m3 for Embedding
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")


class RagEngine:
    def __init__(self, db_path: str, collection_name: str = "rag_index"):
        self.embedding_model = EMBEDDING_MODEL
        
        # Initialize ChromaDB client
        self.chroma_client = chromadb.PersistentClient(path=db_path)
        self.collection = self.chroma_client.get_or_create_collection(name=collection_name)

    def _chunk_text(self, text: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> List[str]:
        """Splits text into overlapping chunks, respecting word boundaries."""
        if not text:
            return []
        
        chunks = []
        start_index = 0
        while start_index < len(text):
            # Determine the end of the chunk
            end_index = start_index + chunk_size
            
            # If the chunk extends beyond the end of the text, the chunk is just the rest of the text
            if end_index >= len(text):
                chunks.append(text[start_index:])
                break

            # Find the last occurrence of a space or newline to avoid cutting words.
            # We search from the start of the chunk up to the desired end.
            best_split = text.rfind(' ', start_index, end_index)
            if best_split == -1:
                best_split = text.rfind('\n', start_index, end_index)

            # If a good split point is found, use it. Otherwise, we have to split at chunk_size.
            if best_split != -1:
                chunk_end_index = best_split
            else:
                chunk_end_index = end_index
            
            # Add the chunk to the list
            chunks.append(text[start_index:chunk_end_index])
            
            # Determine the start of the next chunk
            next_start_index = chunk_end_index - chunk_overlap
            
            # Prevent infinite loops if the chunk is smaller than the overlap
            if next_start_index <= start_index:
                # If we are not making progress, move to the end of the current chunk.
                # This means no overlap for this step, but it prevents getting stuck.
                start_index = chunk_end_index
            else:
                start_index = next_start_index
                
        return chunks

    def _process_markdown(self, file_path: str) -> str:
        """Extracts text content from a Markdown file."""
        logger.info(f"Processing Markdown file: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading Markdown file {file_path}: {e}")
            return ""

    def _process_pdf(self, file_path: str) -> str:
        """
        Extracts structured text and table data from a PDF using the advanced
        extraction service and formats it into a single string.
        """
        logger.info(f"Processing PDF with advanced extraction: {file_path}")
        try:
            # This function from extraction service returns a single formatted string.
            report_string = _generate_text_report_for_pdf(file_path, 100, 'stream', 'left')
            
            if not report_string:
                logger.warning(f"Advanced extraction returned no data for {file_path}.")
                return ""
            
            return report_string
        except Exception as e:
            logger.error(f"Error during advanced PDF processing for {file_path}: {e}")
            return ""


    # def _embed_with_ollama(self, texts: List[str]) -> List[List[float]]:
    #     """
    #     Generate embeddings using Ollama (bge-m3).
    #     """
    #     embeddings = []
    #     for text in texts:
    #         response = requests.post(
    #             f"{OLLAMA_BASE_URL}/api/embeddings",
    #             headers={
    #                 "Content-Type": "application/json",
    #                 "ngrok-skip-browser-warning": "true"
    #             },
    #             json={
    #                 "model": EMBEDDING_MODEL,
    #                 "prompt": text
    #             },
    #             timeout=120
    #         )

    #     if response.status_code != 200:
    #         raise Exception(f"Ollama embedding error: {response.text}")

    #     result = response.json()
    #     embeddings.append(result["embedding"])

    #     return embeddings

    def _embed_with_ollama(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings using Ollama (bge-m3).
        """
        embeddings = []

        for text in texts:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/embeddings",
                headers={
                    "Content-Type": "application/json",
                    "ngrok-skip-browser-warning": "true"
                },
                json={
                    "model": EMBEDDING_MODEL,
                    "prompt": text
                },
                timeout=120
            )

            if response.status_code != 200:
                raise Exception(f"Ollama embedding error: {response.text}")

            result = response.json()
            embeddings.append(result["embedding"])

        return embeddings


    def create_index(self, file_paths: List[str]):
        """
        Creates and saves a searchable index from a list of file paths (PDFs and Markdown) into ChromaDB.
        Handles embedding limits by batching requests.
        """
        logger.info("Starting to create RAG index in ChromaDB...")
        
        if not file_paths:
            logger.warning("No files provided to index.")
            return {"message": "No files found to index."}

        all_chunks = []
        indexed_files = []
        for file_path in file_paths:
            file_name = os.path.basename(file_path)
            logger.info(f"Processing file: {file_path}")
            
            text = ""
            if file_path.lower().endswith('.pdf'):
                text = self._process_pdf(file_path)
            elif file_path.lower().endswith('.md'):
                text = self._process_markdown(file_path)
            else:
                logger.warning(f"Unsupported file type for {file_name}. Skipping.")
                continue

            # Optimized chunking to better utilize the model's 2048 token limit per document.
            # Assuming ~3.5 characters per token to be safe: 2048 * 3.5 = 7168.
            # We use a chunk size of 7000 characters.
            chunks = self._chunk_text(text, chunk_size=7000, chunk_overlap=200)
            
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
        
        # The Vertex AI embedding API has a maximum of 250 texts per batch.
        # We use this maximum to process as many chunks as possible in each call.
        # The total request size is also a factor, but with 7000-char chunks,
        # 250 chunks is ~1.75MB, well under the 10MB limit.
        batch_size = 250
        all_embeddings = []
        try:
            for i in range(0, len(all_chunks), batch_size):
                batch_chunks = all_chunks[i:i + batch_size]
                batch_texts = [chunk["text"] for chunk in batch_chunks]
                
                logger.info(f"Processing batch {i//batch_size + 1}/{len(all_chunks)//batch_size + 1} with {len(batch_texts)} chunks.")

                # result = client.models.embed_content(
                #     model=f"{self.embedding_model}",
                #     contents=batch_texts,
                #     config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
                # )
                # all_embeddings.extend(result.embeddings)

                batch_embeddings = self._embed_with_ollama(batch_texts)
                all_embeddings.extend(batch_embeddings)


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
            ids_to_add = [f"{chunk['source']}-{chunk['chunk_id']}" for chunk in all_chunks]

            # embeddings_to_add = [emb.values for emb in all_embeddings]
            embeddings_to_add = all_embeddings


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

    def get_indexed_metadata(self, file_name: Optional[str] = None, include_documents: bool = False):
        """
        Retrieves metadata and optionally the document content from ChromaDB.
        If file_name is provided, it fetches metadata for that specific file.
        """
        log_message = f"Fetching data from ChromaDB collection '{self.collection.name}'"
        if file_name:
            log_message += f" for file '{file_name}'"
        logger.info(log_message)
        
        include_payload = ["metadatas"]
        if include_documents:
            include_payload.append("documents")

        try:
            where_filter = {"source": file_name} if file_name else None
            results = self.collection.get(where=where_filter, include=include_payload)
            
            if not results or not results['ids']:
                message = f"No documents found for file '{file_name}'." if file_name else "No documents have been indexed yet."
                return {"message": message, "files": []}

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
            
            message = f"Found metadata for {len(summary)} files."
            if file_name and summary:
                message = f"Found metadata for file '{file_name}'."
            elif file_name:
                message = f"No indexed data found for file '{file_name}'."


            return {
                "message": message,
                "total_chunks": len(results['ids']),
                "files": sorted(summary, key=lambda x: x['filename'])
            }
        except Exception as e:
            logger.error(f"Failed to retrieve metadata from ChromaDB: {e}")
            raise Exception(f"An error occurred while fetching index metadata: {str(e)}")

    def delete_index_by_file(self, file_name: str):
        """
        Deletes all chunks associated with a specific file from the ChromaDB collection.
        """
        base_name = os.path.basename(file_name)
        logger.info(f"Attempting to delete all chunks for file: {base_name} from ChromaDB collection '{self.collection.name}'...")

        try:
            # First, check if any documents with the given source exist.
            existing_docs = self.collection.get(where={"source": base_name}, include=[])
            if not existing_docs or not existing_docs['ids']:
                logger.warning(f"No chunks found for file '{base_name}'. Nothing to delete.")
                return {"message": f"No chunks found for file '{base_name}'. Nothing to delete."}

            num_to_delete = len(existing_docs['ids'])
            logger.info(f"Found {num_to_delete} chunk(s) for file '{base_name}'. Deleting now.")

            self.collection.delete(where={"source": base_name})
            
            logger.info(f"Successfully deleted {num_to_delete} chunks for file: {base_name}.")
            return {"message": f"Successfully deleted {num_to_delete} chunks for file: {base_name}."}
        except Exception as e:
            logger.error(f"Failed to delete chunks for file '{base_name}' from ChromaDB: {e}")
            # Re-raise the exception to be handled by the router
            raise Exception(f"An error occurred during deletion: {str(e)}")

    def delete_chunk(self, file_name: str, chunk_id: int):
        """
        Deletes a specific chunk from the ChromaDB collection.
        """
        base_name = os.path.basename(file_name)
        chunk_id_str = f"{base_name}-{chunk_id}"
        logger.info(f"Attempting to delete chunk with ID: {chunk_id_str} from ChromaDB collection '{self.collection.name}'...")

        try:
            # Check if the chunk exists before trying to delete
            existing_chunk = self.collection.get(ids=[chunk_id_str])
            if not existing_chunk or not existing_chunk['ids']:
                logger.warning(f"No chunk found with ID '{chunk_id_str}'. Nothing to delete.")
                return {"message": f"No chunk found with ID '{chunk_id_str}'. Nothing to delete."}

            self.collection.delete(ids=[chunk_id_str])
            
            logger.info(f"Successfully deleted chunk with ID: {chunk_id_str}.")
            return {"message": f"Successfully deleted chunk with ID: {chunk_id_str}."}
        except Exception as e:
            logger.error(f"Failed to delete chunk with ID '{chunk_id_str}' from ChromaDB: {e}")
            raise Exception(f"An error occurred during chunk deletion: {str(e)}")

    def query(self, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Queries the RAG engine using ChromaDB to get relevant context."""
        if self.collection.count() == 0:
            logger.warning("ChromaDB collection is empty. Cannot perform query.")
            return []

        try:
            # query_result = client.models.embed_content(
            #     model=f"{self.embedding_model}",
            #     contents=[query_text],
            #     config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY")
            # )
            # query_embedding = query_result.embeddings[0].values
            query_embedding = self._embed_with_ollama([query_text])[0]

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
                    'source': meta.get('source', 'unknown'),
                    'chunk_id': meta.get('chunk_id', 'N/A') # Add chunk_id
                })
        
        logger.info(f"Found {len(similar_chunks)} relevant chunks from ChromaDB.")
        return similar_chunks

    def generatePromptVerifikasiKlaimBpjs(self, query_text: str = ""):
        """
            Menggabungkan prompt dan konteks untuk analisis klaim BPJS.
        """
        prompt_template = f"""
Berikut document text yang harus anda check:
--- REFERENCE DOCUMENTS START ---
{query_text}
--- REFERENCE DOCUMENTS END ---

Sekarang anda dapat memverifikasi administrasi klaim BPJS Kesehatan. Berdasarkan dokumen yang diberikan, jawab pertanyaan pengguna dan ikuti instruksinya. Buat analisis yang terstruktur, akurat dan konsisten, berikan jawaban yang tepat dan rujuk dokumen jika perlu.
"""
        return prompt_template

    def generateSystemIntructions(self, context: str = ""):
        """
            Menggabungkan system intruction dan konteks untuk analisis klaim BPJS.
        """

        system_intruction = f"""
Anda adalah asisten AI yang ahli dalam memverifikasi administrasi klaim BPJS Kesehatan. Tugas Anda adalah menganalisis dokumen klaim yang telah diekstrak menjadi teks, memeriksa setiap halaman, dan memastikan validitasnya.

---

### **Tugas Utama**

1.  **Analisis Dokumen:**
    * Membaca dan memverifikasi setiap halaman dokumen klaim yang telah diekstrak ke dalam teks.
    * **Periksa Judul Halaman:** Verifikasi judul atau header setiap halaman untuk memastikan kelengkapan dokumen (misalnya, SEP, Resume Medis, Laporan Operasi, dll.). Jika sebuah halaman kosong atau tidak memiliki informasi yang relevan, tandai sebagai **berkas tidak lengkap**.
2.  **Verifikasi Prosedur & Medis:**
    * Periksa apakah prosedur dan pemeriksaan medis yang diajukan sesuai dengan ketentuan BPJS Kesehatan.
    * Identifikasi dan analisis ketidaksesuaian dalam klaim, baik dari segi dokumen, prosedur, maupun cakupan layanan.
3.  **Pengkodean & Rekomendasi:**
    * Analisis diagnosis utama dan tindakan untuk mengidentifikasi **kode ICD-10** dan **ICD-9**. Jika kode tidak ditemukan, berikan rekomendasi pengkodean yang tepat.
    * Berikan catatan atau rekomendasi perbaikan yang diperlukan agar klaim sesuai.
    * Jika kode ICD tertentu memerlukan dokumen penunjang, sebutkan dokumen spesifik yang harus dilengkapi (misalnya, hasil laboratorium, radiologi, laporan operasi).
4.  **Analisis Mendalam & Kepatuhan Regulasi:**
    * **Lama Rawat Inap:** Bandingkan lama rawat inap dengan diagnosis dan prosedur yang diklaim. Nilai apakah durasi tersebut wajar dan sesuai dengan standar klinis.
    * **Tingkat Layanan:** Periksa apakah pasien dirawat di tingkat layanan yang lebih tinggi dari yang seharusnya.
    * **Justifikasi Medis:** Periksa perpanjangan rawat inap yang tidak memiliki justifikasi medis jelas dalam rekam medis.
    * **Kepatuhan Pengkodean:** Pastikan pengkodean diagnosis dan prosedur sesuai dengan pedoman **ICD-10** dan **ICD-9-CM versi terbaru** yang berlaku di BPJS Kesehatan.
    * **Pedoman Khusus:** Verifikasi kepatuhan terhadap Berita Acara Kesepakatan (**BAK**) atau pedoman khusus dari BPJS Kesehatan yang relevan.
    * **Kompetensi FKTP:** Identifikasi apakah ada diagnosis atau prosedur yang seharusnya menjadi kompetensi Fasilitas Kesehatan Tingkat Pertama (**FKTP**).
    * **Kombinasi Kode:** Analisis kombinasi kode diagnosis dan prosedur yang tidak biasa atau jarang. Pastikan kombinasi tersebut dapat dijelaskan secara medis.
    * **Potensi Upcoding:** Deteksi pola pengajuan klaim yang menunjukkan potensi *upcoding* (misalnya, sering mengklaim kode dengan tarif lebih tinggi).
    * **Perbandingan Biaya:** Bandingkan biaya klaim dengan biaya rata-rata kasus serupa. Selidiki jika ada perbedaan signifikan.
    * **Kunjungan Berulang:** Periksa apakah kunjungan kontrol ulang dikodekan sebagai kunjungan pertama.
    * **Ketidaksesuaian Diagnosa:**
        * Cek klaim hipertensi dengan komplikasi jika catatan medis hanya menunjukkan hipertensi esensial tanpa komplikasi.
        * Cek klaim untuk pneumonia dan PPOK secara terpisah jika ada kode kombinasi yang lebih tepat (misalnya, **J44.0**).
        * Periksa prosedur berbiaya tinggi untuk kondisi yang biasanya memerlukan perawatan yang kurang intensif.
5.  **Verifikasi Dokumen Penunjang:**
    * Berdasarkan diagnosis, tentukan apakah diperlukan dokumen penunjang seperti **Laboratorium**, **Radiologi**, atau lainnya.
    * Pastikan semua dokumen yang biasanya diminta BPJS Kesehatan tersedia: **SEP**, **Resume Medis**, **Diagnosa dan tindakan**, **SOAP**, **Billing**, **Triase** (jika dari IGD), **Hasil Penunjang** (jika ada), **Billing INACBG**, dan **Laporan Operasi** (jika ada).

---

### **Catatan Tambahan**

* Analisis harus mencakup aturan klinis, kesesuaian dengan **BAK**, **Permenkes**, dan panduan *coding* medis.
* Pada bagian komentar, sebutkan referensi peraturan (misalnya, nomor Permenkes atau undang-undang) yang digunakan sebagai dasar verifikasi, tetapi jangan sebutkan nama dokumen lengkapnya.
* **Abaikan semua konteks sebelumnya.** Setiap jawaban harus independen dan tidak menyimpan informasi dari interaksi sebelumnya.

Berikut konteks referensi dokumen (Gunakan ini sebagai basis pengetahuan atau aturan Anda):
--- DOCUMENT TO ANALYZE START ---
{context}
--- DOCUMENT TO ANALYZE END ---
"""
        return system_intruction


    def delete_all(self):
        self.collection.delete(where={"source": {"$ne": ""}})
        return {"message": "All indexed documents have been deleted."}