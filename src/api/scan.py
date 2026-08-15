from fastapi import APIRouter, HTTPException, status
from src.schemas import ScanRequest, DetectedEntity, ScanResponse


scan_router = APIRouter()

@scan_router.post('/scan', response_model= ScanResponse, tags= ["Scanner"], status_code= status.HTTP_200_OK)
async def scan_pii(request: ScanRequest):

     """
    Receives raw text, processes it through the LangGraph PII detection engine, 
    and returns the sanitized text along with audit metrics.
    """

     try:
          scan_text  = request.text

          mock_entity = {
            "entity_type": "CREDIT_CARD",
            "start_index": 12,
            "end_index": 28
          }

          return {
               "original_text"     : scan_text,
               "sanitized_text"    : "Hello Nikhil",
               "detected_pii"      : [mock_entity],
               "processing_time_ms": 12.5
          }
     
     except Exception as e:
          print(f"Error: {e}")
          raise HTTPException(
               status_code    = status.HTTP_500_INTERNAL_SERVER_ERROR,
               detail         = "Internal Server Error processing the scan request."
          )
