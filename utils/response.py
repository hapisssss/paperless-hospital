from fastapi import Response
from datetime import datetime
import pytz
import json

def handleError(message: str = 'OK', code: int =500, data: any = None):
    exception = Response(status_code=code, media_type="application/json", content=json.dumps({"detail": {
        'code':code,
        'message':message,
        'data': data
    }}))
    return exception

def handleResponse(data: any = None, message: str = 'Ok', code: int = 200):
    return {
        'code': code,
        'message': message,
        'data': data
    }

def handleResponsePagging(data: any = any, limit: int = 10, offset: int = 0, message: str = 'Ok', code: int = 200):
    return {
        'code': code,
        'message': message,
        'limit': limit,
        'offset': offset,
        'data': data
    }

def responseExampleSwagger(code: int = 401, message: str = "Could not validate credentials", data: any = any):
    error = {
        "content": {"application/json": {"example": {"detail": {"code": code, "message": message, "data": data}}}}
    }
    return error
