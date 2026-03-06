from pydantic import BaseModel, Field
from typing import Dict, List

RESPONSE_SCHEMA_CHECKING_CLAIM_BPJS = {
    "type": "object",
    "properties": {
        "complete": {
            "type": "array",
            "description": "Administrasi atau dokumen klaim yang lengkap",
            "items": {
                "type": "string",
                "description": "Deskripsi atau nama administrasi atau dokumen klaim yang lengkap"
            }
        },
        "incomplete": {
            "type": "object",
            "properties": {
                "analisa_aturan_bak":{
                    "type": "array",
                    "description": "Administrasi dokumen klaim terkait berita acara kesepakatan bpjs yang tidak lengkap",
                    "items": {
                        "type": "string",
                        "description": "Deskripsi atau nama administrasi dokumen klaim terkait berita acara kesepakatan bpjs yang tidak lengkap"
                    }
                },
                "analisa_aturan_klinis":{
                    "type": "array",
                    "description": "Administrasi dokumen klaim terkait aturan klinis yang tidak lengkap",
                    "items": {
                        "type": "string",
                        "description": "Deskripsi atau nama administrasi dokumen klaim terkait aturan klinis yang tidak lengkap"
                    }
                },
                "analisa_permenkes":{
                    "type": "array",
                    "description": "Administrasi dokumen klaim terkait peraturan mentri kesehatan yang tidak lengkap",
                    "items": {
                        "type": "string",
                        "description": "Deskripsi atau nama administrasi dokumen klaim terkait peraturan mentri kesehatan yang tidak lengkap"
                    }
                },
                "analisa_aturan_coding_medis":{
                    "type": "array",
                    "description": "Administrasi dokumen klaim terkait aturan coding medis yang tidak lengkap",
                    "items": {
                        "type": "string",
                        "description": "Deskripsi atau nama administrasi dokumen klaim terkait aturan coding medis yang tidak lengkap"
                    }
                }
            },
            "required": ["analisa_aturan_bak", "analisa_aturan_klinis", "analisa_permenkes", "analisa_aturan_coding_medis"]
        },
        "improvement_suggestions": {
            "type": "object",
            "properties": {
                "analisa_aturan_bak":{
                    "type": "array",
                    "description": "Saran-saran atau berupa perintah perbaikan sdministrasi dokumen klaim terkait berita acara kesepakatan bpjs yang tidak lengkap",
                    "items": {
                        "type": "string",
                        "description": "Deskripsi saran atau perintah perbaikan administrasi atau dokumen klaim terkait berita acara kesepakatan bpjs yang tidak lengkap"
                    }
                },
                "analisa_aturan_klinis":{
                    "type": "array",
                    "description": "Saran-saran atau berupa perintah perbaikan sdministrasi dokumen klaim terkait aturan klinis yang tidak lengkap",
                    "items": {
                        "type": "string",
                        "description": "Deskripsi saran atau perintah perbaikan administrasi atau dokumen klaim terkait aturan klinis yang tidak lengkap"
                    }
                },
                "analisa_permenkes":{
                    "type": "array",
                    "description": "Saran-saran atau berupa perintah perbaikan sdministrasi dokumen klaim terkait peraturan mentri kesehatan yang tidak lengkap",
                    "items": {
                        "type": "string",
                        "description": "Deskripsi saran atau perintah perbaikan administrasi atau dokumen klaim terkait peraturan mentri kesehatan yang tidak lengkap"
                    }
                },
                "analisa_aturan_coding_medis":{
                    "type": "array",
                    "description": "Saran-saran atau berupa perintah perbaikan sdministrasi dokumen klaim terkait aturan coding medis yang tidak lengkap",
                    "items": {
                        "type": "string",
                        "description": "Deskripsi saran atau perintah perbaikan administrasi atau dokumen klaim terkait aturan coding medis yang tidak lengkap"
                    }
                }
            },
            "required": ["analisa_aturan_bak", "analisa_aturan_klinis", "analisa_permenkes", "analisa_aturan_coding_medis"]
        }
    },
    "required": ["complete", "incomplete", "improvement_suggestions"]
}

class KliamBpjsIn(BaseModel):
    result_checkup: str

# This is a generic/deprecated model, we keep it to not break other parts of the code if they use it.
class KliamBpjsOut(BaseModel):
    complete: List[str]
    incomplete: Dict[str, List[str]]
    improvement_suggestions: Dict[str, List[str]]


# --- Detailed Pydantic Models for Structured Output ---

class IncompleteDetail(BaseModel):
    analisa_aturan_bak: List[str] = Field(..., description="Administrasi dokumen klaim terkait berita acara kesepakatan bpjs yang tidak lengkap")
    analisa_aturan_klinis: List[str] = Field(..., description="Administrasi dokumen klaim terkait aturan klinis yang tidak lengkap")
    analisa_permenkes: List[str] = Field(..., description="Administrasi dokumen klaim terkait peraturan mentri kesehatan yang tidak lengkap")
    analisa_aturan_coding_medis: List[str] = Field(..., description="Administrasi dokumen klaim terkait aturan coding medis yang tidak lengkap")

class ImprovementSuggestionsDetail(BaseModel):
    analisa_aturan_bak: List[str] = Field(..., description="Saran-saran atau berupa perintah perbaikan sdministrasi dokumen klaim terkait berita acara kesepakatan bpjs yang tidak lengkap")
    analisa_aturan_klinis: List[str] = Field(..., description="Saran-saran atau berupa perintah perbaikan sdministrasi dokumen klaim terkait aturan klinis yang tidak lengkap")
    analisa_permenkes: List[str] = Field(..., description="Saran-saran atau berupa perintah perbaikan sdministrasi dokumen klaim terkait peraturan mentri kesehatan yang tidak lengkap")
    analisa_aturan_coding_medis: List[str] = Field(..., description="Saran-saran atau berupa perintah perbaikan sdministrasi dokumen klaim terkait aturan coding medis yang tidak lengkap")

class DetailedKlaimBpjsOut(BaseModel):
    """The detailed schema for checking BPJS claims."""
    complete: List[str] = Field(..., description="Administrasi atau dokumen klaim yang lengkap")
    incomplete: IncompleteDetail
    improvement_suggestions: ImprovementSuggestionsDetail
