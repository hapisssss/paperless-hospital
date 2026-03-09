import json
import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from schemas.response import ResponseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from collections import defaultdict
from configs.db import get_db
from models.klaimBpjs import KlaimBpjs
from datetime import datetime
from schemas.klaimBpjs import RESPONSE_SCHEMA_CHECKING_CLAIM_BPJS, KliamBpjsIn, KliamBpjsOut
from sqlalchemy.exc import SQLAlchemyError
from services.rag_engine import RagEngine
from services.prompt import generate, generate_ollama
from utils.general import truncate_text
from utils.response import handleResponse, handleError

router = APIRouter()

# Define paths
CHROMA_DB_PATH = "database/chroma_db"
TEMP_UPLOAD_PATH = "documents/temp_uploads"

# Ensure directories exist
if not os.path.exists(TEMP_UPLOAD_PATH):
    os.makedirs(TEMP_UPLOAD_PATH)
if not os.path.exists(CHROMA_DB_PATH):
    os.makedirs(CHROMA_DB_PATH)

# Initialize RagEngine with ChromaDB
rag_engine = RagEngine(db_path=CHROMA_DB_PATH, collection_name="bpjs_claims_index")

class CheckClaimRequest(BaseModel):
    query: str



@router.post('/pdf-to-text', tags=["RAG Engine Management"])
async def pdf_to_text(file: UploadFile = File(...)):
    """
    Converts an uploaded PDF or Markdown document to text.
    """
    allowed_content_types = ["application/pdf", "text/markdown"]
    
    if file.content_type not in allowed_content_types:
        return handleError(code=400, message=f"Invalid file type for {file.filename}. Only PDF and Markdown are supported.")
    
    temp_file_path = os.path.join(TEMP_UPLOAD_PATH, file.filename)
    
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        return handleError(code=500, message=f"Could not save file {file.filename}: {e}")
    finally:
        file.file.close()

    try:
        result = rag_engine._process_pdf(file_path=temp_file_path)
        if not result:
            raise HTTPException(status_code=500, detail="Failed to extract text from PDF.")
            
        return handleResponse(data={"text": result}, message="PDF to Text processed successfully")
    except Exception as e:
        if isinstance(e, HTTPException):
            return handleError(code=e.status_code, message=e.detail)
        return handleError(code=500, message=str(e))
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


