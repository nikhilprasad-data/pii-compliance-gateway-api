import hashlib
import json
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis 
from src.core import get_db, get_redis, check_rate_limit
from src.agent.graph import build_workflow 
from src.schemas import ScanRequest, ScanResponse
from src.models import AuditLog
import time
import logging

logger = logging.getLogger(__name__)

app_engine = build_workflow()

scan_router = APIRouter()

@scan_router.post('/scan', response_model=ScanResponse, tags=["Scanner"], status_code=status.HTTP_200_OK)
async def scan_pii(request: ScanRequest, db: AsyncSession = Depends(get_db),redis_client: Redis = Depends(get_redis), rate_limit: None = Depends(check_rate_limit)):

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
               cache_time_ms = round((time.perf_counter() - start_time) * 1000, 2)


               cached_response = json.loads(cached_data)
               cached_response["processing_time_ms"] = cache_time_ms

               return cached_response

          result_state = await app_engine.ainvoke({"original_text" : scan_text})
          process_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

          raw_entities = result_state.get("detected_entities", [])

          safe_entities = [
               {
                    "entity_type" : entity.entity_type,
                    "start_index" : entity.start_index,
                    "end_index" : entity.end_index     
               }
               for entity in raw_entities
          ]

          sanitized_text = result_state.get("sanitized_text","")

          new_audit_record = AuditLog(
               sanitized_text  = sanitized_text,
               pii_detection   = safe_entities,
               processing_time = process_time_ms
          )

          db.add(new_audit_record)
          await db.commit()
          await db.refresh(new_audit_record)

          response_payload = {
               "sanitized_text"    : sanitized_text,
               "detected_pii"      : safe_entities,
               "processing_time_ms": process_time_ms
          }

          await redis_client.set(cache_key, json.dumps(response_payload), ex=86400)

          return response_payload
     
     except Exception:
          await db.rollback()

          logger.exception("Unexpected error while processing PII scan request")

          raise HTTPException(
               status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
               detail="Internal Server Error processing the scan request.",
          )
