from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import AuditLog
from src.core import get_db
from src.schemas import ScanRequest, DetectedEntity, ScanResponse
from src.agent.graph import build_workflow
import time

app_engine = build_workflow()

scan_router = APIRouter()

@scan_router.post('/scan', response_model= ScanResponse, tags= ["Scanner"], status_code= status.HTTP_200_OK)
async def scan_pii(request: ScanRequest, db: AsyncSession= Depends(get_db)):

     """
    Receives raw text, processes it through the LangGraph PII detection engine, 
    and returns the sanitized text along with audit metrics.
    """

     try:

          start_time = time.time()

          scan_text  = request.text

          result_state = app_engine.invoke({"original_text" : scan_text})

          process_time_ms = int(time.time() - start_time) * 1000

          raw_entities = result_state.get("detected_entities", [])

          serialized_entities = [entitiy.model_dump() for entitiy in raw_entities]

          new_audit_record = AuditLog(
               original_text  = scan_text,
               sanitized_text = result_state.get("sanitized_text", ""),
               pii_detection  = serialized_entities,
               processing_time= process_time_ms
          )

          db.add(new_audit_record)

          await db.commit()

          await db.refresh(new_audit_record)

          return {
               "original_text"     : scan_text,
               "sanitized_text"    : result_state.get("sanitized_text", ""),
               "detected_pii"      : result_state.get("detected_entities", []),
               "processing_time_ms": process_time_ms
          }
     
     except Exception as e:
          await db.rollback()
          print(f"Error: {e}")
          raise HTTPException(
               status_code    = status.HTTP_500_INTERNAL_SERVER_ERROR,
               detail         = "Internal Server Error processing the scan request."
          )
