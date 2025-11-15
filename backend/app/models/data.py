from pydantic import BaseModel
from typing import List

class TableData(BaseModel):
    title: str
    header: List[str]
    rows: List[List[str]]

class FileData(BaseModel):
    filePath: str
    tables: List[TableData]

class TableUpdate(BaseModel):
    filePath: str
    tableIndex: int
    newRows: List[List[str]]

class SaveRequest(BaseModel):
    updates: List[TableUpdate]

class SaveResponse(BaseModel):
    success: bool
    message: str