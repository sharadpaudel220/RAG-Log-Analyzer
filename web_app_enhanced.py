#!/usr/bin/env python3
"""
Enhanced Flask Web Application for Agentic RAG Log Analyzer
With multi-source log ingestion capabilities
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import time
import json
from datetime import datetime
import threading
import uuid
from werkzeug.utils import secure_filename
from pathlib import Path
from dotenv import load_dotenv

# Base directory for the application
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

from src.utils.logger import get_logger
from src.input_layer.log_ingestion import RawLogEntry, LogIngestion
from src.preprocessing.log_preprocessor import LogPreprocessor
from src.knowledge_base.knowledge_manager import KnowledgeBaseManager
from src.retrieval.retrieval_system import RetrievalSystem
from src.llm_engine.llm_interface import LLMEngine
from src.agentic_controller.agentic_rag import AgenticController
from src.output_layer.alert_generator import AlertGenerator
from src.baselines.rule_based import RuleBasedSystem
from src.baselines.isolation_forest import IsolationForestSystem
from src.baselines.non_agentic_rag import NonAgenticRAGSystem
from src.evaluation.evaluator import SystemEvaluator
from src.connectors.log_sources import (
    LogSourceManager, LogSource, LogSourceType, IngestionMethod, LogFormatter
)
from src.database.config import db_config
from src.database.services import db_service
from src.utils.logger import get_logger

load_dotenv()

logger = get_logger(__name__, log_file=os.path.join(LOGS_DIR, "web_app.log"))


def _get_result_confidence(result) -> float:
    return float(getattr(result, 'confidence', getattr(result, 'confidence_score', 0.0)) or 0.0)


def _to_raw_log_entry(maybe_log) -> RawLogEntry:
    if isinstance(maybe_log, RawLogEntry):
        return maybe_log
    if isinstance(maybe_log, dict):
        content = maybe_log.get('content') or maybe_log.get('message') or str(maybe_log)
        return RawLogEntry(content=str(content), timestamp=datetime.now(), metadata=maybe_log)
    return RawLogEntry(content=str(maybe_log), timestamp=datetime.now())


def _save_analysis_session(session_id: str, data: dict):
    pass

def _load_analysis_session(session_id: str) -> dict:
    return db_service.get_session_with_details(session_id)

def _list_analysis_sessions() -> list:
    return db_service.list_sessions()

app = Flask(__name__, static_folder='web/static', template_folder='web/templates')
CORS(app)

# Disable template caching for development
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

ANALYSIS_SESSIONS_DIR = 'data/analysis_sessions'
Path(ANALYSIS_SESSIONS_DIR).mkdir(parents=True, exist_ok=True)

# Configure upload folder
UPLOAD_FOLDER = 'data/uploads'
ALLOWED_EXTENSIONS = {'log', 'txt', 'json', 'csv'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Global system components
system_components = {
    'initialized': False,
    'ingestion': None,
    'preprocessor': None,
    'knowledge_manager': None,
    'retrieval_system': None,
    'llm_engine': None,
    'agentic_controller': None,
    'alert_generator': None,
    'rule_based': None,
    'isolation_forest': None,
    'non_agentic_rag': None,
    'evaluator': None,
    'source_manager': None,
    'recent_alerts': [],
    'system_stats': {
        'total_logs_analyzed': 0,
        'anomalies_detected': 0,
        'alerts_generated': 0,
        'uptime_start': datetime.now().isoformat()
    }
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def initialize_system():
    """Initialize all system components"""
    if system_components['initialized']:
        return
    
    logger.info("Initializing system components...")
    
    # Initialize database
    logger.info("Initializing database connection...")
    if not db_config.initialize():
        logger.error("Failed to initialize database connection")
    else:
        logger.info("Database connection established")
        # Create tables if they don't exist
        try:
            from src.database.models import Base
            Base.metadata.create_all(bind=db_config.engine)
            logger.info("Database tables verified/created")
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
        
        system_components['ingestion'] = LogIngestion()
        system_components['preprocessor'] = LogPreprocessor()
        system_components['knowledge_manager'] = KnowledgeBaseManager()
        system_components['retrieval_system'] = RetrievalSystem(system_components['knowledge_manager'])
        system_components['llm_engine'] = LLMEngine()
        
        # Check that the configured LLM provider is reachable / has a key
        llm_engine = system_components['llm_engine']
        llm_ok = llm_engine.check_health()
        provider_label = (llm_engine.provider or 'unknown').lower()
        if not llm_ok:
            logger.warning(
                f"LLM provider '{provider_label}' is not ready. "
                f"For cloud providers set the matching API key in .env; "
                f"for ollama start the local server."
            )
            system_components['ollama_available'] = False
            system_components['llm_available'] = False
        else:
            logger.info(f"LLM provider '{provider_label}' ready (model: {llm_engine.model})")
            system_components['ollama_available'] = (provider_label == 'ollama')
            system_components['llm_available'] = True
        
        system_components['agentic_controller'] = AgenticController(
            system_components['retrieval_system'],
            system_components['llm_engine'],
            force_full_react=True
        )
        system_components['alert_generator'] = AlertGenerator()
        system_components['rule_based'] = RuleBasedSystem()
        system_components['isolation_forest'] = IsolationForestSystem()
        system_components['non_agentic_rag'] = NonAgenticRAGSystem(
            system_components['retrieval_system'],
            system_components['llm_engine']
        )
        system_components['evaluator'] = SystemEvaluator()
        system_components['source_manager'] = LogSourceManager()
        
        # Setup knowledge base if needed
        if system_components['knowledge_manager'].index is None:
            system_components['knowledge_manager'].populate_default_knowledge()
        
        # Add default log sources
        _setup_default_sources()
        
        system_components['initialized'] = True
        logger.info("System components initialized successfully")
        return True

def _setup_default_sources():
    """Setup default log sources"""
    source_manager = system_components['source_manager']
    
    # System logs source
    source_manager.add_source(LogSource(
        id='system-logs',
        name='System Logs',
        source_type=LogSourceType.SYSTEM,
        ingestion_method=IngestionMethod.API,
        metadata={'description': 'Operating system logs'}
    ))
    
    # Network logs source
    source_manager.add_source(LogSource(
        id='network-logs',
        name='Network Device Logs',
        source_type=LogSourceType.NETWORK,
        ingestion_method=IngestionMethod.API,
        metadata={'description': 'Router, switch, and firewall logs'}
    ))
    
    # Application logs source
    source_manager.add_source(LogSource(
        id='app-logs',
        name='Application Logs',
        source_type=LogSourceType.APPLICATION,
        ingestion_method=IngestionMethod.API,
        metadata={'description': 'Application and service logs'}
    ))
    
    # Security logs source
    source_manager.add_source(LogSource(
        id='security-logs',
        name='Security/Audit Logs',
        source_type=LogSourceType.SECURITY,
        ingestion_method=IngestionMethod.API,
        metadata={'description': 'Security events and audit trails'}
    ))

# ==================== Web Pages ====================

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/log-analyzer')
def log_analyzer():
    """Log analyzer page"""
    return render_template('log_analyzer.html')

@app.route('/analysis-history')
def analysis_history():
    """Analysis history page"""
    return render_template('analysis_history.html')

@app.route('/api-config')
def api_config():
    """API configuration page"""
    return render_template('api_config.html')

@app.route('/chat')
def chat():
    """Chat interface page"""
    return render_template('chat.html')

@app.route('/sources')
def sources():
    """Log sources management page"""
    return render_template('sources.html')

@app.route('/evaluation')
def evaluation():
    """Evaluation page"""
    return render_template('evaluation.html')

# ==================== System API ====================

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'system_initialized': system_components['initialized'],
        'ollama_available': system_components.get('ollama_available', False)
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    try:
        db_stats = db_service.get_system_stats()
        system_components['system_stats'].update(db_stats)
        return jsonify(system_components['system_stats'])
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify(system_components['system_stats'])
    stats['active_sources'] = len([s for s in system_components['source_manager'].list_sources() if s.enabled])
    stats['total_sources'] = len(system_components['source_manager'].sources)
    
    return jsonify(stats)

# ==================== Log Source Management API ====================

@app.route('/api/sources', methods=['GET'])
def list_sources():
    """List all log sources"""
    if not system_components['initialized']:
        initialize_system()
    
    source_type = request.args.get('type')
    source_manager = system_components['source_manager']
    
    if source_type:
        try:
            sources = source_manager.list_sources(LogSourceType(source_type))
        except ValueError:
            return jsonify({'error': 'Invalid source type'}), 400
    else:
        sources = source_manager.list_sources()
    
    return jsonify({
        'sources': [s.to_dict() for s in sources],
        'total': len(sources)
    })

@app.route('/api/sources', methods=['POST'])
def create_source():
    """Create a new log source"""
    if not system_components['initialized']:
        initialize_system()
    
    try:
        data = request.json
        
        source = LogSource(
            id=data.get('id'),
            name=data.get('name'),
            source_type=LogSourceType(data.get('source_type')),
            ingestion_method=IngestionMethod(data.get('ingestion_method')),
            enabled=data.get('enabled', True),
            filters=data.get('filters'),
            metadata=data.get('metadata')
        )
        
        if system_components['source_manager'].add_source(source):
            return jsonify({
                'success': True,
                'source': source.to_dict(),
                'api_key': source.api_key
            }), 201
        else:
            return jsonify({'error': 'Source already exists'}), 400
            
    except Exception as e:
        logger.error(f"Error creating source: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sources/<source_id>', methods=['GET'])
def get_source(source_id):
    """Get a specific log source"""
    if not system_components['initialized']:
        initialize_system()
    
    source = system_components['source_manager'].get_source(source_id)
    if source:
        return jsonify(source.to_dict())
    return jsonify({'error': 'Source not found'}), 404

@app.route('/api/sources/<source_id>', methods=['DELETE'])
def delete_source(source_id):
    """Delete a log source"""
    if not system_components['initialized']:
        initialize_system()
    
    if system_components['source_manager'].remove_source(source_id):
        return jsonify({'success': True})
    return jsonify({'error': 'Source not found'}), 404

@app.route('/api/sources/<source_id>/enable', methods=['POST'])
def enable_source(source_id):
    """Enable a log source"""
    if not system_components['initialized']:
        initialize_system()
    
    if system_components['source_manager'].enable_source(source_id):
        return jsonify({'success': True})
    return jsonify({'error': 'Source not found'}), 404

@app.route('/api/sources/<source_id>/disable', methods=['POST'])
def disable_source(source_id):
    """Disable a log source"""
    if not system_components['initialized']:
        initialize_system()
    
    if system_components['source_manager'].disable_source(source_id):
        return jsonify({'success': True})
    return jsonify({'error': 'Source not found'}), 404

# ==================== Log Ingestion API ====================

@app.route('/api/ingest', methods=['POST'])
def ingest_logs():
    """
    Main log ingestion endpoint - accepts logs from any source
    Requires API key authentication
    """
    if not system_components['initialized']:
        initialize_system()
    
    try:
        # Authenticate
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({'error': 'API key required'}), 401
        
        source = system_components['source_manager'].get_source_by_api_key(api_key)
        if not source or not source.enabled:
            return jsonify({'error': 'Invalid or disabled source'}), 403
        
        # Get log data
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Support both single log and batch
        logs = data if isinstance(data, list) else [data]
        
        processed_logs = []
        anomalies = []
        
        for raw_log in logs:
            # Format log based on source type
            formatted_log = LogFormatter.format_log(raw_log, source.source_type)
            
            # Preprocess
            parsed_logs = system_components['preprocessor'].preprocess([
                _to_raw_log_entry(formatted_log)
            ])
            if not parsed_logs:
                continue
            
            parsed_log = parsed_logs[0]
            
            # Analyze with agentic system
            result = system_components['agentic_controller'].analyze_log(parsed_log)
            
            if result.is_anomaly:
                alert = system_components['alert_generator'].generate_alert(result)
                anomalies.append({
                    'log': formatted_log,
                    'confidence': _get_result_confidence(result),
                    'alert': alert
                })
                
                # Store alert
                alert_data = {
                    'timestamp': datetime.now().isoformat(),
                    'log_content': formatted_log.get('content'),
                    'severity': alert.get('severity', 'UNKNOWN'),
                    'description': alert.get('description', ''),
                    'source': source.name,
                    'source_type': source.source_type.value
                }
                system_components['recent_alerts'].insert(0, alert_data)
                system_components['recent_alerts'] = system_components['recent_alerts'][:100]
                
                system_components['system_stats']['anomalies_detected'] += 1
                system_components['system_stats']['alerts_generated'] += 1
            
            processed_logs.append(formatted_log)
        
        # Update source stats
        system_components['source_manager'].update_source_stats(source.id, len(logs))
        system_components['system_stats']['total_logs_analyzed'] += len(logs)
        
        return jsonify({
            'success': True,
            'processed': len(processed_logs),
            'anomalies_detected': len(anomalies),
            'anomalies': anomalies[:10]  # Return first 10 anomalies
        })
        
    except Exception as e:
        logger.error(f"Error ingesting logs: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ingest/webhook/<source_id>', methods=['POST'])
def webhook_receiver(source_id):
    """Webhook endpoint for real-time log streaming"""
    if not system_components['initialized']:
        initialize_system()
    
    try:
        source = system_components['source_manager'].get_source(source_id)
        if not source or not source.enabled:
            return jsonify({'error': 'Invalid or disabled source'}), 403
        
        if source.ingestion_method != IngestionMethod.WEBHOOK:
            return jsonify({'error': 'Source not configured for webhooks'}), 400
        
        # Process webhook payload
        data = request.json or request.form.to_dict()
        
        # Format and process log
        formatted_log = LogFormatter.format_log(data, source.source_type)
        parsed_logs = system_components['preprocessor'].preprocess([
            _to_raw_log_entry(formatted_log)
        ])
        
        if parsed_logs:
            result = system_components['agentic_controller'].analyze_log(parsed_logs[0])
            system_components['source_manager'].update_source_stats(source.id)
            system_components['system_stats']['total_logs_analyzed'] += 1
            
            return jsonify({
                'success': True,
                'is_anomaly': result.is_anomaly,
                'confidence': _get_result_confidence(result)
            })
        
        return jsonify({'error': 'Failed to process log'}), 500
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ingest/upload', methods=['POST'])
def upload_file():
    """Upload log file for batch processing"""
    if not system_components['initialized']:
        initialize_system()
    
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type'}), 400
        
        # Get source info
        source_id = request.form.get('source_id', 'file-upload')
        source_type = request.form.get('source_type', 'custom')
        
        # Save file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Process file
        raw_logs = system_components['ingestion'].ingest_file(filepath)
        parsed_logs = system_components['preprocessor'].preprocess(raw_logs)
        
        anomaly_count = 0
        for parsed_log in parsed_logs:
            result = system_components['agentic_controller'].analyze_log(parsed_log)
            if result.is_anomaly:
                anomaly_count += 1
        
        system_components['system_stats']['total_logs_analyzed'] += len(parsed_logs)
        system_components['system_stats']['anomalies_detected'] += anomaly_count
        
        return jsonify({
            'success': True,
            'filename': filename,
            'total_logs': len(parsed_logs),
            'anomalies_detected': anomaly_count
        })
        
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze-file', methods=['POST'])
def analyze_file():
    """Analyze uploaded log file with detailed results"""
    if not system_components['initialized']:
        initialize_system()
    
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type'}), 400
        
        # Get parameters
        system_type = request.form.get('system_type', 'agentic')
        max_logs = int(request.form.get('max_logs', 100))
        
        # Save file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Read file content for database storage
        with open(filepath, 'r') as f:
            file_content = f.read()
        
        # Check if Ollama is available for Agentic RAG
        if system_type == 'agentic' and not system_components.get('ollama_available', False):
            return jsonify({'error': 'Ollama is not running. Agentic RAG requires Ollama to be running for ReAct-based log analysis. Please start Ollama and try again.'}), 503
        
        # Create database session (returns session_id as string)
        session_id = db_service.create_analysis_session(filename, system_type, file_content)
        
        # Process file
        start_time = time.time()
        raw_logs = system_components['ingestion'].ingest_file(filepath)[:max_logs]
        parsed_logs = system_components['preprocessor'].preprocess(raw_logs)
        
        # Analyze logs
        anomalies = []
        anomaly_count = 0
        total_logs = len(parsed_logs)
        
        logger.info(f"Starting {system_type} analysis of {total_logs} logs for session {session_id}")
        
        for idx, parsed_log in enumerate(parsed_logs, 1):
            if idx % 10 == 0 or idx == total_logs:
                logger.info(f"Progress: {idx}/{total_logs} logs analyzed ({int(idx/total_logs*100)}%)")
            
            # Save log entry to database
            log_id = db_service.save_log_entry(session_id, parsed_log.to_dict())
            
            if system_type == 'agentic':
                result = system_components['agentic_controller'].analyze_log(parsed_log)
            elif system_type == 'rule_based':
                result = system_components['rule_based'].analyze(parsed_log)
            elif system_type == 'isolation_forest':
                result = system_components['isolation_forest'].analyze(parsed_log)
            elif system_type == 'non_agentic':
                result = system_components['non_agentic_rag'].analyze(parsed_log)
            else:
                result = system_components['agentic_controller'].analyze_log(parsed_log)
            
            # Save anomaly to database
            anomaly_data = result.to_dict()
            anomaly_id = db_service.save_anomaly(session_id, log_id, anomaly_data)
            
            if result.is_anomaly:
                anomaly_count += 1
                
                # Generate and save alert
                if system_type == 'agentic':
                    alert = system_components['alert_generator'].generate_alert(result)
                    db_service.save_alert(session_id, anomaly_id, alert.to_dict())
                    alert_dict = alert.to_dict()
                else:
                    alert_dict = {
                        'severity': 'HIGH',
                        'description': getattr(result, 'explanation', 'Anomaly detected'),
                        'explanation': getattr(result, 'explanation', 'Anomaly detected')
                    }
                
                anomalies.append({
                    'log': {'content': parsed_log.raw_content, 'message': parsed_log.raw_content},
                    'confidence': _get_result_confidence(result),
                    'alert': alert_dict
                })
        
        total_time = time.time() - start_time
        
        # Update session stats in database
        db_service.update_session_stats(session_id, total_logs, anomaly_count, total_time)
        
        # Update system stats
        db_service.update_system_stats(
            logs_analyzed=total_logs,
            anomalies=anomaly_count,
            alerts=anomaly_count if system_type == 'agentic' else 0,
            sessions=1
        )
        system_components['system_stats']['total_logs_analyzed'] += total_logs
        system_components['system_stats']['anomalies_detected'] += anomaly_count
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'filename': filename,
            'total_logs': len(parsed_logs),
            'anomalies_detected': anomaly_count,
            'total_time': total_time,
            'anomalies': anomalies
        })
        
    except Exception as e:
        logger.error(f"File analysis error: {e}")
        return jsonify({'error': str(e)}), 500

# Analysis Session endpoints
@app.route('/api/analysis-sessions', methods=['GET'])
def get_analysis_sessions():
    """Get list of all analysis sessions"""
    try:
        sessions = _list_analysis_sessions()
        return jsonify({'success': True, 'sessions': sessions})
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analysis-sessions/<session_id>', methods=['GET'])
def get_analysis_session(session_id):
    """Get specific analysis session data"""
    try:
        session_data = _load_analysis_session(session_id)
        if session_data:
            return jsonify({'success': True, 'session': session_data})
        else:
            return jsonify({'error': 'Session not found'}), 404
    except Exception as e:
        logger.error(f"Error loading session: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analysis-sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Delete a specific analysis session"""
    try:
        db_service.delete_session(session_id)
        logger.info(f"Analysis session {session_id} deleted from database")
        return jsonify({'success': True, 'message': 'Session deleted'})
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analysis-sessions', methods=['DELETE'])
def clear_all_sessions():
    """Clear all analysis sessions"""
    try:
        db_service.delete_all_sessions()
        logger.info("All analysis sessions cleared from database")
        return jsonify({'success': True, 'message': 'All sessions cleared'})
    except Exception as e:
        logger.error(f"Error clearing sessions: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat_with_analysis():
    """Chat endpoint for asking questions about analysis"""
    if not system_components['initialized']:
        initialize_system()
    
    try:
        data = request.json
        message = data.get('message', '')
        context = data.get('context', '')
        session_id = data.get('session_id')
        history = data.get('history', [])
        
        if not message:
            return jsonify({'error': 'No message provided'}), 400
        
        # Save user message to database
        if session_id:
            db_service.save_chat_message(session_id, 'user', message, {'context': context})
        
        session_context = ''
        critical_logs_context = ''
        if session_id:
            session_data = _load_analysis_session(session_id)
            if session_data:
                session_context = f"""Analysis Session Context:
Filename: {session_data.get('filename')}
Total Logs: {session_data.get('total_logs')}
Anomalies Detected: {session_data.get('anomalies_detected')}
System Type: {session_data.get('system_type')}
"""
                # Get all critical/high severity anomalies from this session
                anomalies = session_data.get('anomalies', [])
                critical_anomalies = [a for a in anomalies if a.get('alert', {}).get('severity') in ['CRITICAL', 'HIGH']]
                
                if critical_anomalies:
                    critical_logs_context = "\n\nCritical Logs Found in This Session:\n"
                    for i, anom in enumerate(critical_anomalies[:10], 1):
                        alert = anom.get('alert', {})
                        critical_logs_context += f"\n{i}. Severity: {alert.get('severity', 'UNKNOWN')}\n"
                        critical_logs_context += f"   Title: {alert.get('title', 'N/A')}\n"
                        critical_logs_context += f"   Log: {anom.get('log', {}).get('content', '')[:200]}...\n"
        
        full_context = f"""{session_context}{critical_logs_context}
{context}

User Question: {message}"""
        
        system_prompt = """You are a specialized log analysis assistant. Your ONLY purpose is to help analyze system logs, anomalies, errors, and provide technical recommendations.

You MUST:
- Only answer questions related to log analysis, system errors, anomalies, and technical troubleshooting
- Provide specific, technical answers based on the analysis context provided
- Reference specific logs and anomalies when answering

You MUST NOT:
- Answer questions unrelated to log analysis (poems, general knowledge, casual conversation, etc.)
- If asked an off-topic question, respond: "I am designed specifically for log analysis and troubleshooting. Please ask questions related to the analyzed logs, anomalies, or system errors."

Be concise, technical, and helpful for log analysis questions only."""
        
        llm_response = system_components['llm_engine'].generate(
            prompt=full_context,
            system_prompt=system_prompt,
            temperature=0.7
        )
        
        # Save assistant response to database
        if session_id:
            db_service.save_chat_message(session_id, 'assistant', llm_response.content)
        
        return jsonify({
            'success': True,
            'response': llm_response.content
        })
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== API Configuration Endpoints ====================

@app.route('/api/api-connections', methods=['GET'])
def get_api_connections():
    """Get all API connections"""
    try:
        connections = db_service.get_all_api_connections()
        # Ensure connections is always a list
        if connections is None:
            connections = []
        return jsonify({'success': True, 'connections': connections})
    except Exception as e:
        logger.error(f"Error fetching API connections: {e}")
        # Return empty list instead of error to prevent UI errors
        return jsonify({'success': True, 'connections': [], 'warning': str(e)})

@app.route('/api/api-connections', methods=['POST'])
def create_api_connection():
    """Create new API connection"""
    try:
        data = request.json
        connection_id = db_service.create_api_connection(data)
        connection = db_service.get_api_connection(connection_id)
        return jsonify({'success': True, 'connection': connection, 'id': connection_id})
    except Exception as e:
        logger.error(f"Error creating API connection: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/api-connections/<connection_id>', methods=['PUT'])
def update_api_connection(connection_id):
    """Update API connection"""
    try:
        data = request.json
        success = db_service.update_api_connection(connection_id, data)
        if success:
            connection = db_service.get_api_connection(connection_id)
            return jsonify({'success': True, 'connection': connection})
        else:
            return jsonify({'success': False, 'error': 'Connection not found'}), 404
    except Exception as e:
        logger.error(f"Error updating API connection: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/api-connections/<connection_id>', methods=['DELETE'])
def delete_api_connection(connection_id):
    """Delete API connection"""
    try:
        success = db_service.delete_api_connection(connection_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Connection not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting API connection: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/fetch-logs', methods=['POST'])
def fetch_logs_from_api():
    """Fetch logs from configured API connection"""
    try:
        data = request.json
        connection_id = data.get('connection_id')
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        
        if not connection_id:
            return jsonify({'success': False, 'error': 'Connection ID required'}), 400
        
        # Get API connection details
        connection = db_service.get_api_connection(connection_id)
        if not connection:
            return jsonify({'success': False, 'error': 'Connection not found'}), 404
        
        # Prepare authentication headers
        headers = {'Content-Type': 'application/json'}
        auth_type = connection.get('auth_type', 'none')
        auth_data = connection.get('auth_data', {})
        
        if auth_type == 'bearer' and auth_data.get('token'):
            headers['Authorization'] = f"Bearer {auth_data['token']}"
        elif auth_type == 'apikey':
            if auth_data.get('header_name') and auth_data.get('api_key'):
                headers[auth_data['header_name']] = auth_data['api_key']
        
        # Fetch logs from the API endpoint
        import requests
        endpoint = connection.get('endpoint')
        
        # Add query parameters for time range if supported
        params = {}
        if start_time:
            params['start_time'] = start_time
        if end_time:
            params['end_time'] = end_time
        
        try:
            response = requests.get(
                endpoint,
                headers=headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                # Parse response - handle different formats
                try:
                    api_data = response.json()
                    
                    # Extract logs from response (adapt based on API structure)
                    logs = []
                    if isinstance(api_data, list):
                        logs = api_data
                    elif isinstance(api_data, dict):
                        # Try common keys
                        logs = api_data.get('logs', api_data.get('data', api_data.get('results', [api_data])))
                    
                    # Normalize log format
                    normalized_logs = []
                    for log in logs[:100]:  # Limit to 100 logs per fetch
                        if isinstance(log, dict):
                            normalized_logs.append({
                                'timestamp': log.get('timestamp', log.get('time', log.get('date', ''))),
                                'content': log.get('message', log.get('content', log.get('log', str(log)))),
                                'severity': log.get('severity', log.get('level', 'INFO'))
                            })
                        else:
                            normalized_logs.append({
                                'timestamp': '',
                                'content': str(log),
                                'severity': 'INFO'
                            })
                    
                    # Update last fetch time
                    db_service.update_api_connection(connection_id, {
                        'last_fetch_at': datetime.now().isoformat(),
                        'total_logs_fetched': connection.get('total_logs_fetched', 0) + len(normalized_logs)
                    })
                    
                    return jsonify({'success': True, 'logs': normalized_logs})
                    
                except Exception as parse_error:
                    logger.error(f"Error parsing API response: {parse_error}")
                    # Return raw response as single log entry
                    return jsonify({
                        'success': True,
                        'logs': [{
                            'timestamp': datetime.now().isoformat(),
                            'content': response.text[:1000],
                            'severity': 'INFO'
                        }]
                    })
            else:
                return jsonify({
                    'success': False,
                    'error': f'API returned status code {response.status_code}'
                }), 500
                
        except requests.exceptions.RequestException as req_error:
            logger.error(f"Error fetching logs from API: {req_error}")
            return jsonify({
                'success': False,
                'error': f'Failed to connect to API: {str(req_error)}'
            }), 500
            
    except Exception as e:
        logger.error(f"Error in fetch_logs_from_api: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== AI Provider Configuration API ====================

@app.route('/api/ai-providers', methods=['GET'])
def get_ai_providers():
    """Get all configured AI providers"""
    try:
        from src.utils.config_loader import config
        
        providers = {}
        for provider_name in ['groq', 'openai', 'anthropic', 'gemini']:
            api_key = config.get_env(f'{provider_name.upper()}_API_KEY') or config.get(f'llm.{provider_name}.api_key', '')
            model = config.get('llm.model', '') if config.get('llm.provider', '') == provider_name else ''
            base_url = config.get(f'llm.{provider_name}.base_url', '')
            is_active = config.get('llm.provider', '') == provider_name
            
            providers[provider_name] = {
                'configured': bool(api_key),
                'model': model,
                'base_url': base_url,
                'is_active': is_active
            }
        
        return jsonify({'success': True, 'providers': providers})
    except Exception as e:
        logger.error(f"Error getting AI providers: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ai-providers', methods=['POST'])
def save_ai_provider():
    """Save AI provider configuration"""
    try:
        data = request.json
        provider = data.get('provider')
        api_key = data.get('api_key')
        model = data.get('model')
        base_url = data.get('base_url', '')
        set_as_active = data.get('set_as_active', False)
        
        if not provider or not api_key or not model:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        if provider not in ['groq', 'openai', 'anthropic', 'gemini']:
            return jsonify({'success': False, 'error': 'Invalid provider'}), 400
        
        # Save to environment variables (runtime only - recommend using .env file)
        import os
        env_var_name = f'{provider.upper()}_API_KEY'
        os.environ[env_var_name] = api_key
        
        # Update config.yaml
        import yaml
        from pathlib import Path
        config_path = Path(__file__).parent / 'config' / 'config.yaml'
        
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Update provider-specific settings
        if 'llm' not in config_data:
            config_data['llm'] = {}
        if provider not in config_data['llm']:
            config_data['llm'][provider] = {}
        
        config_data['llm'][provider]['api_key'] = ''  # Don't store in config file
        if base_url:
            config_data['llm'][provider]['base_url'] = base_url
        
        # Set as active provider if requested
        if set_as_active:
            config_data['llm']['provider'] = provider
            config_data['llm']['model'] = model
            
            # Reinitialize LLM engine with new provider
            if system_components['initialized']:
                from src.llm_engine.llm_interface import LLMEngine
                system_components['llm_engine'] = LLMEngine()
                logger.info(f"LLM engine reinitialized with provider: {provider}")
        
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
        
        return jsonify({'success': True, 'message': 'AI provider configured successfully'})
        
    except Exception as e:
        logger.error(f"Error saving AI provider: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ai-providers/test', methods=['POST'])
def test_ai_provider():
    """Test AI provider connection"""
    try:
        data = request.json
        provider = data.get('provider')
        api_key = data.get('api_key')
        model = data.get('model')
        base_url = data.get('base_url', '')
        
        if not provider or not api_key or not model:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        # Create a temporary LLM engine instance for testing
        import os
        import requests
        
        # Test with a simple prompt
        test_prompt = "Say 'OK' if you can read this."
        
        if provider == 'openai':
            url = f"{base_url or 'https://api.openai.com'}/v1/chat/completions".replace('//', '/').replace('http:/', 'http://').replace('https:/', 'https://')
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            payload = {
                'model': model,
                'messages': [{'role': 'user', 'content': test_prompt}],
                'max_tokens': 10
            }
        elif provider == 'anthropic':
            url = f"{base_url or 'https://api.anthropic.com'}/v1/messages".replace('//', '/').replace('http:/', 'http://').replace('https:/', 'https://')
            headers = {
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'Content-Type': 'application/json'
            }
            payload = {
                'model': model,
                'messages': [{'role': 'user', 'content': test_prompt}],
                'max_tokens': 10
            }
        elif provider == 'gemini':
            model_name = model.replace('models/', '')
            url = f"{base_url or 'https://generativelanguage.googleapis.com'}/v1beta/models/{model_name}:generateContent".replace('//', '/').replace('http:/', 'http://').replace('https:/', 'https://')
            payload = {
                'contents': [{'role': 'user', 'parts': [{'text': test_prompt}]}],
                'generationConfig': {'maxOutputTokens': 10}
            }
            response = requests.post(url, params={'key': api_key}, json=payload, timeout=10)
        else:
            return jsonify({'success': False, 'error': 'Invalid provider'}), 400
        
        # Make the test request
        if provider != 'gemini':
            response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        response.raise_for_status()
        
        return jsonify({'success': True, 'message': 'Connection successful'})
        
    except requests.exceptions.HTTPError as e:
        error_msg = f"API error: {e.response.status_code} - {e.response.text[:200]}"
        logger.error(f"AI provider test failed: {error_msg}")
        return jsonify({'success': False, 'error': error_msg}), 200
    except Exception as e:
        logger.error(f"Error testing AI provider: {e}")
        return jsonify({'success': False, 'error': str(e)}), 200

# ==================== Log Analysis Endpoints ====================

@app.route('/api/analyze', methods=['POST'])
def analyze_log():
    """Analyze a single log entry"""
    if not system_components['initialized']:
        initialize_system()
    
    try:
        data = request.json
        log_content = data.get('log_content', '')
        system_type = data.get('system', 'agentic')
        
        if not log_content:
            return jsonify({'error': 'No log content provided'}), 400

        # Check if Ollama is available for Agentic RAG
        if system_type == 'agentic' and not system_components.get('ollama_available', False):
            return jsonify({'error': 'Ollama is not running. Agentic RAG requires Ollama to be running for ReAct-based log analysis. Please start Ollama and try again.'}), 503

        raw_log = RawLogEntry(content=log_content, timestamp=datetime.now())
        parsed_logs = system_components['preprocessor'].preprocess([raw_log])
        
        if not parsed_logs:
            return jsonify({'error': 'Failed to parse log'}), 400
        
        parsed_log = parsed_logs[0]
        start_time = time.time()
        
        if system_type == 'agentic':
            result = system_components['agentic_controller'].analyze_log(parsed_log)
            alert = system_components['alert_generator'].generate_alert(result)
        elif system_type == 'rule_based':
            result = system_components['rule_based'].analyze(parsed_log)
            alert = {
                'severity': 'HIGH' if result.is_anomaly else 'INFO',
                'description': f"Rule-based detection: {'Anomaly' if result.is_anomaly else 'Normal'}",
                'confidence': _get_result_confidence(result),
                'explanation': result.explanation
            }
        elif system_type == 'isolation_forest':
            result = system_components['isolation_forest'].analyze(parsed_log)
            alert = {
                'severity': 'HIGH' if result.is_anomaly else 'INFO',
                'description': f"ML-based detection: {'Anomaly' if result.is_anomaly else 'Normal'}",
                'confidence': _get_result_confidence(result),
                'explanation': result.explanation
            }
        elif system_type == 'non_agentic':
            result = system_components['non_agentic_rag'].analyze(parsed_log)
            alert = {
                'severity': 'HIGH' if result.is_anomaly else 'INFO',
                'description': f"Non-Agentic RAG: {'Anomaly' if result.is_anomaly else 'Normal'}",
                'confidence': _get_result_confidence(result),
                'explanation': result.explanation
            }
        else:
            return jsonify({'error': 'Invalid system type'}), 400
        
        analysis_time = time.time() - start_time
        
        system_components['system_stats']['total_logs_analyzed'] += 1
        if result.is_anomaly:
            system_components['system_stats']['anomalies_detected'] += 1
            system_components['system_stats']['alerts_generated'] += 1
            
            alert_data = {
                'timestamp': datetime.now().isoformat(),
                'log_content': log_content,
                'severity': alert.get('severity', 'UNKNOWN'),
                'description': alert.get('description', ''),
                'system': system_type,
                'analysis_time': analysis_time
            }
            system_components['recent_alerts'].insert(0, alert_data)
            system_components['recent_alerts'] = system_components['recent_alerts'][:50]
        
        response = {
            'success': True,
            'is_anomaly': result.is_anomaly,
            'confidence': _get_result_confidence(result),
            'alert': alert,
            'parsed_log': {
                'template': parsed_log.template,
                'severity': parsed_log.severity,
                'component': parsed_log.component
            },
            'analysis_time': analysis_time,
            'reasoning_steps': getattr(result, 'reasoning_steps', [])
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error analyzing log: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat_message():
    """Handle chat messages"""
    if not system_components['initialized']:
        initialize_system()
    
    try:
        data = request.json
        message = data.get('message', '')
        
        if not message:
            return jsonify({'error': 'No message provided'}), 400
        
        if any(keyword in message.lower() for keyword in ['analyze', 'check', 'error', 'log']):
            log_content = message
            raw_log = RawLogEntry(content=log_content, timestamp=datetime.now())
            parsed_logs = system_components['preprocessor'].preprocess([raw_log])
            
            if parsed_logs:
                parsed_log = parsed_logs[0]
                result = system_components['agentic_controller'].analyze_log(parsed_log)
                
                response_text = f"**Analysis Result:**\n\n"
                response_text += f"**Is Anomaly:** {'Yes' if result.is_anomaly else 'No'}\n"
                response_text += f"**Confidence:** {_get_result_confidence(result):.2%}\n\n"
                
                if result.reasoning_steps:
                    response_text += "**Reasoning:**\n"
                    for i, step in enumerate(result.reasoning_steps, 1):
                        response_text += f"{i}. {step}\n"
                
                return jsonify({
                    'success': True,
                    'response': response_text,
                    'is_anomaly': result.is_anomaly,
                    'confidence': _get_result_confidence(result)
                })
        
        response_text = "I'm the Agentic RAG Log Analyzer. I can help you analyze system logs and detect anomalies. Try sending me a log entry to analyze!"
        
        return jsonify({
            'success': True,
            'response': response_text
        })
        
    except Exception as e:
        logger.error(f"Error in chat: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/alerts')
def get_alerts():
    """Get recent alerts"""
    return jsonify({
        'alerts': system_components['recent_alerts'][:20]
    })

@app.route('/api/evaluate', methods=['POST'])
def evaluate_systems():
    """Run comparative evaluation with detailed metrics"""
    if not system_components['initialized']:
        initialize_system()
    
    try:
        data = request.json
        log_file = data.get('log_file', 'data/datasets/sample/sample_logs.log')
        max_logs = data.get('max_logs', 10)
        session_id = data.get('session_id')
        
        if session_id:
            session_data = _load_analysis_session(session_id)
            if not session_data:
                return jsonify({'error': 'Session not found'}), 404
            logger.info(f"Session data loaded: {len(session_data.get('all_logs', []))} logs, keys: {list(session_data.keys())}")
            from src.input_layer.log_ingestion import RawLogEntry
            raw_logs = []
            for log in session_data.get('all_logs', []):
                raw_logs.append(RawLogEntry(
                    content=log.get('content', log.get('raw_content', '')),
                    timestamp=datetime.now(),
                    metadata=log
                ))
            logger.info(f"Built {len(raw_logs)} raw log entries for session evaluation")
            parsed_logs = system_components['preprocessor'].preprocess(raw_logs)[:max_logs]
            logger.info(f"Preprocessed into {len(parsed_logs)} parsed log entries")
        else:
            raw_logs = system_components['ingestion'].ingest_file(log_file)[:max_logs]
            logger.info(f"Ingested {len(raw_logs)} raw log entries from file {log_file}")
            parsed_logs = system_components['preprocessor'].preprocess(raw_logs)
            logger.info(f"Preprocessed into {len(parsed_logs)} parsed log entries")
        
        if not parsed_logs:
            return jsonify({'error': 'No logs available for evaluation'}), 400
        
        ground_truth = [log.severity in ['ERROR', 'CRITICAL', 'FATAL'] for log in parsed_logs]
        total_logs = len(parsed_logs)
        
        results = []
        
        for system_name, analyzer in [
            ('Rule-Based', system_components['rule_based'].analyze),
            ('Isolation Forest', system_components['isolation_forest'].analyze),
            ('Non-Agentic RAG', system_components['non_agentic_rag'].analyze),
            ('Agentic RAG', system_components['agentic_controller'].analyze_log)
        ]:
            result = system_components['evaluator'].evaluate_system(
                system_name=system_name,
                analysis_function=analyzer,
                log_entries=parsed_logs,
                ground_truth=ground_truth
            )
            
            dm = result.detection_metrics
            em = result.efficiency_metrics
            
            results.append({
                'system': system_name,
                'f1': dm.f1_score,
                'precision': dm.precision,
                'recall': dm.recall,
                'accuracy': dm.accuracy,
                'auc_roc': dm.auc_roc,
                'auc_pr': dm.auc_pr,
                'mcc': dm.mcc,
                'latency': em.average_latency,
                'throughput': em.throughput,
                'true_positives': dm.true_positives,
                'true_negatives': dm.true_negatives,
                'false_positives': dm.false_positives,
                'false_negatives': dm.false_negatives,
                'total_time': em.total_time,
                'total_logs': total_logs
            })
        
        return jsonify({
            'success': True,
            'results': results,
            'logs_analyzed': total_logs
        })
        
    except Exception as e:
        logger.error(f"Error in evaluation: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/evaluate/benchmark', methods=['POST'])
def evaluate_benchmark():
    """Run evaluation on benchmark datasets with validated ground truth (thesis-level rigor)."""
    if not system_components['initialized']:
        initialize_system()
    
    try:
        data = request.json or {}
        dataset_name = data.get('dataset', 'hdfs')
        max_logs = data.get('max_logs', 2000)
        use_cv = data.get('use_cross_validation', False)
        n_folds = data.get('n_folds', 5)
        n_runs = data.get('n_runs', 3)
        
        # Load benchmark dataset with pre-labeled ground truth
        from src.evaluation.dataset_loader import get_dataset
        dataset = get_dataset(dataset_name, max_logs=max_logs)
        
        if not dataset:
            return jsonify({
                'error': f'Benchmark dataset "{dataset_name}" not found. Available: HDFS, BGL'
            }), 404
        
        # Preprocess logs
        parsed_logs = system_components['preprocessor'].preprocess(dataset.raw_logs)
        
        if not parsed_logs:
            return jsonify({'error': 'No logs could be preprocessed'}), 400
        
        # Use actual labeled ground truth from dataset (NOT keyword-based)
        ground_truth = dataset.ground_truth[:len(parsed_logs)]
        total_logs = len(parsed_logs)
        
        logger.info(f"Benchmark evaluation: {dataset.name}, {total_logs} logs, "
                   f"{dataset.anomaly_count} anomalies ({dataset.anomaly_ratio:.2%})")
        
        systems = [
            ('Rule-Based', system_components['rule_based'].analyze),
            ('Isolation Forest', system_components['isolation_forest'].analyze),
            ('Non-Agentic RAG', system_components['non_agentic_rag'].analyze),
            ('Agentic RAG', system_components['agentic_controller'].analyze_log)
        ]
        
        results = []
        cv_fold_scores = {}  # For statistical testing
        
        for system_name, analyzer in systems:
            if use_cv:
                # Run cross-validation for statistical robustness
                cv_result = system_components['evaluator'].evaluate_with_cross_validation(
                    system_name=system_name,
                    analysis_function=analyzer,
                    log_entries=parsed_logs,
                    ground_truth=ground_truth,
                    n_folds=n_folds,
                    n_runs=n_runs
                )
                
                # Extract mean scores for display
                agg = cv_result['aggregated_metrics']
                dm_dict = {
                    'precision': agg['precision']['mean'],
                    'recall': agg['recall']['mean'],
                    'f1_score': agg['f1_score']['mean'],
                    'accuracy': agg['accuracy']['mean'],
                    'auc_roc': agg['auc_roc']['mean'],
                    'auc_pr': agg['auc_pr']['mean'],
                    'mcc': agg['mcc']['mean'],
                    'true_positives': 0,
                    'true_negatives': 0,
                    'false_positives': 0,
                    'false_negatives': 0
                }
                em_dict = {
                    'average_latency': 0,
                    'total_time': 0,
                    'throughput': 0,
                    'memory_usage_mb': 0
                }
                
                cv_fold_scores[system_name] = agg['f1_score']['values']
                
                results.append({
                    'system': system_name,
                    'f1': agg['f1_score']['mean'],
                    'precision': agg['precision']['mean'],
                    'recall': agg['recall']['mean'],
                    'accuracy': agg['accuracy']['mean'],
                    'auc_roc': agg['auc_roc']['mean'],
                    'auc_pr': agg['auc_pr']['mean'],
                    'mcc': agg['mcc']['mean'],
                    'f1_std': agg['f1_score']['std'],
                    'f1_ci_low': agg['f1_score']['ci_95_low'],
                    'f1_ci_high': agg['f1_score']['ci_95_high'],
                    'latency': 0,
                    'throughput': 0,
                    'total_time': 0,
                    'total_logs': total_logs,
                    'is_cv': True,
                    'n_folds': n_folds,
                    'n_runs': n_runs
                })
            else:
                # Single run (faster)
                result = system_components['evaluator'].evaluate_system(
                    system_name=system_name,
                    analysis_function=analyzer,
                    log_entries=parsed_logs,
                    ground_truth=ground_truth
                )
                
                dm = result.detection_metrics
                em = result.efficiency_metrics
                
                results.append({
                    'system': system_name,
                    'f1': dm.f1_score,
                    'precision': dm.precision,
                    'recall': dm.recall,
                    'accuracy': dm.accuracy,
                    'auc_roc': dm.auc_roc,
                    'auc_pr': dm.auc_pr,
                    'mcc': dm.mcc,
                    'f1_std': 0,
                    'f1_ci_low': dm.f1_score,
                    'f1_ci_high': dm.f1_score,
                    'latency': em.average_latency,
                    'throughput': em.throughput,
                    'true_positives': dm.true_positives,
                    'true_negatives': dm.true_negatives,
                    'false_positives': dm.false_positives,
                    'false_negatives': dm.false_negatives,
                    'total_time': em.total_time,
                    'total_logs': total_logs,
                    'is_cv': False
                })
        
        # Statistical comparison (if cross-validation used)
        statistical_tests = []
        if use_cv and len(results) >= 2:
            for i in range(len(systems)):
                for j in range(i + 1, len(systems)):
                    s1_name = systems[i][0]
                    s2_name = systems[j][0]
                    if s1_name in cv_fold_scores and s2_name in cv_fold_scores:
                        test_result = system_components['evaluator'].metrics_calculator.paired_t_test(
                            cv_fold_scores[s1_name], cv_fold_scores[s2_name], alpha=0.05
                        )
                        test_result['system1'] = s1_name
                        test_result['system2'] = s2_name
                        statistical_tests.append(test_result)
        
        return jsonify({
            'success': True,
            'results': results,
            'logs_analyzed': total_logs,
            'dataset': dataset.name,
            'anomaly_count': dataset.anomaly_count,
            'anomaly_ratio': dataset.anomaly_ratio,
            'use_cross_validation': use_cv,
            'statistical_tests': statistical_tests
        })
        
    except Exception as e:
        logger.error(f"Error in benchmark evaluation: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/datasets', methods=['GET'])
def list_datasets():
    """List available benchmark datasets."""
    from src.evaluation.dataset_loader import list_available_datasets
    datasets = list_available_datasets()
    return jsonify({'success': True, 'datasets': datasets})


@app.route('/api/evaluate/ablation', methods=['POST'])
def run_ablation_study():
    """Run ablation study on Agentic RAG components using benchmark datasets."""
    if not system_components['initialized']:
        initialize_system()
    
    try:
        data = request.json or {}
        dataset_name = data.get('dataset', 'hdfs')
        max_logs = data.get('max_logs', 1000)
        
        # Load benchmark dataset with pre-labeled ground truth
        from src.evaluation.dataset_loader import get_dataset
        dataset = get_dataset(dataset_name, max_logs=max_logs)
        
        if not dataset:
            return jsonify({
                'error': f'Benchmark dataset "{dataset_name}" not found. Available: HDFS, BGL'
            }), 404
        
        # Preprocess logs
        parsed_logs = system_components['preprocessor'].preprocess(dataset.raw_logs)
        
        if not parsed_logs:
            return jsonify({'error': 'No logs could be preprocessed'}), 400
        
        ground_truth = dataset.ground_truth[:len(parsed_logs)]
        total_logs = len(parsed_logs)
        
        logger.info(f"Ablation study on {dataset.name}, {total_logs} logs")
        
        # Run ablation study
        ablation_results = system_components['evaluator'].run_ablation_study(
            base_controller=system_components['agentic_controller'],
            log_entries=parsed_logs,
            ground_truth=ground_truth
        )
        
        return jsonify({
            'success': True,
            'dataset': dataset.name,
            'logs_analyzed': total_logs,
            'anomaly_count': dataset.anomaly_count,
            'anomaly_ratio': dataset.anomaly_ratio,
            'full_system_f1': ablation_results['full_system_f1'],
            'ablation_results': ablation_results['ablation_results'],
            'total_variants': ablation_results['total_variants']
        })
        
    except Exception as e:
        logger.error(f"Error in ablation study: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/evaluate/qualitative', methods=['POST'])
def evaluate_qualitative():
    """Run qualitative analysis with sample predictions and explanations (thesis-level explainability)."""
    if not system_components['initialized']:
        initialize_system()
    
    try:
        data = request.json or {}
        dataset_name = data.get('dataset', 'hdfs')
        system_name = data.get('system', 'Agentic RAG')
        max_logs = data.get('max_logs', 200)
        max_examples = data.get('max_examples', 10)
        
        # Load benchmark dataset
        from src.evaluation.dataset_loader import get_dataset
        dataset = get_dataset(dataset_name, max_logs=max_logs)
        
        if not dataset:
            return jsonify({
                'error': f'Benchmark dataset "{dataset_name}" not found. Available: HDFS, BGL'
            }), 404
        
        parsed_logs = system_components['preprocessor'].preprocess(dataset.raw_logs)
        if not parsed_logs:
            return jsonify({'error': 'No logs could be preprocessed'}), 400
        
        ground_truth = dataset.ground_truth[:len(parsed_logs)]
        
        # Map system name to analyzer
        analyzers = {
            'Rule-Based': system_components['rule_based'].analyze,
            'Isolation Forest': system_components['isolation_forest'].analyze,
            'Non-Agentic RAG': system_components['non_agentic_rag'].analyze,
            'Agentic RAG': system_components['agentic_controller'].analyze_log
        }
        
        analyzer = analyzers.get(system_name)
        if not analyzer:
            return jsonify({'error': f'Unknown system: {system_name}'}), 400
        
        result = system_components['evaluator'].evaluate_with_explanations(
            system_name=system_name,
            analysis_function=analyzer,
            log_entries=parsed_logs,
            ground_truth=ground_truth,
            max_examples=max_examples
        )
        
        return jsonify({
            'success': True,
            'system_name': result['system_name'],
            'dataset': dataset.name,
            'total_logs': result['total_logs'],
            'detection_metrics': result['detection_metrics'],
            'examples': result['examples']
        })
        
    except Exception as e:
        logger.error(f"Error in qualitative evaluation: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== Full Dissertation Evaluation ====================

import threading as _eval_threading

_full_eval_thread = None
_full_eval_lock = _eval_threading.Lock()


def _run_full_eval_in_background(max_logs):
    """Background runner for the full dissertation evaluation pipeline."""
    try:
        from run_full_evaluation import run_full_evaluation
        run_full_evaluation(max_logs_per_dataset=max_logs)
    except Exception as exc:
        logger.error(f"Full evaluation crashed: {exc}", exc_info=True)
        try:
            import json as _j
            from pathlib import Path as _P
            status_path = _P('evaluation_status.json')
            state = {}
            if status_path.exists():
                state = _j.loads(status_path.read_text())
            state['state'] = 'error'
            state['message'] = f'Crashed: {exc}'
            status_path.write_text(_j.dumps(state, indent=2, default=str))
        except Exception:
            pass


@app.route('/api/evaluation/full/start', methods=['POST'])
def start_full_evaluation():
    """Kick off the full dissertation evaluation in a background thread."""
    global _full_eval_thread
    with _full_eval_lock:
        if _full_eval_thread is not None and _full_eval_thread.is_alive():
            return jsonify({'success': False, 'error': 'Evaluation already running'}), 409
        data = request.json or {}
        max_logs = data.get('max_logs')  # None = full dataset
        # Wipe checkpoint if user requested a fresh run
        if data.get('reset', True):
            for fname in ('evaluation_status.json', 'evaluation_checkpoint.json'):
                try:
                    p = os.path.join(os.path.dirname(__file__), fname)
                    if os.path.exists(p):
                        os.remove(p)
                except Exception:
                    pass
        _full_eval_thread = _eval_threading.Thread(
            target=_run_full_eval_in_background, args=(max_logs,), daemon=True
        )
        _full_eval_thread.start()
        return jsonify({'success': True, 'message': 'Full evaluation started'})


@app.route('/api/evaluation/full/status', methods=['GET'])
def full_evaluation_status():
    """Return the current evaluation status (polled by the UI)."""
    status_path = os.path.join(os.path.dirname(__file__), 'evaluation_status.json')
    if not os.path.exists(status_path):
        return jsonify({'state': 'idle', 'percent': 0})
    try:
        with open(status_path, 'r') as f:
            return jsonify(json.load(f))
    except Exception as exc:
        return jsonify({'state': 'error', 'message': str(exc)}), 500


@app.route('/api/evaluation/full/results', methods=['GET'])
def full_evaluation_results():
    """Return parsed dissertation_results.json."""
    results_path = os.path.join(os.path.dirname(__file__), 'evaluation_results.json')
    if not os.path.exists(results_path):
        return jsonify({'error': 'No results yet. Run evaluation first.'}), 404
    try:
        with open(results_path, 'r') as f:
            return jsonify(json.load(f))
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@app.route('/api/evaluation/full/download/<filename>', methods=['GET'])
def full_evaluation_download(filename):
    """Serve one of the four output artifacts for download."""
    allowed = {
        'evaluation_results.json',
        'evaluation_metrics.csv',
        'evaluation_report.txt',
        'evaluation_run_log.txt',
    }
    if filename not in allowed:
        return jsonify({'error': 'Invalid file'}), 400
    path = os.path.join(os.path.dirname(__file__), filename)
    if not os.path.exists(path):
        return jsonify({'error': 'File not generated yet'}), 404
    from flask import send_file
    return send_file(path, as_attachment=True, download_name=filename)


@app.route('/api/evaluation/full/stop', methods=['POST'])
def stop_full_evaluation():
    """Soft-stop: marks status as cancelled. Background thread continues but
    the next checkpoint flush will reflect the cancel and the UI will stop polling."""
    status_path = os.path.join(os.path.dirname(__file__), 'evaluation_status.json')
    try:
        if os.path.exists(status_path):
            with open(status_path, 'r') as f:
                state = json.load(f)
            state['state'] = 'cancelled'
            state['message'] = 'Cancelled by user'
            with open(status_path, 'w') as f:
                json.dump(state, f, indent=2, default=str)
        return jsonify({'success': True})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


# ==================== Network Capture API ====================

# Global network capture instance
network_capture_instance = None

@app.route('/api/network-capture/test', methods=['POST'])
def test_network_capture():
    """Test network capture capability"""
    try:
        data = request.json or {}
        interface = data.get('interface', 'en0')
        
        # Check if tcpdump is available
        import subprocess
        try:
            subprocess.run(['which', 'tcpdump'], check=True, capture_output=True)
            return jsonify({
                'success': True,
                'message': f'Network capture is available. Interface: {interface}',
                'requires_sudo': True
            })
        except subprocess.CalledProcessError:
            return jsonify({
                'success': False,
                'error': 'tcpdump not found. Please ensure tcpdump is installed.'
            }), 400
            
    except Exception as e:
        logger.error(f"Error testing network capture: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/network-capture/start', methods=['POST'])
def start_network_capture():
    """Start network packet capture"""
    global network_capture_instance
    
    if not system_components['initialized']:
        initialize_system()
    
    try:
        if network_capture_instance and hasattr(network_capture_instance, 'capture'):
            if network_capture_instance.capture.running:
                return jsonify({'error': 'Network capture already running'}), 400
        
        data = request.json or {}
        interface = data.get('interface', 'en0')
        filter_expr = data.get('filter', 'tcp or udp or icmp')
        auto_analyze = data.get('auto_analyze', True) in (True, 'true', 'True', 'yes', 1, '1')
        store_logs = data.get('store_logs', True) in (True, 'true', 'True', 'yes', 1, '1')

        # Create dynamic log file name
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        network_log_filename = os.path.join(LOGS_DIR, f"network_logs_{timestamp}.log")

        # Import network capture module
        from src.connectors.network_capture import NetworkLogCollector

        # Open log file if store_logs is enabled
        network_log_file = None
        if store_logs:
            os.makedirs(LOGS_DIR, exist_ok=True)
            network_log_file = open(network_log_filename, 'a')

        # Define callback for captured logs
        def on_network_log(log_entry):
            try:
                # Write to log file if enabled
                if network_log_file:
                    log_line = f"{log_entry.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))} - {log_entry.get('severity', 'INFO')} - {log_entry.get('content', '')}\n"
                    network_log_file.write(log_line)
                    network_log_file.flush()
                    os.fsync(network_log_file.fileno())

                if auto_analyze and system_components['agentic_controller']:
                    # Analyze the log
                    raw_log = _to_raw_log_entry(log_entry)
                    parsed_logs = system_components['preprocessor'].preprocess([raw_log])

                    if parsed_logs:
                        result = system_components['agentic_controller'].analyze_log(parsed_logs[0])
                        system_components['system_stats']['total_logs_analyzed'] += 1

                        if result.is_anomaly:
                            system_components['system_stats']['anomalies_detected'] += 1

                            # Generate alert if needed
                            if result.severity in ['CRITICAL', 'HIGH']:
                                alert = system_components['alert_generator'].generate_alert(result)
                                system_components['recent_alerts'].insert(0, alert)
                                system_components['system_stats']['alerts_generated'] += 1

                                # Keep only last 100 alerts
                                if len(system_components['recent_alerts']) > 100:
                                    system_components['recent_alerts'] = system_components['recent_alerts'][:100]
            except Exception as e:
                logger.error(f"Error processing network log: {e}")
        
        # Create and start collector
        network_capture_instance = NetworkLogCollector(
            interface=interface,
            filter_expression=filter_expr,
            log_callback=on_network_log if auto_analyze or store_logs else None
        )

        # Store log file reference in the instance
        network_capture_instance.log_file = network_log_file
        network_capture_instance.log_filename = network_log_filename

        network_capture_instance.start()

        logger.info(f"Network capture started on {interface}, saving to {network_log_filename}")

        return jsonify({
            'success': True,
            'message': f'Network capture started on interface {interface}',
            'interface': interface,
            'filter': filter_expr,
            'log_file': network_log_filename if store_logs else None
        })
        
    except PermissionError:
        return jsonify({
            'error': 'Permission denied. Network capture requires root/sudo privileges.',
            'help': 'Please run the web application with sudo or grant tcpdump permissions.'
        }), 403
    except Exception as e:
        logger.error(f"Error starting network capture: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/network-capture/stop', methods=['POST'])
def stop_network_capture():
    """Stop network packet capture"""
    global network_capture_instance

    try:
        if not network_capture_instance:
            return jsonify({'error': 'Network capture not running'}), 400

        stats = network_capture_instance.get_stats()

        # Stop capture first so callback isn't called anymore
        network_capture_instance.stop()

        # Close log file safely after capture stops
        try:
            if hasattr(network_capture_instance, 'log_file') and network_capture_instance.log_file:
                network_capture_instance.log_file.flush()
                network_capture_instance.log_file.close()
                logger.info(f"Closed network capture log file: {network_capture_instance.log_filename}")
        except Exception as close_err:
            logger.warning(f"Error closing network log file: {close_err}")

        network_capture_instance = None  # Clear the global instance

        logger.info("Network capture stopped")

        return jsonify({
            'success': True,
            'message': 'Network capture stopped',
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error stopping network capture: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/network-capture/stats', methods=['GET'])
def get_network_capture_stats():
    """Get network capture statistics"""
    global network_capture_instance
    
    try:
        if not network_capture_instance:
            return jsonify({
                'running': False,
                'packets_captured': 0,
                'logs_generated': 0
            })
        
        stats = network_capture_instance.get_stats()
        stats['running'] = network_capture_instance.capture.running if hasattr(network_capture_instance, 'capture') else False
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting network capture stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/network-capture/status', methods=['GET'])
def get_network_capture_status():
    """Get network capture status"""
    global network_capture_instance
    
    try:
        if not network_capture_instance:
            return jsonify({'running': False})
        
        running = network_capture_instance.capture.running if hasattr(network_capture_instance, 'capture') else False
        
        return jsonify({
            'running': running,
            'stats': network_capture_instance.get_stats() if running else {}
        })
        
    except Exception as e:
        logger.error(f"Error getting network capture status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/network-capture/logs', methods=['GET'])
def get_network_capture_logs():
    """Get captured network logs for analysis from the dynamic log file"""
    global network_capture_instance

    try:
        # Check if network capture is running or has been stopped
        if not network_capture_instance:
            # Try to find the most recent network capture log file
            logs_dir = LOGS_DIR
            if not os.path.exists(logs_dir):
                logger.warning("Logs directory not found")
                return jsonify({
                    'error': 'No network capture logs found. Please start network capture first.',
                    'logs': [],
                    'count': 0
                }), 400

            # Find the most recent network_logs_*.log file
            network_log_files = [f for f in os.listdir(logs_dir) if f.startswith('network_logs_') and f.endswith('.log')]
            if not network_log_files:
                logger.warning("No network capture log files found")
                return jsonify({
                    'error': 'No network capture logs found. Please start network capture first.',
                    'logs': [],
                    'count': 0
                }), 400

            # Sort by modification time and get the most recent
            network_log_files.sort(key=lambda f: os.path.getmtime(os.path.join(logs_dir, f)), reverse=True)
            log_file_path = os.path.join(logs_dir, network_log_files[0])
        else:
            # Use the current network capture log file
            log_file_path = network_capture_instance.log_filename if hasattr(network_capture_instance, 'log_filename') else None
            has_file = log_file_path and os.path.exists(log_file_path)
            
            # If log file exists, read from file (primary source)
            if has_file:
                try:
                    with open(log_file_path, 'r', errors='ignore') as f:
                        lines = f.readlines()
                except Exception as e:
                    logger.error(f"Error reading network capture log file: {e}")
                    return jsonify({
                        'error': f'Error reading log file: {str(e)}',
                        'logs': [],
                        'count': 0
                    }), 500
            # If no log file but capture is running, fall back to in-memory logs
            elif hasattr(network_capture_instance, 'recent_logs') and network_capture_instance.recent_logs:
                logger.info(f"No log file on disk; returning {len(network_capture_instance.recent_logs)} in-memory network logs")
                return jsonify({
                    'logs': network_capture_instance.recent_logs,
                    'count': len(network_capture_instance.recent_logs),
                    'source': 'network-capture-memory'
                })
            elif hasattr(network_capture_instance, 'collected_logs') and network_capture_instance.collected_logs:
                logger.info(f"No log file on disk; returning {len(network_capture_instance.collected_logs)} in-memory network logs")
                return jsonify({
                    'logs': network_capture_instance.collected_logs,
                    'count': len(network_capture_instance.collected_logs),
                    'source': 'network-capture-memory'
                })
            else:
                logger.warning(f"Network capture log file not found: {log_file_path}")
                return jsonify({
                    'error': 'Network capture log file not found. Please start network capture first.',
                    'logs': [],
                    'count': 0
                }), 400
            
            # Get last 100 lines or all if less
            recent_lines = lines[-100:] if len(lines) > 100 else lines
            
            for line in recent_lines:
                line = line.strip()
                if not line:
                    continue
                
                # Parse log line format: "2026-03-15 20:46:03 - __main__ - INFO - Network capture started on en0"
                try:
                    parts = line.split(' - ', 3)
                    if len(parts) >= 4:
                        timestamp = parts[0]
                        module = parts[1]
                        severity = parts[2]
                        content = parts[3]
                        
                        formatted_logs.append({
                            'timestamp': timestamp,
                            'content': line,  # Use full line as content
                            'severity': severity,
                            'source': 'network-capture',
                            'module': module
                        })
                    else:
                        # If parsing fails, use the whole line
                        formatted_logs.append({
                            'timestamp': '',
                            'content': line,
                            'severity': 'INFO',
                            'source': 'network-capture'
                        })
                except Exception as parse_error:
                    logger.warning(f"Failed to parse log line: {line[:50]}... Error: {parse_error}")
                    # Still include the line even if parsing fails
                    formatted_logs.append({
                        'timestamp': '',
                        'content': line,
                        'severity': 'INFO',
                        'source': 'network-capture'
                    })
            
            # Check if we have any formatted logs
            if len(formatted_logs) == 0:
                logger.warning("No valid logs found in file")
                return jsonify({
                    'error': 'No valid logs found. The log file exists but contains no parseable log entries.',
                    'logs': [],
                    'count': 0
                }), 400
            
            logger.info(f"Successfully read {len(formatted_logs)} logs from {log_file_path}")
            
            return jsonify({
                'logs': formatted_logs,
                'count': len(formatted_logs),
                'source_file': log_file_path
            })
            
    except Exception as e:
        logger.error(f"Error getting network capture logs: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
            'logs': [],
            'count': 0
        }), 500

# ==================== System Log Capture ====================

# Global system log capture instance
system_log_capture_instance = None

def capture_system_logs_thread():
    """Background thread that reads system logs from source directory and writes to capture file"""
    global system_log_capture_instance

    first_run = True

    while system_log_capture_instance and system_log_capture_instance.get('running', False):
        try:
            instance = system_log_capture_instance
            if not instance or not instance.get('running', False):
                break

            log_directory = instance['log_directory']
            file_pattern = instance['file_pattern']
            log_file = instance['log_file']
            max_lines = int(instance['max_lines'])

            all_lines = []
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if first_run:
                # Always write a startup entry on first run
                all_lines.append(f"=== System Log Capture Started at {timestamp} ===")
                all_lines.append(f"Watching: {log_directory}/{file_pattern}")

            # Find and read matching log files
            import glob
            search_pattern = os.path.join(log_directory, file_pattern)
            log_files = glob.glob(search_pattern)

            if not log_files:
                logger.warning(f"No log files found in {log_directory} matching {file_pattern}")
            else:
                for log_file_path in log_files:
                    try:
                        with open(log_file_path, 'r', errors='ignore') as f:
                            lines = f.readlines()
                            all_lines.extend([line.strip() for line in lines if line.strip()])
                    except Exception as e:
                        logger.warning(f"Could not read log file {log_file_path}: {e}")

            # Limit lines and write to file
            if len(all_lines) > max_lines:
                all_lines = all_lines[-max_lines:]

            if all_lines:
                if not first_run:
                    log_file.write(f"\n=== Capture at {timestamp} ===\n")
                for line in all_lines:
                    log_file.write(line + '\n')
                log_file.flush()
                os.fsync(log_file.fileno())
                logger.info(f"Wrote {len(all_lines)} lines to system log capture file")

            first_run = False

            # Wait for refresh interval
            import time
            time.sleep(int(instance['refresh_interval']))

        except Exception as e:
            logger.error(f"Error in system log capture thread: {e}", exc_info=True)
            import time
            time.sleep(2)

    logger.info("System log capture thread stopped")

@app.route('/api/system-log/start', methods=['POST'])
def start_system_log_capture():
    """Start system log capture"""
    global system_log_capture_instance

    if not system_components['initialized']:
        initialize_system()

    try:
        if system_log_capture_instance:
            return jsonify({'error': 'System log capture already running'}), 400

        data = request.json or {}
        log_directory = data.get('log_directory', '/var/log')
        file_pattern = data.get('file_pattern', '*.log')
        refresh_interval = int(data.get('refresh_interval', 1))
        max_lines = int(data.get('max_lines', 100))

        # Create dynamic log file name
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        system_log_filename = os.path.join(LOGS_DIR, f"system_logs_{timestamp}.log")

        # Open log file
        os.makedirs(LOGS_DIR, exist_ok=True)
        system_log_file = open(system_log_filename, 'a')

        # Create system log capture instance
        system_log_capture_instance = {
            'log_directory': log_directory,
            'file_pattern': file_pattern,
            'refresh_interval': refresh_interval,
            'max_lines': max_lines,
            'log_file': system_log_file,
            'log_filename': system_log_filename,
            'running': True,
            'started_at': datetime.now()
        }

        # Start background capture thread
        capture_thread = threading.Thread(target=capture_system_logs_thread, daemon=True)
        system_log_capture_instance['thread'] = capture_thread
        capture_thread.start()

        logger.info(f"System log capture started, saving to {system_log_filename}")

        return jsonify({
            'success': True,
            'message': f'System log capture started for {log_directory}',
            'log_directory': log_directory,
            'file_pattern': file_pattern,
            'log_file': system_log_filename
        })

    except Exception as e:
        logger.error(f"Error starting system log capture: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/system-log/stop', methods=['POST'])
def stop_system_log_capture():
    """Stop system log capture"""
    global system_log_capture_instance

    try:
        if not system_log_capture_instance:
            return jsonify({'error': 'System log capture not running'}), 400

        # Signal the thread to stop
        system_log_capture_instance['running'] = False

        # Wait for thread to finish (up to 5 seconds)
        thread = system_log_capture_instance.get('thread')
        if thread and thread.is_alive():
            thread.join(timeout=5)
            if thread.is_alive():
                logger.warning("System log capture thread did not exit in time")

        # Close log file safely
        try:
            log_file = system_log_capture_instance.get('log_file')
            if log_file:
                log_file.flush()
                log_file.close()
                logger.info(f"Closed system log capture file: {system_log_capture_instance['log_filename']}")
        except Exception as close_err:
            logger.warning(f"Error closing system log file: {close_err}")

        system_log_capture_instance = None

        logger.info("System log capture stopped")

        return jsonify({
            'success': True,
            'message': 'System log capture stopped'
        })

    except Exception as e:
        logger.error(f"Error stopping system log capture: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/system-log/status', methods=['GET'])
def get_system_log_status():
    """Get system log capture status"""
    global system_log_capture_instance

    try:
        if not system_log_capture_instance:
            return jsonify({'running': False})

        return jsonify({
            'running': system_log_capture_instance['running'],
            'log_directory': system_log_capture_instance['log_directory'],
            'file_pattern': system_log_capture_instance['file_pattern'],
            'started_at': system_log_capture_instance['started_at'].isoformat() if system_log_capture_instance.get('started_at') else None
        })

    except Exception as e:
        logger.error(f"Error getting system log status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/system-log/logs', methods=['GET'])
def get_system_logs():
    """Get captured system logs for analysis from the dynamic log file"""
    global system_log_capture_instance

    try:
        # Check if system log capture is running or has been stopped
        if not system_log_capture_instance:
            # Try to find the most recent system log capture file
            logs_dir = LOGS_DIR
            if not os.path.exists(logs_dir):
                logger.warning("Logs directory not found")
                return jsonify({
                    'error': 'No system log capture logs found. Please start system log capture first.',
                    'logs': [],
                    'count': 0
                }), 400

            # Find the most recent system_logs_*.log file
            system_log_files = [f for f in os.listdir(logs_dir) if f.startswith('system_logs_') and f.endswith('.log')]
            if not system_log_files:
                logger.warning("No system log capture files found")
                return jsonify({
                    'error': 'No system log capture logs found. Please start system log capture first.',
                    'logs': [],
                    'count': 0
                }), 400

            # Sort by modification time and get the most recent
            system_log_files.sort(key=lambda f: os.path.getmtime(os.path.join(logs_dir, f)), reverse=True)
            log_file_path = os.path.join(logs_dir, system_log_files[0])
        else:
            # Use the current system log capture file
            log_file_path = system_log_capture_instance.get('log_filename')
            if not log_file_path or not os.path.exists(log_file_path):
                logger.warning(f"System log capture file not found: {log_file_path}")
                return jsonify({
                    'error': 'System log capture file not found. Please start system log capture first.',
                    'logs': [],
                    'count': 0
                }), 400

        # Read and parse log file
        formatted_logs = []
        try:
            with open(log_file_path, 'r') as f:
                lines = f.readlines()

            # Check if file is empty
            if not lines or len(lines) == 0:
                logger.warning("System log file is empty")
                return jsonify({
                    'error': 'No logs captured yet. Please wait for system logs to be collected.',
                    'logs': [],
                    'count': 0
                }), 400

            # Get last 100 lines or all if less
            recent_lines = lines[-100:] if len(lines) > 100 else lines

            for line in recent_lines:
                line = line.strip()
                if line:
                    formatted_logs.append({
                        'timestamp': '',
                        'content': line,
                        'severity': 'INFO',
                        'source': 'system-log'
                    })

            logger.info(f"Successfully read {len(formatted_logs)} logs from {log_file_path}")

            return jsonify({
                'logs': formatted_logs,
                'count': len(formatted_logs),
                'source_file': log_file_path
            })

        except Exception as read_error:
            logger.error(f"Error reading system log file: {read_error}", exc_info=True)
            return jsonify({
                'error': f'Error reading system log file: {str(read_error)}',
                'logs': [],
                'count': 0
            }), 500

    except Exception as e:
        logger.error(f"Error getting system logs: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
            'logs': [],
            'count': 0
        }), 500


if __name__ == '__main__':
    print("="*80)
    print("Agentic RAG Log Analyzer - Enhanced Web Interface")
    print("="*80)
    print()
    print("Initializing system...")
    
    if initialize_system():
        print("✓ System initialized successfully")
        print()
        print("Starting web server...")
        print("Dashboard: http://localhost:5001")
        print("Chat Interface: http://localhost:5001/chat")
        print("Log Sources: http://localhost:5001/sources")
        print()
        print("API Endpoints:")
        print("  POST /api/ingest - Ingest logs with API key")
        print("  POST /api/ingest/webhook/<source_id> - Webhook receiver")
        print("  POST /api/ingest/upload - File upload")
        print("  GET  /api/sources - List log sources")
        print("  POST /api/sources - Create log source")
        print()
        app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)
    else:
        print("✗ Failed to initialize system")
