from google import genai
from google.genai import types
from typing import List, Dict, Union, Optional
import os
import httpx
import json


from dotenv import load_dotenv
load_dotenv(override=True)

GOOGLE_PROJECT = os.getenv("GOOGLE_PROJECT")
GOOGLE_PROJECT_LOCATION = os.getenv("GOOGLE_PROJECT_LOCATION")
GEMINI_MODEL = os.getenv("GEMINI_MODEL")
1
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS


#  use ollama paperless-qwen3vl for Text Generation
TEXT_GENERATION_MODEL = os.getenv("TEXT_GENERATION_MODEL")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL") 

client = genai.Client(
    vertexai=True,
    project=GOOGLE_PROJECT,
    location=GOOGLE_PROJECT_LOCATION,
)

async def modelInfo(model_name: str = GEMINI_MODEL):
    model_info = await client.aio.models.get(model=model_name)
    return model_info

async def countToken(model_name: str = GEMINI_MODEL, prompt: str = ""):
    total_tokens = await client.aio.models.count_tokens(model=model_name, contents=prompt)

    return total_tokens.total_tokens


async def generate(prompt: str, file: Optional[Union[List[Dict[str, str]], Dict[str, str]]] = None, system_instruction: str = None, response_mime_type: str = "text/plain", response_schema: dict = None, model_name: str = GEMINI_MODEL, max_output_tokens: int = 8192, temperature: float = 0.0, seed: int = 1, top_k: float = None, top_p: float = None):
    generate_content_config = types.GenerateContentConfig(
        max_output_tokens = max_output_tokens,
        temperature = temperature,
        top_k = top_k,
        top_p = top_p,
        seed = seed,
        safety_settings = [types.SafetySetting(
            category="HARM_CATEGORY_HATE_SPEECH",
            threshold="OFF"
        ),types.SafetySetting(
            category="HARM_CATEGORY_DANGEROUS_CONTENT",
            threshold="OFF"
        ),types.SafetySetting(
            category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
            threshold="OFF"
        ),types.SafetySetting(
            category="HARM_CATEGORY_HARASSMENT",
            threshold="OFF"
        )]
    )

    if response_schema:
        generate_content_config.response_mime_type=response_mime_type
        generate_content_config.response_schema=response_schema

    if system_instruction:
        generate_content_config.system_instruction=system_instruction

    parts = []
    if(file is not None):
        if isinstance(file, list):
            for f in file:
                parts.append(types.Part.from_uri(file_uri=f["uri"], mime_type=f["mime_type"]))
        else:
            parts.append(types.Part.from_uri(file_uri=file["uri"], mime_type=file["mime_type"]))

    contents = [types.Part.from_text(text=prompt)]
    if parts:
        contents = contents + parts

    responses = await client.aio.models.generate_content(
        model=model_name,
        contents=contents,
        config=generate_content_config,
    )

    return responses


async def generate_ollama(
    prompt: str,
    system_instruction: str = None,
    response_schema: dict = None,
    temperature: float = 0.0,
    seed: int = 1,
    #max_output_tokens: int = 1024,
):
    
    payload = {
        "model": TEXT_GENERATION_MODEL,
        "stream": False,
        "messages": [
            {
    "role": "system",
    "content": system_instruction
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "format": response_schema,
        "options": {"temperature": 0}
    }
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload
        )
        response.raise_for_status()
        return response.json()


# async def generate_ollama(
#     prompt: str,
#     system_instruction: str = None,
#     response_schema: dict = None,
#     temperature: float = 0.0,
#     seed: int = 1,
#     max_output_tokens: int = 1024,
# ):
#     # add schema if exist too the system instruction
#     full_system = system_instruction or ""
#     if response_schema:
#         full_system += f"""

# PENTING: Anda HARUS merespons HANYA dengan JSON murni, tanpa teks tambahan, tanpa markdown, tanpa penjelasan.
# Struktur JSON yang harus dikembalikan adalah sebagai berikut:
# {json.dumps(response_schema, indent=2, ensure_ascii=False)}
# """

#     payload = {
#         "model": TEXT_GENERATION_MODEL,
#         "prompt": prompt, 
#         "stream": False,
#         # "format": "json",
#         "system" : system_instruction,
#         "options": {
#             "temperature": temperature,
#             "seed": seed,
#             "num_predict": max_output_tokens,
#         }
#     }

#     if full_system:
#         payload["system"] = full_system

#     async with httpx.AsyncClient(timeout=300.0) as client:
#         response = await client.post(
#             f"{OLLAMA_BASE_URL}/api/generate",
#             json=payload
#         )
#         response.raise_for_status()
#         return response.json()

