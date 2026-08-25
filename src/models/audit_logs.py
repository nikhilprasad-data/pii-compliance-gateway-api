from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Text, JSON, DateTime, func
from uuid import UUID,uuid4
from datetime import datetime

class Base(DeclarativeBase):

     pass

class AuditLog(Base):

     __tablename__ = "audit_logs"

     __table_args__ = {"schema": "compliance"}

     id: Mapped[UUID] = mapped_column(primary_key= True, default= uuid4)

     original_text: Mapped[str] = mapped_column(Text, nullable= False)

     sanitized_text: Mapped[str] = mapped_column(Text, nullable= False) 

     pii_detection: Mapped[list[dict]] = mapped_column(JSON, nullable= False) 

     processing_time: Mapped[int] = mapped_column(Integer, nullable= False) 

     time_stamp: Mapped[datetime] = mapped_column(DateTime, server_default= func.now(), nullable= False) 