@router.post("/rag-engine/create-index", tags=["RAG Engine Management"])
async def create_rag_index(files: List[UploadFile] = File(...)):
    """
    Creates or updates the RAG index from one or more uploaded PDF or Markdown documents.
    This can be a a long-running process.
    """
    if not files:
        return handleError(code=400, message="No files uploaded.")

    allowed_content_types = ["application/pdf", "text/markdown"]
    temp_file_paths = []
    for file in files:
        if file.content_type not in allowed_content_types:
            for path in temp_file_paths:
                if os.path.exists(path):
                    os.remove(path)
            return handleError(code=400, message=f"Invalid file type for {file.filename}. Only PDF and Markdown are supported.")
        
        temp_file_path = os.path.join(TEMP_UPLOAD_PATH, file.filename)
        try:
            with open(temp_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            temp_file_paths.append(temp_file_path)
        except Exception as e:
            for path in temp_file_paths:
                if os.path.exists(path):
                    os.remove(path)
            return handleError(code=500, message=f"Could not save file {file.filename}: {e}")
        finally:
            file.file.close()

    try:
        result = rag_engine.create_index(file_paths=temp_file_paths)
        
        if "error" in result or "Failed" in result.get("message", ""):
            raise HTTPException(status_code=500, detail=result.get("message", "An unknown error occurred during indexing."))
            
        return handleResponse(data=result, message="RAG index created successfully.")
    except Exception as e:
        if isinstance(e, HTTPException):
            return handleError(code=e.status_code, message=e.detail)
        return handleError(code=500, message=str(e))
    finally:
        for path in temp_file_paths:
            if os.path.exists(path):
                os.remove(path)

@router.get("/rag-engine/indexed-files", tags=["RAG Engine Management"])
async def get_indexed_files(file_name: Optional[str] = None, include_documents: bool = False):
    """
    Retrieves a list of indexed files and metadata from the RAG engine.
    
    - If `file_name` is provided, it returns metadata for that specific file.
    - `include_documents=true` will include the content of the indexed chunks.
    """
    try:
        metadata = rag_engine.get_indexed_metadata(file_name=file_name, include_documents=include_documents)
        
        if file_name and not metadata.get("files"):
            return handleError(code=404, message=f"No indexed data found for file '{file_name}'.")

        return handleResponse(data=metadata, message="Successfully retrieved indexed file metadata.")
    except Exception as e:
        if isinstance(e, HTTPException):
            return handleError(code=e.status_code, message=e.detail)
        return handleError(code=500, message=f"An internal error occurred: {str(e)}")

@router.delete("/rag-engine/delete-index/{file_name:path}", tags=["RAG Engine Management"])
async def delete_index_by_file(file_name: str):
    """
    Deletes all indexed chunks for a specific file from the RAG engine.
    """
    if not file_name:
        return handleError(code=400, message="File name cannot be empty.")

    try:
        result = rag_engine.delete_index_by_file(file_name=file_name)
        if "not found" in result.get("message", ""):
             return handleError(code=404, message=result.get("message"))
        return handleResponse(data=result, message=f"Index for file '{file_name}' deleted successfully.")
    except Exception as e:
        return handleError(code=500, message=f"An internal error occurred: {str(e)}")


@router.delete("/rag-engine/delete-chunk/{file_name:path}/{chunk_id}", tags=["RAG Engine Management"])
async def delete_chunk_by_id(file_name: str, chunk_id: int):
    """
    Deletes a specific indexed chunk for a file from the RAG engine.
    """
    if not file_name or chunk_id is None:
        return handleError(code=400, message="File name and chunk ID cannot be empty.")

    try:
        result = rag_engine.delete_chunk(file_name=file_name, chunk_id=chunk_id)
        if "not found" in result.get("message", ""):
             return handleError(code=404, message=result.get("message"))
        return handleResponse(data=result, message=f"Chunk '{chunk_id}' from file '{file_name}' deleted successfully.")
    except Exception as e:
        return handleError(code=500, message=f"An internal error occurred: {str(e)}")
    


@router.post("/check-kelengkapan-berkas", tags=["RAG Engine Query"], summary="Check kelengkapan berkas claim bpjs", description="Endpoint ini digunakan untuk mengecek kelengkapan berkas claim bpjs")
async def checkKelengkapanBerkas(payload: KliamBpjsIn, db: Session = Depends(get_db)):
    try:
        query_text_from_payload = ""
        response = ""
        if payload.result_checkup == '' or payload.result_checkup is None:
            return handleError(code=422, message='Result Checkup tidak boleh kosong', data=None)

        query_text_from_payload = payload.result_checkup

        # 1. Retrieve relevant context from RAG index
        query_text = query_text_from_payload
        relevant_chunks = rag_engine.query(query_text, top_k=7)
        if not relevant_chunks:
            return handleError(code=404, message="Could not find relevant documents in the index. The index might be empty. Please try indexing documents first.")
 
        contextQuery = "\n\n---".join([chunk['text'] for chunk in relevant_chunks])
        

        # Group relevant chunks by source file
        source_map = defaultdict(list)
        for chunk in relevant_chunks:
            source_map[chunk['source']].append({
                "chunk_id": chunk['chunk_id'],
                "content": chunk['text']
            })

        # Format for response
        source_documents = []
        for filename, chunks in source_map.items():
            source_documents.append({
                "filename": filename,
                "relevant_chunks_count": len(chunks),
                "documents": chunks
            })

        query_text_from_payload = truncate_text(query_text_from_payload)
        contextQuery = truncate_text(contextQuery)

        print("INI KONTEKSSNYA")
        print(contextQuery)
        print("INI KONTEKSNYA")


        # 2. Augment the prompt and generate the final response
        prompt = rag_engine.generatePromptVerifikasiKlaimBpjs(query_text=query_text_from_payload)
        system_intruction = rag_engine.generateSystemIntructions(context=contextQuery)
        

        # 3. Generate Answer
        response = await generate_ollama(prompt=prompt, system_instruction=system_intruction, response_schema=RESPONSE_SCHEMA_CHECKING_CLAIM_BPJS,temperature=0.1, seed=len(prompt))
        
        final_answer = response["message"]["content"]
        parsed = json.loads(final_answer) 

        return handleResponse(
            code=200,
            message='OK',
            data={
                "result": parsed,
                "debug": {
                    "prompt": prompt,
                    "system_instruction": system_intruction,
                }
            }
        )
    except SQLAlchemyError as e:
        # db.rollback()
        return handleError(code=500, message=f"Kesalahan dalam memproses data. {str(e)}", data=None)
    except Exception as e:
        return handleError(code=500, message=str(e))


@router.post("/check-kelengkapan-berkas-document", tags=["RAG Engine Query"], response_model=ResponseModel[KliamBpjsOut])
async def check_claim(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Performs a check on a claim by querying the RAG engine.
    You can provide upload a `file` (PDF) to be analyzed.
    """
    if not file:
        return handleError(code=422, message="Please provide either a text query or a file.")

    try:
        query_text_from_file = ""
        query_text = ""
        if file:
            if file.content_type != 'application/pdf':
                return handleError(code=422, message="Invalid file type. Only PDF is supported.")
            
            temp_file_path = os.path.join(TEMP_UPLOAD_PATH, file.filename)
            with open(temp_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            query_text_from_file = rag_engine._process_pdf(temp_file_path)
            
            query_text = f"Analyze and summarize the following document : \n\n{query_text_from_file}"
            
            os.remove(temp_file_path)

        # 1. Retrieve relevant context from RAG index
        relevant_chunks = rag_engine.query(query_text, top_k=7)
        if not relevant_chunks:
            return handleError(code=404, message="Could not find relevant documents in the index. The index might be empty. Please try indexing documents first.")

        contextQuery = "\n\n---".join([chunk['text'] for chunk in relevant_chunks])
        
        # Group relevant chunks by source file
        source_map = defaultdict(list)
        for chunk in relevant_chunks:
            source_map[chunk['source']].append({
                "chunk_id": chunk['chunk_id'],
                "content": chunk['text']
            })

        # Format for response
        source_documents = []
        for filename, chunks in source_map.items():
            source_documents.append({
                "filename": filename,
                "relevant_chunks_count": len(chunks),
                "documents": chunks
            })

        query_text_from_file = truncate_text(query_text_from_file)
        contextQuery = truncate_text(contextQuery)

        # 2. Augment the prompt and generate the final response
        prompt = rag_engine.generatePromptVerifikasiKlaimBpjs(query_text=query_text_from_file)
        system_intruction = rag_engine.generateSystemIntructions(context=contextQuery)

        # 3. Generate Answer
        response = await generate_ollama(prompt=prompt, system_instruction=system_intruction, response_schema=RESPONSE_SCHEMA_CHECKING_CLAIM_BPJS,temperature=0.1, seed=len(prompt))
        final_answer = response["message"]["content"]
        parsed = json.loads(final_answer)

        # Store to the Databse
        medicalScribeEntry  = KlaimBpjs(
            document_name="Direct Input",
            document_extraction=query_text_from_file,
            retrieval_content_query=json.dumps(source_documents),
            prompt=prompt,
            response=json.dumps(parsed),
            token_request=token_request,
            token_response=token_response,
            token_counts=token_counts,
            timestamp=datetime.now()
        )
        db.add(medicalScribeEntry)
        db.commit()
        db.refresh(medicalScribeEntry)       

        return handleResponse(parsed)
    except Exception as e:
        return handleError(code=500, message=f"An internal error occurred: {str(e)}")


# @router.post("/check-kelengkapan-berkas", tags=["RAG Engine Query"], summary="Check kelengkapan berkas claim bpjs", response_model=ResponseModel[KliamBpjsOut], description="Endpoint ini digunakan untuk mengecek kelengkapan berkas claim bpjs")
# async def checkKelengkapanBerkas(payload: KliamBpjsIn, db: Session = Depends(get_db)):
#     try:
#         query_text_from_payload = ""
#         response = ""
#         if payload.result_checkup == '' or payload.result_checkup is None:
#             return handleError(code=422, message='Result Checkup tidak boleh kosong', data=None)

#         query_text_from_payload = payload.result_checkup
#         # 1. Retrieve relevant context from RAG index
#         query_text = f"Analyze and summarize the following document : \n\n{query_text_from_payload}"
#         relevant_chunks = rag_engine.query(query_text, top_k=7)
#         if not relevant_chunks:
#             return handleError(code=404, message="Could not find relevant documents in the index. The index might be empty. Please try indexing documents first.")

#         contextQuery = "\n\n---".join([chunk['text'] for chunk in relevant_chunks])

#         # Group relevant chunks by source file
#         source_map = defaultdict(list)
#         for chunk in relevant_chunks:
#             source_map[chunk['source']].append({
#                 "chunk_id": chunk['chunk_id'],
#                 "content": chunk['text']
#             })

#         # Format for response
#         source_documents = []
#         for filename, chunks in source_map.items():
#             source_documents.append({
#                 "filename": filename,
#                 "relevant_chunks_count": len(chunks),
#                 "documents": chunks
#             })

#         query_text_from_payload = truncate_text(query_text_from_payload)
#         contextQuery = truncate_text(contextQuery)

#         # 2. Augment the prompt and generate the final response
#         prompt = rag_engine.generatePromptVerifikasiKlaimBpjs(query_text=query_text_from_payload)
#         system_intruction = rag_engine.generateSystemIntructions(context=contextQuery)

#         response = await generate(prompt=prompt, system_instruction=system_intruction, response_mime_type="application/json", response_schema=RESPONSE_SCHEMA_CHECKING_CLAIM_BPJS, temperature=0.0, seed=len(prompt))

#         if not response or not getattr(response, "text", "").strip():
#             response = await generate(prompt=prompt, system_instruction=system_intruction, response_mime_type="application/json", response_schema=RESPONSE_SCHEMA_CHECKING_CLAIM_BPJS, temperature=0.0, seed=len(prompt))

#             if not response or not getattr(response, "text", "").strip():
#                 return handleError(code=500, message="Gagal menganalisis data.", data=None)

#         prompt_tokens = 0
#         candidates_tokens = 0
#         total_tokens = 0

#         if hasattr(response, 'usage_metadata'):
#             prompt_tokens = response.usage_metadata.prompt_token_count
#             candidates_tokens = response.usage_metadata.candidates_token_count
#             total_tokens = response.usage_metadata.total_token_count
        
#         final_answer = response.text if hasattr(response, 'text') else str(response)

#         medicalScribeEntry = KlaimBpjs(
#             document_name="Direct Input",
#             document_extraction=query_text_from_payload,
#             retrieval_content_query=json.dumps(source_documents),
#             prompt=prompt,
#             response=final_answer,
#             token_request=prompt_tokens,
#             token_response=candidates_tokens,
#             token_counts=total_tokens,
#             timestamp=datetime.now()
#         )
#         db.add(medicalScribeEntry)
#         db.commit()
        
#         return handleResponse(code=200, message='OK', data=json.loads(final_answer))
#     except SQLAlchemyError as e:
#         db.rollback()
#         return handleError(code=500, message=f"Kesalahan dalam memproses data. {str(e)}", data=None)
#     except Exception as e:
#         return handleError(code=500, message=str(e))


# @router.post("/check-kelengkapan-berkas-document", tags=["RAG Engine Query"], response_model=ResponseModel[KliamBpjsOut])
# async def check_claim(
#     file: UploadFile = File(...),
#     db: Session = Depends(get_db)
# ):
#     """
#     Performs a check on a claim by querying the RAG engine.
#     You can provide upload a `file` (PDF) to be analyzed.
#     """
#     if not file:
#         return handleError(code=422, message="Please provide either a text query or a file.")

#     try:
#         query_text_from_file = ""
#         query_text = ""
#         if file:
#             if file.content_type != 'application/pdf':
#                 return handleError(code=422, message="Invalid file type. Only PDF is supported.")
            
#             temp_file_path = os.path.join(TEMP_UPLOAD_PATH, file.filename)
#             with open(temp_file_path, "wb") as buffer:
#                 shutil.copyfileobj(file.file, buffer)
            
#             query_text_from_file = rag_engine._process_pdf(temp_file_path)
            
#             query_text = f"Analyze and summarize the following document : \n\n{query_text_from_file}"
            
#             os.remove(temp_file_path)

#         # 1. Retrieve relevant context from RAG index
#         relevant_chunks = rag_engine.query(query_text, top_k=7)
#         if not relevant_chunks:
#             return handleError(code=404, message="Could not find relevant documents in the index. The index might be empty. Please try indexing documents first.")

#         contextQuery = "\n\n---".join([chunk['text'] for chunk in relevant_chunks])
        
#         # Group relevant chunks by source file
#         source_map = defaultdict(list)
#         for chunk in relevant_chunks:
#             source_map[chunk['source']].append({
#                 "chunk_id": chunk['chunk_id'],
#                 "content": chunk['text']
#             })

#         # Format for response
#         source_documents = []
#         for filename, chunks in source_map.items():
#             source_documents.append({
#                 "filename": filename,
#                 "relevant_chunks_count": len(chunks),
#                 "documents": chunks
#             })

#         query_text_from_file = truncate_text(query_text_from_file)
#         contextQuery = truncate_text(contextQuery)

#         # 2. Augment the prompt and generate the final response
#         prompt = rag_engine.generatePromptVerifikasiKlaimBpjs(query_text=query_text_from_file)
#         system_intruction = rag_engine.generateSystemIntructions(context=contextQuery)

#         response = await generate(prompt=prompt, system_instruction=system_intruction, response_mime_type="application/json", response_schema=RESPONSE_SCHEMA_CHECKING_CLAIM_BPJS, temperature=0.0, seed=len(prompt))

#         if not response or not getattr(response, "text", "").strip():

#             response = await generate(prompt=prompt, system_instruction=system_intruction, response_mime_type="application/json", response_schema=RESPONSE_SCHEMA_CHECKING_CLAIM_BPJS, temperature=0.0, seed=len(prompt))

#             if not response or not getattr(response, "text", "").strip():
#                 return handleError(code=500, message="Gagal menganalisis data.", data=None)
        
#         prompt_tokens = 0
#         candidates_tokens = 0
#         total_tokens = 0

#         if hasattr(response, 'usage_metadata'):
#             prompt_tokens = response.usage_metadata.prompt_token_count
#             candidates_tokens = response.usage_metadata.candidates_token_count
#             total_tokens = response.usage_metadata.total_token_count
        
#         final_answer = response.text if hasattr(response, 'text') else str(response)

#         medicalScribeEntry = KlaimBpjs(
#             document_name=file.filename,
#             document_extraction=query_text_from_file,
#             retrieval_content_query=json.dumps(source_documents),
#             prompt=prompt,
#             response=final_answer,
#             token_request=prompt_tokens,
#             token_response=candidates_tokens,
#             token_counts=total_tokens,
#             timestamp=datetime.now()
#         )
#         db.add(medicalScribeEntry)
#         db.commit()

#         return handleResponse(
#             data=json.loads(final_answer),
#             message="Claim check completed successfully."
#         )

#     except Exception as e:
#         return handleError(code=500, message=f"An internal error occurred: {str(e)}")


@router.post("/test-db-commit")
def test_db_commit(db: Session = Depends(get_db)):
    try:
        dummy_data = KlaimBpjs(
            document_name="Dummy Document",
            document_extraction="Ini adalah hasil checkup dummy.",
            retrieval_content_query=json.dumps([
                {
                    "filename": "dummy.pdf",
                    "relevant_chunks_count": 2,
                    "documents": [
                        {"chunk_id": 1, "content": "Dummy chunk 1"},
                        {"chunk_id": 2, "content": "Dummy chunk 2"}
                    ]
                }
            ]),
            prompt="Dummy prompt",
            response='{"status": "lengkap"}',
            token_request=100,
            token_response=50,
            token_counts=150,
            timestamp=datetime.now()
        )

        db.add(dummy_data)
        db.commit()
        db.refresh(dummy_data)

        return {
            "status": "success",
            "inserted_id": dummy_data.id
        }

    except Exception as e:
        db.rollback()
        return {"error": str(e)}



@router.delete("/rag-engine/delete-all-index", tags=["RAG Engine Management"])
async def delete_all_index():
    """
    Deletes ALL indexed documents from the RAG engine.
    """
    try:
        result = rag_engine.delete_all()
        return handleResponse(data=result, message="All indexes deleted successfully.")
    except Exception as e:
        return handleError(code=500, message=f"An internal error occurred: {str(e)}")