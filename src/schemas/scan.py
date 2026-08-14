from pydantic import BaseModel, ConfigDict
from typing import List

class ScanRequest(BaseModel):
     """The incoming JSON payload from the user containing the raw text to be scanned."""

     text:str

class DetectedEntity(BaseModel):
     """A single piece of identified PII, including its category and exact position in the text."""

     entity_type:str
     start_index:int
     end_index:int

class ScanResponse(BaseModel):
     """The final JSON response sent back to the client with the safe text and audit details."""
     
     original_text: str
     sanitized_text: str
     detected_pii: List[DetectedEntity]
     processing_time_ms: float

     model_config = ConfigDict(from_attributes=True)
