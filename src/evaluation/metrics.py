import time
import psutil
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import numpy as np
from scipy import stats

from src.utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class DetectionMetrics:
    precision: float
    recall: float
    f1_score: float
    false_positive_rate: float
    false_negative_rate: float
    accuracy: float
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int
    auc_roc: float = 0.0
    auc_pr: float = 0.0
    mcc: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'precision': self.precision,
            'recall': self.recall,
            'f1_score': self.f1_score,
            'false_positive_rate': self.false_positive_rate,
            'false_negative_rate': self.false_negative_rate,
            'accuracy': self.accuracy,
            'auc_roc': self.auc_roc,
            'auc_pr': self.auc_pr,
            'mcc': self.mcc,
            'true_positives': self.true_positives,
            'true_negatives': self.true_negatives,
            'false_positives': self.false_positives,
            'false_negatives': self.false_negatives
        }

@dataclass
class EfficiencyMetrics:
    average_latency: float
    total_time: float
    memory_usage_mb: float
    throughput: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'average_latency': self.average_latency,
            'total_time': self.total_time,
            'memory_usage_mb': self.memory_usage_mb,
            'throughput': self.throughput
        }

class MetricsCalculator:
    def __init__(self):
        logger.info("MetricsCalculator initialized")
    
    def calculate_detection_metrics(
        self, 
        predictions: List[bool], 
        ground_truth: List[bool],
        confidence_scores: List[float] = None
    ) -> DetectionMetrics:
        if len(predictions) != len(ground_truth):
            raise ValueError("Predictions and ground truth must have same length")
        
        tp = sum(1 for p, g in zip(predictions, ground_truth) if p and g)
        tn = sum(1 for p, g in zip(predictions, ground_truth) if not p and not g)
        fp = sum(1 for p, g in zip(predictions, ground_truth) if p and not g)
        fn = sum(1 for p, g in zip(predictions, ground_truth) if not p and g)
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
        
        accuracy = (tp + tn) / len(predictions) if len(predictions) > 0 else 0.0
        
        # Matthews Correlation Coefficient (balanced measure for imbalanced data)
        mcc_denom = ((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)) ** 0.5
        mcc = (tp * tn - fp * fn) / mcc_denom if mcc_denom > 0 else 0.0
        
        # AUC-ROC and AUC-PR (require confidence scores)
        auc_roc = 0.0
        auc_pr = 0.0
        
        if confidence_scores and len(confidence_scores) == len(ground_truth):
            try:
                from sklearn.metrics import roc_auc_score, average_precision_score
                y_true = [1 if g else 0 for g in ground_truth]
                auc_roc = roc_auc_score(y_true, confidence_scores)
                auc_pr = average_precision_score(y_true, confidence_scores)
                logger.info(f"AUC-ROC: {auc_roc:.4f}, AUC-PR: {auc_pr:.4f}")
            except Exception as e:
                logger.warning(f"Could not compute AUC metrics: {e}")
        
        logger.info(f"Detection metrics - Precision: {precision:.4f}, Recall: {recall:.4f}, F1: {f1_score:.4f}, MCC: {mcc:.4f}, AUC-ROC: {auc_roc:.4f}, AUC-PR: {auc_pr:.4f}")
        
        return DetectionMetrics(
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            false_positive_rate=fpr,
            false_negative_rate=fnr,
            accuracy=accuracy,
            auc_roc=auc_roc,
            auc_pr=auc_pr,
            mcc=mcc,
            true_positives=tp,
            true_negatives=tn,
            false_positives=fp,
            false_negatives=fn
        )
    
    def calculate_efficiency_metrics(
        self,
        latencies: List[float],
        total_time: float,
        memory_usage: float
    ) -> EfficiencyMetrics:
        avg_latency = np.mean(latencies) if latencies else 0.0
        throughput = len(latencies) / total_time if total_time > 0 else 0.0
        
        logger.info(f"Efficiency metrics - Avg Latency: {avg_latency:.4f}s, Throughput: {throughput:.2f} logs/s")
        
        return EfficiencyMetrics(
            average_latency=avg_latency,
            total_time=total_time,
            memory_usage_mb=memory_usage,
            throughput=throughput
        )
    
    def paired_t_test(
        self,
        scores1: List[float],
        scores2: List[float],
        alpha: float = 0.05
    ) -> Dict[str, Any]:
        if len(scores1) != len(scores2):
            raise ValueError("Score lists must have same length")
        
        t_statistic, p_value = stats.ttest_rel(scores1, scores2)
        
        is_significant = p_value < alpha
        
        mean_diff = np.mean(scores1) - np.mean(scores2)
        
        logger.info(f"Paired t-test - t-statistic: {t_statistic:.4f}, p-value: {p_value:.4f}, significant: {is_significant}")
        
        return {
            't_statistic': float(t_statistic),
            'p_value': float(p_value),
            'is_significant': is_significant,
            'alpha': alpha,
            'mean_difference': float(mean_diff)
        }
    
    def confusion_matrix(
        self,
        predictions: List[bool],
        ground_truth: List[bool]
    ) -> np.ndarray:
        tp = sum(1 for p, g in zip(predictions, ground_truth) if p and g)
        tn = sum(1 for p, g in zip(predictions, ground_truth) if not p and not g)
        fp = sum(1 for p, g in zip(predictions, ground_truth) if p and not g)
        fn = sum(1 for p, g in zip(predictions, ground_truth) if not p and g)
        
        return np.array([[tn, fp], [fn, tp]])

class PerformanceMonitor:
    def __init__(self):
        self.start_time = None
        self.latencies = []
        self.process = psutil.Process()
        self.initial_memory = None
        
    def start(self):
        self.start_time = time.time()
        self.initial_memory = self.process.memory_info().rss / 1024 / 1024
        self.latencies = []
    
    def record_latency(self, latency: float):
        self.latencies.append(latency)
    
    def get_metrics(self) -> EfficiencyMetrics:
        total_time = time.time() - self.start_time if self.start_time else 0.0
        current_memory = self.process.memory_info().rss / 1024 / 1024
        memory_usage = current_memory - (self.initial_memory or 0)
        
        avg_latency = np.mean(self.latencies) if self.latencies else 0.0
        throughput = len(self.latencies) / total_time if total_time > 0 else 0.0
        
        return EfficiencyMetrics(
            average_latency=avg_latency,
            total_time=total_time,
            memory_usage_mb=memory_usage,
            throughput=throughput
        )
