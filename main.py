#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

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
from src.evaluation.visualizer import ResultVisualizer
from src.utils.logger import get_logger
from src.utils.config_loader import config

logger = get_logger(__name__, log_file="logs/main.log")

class LogAnalyzerPipeline:
    def __init__(self):
        logger.info("Initializing Log Analyzer Pipeline...")
        
        self.ingestion = LogIngestion()
        self.preprocessor = LogPreprocessor()
        self.knowledge_manager = KnowledgeBaseManager()
        self.retrieval_system = RetrievalSystem(self.knowledge_manager)
        self.llm_engine = LLMEngine()
        self.agentic_controller = AgenticController(self.retrieval_system, self.llm_engine)
        self.alert_generator = AlertGenerator()
        
        self.rule_based = RuleBasedSystem()
        self.isolation_forest = IsolationForestSystem()
        self.non_agentic_rag = NonAgenticRAGSystem(self.retrieval_system, self.llm_engine)
        
        self.evaluator = SystemEvaluator()
        self.visualizer = ResultVisualizer()
        
        logger.info("Pipeline initialized successfully")
    
    def setup_knowledge_base(self, force_rebuild: bool = False):
        logger.info("Setting up knowledge base...")
        
        if force_rebuild or self.knowledge_manager.index is None:
            logger.info("Populating knowledge base with default documents")
            self.knowledge_manager.populate_default_knowledge()
        else:
            logger.info(f"Knowledge base already exists with {len(self.knowledge_manager.documents)} documents")
        
        stats = self.knowledge_manager.get_statistics()
        logger.info(f"Knowledge base statistics: {stats}")
    
    def analyze_logs_agentic(self, log_file: str, output_dir: str = "results"):
        logger.info(f"Starting Agentic RAG analysis on {log_file}")
        
        raw_logs = self.ingestion.ingest_file(log_file)
        logger.info(f"Ingested {len(raw_logs)} raw log entries")
        
        parsed_logs = self.preprocessor.preprocess(raw_logs)
        logger.info(f"Parsed {len(parsed_logs)} log entries")
        
        analysis_results = []
        for i, log_entry in enumerate(parsed_logs):
            if i % 10 == 0:
                logger.info(f"Processing log {i+1}/{len(parsed_logs)}")
            
            result = self.agentic_controller.analyze_log(log_entry)
            analysis_results.append(result)
        
        alerts = self.alert_generator.generate_alerts_batch(analysis_results)
        logger.info(f"Generated {len(alerts)} alerts")
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        self.alert_generator.save_alerts(alerts, str(output_path / "agentic_alerts.json"))
        
        for i, alert in enumerate(alerts[:5]):
            logger.info(f"\n{alert.to_human_readable()}")
        
        return analysis_results, alerts
    
    def run_comparative_evaluation(self, log_file: str, ground_truth_file: str = None):
        logger.info("Starting comparative evaluation...")
        
        raw_logs = self.ingestion.ingest_file(log_file)
        parsed_logs = self.preprocessor.preprocess(raw_logs)
        
        if ground_truth_file:
            ground_truth = self._load_ground_truth(ground_truth_file)
        else:
            ground_truth = self._generate_synthetic_ground_truth(parsed_logs)
        
        logger.info(f"Evaluating on {len(parsed_logs)} log entries")
        
        self.isolation_forest.train(parsed_logs[:int(len(parsed_logs) * 0.7)])
        
        results = []
        
        logger.info("Evaluating Rule-Based System...")
        rule_based_result = self.evaluator.evaluate_system(
            system_name="Rule-Based",
            analysis_function=self.rule_based.analyze,
            log_entries=parsed_logs,
            ground_truth=ground_truth,
            additional_info={'type': 'baseline'}
        )
        results.append(rule_based_result)
        
        logger.info("Evaluating Isolation Forest System...")
        isolation_forest_result = self.evaluator.evaluate_system(
            system_name="Isolation Forest",
            analysis_function=self.isolation_forest.analyze,
            log_entries=parsed_logs,
            ground_truth=ground_truth,
            additional_info={'type': 'baseline'}
        )
        results.append(isolation_forest_result)
        
        logger.info("Evaluating Non-Agentic RAG System...")
        non_agentic_result = self.evaluator.evaluate_system(
            system_name="Non-Agentic RAG",
            analysis_function=self.non_agentic_rag.analyze,
            log_entries=parsed_logs,
            ground_truth=ground_truth,
            additional_info={'type': 'baseline'}
        )
        results.append(non_agentic_result)
        
        logger.info("Evaluating Agentic RAG System...")
        agentic_result = self.evaluator.evaluate_system(
            system_name="Agentic RAG",
            analysis_function=self.agentic_controller.analyze_log,
            log_entries=parsed_logs,
            ground_truth=ground_truth,
            additional_info={'type': 'proposed'}
        )
        results.append(agentic_result)
        
        self.evaluator.generate_report(results, "results/evaluation_report.json")
        
        self.visualizer.generate_all_plots(results)
        
        logger.info("Comparative evaluation completed!")
        
        return results
    
    def _load_ground_truth(self, ground_truth_file: str):
        import json
        with open(ground_truth_file, 'r') as f:
            data = json.load(f)
        return data.get('labels', [])
    
    def _generate_synthetic_ground_truth(self, parsed_logs):
        ground_truth = []
        
        for log in parsed_logs:
            is_anomaly = False
            
            if log.severity in ['ERROR', 'CRITICAL', 'FATAL']:
                is_anomaly = True
            
            error_keywords = ['error', 'exception', 'failed', 'failure', 'critical']
            if any(keyword in log.raw_content.lower() for keyword in error_keywords):
                is_anomaly = True
            
            ground_truth.append(is_anomaly)
        
        logger.info(f"Generated synthetic ground truth: {sum(ground_truth)}/{len(ground_truth)} anomalies")
        return ground_truth
    
    def check_system_health(self):
        logger.info("Checking system health...")
        
        health_status = {
            'llm_engine': self.llm_engine.check_health(),
            'knowledge_base': len(self.knowledge_manager.documents) > 0,
            'vector_index': self.knowledge_manager.index is not None
        }
        
        for component, status in health_status.items():
            logger.info(f"{component}: {'✓ OK' if status else '✗ FAILED'}")
        
        return all(health_status.values())

