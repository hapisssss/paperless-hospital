import vertexai
from vertexai.generative_models import GenerationConfig, GenerativeModel, Part, SafetySetting
from typing import List, Dict, Union, Optional
import os

from dotenv import load_dotenv
load_dotenv(override=True)

GOOGLE_PROJECT = os.getenv("GOOGLE_PROJECT")
GOOGLE_PROJECT_LOCATION = os.getenv("GOOGLE_PROJECT_LOCATION")
GEMINI_MODEL = os.getenv("GEMINI_MODEL")

vertexai.init(project=GOOGLE_PROJECT, location=GOOGLE_PROJECT_LOCATION)
safety_settings = [
    SafetySetting(
        category=SafetySetting.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=SafetySetting.HarmBlockThreshold.OFF
    ),
    SafetySetting(
        category=SafetySetting.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=SafetySetting.HarmBlockThreshold.OFF
    ),
    SafetySetting(
        category=SafetySetting.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=SafetySetting.HarmBlockThreshold.OFF
    ),
    SafetySetting(
        category=SafetySetting.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=SafetySetting.HarmBlockThreshold.OFF
    ),
]

def promptFreeForm(prompt: str, file: Optional[Union[List[Dict[str, str]], Dict[str, str]]] = None, response_schema: dict = None, model_name: str = GEMINI_MODEL):
    model = GenerativeModel(model_name=model_name, safety_settings=None)

    part = []
    if(file is not None):
        if isinstance(file, list):
            for f in file:
                part.append(Part.from_uri(f["uri"], mime_type=f["mime_type"]))
        else:
            part.append(Part.from_uri(file["uri"], mime_type=file["mime_type"]))

    part.append(prompt)
    
    generation_config = GenerationConfig(
        response_mime_type="application/json", 
        response_schema=response_schema
    )

    responses = model.generate_content(
        contents=part,
        generation_config=generation_config,
        safety_settings=safety_settings
    )

    return responses

def promptChat(message: str, history: Optional[List[Dict[str, str]]] = None, model_name: str = GEMINI_MODEL):
    model = GenerativeModel(model_name=model_name, safety_settings=None)
    chat = model.start_chat(history=history)
    response = chat.send_message(message)
    return response.text

