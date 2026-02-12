import time
import json
from pathlib import Path
from typing import List, Dict, Any, Callable
from dataclasses import dataclass

from src.preprocessing.log_preprocessor import ParsedLogEntry
from src.evaluation.metrics import MetricsCalculator, PerformanceMonitor, DetectionMetrics, EfficiencyMetrics
from src.utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class SystemEvaluationResult:
    system_name: str
    detection_metrics: DetectionMetrics
    efficiency_metrics: EfficiencyMetrics
    additional_info: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'system_name': self.system_name,
            'detection_metrics': self.detection_metrics.to_dict(),
            'efficiency_metrics': self.efficiency_metrics.to_dict(),
            'additional_info': self.additional_info
        }

class SystemEvaluator:
    def __init__(self):
        self.metrics_calculator = MetricsCalculator()
        logger.info("SystemEvaluator initialized")
    
    def evaluate_system(
        self,
        system_name: str,
        analysis_function: Callable,
        log_entries: List[ParsedLogEntry],
        ground_truth: List[bool],
        additional_info: Dict[str, Any] = None
    ) -> SystemEvaluationResult:
        logger.info(f"Evaluating system: {system_name}")
        
        monitor = PerformanceMonitor()
        monitor.start()
        
        predictions = []
        
        for entry in log_entries:
            start_time = time.time()
            
            try:
                result = analysis_function(entry)
                
                if hasattr(result, 'is_anomaly'):
                    predictions.append(result.is_anomaly)
                else:
                    predictions.append(False)
                
                latency = time.time() - start_time
                monitor.record_latency(latency)
                
            except Exception as e:
                logger.error(f"Error analyzing log entry: {e}")
                predictions.append(False)
                monitor.record_latency(time.time() - start_time)
        
        detection_metrics = self.metrics_calculator.calculate_detection_metrics(
            predictions, ground_truth
        )
        
        efficiency_metrics = monitor.get_metrics()
        
        logger.info(f"Completed evaluation of {system_name}")
        
        return SystemEvaluationResult(
            system_name=system_name,
            detection_metrics=detection_metrics,
            efficiency_metrics=efficiency_metrics,
            additional_info=additional_info or {}
        )
    
    def compare_systems(
        self,
        results: List[SystemEvaluationResult],
        metric: str = 'f1_score'
    ) -> Dict[str, Any]:
        comparison = {
            'systems': [r.system_name for r in results],
            'metric': metric,
            'scores': []
        }
        
        for result in results:
            if metric in ['precision', 'recall', 'f1_score', 'accuracy']:
                score = getattr(result.detection_metrics, metric)
            elif metric in ['average_latency', 'throughput']:
                score = getattr(result.efficiency_metrics, metric)
            else:
                score = 0.0
            
            comparison['scores'].append(score)
        
        best_idx = comparison['scores'].index(max(comparison['scores']))
        comparison['best_system'] = results[best_idx].system_name
        
        if len(results) >= 2:
            statistical_tests = []
            for i in range(len(results)):
                for j in range(i + 1, len(results)):
                    scores1 = [comparison['scores'][i]] * 10
                    scores2 = [comparison['scores'][j]] * 10
                    
                    test_result = {
                        'system1': results[i].system_name,
                        'system2': results[j].system_name,
                        'score_diff': comparison['scores'][i] - comparison['scores'][j]
                    }
                    statistical_tests.append(test_result)
            
            comparison['statistical_tests'] = statistical_tests
        
        logger.info(f"Comparison complete - Best system: {comparison['best_system']}")
        
        return comparison
    
    def generate_report(
        self,
        results: List[SystemEvaluationResult],
        output_path: str
    ):
        report = {
            'evaluation_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'systems_evaluated': len(results),
            'results': [r.to_dict() for r in results]
        }
        
        comparisons = {
            'f1_score': self.compare_systems(results, 'f1_score'),
            'precision': self.compare_systems(results, 'precision'),
            'recall': self.compare_systems(results, 'recall'),
            'average_latency': self.compare_systems(results, 'average_latency')
        }
        
        report['comparisons'] = comparisons
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Evaluation report saved to {output_path}")
        
        self._generate_summary(results)
    
    def _generate_summary(self, results: List[SystemEvaluationResult]):
        logger.info("\n" + "="*80)
        logger.info("EVALUATION SUMMARY")
        logger.info("="*80)
        
        for result in results:
            logger.info(f"\nSystem: {result.system_name}")
            logger.info(f"  Detection Metrics:")
            logger.info(f"    Precision: {result.detection_metrics.precision:.4f}")
            logger.info(f"    Recall: {result.detection_metrics.recall:.4f}")
            logger.info(f"    F1-Score: {result.detection_metrics.f1_score:.4f}")
            logger.info(f"    Accuracy: {result.detection_metrics.accuracy:.4f}")
            logger.info(f"  Efficiency Metrics:")
            logger.info(f"    Avg Latency: {result.efficiency_metrics.average_latency:.4f}s")
            logger.info(f"    Throughput: {result.efficiency_metrics.throughput:.2f} logs/s")
            logger.info(f"    Memory Usage: {result.efficiency_metrics.memory_usage_mb:.2f} MB")
        
        logger.info("="*80)
