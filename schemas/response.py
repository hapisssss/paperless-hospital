from pydantic import BaseModel, Field
from typing import Optional, Generic, TypeVar, Union, List

T = TypeVar('T')

class ResponseModelPagging(BaseModel, Generic[T]):
    code: int = 200
    message: str = 'OK'
    limit: Optional[int] = None
    offset: Optional[int] = None
    data: Optional[Union[T, List[T]]] = None

class ResponseModel(BaseModel, Generic[T]):
    code: int = 200
    message: str = 'OK'
    data: Optional[Union[T, List[T]]] = None