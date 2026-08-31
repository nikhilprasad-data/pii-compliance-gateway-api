import hashlib
import json
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis 
from src.core import get_db, get_redis
from src.agent.graph import build_workflow 
from src.schemas import ScanRequest, ScanResponse, DetectedEntity
from src.models import AuditLog
import time

app_engine = build_workflow()

scan_router = APIRouter()

@scan_router.post('/scan', response_model=ScanResponse, tags=["Scanner"], status_code=status.HTTP_200_OK)
async def scan_pii(request: ScanRequest, db: AsyncSession = Depends(get_db),redis_client: Redis = Depends(get_redis)):

     """
     Receives raw text, processes it through the LangGraph PII detection engine,
     and returns the sanitized text along with audit metrics.
     """

     try:
          start_time = time.perf_counter()
          scan_text  = request.text

          text_hash = hashlib.sha256(scan_text.encode('utf-8')).hexdigest()
          cache_key = f"scan_cache:{text_hash}"

          cached_data = await redis_client.get(cache_key)

          if cached_data:
               cache_time_ms = int((time.perf_counter() - start_time) * 1000)


               cached_response = json.loads(cached_data)
               cached_response["processing_time_ms"] = cache_time_ms

               return cached_response

          result_state = app_engine.invoke({"original_text" : scan_text})
          process_time_ms = int((time.perf_counter() - start_time) * 1000)

          raw_entities = result_state.get("detected_entities", [])
          serialized_entities = [entity.model_dump() for entity in raw_entities]

          new_audit_record = AuditLog(
               original_text   = scan_text,
               sanitized_text  = result_state.get("sanitized_text", ""),
               pii_detection   = serialized_entities,
               processing_time = process_time_ms
          )

          db.add(new_audit_record)
          await db.commit()
          await db.refresh(new_audit_record)

          response_payload = {
               "original_text"     : scan_text,
               "sanitized_text"    : result_state.get("sanitized_text", ""),
               "detected_pii"      : serialized_entities,
               "processing_time_ms": process_time_ms
          }

          await redis_client.set(cache_key, json.dumps(response_payload), ex=86400)

          return response_payload
     
     except Exception as e:
          await db.rollback()
          print(f"Error: {e}")
          raise HTTPException(
               status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
               detail      = "Internal Server Error processing the scan request."
          )