def main():
    parser = argparse.ArgumentParser(description="Agentic RAG Log Analyzer")
    parser.add_argument('command', choices=['analyze', 'evaluate', 'setup', 'health'],
                       help='Command to execute')
    parser.add_argument('--log-file', type=str, help='Path to log file')
    parser.add_argument('--ground-truth', type=str, help='Path to ground truth labels')
    parser.add_argument('--output-dir', type=str, default='results', help='Output directory')
    parser.add_argument('--rebuild-kb', action='store_true', help='Rebuild knowledge base')
    
    args = parser.parse_args()
    
    try:
        pipeline = LogAnalyzerPipeline()
        
        if args.command == 'setup':
            pipeline.setup_knowledge_base(force_rebuild=args.rebuild_kb)
            logger.info("Setup completed successfully")
        
        elif args.command == 'health':
            if pipeline.check_system_health():
                logger.info("All systems operational")
                sys.exit(0)
            else:
                logger.error("Some systems are not operational")
                sys.exit(1)
        
        elif args.command == 'analyze':
            if not args.log_file:
                logger.error("--log-file is required for analyze command")
                sys.exit(1)
            
            pipeline.setup_knowledge_base()
            pipeline.analyze_logs_agentic(args.log_file, args.output_dir)
        
        elif args.command == 'evaluate':
            if not args.log_file:
                logger.error("--log-file is required for evaluate command")
                sys.exit(1)
            
            pipeline.setup_knowledge_base()
            pipeline.run_comparative_evaluation(args.log_file, args.ground_truth)
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
