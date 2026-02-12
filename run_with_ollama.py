#!/usr/bin/env python3
"""
Run the Agentic RAG Log Analyzer with real Ollama/Mistral LLM
This script runs the full comparative evaluation on sample or real datasets
"""

import sys
import argparse
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

logger = get_logger(__name__, log_file="logs/ollama_run.log")

def main():
    parser = argparse.ArgumentParser(description="Run Agentic RAG Log Analyzer with Ollama")
    parser.add_argument('--log-file', type=str, default='data/datasets/sample/sample_logs.log',
                        help='Path to log file')
    parser.add_argument('--output-dir', type=str, default='results/ollama',
                        help='Output directory for results')
    parser.add_argument('--max-logs', type=int, default=None,
                        help='Maximum number of logs to process (for testing)')
    args = parser.parse_args()
    
    print("="*80)
    print("Agentic RAG Log Analyzer - Running with Ollama/Mistral")
    print("="*80)
    print()
    
    # Initialize components
    print("Initializing system components...")
    ingestion = LogIngestion()
    preprocessor = LogPreprocessor()
    knowledge_manager = KnowledgeBaseManager()
    retrieval_system = RetrievalSystem(knowledge_manager)
    
    # Initialize LLM Engine (will use Ollama)
    print("Connecting to Ollama...")
    try:
        llm_engine = LLMEngine()
        if not llm_engine.check_health():
            print("✗ Cannot connect to Ollama. Please ensure:")
            print("  1. Ollama is running: ollama serve")
            print("  2. Mistral model is pulled: ollama pull mistral:7b-instruct")
            sys.exit(1)
        print("✓ Connected to Ollama with Mistral model")
    except Exception as e:
        print(f"✗ Error initializing LLM: {e}")
        sys.exit(1)
    
    agentic_controller = AgenticController(retrieval_system, llm_engine)
    alert_generator = AlertGenerator()
    
    # Initialize baselines
    rule_based = RuleBasedSystem()
    isolation_forest = IsolationForestSystem()
    non_agentic_rag = NonAgenticRAGSystem(retrieval_system, llm_engine)
    
    evaluator = SystemEvaluator()
    visualizer = ResultVisualizer(output_dir=f"{args.output_dir}/figures")
    
    print("✓ All components initialized")
    print()
    
    # Setup knowledge base if needed
    if knowledge_manager.index is None or len(knowledge_manager.documents) == 0:
        print("Setting up knowledge base...")
        knowledge_manager.populate_default_knowledge()
        print(f"✓ Knowledge base ready with {len(knowledge_manager.documents)} documents")
    print()
    
    # Load logs
    print(f"Loading logs from: {args.log_file}")
    if not Path(args.log_file).exists():
        print(f"✗ Log file not found: {args.log_file}")
        sys.exit(1)
    
    raw_logs = ingestion.ingest_file(args.log_file)
    print(f"✓ Loaded {len(raw_logs)} log entries")
    
    if args.max_logs:
        raw_logs = raw_logs[:args.max_logs]
        print(f"  (Limited to {len(raw_logs)} logs for testing)")
    print()
    
    # Preprocess logs
    print("Preprocessing logs...")
    parsed_logs = preprocessor.preprocess(raw_logs)
    print(f"✓ Parsed {len(parsed_logs)} log entries")
    print()
    
    # Create ground truth
    ground_truth = []
    for log in parsed_logs:
        is_anomaly = log.severity in ['ERROR', 'CRITICAL', 'FATAL']
        ground_truth.append(is_anomaly)
    
    anomaly_count = sum(ground_truth)
    print(f"Ground truth: {anomaly_count}/{len(ground_truth)} anomalies")
    print()
    
    # Run comparative evaluation
    print("="*80)
    print("Running Comparative Evaluation with Real LLM")
    print("="*80)
    print()
    
    results = []
    
    # 1. Rule-Based System
    print("1. Evaluating Rule-Based System...")
    rule_result = evaluator.evaluate_system(
        system_name="Rule-Based",
        analysis_function=rule_based.analyze,
        log_entries=parsed_logs,
        ground_truth=ground_truth
    )
    results.append(rule_result)
    print(f"   ✓ F1-Score: {rule_result.detection_metrics.f1_score:.4f}")
    print(f"   ✓ Latency: {rule_result.efficiency_metrics.average_latency:.4f}s")
    print()
    
    # 2. Isolation Forest
    print("2. Evaluating Isolation Forest System...")
    train_size = int(len(parsed_logs) * 0.7)
    isolation_forest.train(parsed_logs[:train_size])
    iso_result = evaluator.evaluate_system(
        system_name="Isolation Forest",
        analysis_function=isolation_forest.analyze,
        log_entries=parsed_logs,
        ground_truth=ground_truth
    )
    results.append(iso_result)
    print(f"   ✓ F1-Score: {iso_result.detection_metrics.f1_score:.4f}")
    print(f"   ✓ Latency: {iso_result.efficiency_metrics.average_latency:.4f}s")
    print()
    
    # 3. Non-Agentic RAG (with real LLM)
    print("3. Evaluating Non-Agentic RAG System (with Ollama/Mistral)...")
    non_agentic_result = evaluator.evaluate_system(
        system_name="Non-Agentic RAG",
        analysis_function=non_agentic_rag.analyze,
        log_entries=parsed_logs,
        ground_truth=ground_truth
    )
    results.append(non_agentic_result)
    print(f"   ✓ F1-Score: {non_agentic_result.detection_metrics.f1_score:.4f}")
    print(f"   ✓ Latency: {non_agentic_result.efficiency_metrics.average_latency:.4f}s")
    print()
    
    # 4. Agentic RAG (Proposed - with real LLM)
    print("4. Evaluating Agentic RAG System (Proposed - with Ollama/Mistral)...")
    agentic_result = evaluator.evaluate_system(
        system_name="Agentic RAG",
        analysis_function=agentic_controller.analyze_log,
        log_entries=parsed_logs,
        ground_truth=ground_truth
    )
    results.append(agentic_result)
    print(f"   ✓ F1-Score: {agentic_result.detection_metrics.f1_score:.4f}")
    print(f"   ✓ Latency: {agentic_result.efficiency_metrics.average_latency:.4f}s")
    print()
    
    # Generate report
    print("="*80)
    print("Evaluation Results Summary (with Real Ollama/Mistral)")
    print("="*80)
    print()
    
    for result in results:
        print(f"{result.system_name}:")
        print(f"  Detection Metrics:")
        print(f"    Precision: {result.detection_metrics.precision:.4f}")
        print(f"    Recall:    {result.detection_metrics.recall:.4f}")
        print(f"    F1-Score:  {result.detection_metrics.f1_score:.4f}")
        print(f"    Accuracy:  {result.detection_metrics.accuracy:.4f}")
        print(f"  Efficiency Metrics:")
        print(f"    Avg Latency: {result.efficiency_metrics.average_latency:.4f}s")
        print(f"    Throughput:  {result.efficiency_metrics.throughput:.2f} logs/s")
        print()
    
    # Save report
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    report_path = f"{args.output_dir}/evaluation_report.json"
    evaluator.generate_report(results, report_path)
    print(f"✓ Evaluation report saved to: {report_path}")
    
    # Generate visualizations
    print()
    print("Generating visualizations...")
    try:
        visualizer.generate_all_plots(results)
        print(f"✓ Plots saved to: {args.output_dir}/figures/")
    except Exception as e:
        print(f"⚠ Could not generate plots: {e}")
    
    print()
    print("="*80)
    print("Evaluation Complete with Real Ollama/Mistral!")
    print("="*80)
    print()
    
    # Find best system
    best_f1 = max(r.detection_metrics.f1_score for r in results)
    best_system = [r for r in results if r.detection_metrics.f1_score == best_f1][0]
    
    print("Key Findings:")
    print(f"  • Best F1-Score: {best_system.system_name} ({best_f1:.4f})")
    print(f"  • Fastest System: {min(results, key=lambda r: r.efficiency_metrics.average_latency).system_name}")
    print(f"  • Total Logs Analyzed: {len(parsed_logs)}")
    print(f"  • Anomalies Detected: {anomaly_count}")
    print()
    print("Results saved to:")
    print(f"  • Report: {report_path}")
    print(f"  • Figures: {args.output_dir}/figures/")
    print()

if __name__ == "__main__":
    main()
