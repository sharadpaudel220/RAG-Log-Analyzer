"""
SQLAlchemy ORM models for PostgreSQL database
"""
from sqlalchemy import Column, String, Integer, BigInteger, Boolean, DECIMAL, TIMESTAMP, Text, ForeignKey, ARRAY, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid

from src.database.config import Base

class AnalysisSession(Base):
    __tablename__ = 'analysis_sessions'
    
    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    file_hash = Column(String(64))
    system_type = Column(String(50), nullable=False)
    total_logs = Column(Integer, nullable=False)
    anomalies_detected = Column(Integer, nullable=False)
    analysis_time_seconds = Column(DECIMAL(10, 3))
    status = Column(String(20), default='completed')
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    meta = Column(JSONB)
    
    uploaded_files = relationship("UploadedFile", back_populates="session", cascade="all, delete-orphan")
    log_entries = relationship("LogEntry", back_populates="session", cascade="all, delete-orphan")
    anomalies = relationship("Anomaly", back_populates="session", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="session", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

class UploadedFile(Base):
    __tablename__ = 'uploaded_files'
    
    file_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey('analysis_sessions.session_id', ondelete='CASCADE'))
    filename = Column(String(255), nullable=False)
    file_size = Column(BigInteger)
    file_content = Column(Text)
    file_path = Column(String(500))
    mime_type = Column(String(100))
    uploaded_at = Column(TIMESTAMP, server_default=func.now())
    
    session = relationship("AnalysisSession", back_populates="uploaded_files")

class LogEntry(Base):
    __tablename__ = 'log_entries'
    
    log_id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey('analysis_sessions.session_id', ondelete='CASCADE'))
    raw_content = Column(Text, nullable=False)
    template = Column(Text)
    template_id = Column(Integer)
    parameters = Column(ARRAY(Text))
    timestamp = Column(TIMESTAMP)
    severity = Column(String(20))
    component = Column(String(100))
    source_file = Column(String(255))
    line_number = Column(Integer)
    meta = Column(JSONB)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    session = relationship("AnalysisSession", back_populates="log_entries")
    anomaly = relationship("Anomaly", back_populates="log_entry", uselist=False)

class Anomaly(Base):
    __tablename__ = 'anomalies'
    
    anomaly_id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey('analysis_sessions.session_id', ondelete='CASCADE'))
    log_id = Column(BigInteger, ForeignKey('log_entries.log_id', ondelete='CASCADE'))
    is_anomaly = Column(Boolean, nullable=False)
    severity = Column(String(20), nullable=False)
    confidence_score = Column(DECIMAL(5, 4))
    anomaly_score = Column(DECIMAL(5, 4))
    final_analysis = Column(Text)
    matched_rules = Column(ARRAY(Text))
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    session = relationship("AnalysisSession", back_populates="anomalies")
    log_entry = relationship("LogEntry", back_populates="anomaly")
    reasoning_steps = relationship("ReasoningStep", back_populates="anomaly", cascade="all, delete-orphan")
    retrieved_documents = relationship("RetrievedDocument", back_populates="anomaly", cascade="all, delete-orphan")
    alert = relationship("Alert", back_populates="anomaly", uselist=False)

class ReasoningStep(Base):
    __tablename__ = 'reasoning_steps'
    
    step_id = Column(BigInteger, primary_key=True, autoincrement=True)
    anomaly_id = Column(BigInteger, ForeignKey('anomalies.anomaly_id', ondelete='CASCADE'))
    step_number = Column(Integer, nullable=False)
    thought = Column(Text)
    action = Column(String(50))
    action_input = Column(JSONB)
    observation = Column(Text)
    confidence = Column(DECIMAL(5, 4))
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    anomaly = relationship("Anomaly", back_populates="reasoning_steps")

class RetrievedDocument(Base):
    __tablename__ = 'retrieved_documents'
    
    retrieval_id = Column(BigInteger, primary_key=True, autoincrement=True)
    anomaly_id = Column(BigInteger, ForeignKey('anomalies.anomaly_id', ondelete='CASCADE'))
    document_id = Column(String(100))
    document_title = Column(String(255))
    document_content = Column(Text)
    document_type = Column(String(50))
    similarity_score = Column(DECIMAL(5, 4))
    relevance_score = Column(DECIMAL(5, 4))
    rank = Column(Integer)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    anomaly = relationship("Anomaly", back_populates="retrieved_documents")

class Alert(Base):
    __tablename__ = 'alerts'
    
    alert_id = Column(String(50), primary_key=True)
    anomaly_id = Column(BigInteger, ForeignKey('anomalies.anomaly_id', ondelete='CASCADE'))
    session_id = Column(UUID(as_uuid=True), ForeignKey('analysis_sessions.session_id', ondelete='CASCADE'))
    severity = Column(String(20), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    affected_component = Column(String(100))
    recommendations = Column(ARRAY(Text))
    confidence_score = Column(DECIMAL(5, 4))
    meta = Column(JSONB)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    session = relationship("AnalysisSession", back_populates="alerts")
    anomaly = relationship("Anomaly", back_populates="alert")

class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    
    message_id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey('analysis_sessions.session_id', ondelete='CASCADE'))
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    context = Column(JSONB)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    session = relationship("AnalysisSession", back_populates="chat_messages")

class KnowledgeDoc(Base):
    __tablename__ = 'knowledge_documents'
    
    document_id = Column(String(100), primary_key=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    doc_type = Column(String(50))
    embedding = Column(ARRAY(DECIMAL))
    meta = Column(JSONB)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

class SystemStats(Base):
    __tablename__ = 'system_stats'
    
    stat_id = Column(Integer, primary_key=True, default=1)
    total_logs_analyzed = Column(BigInteger, default=0)
    total_anomalies_detected = Column(BigInteger, default=0)
    total_alerts_generated = Column(BigInteger, default=0)
    total_sessions = Column(Integer, default=0)
    last_updated = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
