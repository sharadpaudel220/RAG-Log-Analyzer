#!/usr/bin/env python3
"""
Demo script to run the Agentic RAG Log Analyzer with mock LLM
This demonstrates the system working without requiring Ollama
"""

import sys
from pathlib import Path

# Force use of mock LLM
import os
os.environ['USE_MOCK_LLM'] = 'true'

from src.input_layer.log_ingestion import LogIngestion
from src.preprocessing.log_preprocessor import LogPreprocessor
from src.knowledge_base.knowledge_manager import KnowledgeBaseManager
from src.retrieval.retrieval_system import RetrievalSystem
from src.llm_engine.mock_llm import MockLLMEngine
from src.agentic_controller.agentic_rag import AgenticController
from src.output_layer.alert_generator import AlertGenerator
from src.baselines.rule_based import RuleBasedSystem
from src.baselines.isolation_forest import IsolationForestSystem
from src.baselines.non_agentic_rag import NonAgenticRAGSystem
from src.evaluation.evaluator import SystemEvaluator
from src.evaluation.visualizer import ResultVisualizer
from src.utils.logger import get_logger

logger = get_logger(__name__, log_file="logs/demo.log")

def main():
    print("="*80)
    print("Agentic RAG Log Analyzer - Demo Run")
    print("="*80)
    print()
    
    # Initialize components with mock LLM
    print("Initializing system components...")
    ingestion = LogIngestion()
    preprocessor = LogPreprocessor()
    knowledge_manager = KnowledgeBaseManager()
    retrieval_system = RetrievalSystem(knowledge_manager)
    mock_llm = MockLLMEngine()  # Use mock LLM directly
    agentic_controller = AgenticController(retrieval_system, mock_llm)
    alert_generator = AlertGenerator()
    
    # Initialize baselines
    rule_based = RuleBasedSystem()
    isolation_forest = IsolationForestSystem()
    non_agentic_rag = NonAgenticRAGSystem(retrieval_system, mock_llm)
    
    evaluator = SystemEvaluator()
    visualizer = ResultVisualizer()
    
    print("✓ System initialized with mock LLM")
    print()
    
    # Setup knowledge base if needed
    if knowledge_manager.index is None or len(knowledge_manager.documents) == 0:
        print("Setting up knowledge base...")
        knowledge_manager.populate_default_knowledge()
        print(f"✓ Knowledge base ready with {len(knowledge_manager.documents)} documents")
    print()
    
    # Load sample logs
    log_file = "data/datasets/sample/sample_logs.log"
    print(f"Loading logs from: {log_file}")
    raw_logs = ingestion.ingest_file(log_file)
    print(f"✓ Loaded {len(raw_logs)} log entries")
    print()
    
    # Preprocess logs
    print("Preprocessing logs...")
    parsed_logs = preprocessor.preprocess(raw_logs)
    print(f"✓ Parsed {len(parsed_logs)} log entries")
    print()
    
    # Create ground truth (mark ERROR/FATAL as anomalies)
    ground_truth = []
    for log in parsed_logs:
        is_anomaly = log.severity in ['ERROR', 'CRITICAL', 'FATAL']
        ground_truth.append(is_anomaly)
    
    anomaly_count = sum(ground_truth)
    print(f"Ground truth: {anomaly_count}/{len(ground_truth)} anomalies")
    print()
    
    # Run comparative evaluation
    print("="*80)
    print("Running Comparative Evaluation")
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
    isolation_forest.train(parsed_logs[:int(len(parsed_logs)*0.7)])
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
    
    # 3. Non-Agentic RAG
    print("3. Evaluating Non-Agentic RAG System...")
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
    
    # 4. Agentic RAG (Proposed)
    print("4. Evaluating Agentic RAG System (Proposed)...")
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
    print("Evaluation Results Summary")
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
    evaluator.generate_report(results, "results/demo_evaluation_report.json")
    print("✓ Evaluation report saved to: results/demo_evaluation_report.json")
    
    # Generate visualizations
    print()
    print("Generating visualizations...")
    try:
        visualizer.generate_all_plots(results)
        print("✓ Plots saved to: results/figures/")
    except Exception as e:
        print(f"⚠ Could not generate plots: {e}")
    
    print()
    print("="*80)
    print("Demo Complete!")
    print("="*80)
    print()
    print("Key Findings:")
    
    # Find best system
    best_f1 = max(r.detection_metrics.f1_score for r in results)
    best_system = [r for r in results if r.detection_metrics.f1_score == best_f1][0]
    
    print(f"  • Best F1-Score: {best_system.system_name} ({best_f1:.4f})")
    print(f"  • Fastest System: {min(results, key=lambda r: r.efficiency_metrics.average_latency).system_name}")
    print(f"  • Total Logs Analyzed: {len(parsed_logs)}")
    print(f"  • Anomalies Detected: {anomaly_count}")
    print()
    print("Next Steps:")
    print("  1. Review results/demo_evaluation_report.json")
    print("  2. Check visualizations in results/figures/")
    print("  3. Run on larger datasets (HDFS, BGL) for full evaluation")
    print()

if __name__ == "__main__":
    main()
