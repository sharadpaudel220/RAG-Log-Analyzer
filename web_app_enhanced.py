#!/usr/bin/env python3
"""
Enhanced Flask Web Application for Agentic RAG Log Analyzer
With multi-source log ingestion capabilities
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import json
from pathlib import Path
from datetime import datetime
import threading
import time
from werkzeug.utils import secure_filename
import os

from src.input_layer.log_ingestion import LogIngestion
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
from src.utils.logger import get_logger

logger = get_logger(__name__, log_file="logs/web_app.log")

app = Flask(__name__, static_folder='web/static', template_folder='web/templates')
CORS(app)

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
    try:
        logger.info("Initializing system components...")
        
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
    except Exception as e:
        logger.error(f"Error initializing system: {e}")
        return False

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

@app.route('/api/stats')
def get_stats():
    """Get system statistics"""
    if not system_components['initialized']:
        initialize_system()
    
    stats = system_components['system_stats'].copy()
    stats['knowledge_base_size'] = len(system_components['knowledge_manager'].documents) if system_components['knowledge_manager'] else 0
    stats['recent_alerts_count'] = len(system_components['recent_alerts'])
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
            parsed_logs = system_components['preprocessor'].preprocess([formatted_log])
            if not parsed_logs:
                continue
            
            parsed_log = parsed_logs[0]
            
            # Analyze with agentic system
            result = system_components['agentic_controller'].analyze_log(parsed_log)
            
            if result.is_anomaly:
                alert = system_components['alert_generator'].generate_alert(result, parsed_log)
                anomalies.append({
                    'log': formatted_log,
                    'confidence': result.confidence,
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
        parsed_logs = system_components['preprocessor'].preprocess([formatted_log])
        
        if parsed_logs:
            result = system_components['agentic_controller'].analyze_log(parsed_logs[0])
            system_components['source_manager'].update_source_stats(source.id)
            system_components['system_stats']['total_logs_analyzed'] += 1
            
            return jsonify({
                'success': True,
                'is_anomaly': result.is_anomaly,
                'confidence': result.confidence
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
        
        # Process file
        start_time = time.time()
        raw_logs = system_components['ingestion'].ingest_file(filepath)[:max_logs]
        parsed_logs = system_components['preprocessor'].preprocess(raw_logs)
        
        # Analyze logs
        anomalies = []
        anomaly_count = 0
        
        for parsed_log in parsed_logs:
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
            
            if result.is_anomaly:
                anomaly_count += 1
                alert = system_components['alert_generator'].generate_alert(result, parsed_log) if system_type == 'agentic' else {
                    'severity': 'HIGH',
                    'description': result.explanation,
                    'explanation': result.explanation
                }
                anomalies.append({
                    'log': {'content': parsed_log.content, 'message': parsed_log.content},
                    'confidence': result.confidence,
                    'alert': alert
                })
        
        total_time = time.time() - start_time
        
        # Update stats
        system_components['system_stats']['total_logs_analyzed'] += len(parsed_logs)
        system_components['system_stats']['anomalies_detected'] += anomaly_count
        
        return jsonify({
            'success': True,
            'filename': filename,
            'total_logs': len(parsed_logs),
            'anomalies_detected': anomaly_count,
            'total_time': total_time,
            'anomalies': anomalies[:50]  # Return first 50 anomalies
        })
        
    except Exception as e:
        logger.error(f"File analysis error: {e}")
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

# ==================== Original Endpoints ====================

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
        
        raw_log = {'content': log_content, 'timestamp': datetime.now().isoformat()}
        parsed_logs = system_components['preprocessor'].preprocess([raw_log])
        
        if not parsed_logs:
            return jsonify({'error': 'Failed to parse log'}), 400
        
        parsed_log = parsed_logs[0]
        start_time = time.time()
        
        if system_type == 'agentic':
            result = system_components['agentic_controller'].analyze_log(parsed_log)
            alert = system_components['alert_generator'].generate_alert(result, parsed_log)
        elif system_type == 'rule_based':
            result = system_components['rule_based'].analyze(parsed_log)
            alert = {
                'severity': 'HIGH' if result.is_anomaly else 'INFO',
                'description': f"Rule-based detection: {'Anomaly' if result.is_anomaly else 'Normal'}",
                'confidence': result.confidence,
                'explanation': result.explanation
            }
        elif system_type == 'isolation_forest':
            result = system_components['isolation_forest'].analyze(parsed_log)
            alert = {
                'severity': 'HIGH' if result.is_anomaly else 'INFO',
                'description': f"ML-based detection: {'Anomaly' if result.is_anomaly else 'Normal'}",
                'confidence': result.confidence,
                'explanation': result.explanation
            }
        elif system_type == 'non_agentic':
            result = system_components['non_agentic_rag'].analyze(parsed_log)
            alert = {
                'severity': 'HIGH' if result.is_anomaly else 'INFO',
                'description': f"Non-Agentic RAG: {'Anomaly' if result.is_anomaly else 'Normal'}",
                'confidence': result.confidence,
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
            'confidence': result.confidence,
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
            raw_log = {'content': log_content, 'timestamp': datetime.now().isoformat()}
            parsed_logs = system_components['preprocessor'].preprocess([raw_log])
            
            if parsed_logs:
                parsed_log = parsed_logs[0]
                result = system_components['agentic_controller'].analyze_log(parsed_log)
                
                response_text = f"**Analysis Result:**\n\n"
                response_text += f"**Is Anomaly:** {'Yes' if result.is_anomaly else 'No'}\n"
                response_text += f"**Confidence:** {result.confidence:.2%}\n\n"
                
                if result.reasoning_steps:
                    response_text += "**Reasoning:**\n"
                    for i, step in enumerate(result.reasoning_steps, 1):
                        response_text += f"{i}. {step}\n"
                
                return jsonify({
                    'success': True,
                    'response': response_text,
                    'is_anomaly': result.is_anomaly,
                    'confidence': result.confidence
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
