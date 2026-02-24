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

logger = get_logger(__name__, log_file="logs/web_app.log")


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
        
        system_components['ingestion'] = LogIngestion()
        system_components['preprocessor'] = LogPreprocessor()
        system_components['knowledge_manager'] = KnowledgeBaseManager()
        system_components['retrieval_system'] = RetrievalSystem(system_components['knowledge_manager'])
        system_components['llm_engine'] = LLMEngine()
        system_components['agentic_controller'] = AgenticController(
            system_components['retrieval_system'],
            system_components['llm_engine']
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
    if not system_components['initialized']:
        initialize_system()
    
    health_status = {
        'status': 'healthy' if system_components['initialized'] else 'initializing',
        'components': {
            'llm_engine': system_components['llm_engine'].check_health() if system_components['llm_engine'] else False,
            'knowledge_base': len(system_components['knowledge_manager'].documents) if system_components['knowledge_manager'] else 0,
            'preprocessor': system_components['preprocessor'] is not None,
            'agentic_controller': system_components['agentic_controller'] is not None,
            'log_sources': len(system_components['source_manager'].sources) if system_components['source_manager'] else 0
        },
        'timestamp': datetime.now().isoformat()
    }
    return jsonify(health_status)

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

# API Configuration endpoints
@app.route('/api/api-connections', methods=['GET'])
def get_api_connections():
    """Get all API connections"""
    # Mock data for now - implement actual storage later
    connections = [
        {
            'id': 'elastic-prod',
            'name': 'Production Elasticsearch',
            'type': 'elasticsearch',
            'endpoint': 'https://elastic.example.com:9200',
            'status': 'active'
        }
    ]
    return jsonify({'success': True, 'connections': connections})

@app.route('/api/api-connections', methods=['POST'])
def create_api_connection():
    """Create new API connection"""
    data = request.json
    # Implement actual storage
    return jsonify({'success': True, 'connection': data})

@app.route('/api/api-connections/<connection_id>', methods=['DELETE'])
def delete_api_connection(connection_id):
    """Delete API connection"""
    return jsonify({'success': True})

@app.route('/api/fetch-logs', methods=['POST'])
def fetch_logs_from_api():
    """Fetch logs from configured API"""
    data = request.json
    # Mock implementation - integrate with actual APIs
    logs = [
        {'timestamp': '2024-01-15T10:23:45Z', 'severity': 'ERROR', 'message': 'Sample fetched log'}
    ]
    return jsonify({'success': True, 'logs': logs})

# ==================== AI Provider Configuration API ====================

@app.route('/api/ai-providers', methods=['GET'])
def get_ai_providers():
    """Get all configured AI providers"""
    try:
        from src.utils.config_loader import config
        
        providers = {}
        for provider_name in ['openai', 'anthropic', 'gemini']:
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
        
        if provider not in ['openai', 'anthropic', 'gemini']:
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
    """Run comparative evaluation"""
    if not system_components['initialized']:
        initialize_system()
    
    try:
        data = request.json
        log_file = data.get('log_file', 'data/datasets/sample/sample_logs.log')
        max_logs = data.get('max_logs', 10)
        
        raw_logs = system_components['ingestion'].ingest_file(log_file)[:max_logs]
        parsed_logs = system_components['preprocessor'].preprocess(raw_logs)
        
        ground_truth = [log.severity in ['ERROR', 'CRITICAL', 'FATAL'] for log in parsed_logs]
        
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
            
            results.append({
                'system': system_name,
                'f1_score': result.detection_metrics.f1_score,
                'precision': result.detection_metrics.precision,
                'recall': result.detection_metrics.recall,
                'accuracy': result.detection_metrics.accuracy,
                'latency': result.efficiency_metrics.average_latency,
                'throughput': result.efficiency_metrics.throughput
            })
        
        return jsonify({
            'success': True,
            'results': results,
            'logs_analyzed': len(parsed_logs)
        })
        
    except Exception as e:
        logger.error(f"Error in evaluation: {e}")
        return jsonify({'error': str(e)}), 500

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
