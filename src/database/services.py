"""
Database service layer for CRUD operations
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
import hashlib
from sqlalchemy import desc, func

from src.database.config import db_config
from src.database.models import (
    AnalysisSession, UploadedFile, LogEntry, Anomaly,
    ReasoningStep, RetrievedDocument, Alert, ChatMessage,
    KnowledgeDoc, SystemStats, APIConnection
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

class DatabaseService:
    """Service layer for database operations"""
    
    @staticmethod
    def create_analysis_session(filename: str, system_type: str, file_content: str = None) -> str:
        """Create a new analysis session and return session_id"""
        with db_config.get_session() as session:
            file_hash = None
            if file_content:
                file_hash = hashlib.sha256(file_content.encode()).hexdigest()
            
            analysis_session = AnalysisSession(
                filename=filename,
                file_hash=file_hash,
                system_type=system_type,
                total_logs=0,
                anomalies_detected=0,
                status='processing'
            )
            session.add(analysis_session)
            session.flush()
            
            session_id = str(analysis_session.session_id)
            
            if file_content:
                uploaded_file = UploadedFile(
                    session_id=analysis_session.session_id,
                    filename=filename,
                    file_content=file_content,
                    file_size=len(file_content)
                )
                session.add(uploaded_file)
            
            logger.info(f"Created analysis session: {session_id}")
            return session_id
    
    @staticmethod
    def update_session_stats(session_id: str, total_logs: int, anomalies_detected: int, 
                            analysis_time: float, status: str = 'completed'):
        """Update session statistics"""
        with db_config.get_session() as session:
            analysis_session = session.query(AnalysisSession).filter_by(session_id=session_id).first()
            if analysis_session:
                analysis_session.total_logs = total_logs
                analysis_session.anomalies_detected = anomalies_detected
                analysis_session.analysis_time_seconds = analysis_time
                analysis_session.status = status
                logger.info(f"Updated session stats: {session_id}")
    
    @staticmethod
    def save_log_entry(session_id: str, log_data: Dict[str, Any]) -> int:
        """Save a parsed log entry and return log_id"""
        with db_config.get_session() as session:
            log_entry = LogEntry(
                session_id=session_id,
                raw_content=log_data.get('raw_content'),
                template=log_data.get('template'),
                template_id=log_data.get('template_id'),
                parameters=log_data.get('parameters', []),
                timestamp=log_data.get('timestamp'),
                severity=log_data.get('severity'),
                component=log_data.get('component'),
                source_file=log_data.get('source_file'),
                line_number=log_data.get('line_number'),
                meta=log_data.get('metadata', {})
            )
            session.add(log_entry)
            session.flush()
            log_id = log_entry.log_id
            return log_id
    
    @staticmethod
    def save_anomaly(session_id: str, log_id: int, anomaly_data: Dict[str, Any]) -> int:
        """Save anomaly detection result and return anomaly_id"""
        with db_config.get_session() as session:
            anomaly = Anomaly(
                session_id=session_id,
                log_id=log_id,
                is_anomaly=anomaly_data.get('is_anomaly', False),
                severity=anomaly_data.get('severity', 'INFO'),
                confidence_score=anomaly_data.get('confidence_score'),
                anomaly_score=anomaly_data.get('anomaly_score'),
                final_analysis=anomaly_data.get('final_analysis'),
                matched_rules=anomaly_data.get('matched_rules', [])
            )
            session.add(anomaly)
            session.flush()
            
            anomaly_id = anomaly.anomaly_id
            
            if 'reasoning_chain' in anomaly_data:
                for step_data in anomaly_data['reasoning_chain']:
                    reasoning_step = ReasoningStep(
                        anomaly_id=anomaly_id,
                        step_number=step_data.get('step_number'),
                        thought=step_data.get('thought'),
                        action=step_data.get('action'),
                        action_input=step_data.get('action_input', {}),
                        observation=step_data.get('observation'),
                        confidence=step_data.get('confidence')
                    )
                    session.add(reasoning_step)
            
            if 'retrieved_documents' in anomaly_data:
                for doc_data in anomaly_data['retrieved_documents']:
                    retrieved_doc = RetrievedDocument(
                        anomaly_id=anomaly_id,
                        document_id=doc_data.get('document', {}).get('id'),
                        document_title=doc_data.get('document', {}).get('title'),
                        document_content=doc_data.get('document', {}).get('content'),
                        document_type=doc_data.get('document', {}).get('doc_type'),
                        similarity_score=doc_data.get('similarity_score'),
                        relevance_score=doc_data.get('relevance_score'),
                        rank=doc_data.get('rank')
                    )
                    session.add(retrieved_doc)
            
            return anomaly_id
    
    @staticmethod
    def save_alert(session_id: str, anomaly_id: int, alert_data: Dict[str, Any]) -> str:
        """Save generated alert and return alert_id"""
        with db_config.get_session() as session:
            alert = Alert(
                alert_id=alert_data.get('alert_id'),
                anomaly_id=anomaly_id,
                session_id=session_id,
                severity=alert_data.get('severity'),
                title=alert_data.get('title'),
                description=alert_data.get('description'),
                affected_component=alert_data.get('affected_component'),
                recommendations=alert_data.get('recommendations', []),
                confidence_score=alert_data.get('confidence_score'),
                meta=alert_data.get('metadata', {})
            )
            session.add(alert)
            session.flush()
            return alert.alert_id
    
    @staticmethod
    def save_chat_message(session_id: str, role: str, content: str, context: Dict = None) -> int:
        """Save chat message and return message_id"""
        with db_config.get_session() as session:
            message = ChatMessage(
                session_id=session_id,
                role=role,
                content=content,
                context=context or {}
            )
            session.add(message)
            session.flush()
            return message.message_id
    
    @staticmethod
    def get_session(session_id: str) -> Optional[AnalysisSession]:
        """Get analysis session by ID"""
        with db_config.get_session() as session:
            return session.query(AnalysisSession).filter_by(session_id=session_id).first()
    
    @staticmethod
    def get_session_with_details(session_id: str) -> Optional[Dict[str, Any]]:
        """Get session with all related data"""
        with db_config.get_session() as session:
            analysis_session = session.query(AnalysisSession).filter_by(session_id=session_id).first()
            
            if not analysis_session:
                return None
            
            anomalies = session.query(Anomaly).filter_by(
                session_id=session_id, 
                is_anomaly=True
            ).all()
            
            logs = session.query(LogEntry).filter_by(session_id=session_id).limit(100).all()
            
            chat_messages = session.query(ChatMessage).filter_by(
                session_id=session_id
            ).order_by(ChatMessage.created_at).all()
            
            return {
                'session_id': str(analysis_session.session_id),
                'filename': analysis_session.filename,
                'system_type': analysis_session.system_type,
                'total_logs': analysis_session.total_logs,
                'anomalies_detected': analysis_session.anomalies_detected,
                'analysis_time': float(analysis_session.analysis_time_seconds) if analysis_session.analysis_time_seconds else 0,
                'timestamp': analysis_session.created_at.isoformat(),
                'status': analysis_session.status,
                'anomalies': [
                    {
                        'log_content': a.log_entry.raw_content if a.log_entry else '',
                        'severity': a.severity,
                        'confidence': float(a.confidence_score) if a.confidence_score else 0,
                        'analysis': a.final_analysis
                    }
                    for a in anomalies[:50]
                ],
                'all_logs': [
                    {
                        'content': log.raw_content,
                        'severity': log.severity,
                        'template': log.template
                    }
                    for log in logs
                ],
                'chat_history': [
                    {
                        'role': msg.role,
                        'content': msg.content,
                        'timestamp': msg.created_at.isoformat()
                    }
                    for msg in chat_messages
                ]
            }
    
    @staticmethod
    def list_sessions(limit: int = 50) -> List[Dict[str, Any]]:
        """List all analysis sessions"""
        with db_config.get_session() as session:
            sessions = session.query(AnalysisSession).order_by(
                desc(AnalysisSession.created_at)
            ).limit(limit).all()
            
            return [
                {
                    'session_id': str(s.session_id),
                    'filename': s.filename,
                    'system_type': s.system_type,
                    'total_logs': s.total_logs,
                    'anomalies_detected': s.anomalies_detected,
                    'timestamp': s.created_at.isoformat(),
                    'status': s.status
                }
                for s in sessions
            ]
    
    @staticmethod
    def delete_session(session_id: str):
        """Delete a specific analysis session"""
        try:
            with db_config.get_session() as session:
                analysis_session = session.query(AnalysisSession).filter_by(session_id=session_id).first()
                if analysis_session:
                    session.delete(analysis_session)
                    session.flush()
                    logger.info(f"Deleted analysis session: {session_id}")
                    return True
                else:
                    logger.warning(f"Session not found: {session_id}")
                    return False
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            raise
    
    @staticmethod
    def delete_all_sessions():
        """Delete all analysis sessions"""
        with db_config.get_session() as session:
            session.query(AnalysisSession).delete()
            logger.warning("Deleted all analysis sessions")
    
    @staticmethod
    def get_chat_history(session_id: str) -> List[Dict[str, Any]]:
        """Get chat history for a session"""
        with db_config.get_session() as session:
            messages = session.query(ChatMessage).filter_by(
                session_id=session_id
            ).order_by(ChatMessage.created_at).all()
            
            return [
                {
                    'role': msg.role,
                    'content': msg.content,
                    'timestamp': msg.created_at.isoformat()
                }
                for msg in messages
            ]
    
    @staticmethod
    def update_system_stats(logs_analyzed: int = 0, anomalies: int = 0, alerts: int = 0, sessions: int = 0):
        """Update system statistics"""
        with db_config.get_session() as session:
            stats = session.query(SystemStats).filter_by(stat_id=1).first()
            if stats:
                if logs_analyzed > 0:
                    stats.total_logs_analyzed += logs_analyzed
                if anomalies > 0:
                    stats.total_anomalies_detected += anomalies
                if alerts > 0:
                    stats.total_alerts_generated += alerts
                if sessions > 0:
                    stats.total_sessions += sessions
    
    @staticmethod
    def get_system_stats() -> Dict[str, Any]:
        """Get system statistics"""
        with db_config.get_session() as session:
            stats = session.query(SystemStats).filter_by(stat_id=1).first()
            if stats:
                return {
                    'total_logs_analyzed': stats.total_logs_analyzed,
                    'total_anomalies_detected': stats.total_anomalies_detected,
                    'total_alerts_generated': stats.total_alerts_generated,
                    'total_sessions': stats.total_sessions,
                    'last_updated': stats.last_updated.isoformat()
                }
            return {
                'total_logs_analyzed': 0,
                'total_anomalies_detected': 0,
                'total_alerts_generated': 0,
                'total_sessions': 0
            }

    # ==================== API Connection Methods ====================
    
    @staticmethod
    def create_api_connection(connection_data: Dict[str, Any]) -> str:
        """Create a new API connection and return connection_id"""
        with db_config.get_session() as session:
            connection = APIConnection(
                name=connection_data.get('name'),
                connection_type=connection_data.get('sourceType', connection_data.get('type')),
                api_type=connection_data.get('type'),
                endpoint=connection_data.get('endpoint'),
                auth_type=connection_data.get('authType', 'none'),
                auth_data=connection_data.get('authData', {}),
                fetch_interval=connection_data.get('interval', 5),
                enabled=True,
                meta=connection_data.get('meta', {})
            )
            session.add(connection)
            session.flush()
            
            connection_id = str(connection.connection_id)
            logger.info(f"Created API connection: {connection_id}")
            return connection_id
    
    @staticmethod
    def get_all_api_connections() -> List[Dict[str, Any]]:
        """Get all API connections"""
        with db_config.get_session() as session:
            connections = session.query(APIConnection).order_by(APIConnection.created_at.desc()).all()
            
            return [
                {
                    'id': str(conn.connection_id),
                    'name': conn.name,
                    'type': conn.api_type,
                    'sourceType': conn.connection_type,
                    'endpoint': conn.endpoint,
                    'authType': conn.auth_type,
                    'authData': conn.auth_data,
                    'interval': conn.fetch_interval,
                    'enabled': conn.enabled,
                    'lastFetchAt': conn.last_fetch_at.isoformat() if conn.last_fetch_at else None,
                    'totalLogsFetched': conn.total_logs_fetched,
                    'createdAt': conn.created_at.isoformat()
                }
                for conn in connections
            ]
    
    @staticmethod
    def get_api_connection(connection_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific API connection"""
        with db_config.get_session() as session:
            conn = session.query(APIConnection).filter_by(connection_id=connection_id).first()
            if conn:
                return {
                    'id': str(conn.connection_id),
                    'name': conn.name,
                    'type': conn.api_type,
                    'sourceType': conn.connection_type,
                    'endpoint': conn.endpoint,
                    'authType': conn.auth_type,
                    'authData': conn.auth_data,
                    'interval': conn.fetch_interval,
                    'enabled': conn.enabled,
                    'lastFetchAt': conn.last_fetch_at.isoformat() if conn.last_fetch_at else None,
                    'totalLogsFetched': conn.total_logs_fetched,
                    'createdAt': conn.created_at.isoformat()
                }
            return None
    
    @staticmethod
    def update_api_connection(connection_id: str, update_data: Dict[str, Any]) -> bool:
        """Update an API connection"""
        with db_config.get_session() as session:
            conn = session.query(APIConnection).filter_by(connection_id=connection_id).first()
            if conn:
                if 'name' in update_data:
                    conn.name = update_data['name']
                if 'endpoint' in update_data:
                    conn.endpoint = update_data['endpoint']
                if 'authType' in update_data:
                    conn.auth_type = update_data['authType']
                if 'authData' in update_data:
                    conn.auth_data = update_data['authData']
                if 'interval' in update_data:
                    conn.fetch_interval = update_data['interval']
                if 'enabled' in update_data:
                    conn.enabled = update_data['enabled']
                
                logger.info(f"Updated API connection: {connection_id}")
                return True
            return False
    
    @staticmethod
    def delete_api_connection(connection_id: str) -> bool:
        """Delete an API connection"""
        with db_config.get_session() as session:
            conn = session.query(APIConnection).filter_by(connection_id=connection_id).first()
            if conn:
                session.delete(conn)
                logger.info(f"Deleted API connection: {connection_id}")
                return True
            return False
    
    @staticmethod
    def get_enabled_connections_by_type(connection_type: str) -> List[Dict[str, Any]]:
        """Get all enabled connections for a specific type"""
        with db_config.get_session() as session:
            connections = session.query(APIConnection).filter_by(
                connection_type=connection_type,
                enabled=True
            ).all()
            
            return [
                {
                    'id': str(conn.connection_id),
                    'name': conn.name,
                    'endpoint': conn.endpoint,
                    'authType': conn.auth_type,
                    'authData': conn.auth_data,
                    'interval': conn.fetch_interval
                }
                for conn in connections
            ]

db_service = DatabaseService()
