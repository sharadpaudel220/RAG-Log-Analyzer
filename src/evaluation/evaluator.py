import time
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Callable, Tuple, Optional
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
        confidence_scores = []
        
        for entry in log_entries:
            start_time = time.time()
            
            try:
                result = analysis_function(entry)
                
                if hasattr(result, 'is_anomaly'):
                    predictions.append(result.is_anomaly)
                else:
                    predictions.append(False)
                
                # Extract confidence score if available
                conf_score = 0.5
                if hasattr(result, 'confidence_score'):
                    conf_score = float(result.confidence_score)
                elif hasattr(result, 'score'):
                    conf_score = float(result.score)
                elif hasattr(result, 'anomaly_score'):
                    conf_score = float(result.anomaly_score)
                
                # Adjust confidence: high for anomalies, low for normal (range 0-1)
                if predictions[-1]:
                    confidence_scores.append(max(conf_score, 0.5))
                else:
                    confidence_scores.append(min(conf_score, 0.5))
                
                latency = time.time() - start_time
                monitor.record_latency(latency)
                
            except Exception as e:
                logger.error(f"Error analyzing log entry: {e}")
                predictions.append(False)
                confidence_scores.append(0.0)
                monitor.record_latency(time.time() - start_time)
        
        detection_metrics = self.metrics_calculator.calculate_detection_metrics(
            predictions, ground_truth, confidence_scores
        )
        
        efficiency_metrics = monitor.get_metrics()
        
        logger.info(f"Completed evaluation of {system_name}")
        
        return SystemEvaluationResult(
            system_name=system_name,
            detection_metrics=detection_metrics,
            efficiency_metrics=efficiency_metrics,
            additional_info=additional_info or {}
        )
    
    def evaluate_with_cross_validation(
        self,
        system_name: str,
        analysis_function: Callable,
        log_entries: List[ParsedLogEntry],
        ground_truth: List[bool],
        n_folds: int = 5,
        n_runs: int = 3
    ) -> Dict[str, Any]:
        """
        Run k-fold cross-validation with multiple runs for statistical robustness.
        Returns mean, std, confidence intervals for all metrics.
        """
        logger.info(f"Running {n_folds}-fold cross-validation with {n_runs} runs for {system_name}")
        
        all_fold_results = []
        
        for run in range(n_runs):
            # Shuffle indices for this run
            indices = np.arange(len(log_entries))
            np.random.seed(42 + run)
            np.random.shuffle(indices)
            
            fold_size = len(log_entries) // n_folds
            
            for fold in range(n_folds):
                start = fold * fold_size
                end = start + fold_size if fold < n_folds - 1 else len(log_entries)
                
                test_idx = indices[start:end]
                
                test_logs = [log_entries[i] for i in test_idx]
                test_gt = [ground_truth[i] for i in test_idx]
                
                result = self.evaluate_system(
                    system_name=f"{system_name}_run{run+1}_fold{fold+1}",
                    analysis_function=analysis_function,
                    log_entries=test_logs,
                    ground_truth=test_gt
                )
                
                all_fold_results.append(result.detection_metrics)
        
        # Aggregate results
        metrics_names = ['precision', 'recall', 'f1_score', 'accuracy', 'auc_roc', 'auc_pr', 'mcc']
        aggregated = {}
        
        for metric_name in metrics_names:
            values = [getattr(r, metric_name) for r in all_fold_results]
            mean_val = np.mean(values)
            std_val = np.std(values)
            # 95% confidence interval
            ci_low = mean_val - 1.96 * std_val / np.sqrt(len(values))
            ci_high = mean_val + 1.96 * std_val / np.sqrt(len(values))
            
            aggregated[metric_name] = {
                'mean': round(float(mean_val), 4),
                'std': round(float(std_val), 4),
                'ci_95_low': round(float(ci_low), 4),
                'ci_95_high': round(float(ci_high), 4),
                'values': [round(float(v), 4) for v in values]
            }
        
        return {
            'system_name': system_name,
            'n_folds': n_folds,
            'n_runs': n_runs,
            'total_evaluations': len(all_fold_results),
            'aggregated_metrics': aggregated
        }
    
    def compare_systems(
        self,
        results: List[SystemEvaluationResult],
        metric: str = 'f1_score',
        cv_results: Dict[str, List[float]] = None
    ) -> Dict[str, Any]:
        comparison = {
            'systems': [r.system_name for r in results],
            'metric': metric,
            'scores': []
        }
        
        for result in results:
            if metric in ['precision', 'recall', 'f1_score', 'accuracy', 'auc_roc', 'auc_pr', 'mcc']:
                score = getattr(result.detection_metrics, metric)
            elif metric in ['average_latency', 'throughput']:
                score = getattr(result.efficiency_metrics, metric)
            else:
                score = 0.0
            
            comparison['scores'].append(score)
        
        best_idx = comparison['scores'].index(max(comparison['scores']))
        comparison['best_system'] = results[best_idx].system_name
        
        if cv_results and len(results) >= 2:
            statistical_tests = []
            for i in range(len(results)):
                for j in range(i + 1, len(results)):
                    sys1_name = results[i].system_name
                    sys2_name = results[j].system_name
                    
                    if sys1_name in cv_results and sys2_name in cv_results:
                        scores1 = cv_results[sys1_name]
                        scores2 = cv_results[sys2_name]
                        
                        test_result = self.metrics_calculator.paired_t_test(
                            scores1, scores2, alpha=0.05
                        )
                        test_result['system1'] = sys1_name
                        test_result['system2'] = sys2_name
                        statistical_tests.append(test_result)
            
            comparison['statistical_tests'] = statistical_tests
        
        logger.info(f"Comparison complete - Best system: {comparison['best_system']}")
        
        return comparison

    def evaluate_with_explanations(
        self,
        system_name: str,
        analysis_function: Callable,
        log_entries: List[ParsedLogEntry],
        ground_truth: List[bool],
        max_examples: int = 5
    ) -> Dict[str, Any]:
        """
        Evaluate system and collect qualitative examples with explanations.
        Returns sample of correct/incorrect predictions for thesis analysis.
        """
        logger.info(f"Collecting explanations for {system_name}")
        
        predictions = []
        confidence_scores = []
        examples = []
        
        for i, entry in enumerate(log_entries):
            is_anomaly = False
            conf = 0.5
            try:
                result = analysis_function(entry)
                is_anomaly = getattr(result, 'is_anomaly', False)
                
                if hasattr(result, 'confidence_score'):
                    conf = float(result.confidence_score)
                elif hasattr(result, 'score'):
                    conf = float(result.score)
            except Exception as e:
                logger.warning(f"Error analyzing log entry {i}: {e}")
                is_anomaly = False
                conf = 0.0
            
            predictions.append(is_anomaly)
            confidence_scores.append(conf)
            
            # Collect examples (balanced: correct TP, TN, FP, FN)
            if len(examples) < max_examples and i < len(ground_truth):
                gt = ground_truth[i]
                category = None
                if is_anomaly and gt:
                    category = 'TP'
                elif not is_anomaly and not gt:
                    category = 'TN'
                elif is_anomaly and not gt:
                    category = 'FP'
                else:
                    category = 'FN'
                
                explanation = ''
                if hasattr(result, 'final_analysis'):
                    explanation = result.final_analysis
                elif hasattr(result, 'analysis'):
                    explanation = result.analysis
                elif hasattr(result, 'reason'):
                    explanation = result.reason
                elif hasattr(result, 'matched_rules'):
                    explanation = f"Matched rules: {result.matched_rules}"
                
                reasoning_chain = []
                if hasattr(result, 'reasoning_chain') and result.reasoning_chain:
                    reasoning_chain = [step.thought for step in result.reasoning_chain]
                
                # Handle both ParsedLogEntry (raw_content) and RawLogEntry (content)
                log_content = getattr(entry, 'raw_content', getattr(entry, 'content', str(entry)))[:200]
                
                examples.append({
                    'index': i,
                    'log_content': log_content,
                    'ground_truth': gt,
                    'predicted': is_anomaly,
                    'category': category,
                    'confidence': round(conf, 4),
                    'severity': getattr(result, 'severity', 'UNKNOWN') if 'result' in dir() else 'UNKNOWN',
                    'explanation': explanation[:500],
                    'reasoning_chain': reasoning_chain
                })
        
        detection_metrics = self.metrics_calculator.calculate_detection_metrics(
            predictions, ground_truth, confidence_scores
        )
        
        return {
            'system_name': system_name,
            'detection_metrics': detection_metrics.to_dict(),
            'examples': examples,
            'total_logs': len(log_entries)
        }

    def run_ablation_study(
        self,
        base_controller,
        log_entries: List[ParsedLogEntry],
        ground_truth: List[bool]
    ) -> Dict[str, Any]:
        """
        Run ablation study for Agentic RAG components.
        Tests full system vs variants with specific components disabled.
        
        Components ablated:
        - retrieval: Disable knowledge base retrieval
        - reflection: Disable self-reflection step
        - reasoning_steps: Reduce to single-step (no chain-of-thought)
        - fast_mode: Disable fast mode (force full analysis on all logs)
        - template_cache: Disable template-based caching
        - skip_heuristics: Disable early skip heuristics (analyze all logs)
        """
        logger.info("Starting ablation study for Agentic RAG components")
        
        ablation_configs = {
            'full_system': {},
            'no_retrieval': {'disable_retrieval': True},
            'no_reflection': {'disable_reflection': True},
            'no_reasoning_chain': {'single_step': True},
            'no_fast_mode': {'disable_fast_mode': True},
            'no_template_cache': {'disable_template_cache': True},
            'no_skip_heuristics': {'disable_skip_heuristics': True}
        }
        
        ablation_results = []
        
        for variant_name, config_overrides in ablation_configs.items():
            logger.info(f"Evaluating ablation variant: {variant_name}")
            
            # Create a modified analysis function for this variant
            analysis_function = self._create_ablated_analyzer(
                base_controller, config_overrides
            )
            
            result = self.evaluate_system(
                system_name=f"Agentic RAG ({variant_name})",
                analysis_function=analysis_function,
                log_entries=log_entries,
                ground_truth=ground_truth
            )
            
            ablation_results.append({
                'variant': variant_name,
                'f1': result.detection_metrics.f1_score,
                'precision': result.detection_metrics.precision,
                'recall': result.detection_metrics.recall,
                'accuracy': result.detection_metrics.accuracy,
                'auc_roc': result.detection_metrics.auc_roc,
                'auc_pr': result.detection_metrics.auc_pr,
                'mcc': result.detection_metrics.mcc,
                'latency': result.efficiency_metrics.average_latency,
                'throughput': result.efficiency_metrics.throughput
            })
        
        # Calculate component impact (F1 drop from full system)
        full_f1 = ablation_results[0]['f1']  # full_system is first
        for result in ablation_results[1:]:
            result['f1_drop'] = full_f1 - result['f1']
            result['f1_drop_pct'] = (result['f1_drop'] / full_f1 * 100) if full_f1 > 0 else 0
        
        return {
            'full_system_f1': full_f1,
            'ablation_results': ablation_results,
            'total_variants': len(ablation_configs)
        }
    
    def _create_ablated_analyzer(self, base_controller, config_overrides: Dict[str, Any]) -> Callable:
        """Create an ablated analyzer function based on config overrides."""
        
        def ablated_analyze(log_entry: ParsedLogEntry):
            # Temporarily override controller settings
            original_settings = {}
            
            if config_overrides.get('disable_retrieval'):
                # Mock empty retrieval
                original_retrieve = base_controller.retrieval_system.retrieve
                base_controller.retrieval_system.retrieve = lambda *args, **kwargs: []
            
            if config_overrides.get('disable_reflection'):
                original_settings['enable_self_reflection'] = base_controller.enable_self_reflection
                base_controller.enable_self_reflection = False
            
            if config_overrides.get('single_step'):
                original_settings['max_reasoning_steps'] = base_controller.max_reasoning_steps
                base_controller.max_reasoning_steps = 1
                original_settings['max_steps_fast'] = base_controller.max_steps_fast
                base_controller.max_steps_fast = 1
            
            if config_overrides.get('disable_fast_mode'):
                original_settings['fast_mode'] = base_controller.fast_mode
                base_controller.fast_mode = False
            
            if config_overrides.get('disable_template_cache'):
                original_settings['enable_template_cache'] = base_controller.enable_template_cache
                base_controller.enable_template_cache = False
                base_controller.template_cache = None
            
            if config_overrides.get('disable_skip_heuristics'):
                original_settings['skip_info_logs'] = base_controller.skip_info_logs
                base_controller.skip_info_logs = False
                original_settings['skip_warning_logs'] = base_controller.skip_warning_logs
                base_controller.skip_warning_logs = False
                original_settings['only_analyze_errors'] = base_controller.only_analyze_errors
                base_controller.only_analyze_errors = False
                original_settings['early_stop_on_low_severity'] = base_controller.early_stop_on_low_severity
                base_controller.early_stop_on_low_severity = False
            
            try:
                result = base_controller.analyze_log(log_entry)
            finally:
                # Restore original settings
                if config_overrides.get('disable_retrieval'):
                    base_controller.retrieval_system.retrieve = original_retrieve
                
                for key, value in original_settings.items():
                    setattr(base_controller, key, value)
                
                if 'enable_template_cache' in original_settings:
                    if original_settings['enable_template_cache']:
                        base_controller.template_cache = {}
            
            return result
        
        return ablated_analyze
    
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
