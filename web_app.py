#!/usr/bin/env python3
"""
Flask Web Application for Agentic RAG Log Analyzer
Provides a professional dashboard and chat interface
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import json
from pathlib import Path
from datetime import datetime
import threading
import time

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
from src.utils.logger import get_logger

logger = get_logger(__name__, log_file="logs/web_app.log")

app = Flask(__name__, static_folder='web/static', template_folder='web/templates')
CORS(app)

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
    'recent_alerts': [],
    'system_stats': {
        'total_logs_analyzed': 0,
        'anomalies_detected': 0,
        'alerts_generated': 0,
        'uptime_start': datetime.now().isoformat()
    }
}

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
        
        # Setup knowledge base if needed
        if system_components['knowledge_manager'].index is None:
            system_components['knowledge_manager'].populate_default_knowledge()
        
        system_components['initialized'] = True
        logger.info("System components initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing system: {e}")
        return False

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/chat')
def chat():
    """Chat interface page"""
    return render_template('chat.html')

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
            'agentic_controller': system_components['agentic_controller'] is not None
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
    
    return jsonify(stats)

@app.route('/api/analyze', methods=['POST'])
def analyze_log():
    """Analyze a single log entry"""
    if not system_components['initialized']:
        initialize_system()
    
    try:
        data = request.json
        log_content = data.get('log_content', '')
        system_type = data.get('system', 'agentic')  # agentic, rule_based, isolation_forest, non_agentic
        
        if not log_content:
            return jsonify({'error': 'No log content provided'}), 400
        
        # Ingest and preprocess
        raw_log = {'content': log_content, 'timestamp': datetime.now().isoformat()}
        parsed_logs = system_components['preprocessor'].preprocess([raw_log])
        
        if not parsed_logs:
            return jsonify({'error': 'Failed to parse log'}), 400
        
        parsed_log = parsed_logs[0]
        
        # Analyze based on system type
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
        
        # Update stats
        system_components['system_stats']['total_logs_analyzed'] += 1
        if result.is_anomaly:
            system_components['system_stats']['anomalies_detected'] += 1
            system_components['system_stats']['alerts_generated'] += 1
            
            # Store recent alert
            alert_data = {
                'timestamp': datetime.now().isoformat(),
                'log_content': log_content,
                'severity': alert.get('severity', 'UNKNOWN'),
                'description': alert.get('description', ''),
                'system': system_type,
                'analysis_time': analysis_time
            }
            system_components['recent_alerts'].insert(0, alert_data)
            system_components['recent_alerts'] = system_components['recent_alerts'][:50]  # Keep last 50
        
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
        
        # Check if it's a log analysis request
        if any(keyword in message.lower() for keyword in ['analyze', 'check', 'error', 'log']):
            # Extract potential log content from message
            log_content = message
            
            # Analyze the log
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
        
        # General query - use LLM
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
        
        # Load and preprocess logs
        raw_logs = system_components['ingestion'].ingest_file(log_file)[:max_logs]
        parsed_logs = system_components['preprocessor'].preprocess(raw_logs)
        
        # Create ground truth
        ground_truth = [log.severity in ['ERROR', 'CRITICAL', 'FATAL'] for log in parsed_logs]
        
        # Evaluate systems
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
    print("Agentic RAG Log Analyzer - Web Interface")
    print("="*80)
    print()
    print("Initializing system...")
    
    if initialize_system():
        print("✓ System initialized successfully")
        print()
        print("Starting web server...")
        print("Dashboard: http://localhost:5001")
        print("Chat Interface: http://localhost:5001/chat")
        print()
        app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)
    else:
        print("✗ Failed to initialize system")
