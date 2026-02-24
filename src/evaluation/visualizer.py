import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path
from typing import List, Dict, Any

from src.evaluation.evaluator import SystemEvaluationResult
from src.utils.logger import get_logger

logger = get_logger(__name__)

class ResultVisualizer:
    def __init__(self, output_dir: str = "results/figures"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        sns.set_style("whitegrid")
        plt.rcParams['figure.figsize'] = (12, 8)
        
        logger.info(f"ResultVisualizer initialized, output dir: {self.output_dir}")
    
    def plot_detection_metrics_comparison(
        self,
        results: List[SystemEvaluationResult],
        output_filename: str = "detection_metrics_comparison.png"
    ):
        systems = [r.system_name for r in results]
        metrics = ['precision', 'recall', 'f1_score', 'accuracy']
        
        data = {metric: [] for metric in metrics}
        
        for result in results:
            for metric in metrics:
                data[metric].append(getattr(result.detection_metrics, metric))
        
        x = np.arange(len(systems))
        width = 0.2
        
        fig, ax = plt.subplots(figsize=(14, 8))
        
        for i, metric in enumerate(metrics):
            offset = width * (i - len(metrics) / 2 + 0.5)
            ax.bar(x + offset, data[metric], width, label=metric.replace('_', ' ').title())
        
        ax.set_xlabel('Systems', fontsize=12)
        ax.set_ylabel('Score', fontsize=12)
        ax.set_title('Detection Metrics Comparison Across Systems', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(systems, rotation=15, ha='right')
        ax.legend()
        ax.set_ylim(0, 1.1)
        
        plt.tight_layout()
        output_path = self.output_dir / output_filename
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Detection metrics comparison saved to {output_path}")
    
    def plot_efficiency_metrics_comparison(
        self,
        results: List[SystemEvaluationResult],
        output_filename: str = "efficiency_metrics_comparison.png"
    ):
        systems = [r.system_name for r in results]
        
        latencies = [r.efficiency_metrics.average_latency for r in results]
        throughputs = [r.efficiency_metrics.throughput for r in results]
        memory_usage = [r.efficiency_metrics.memory_usage_mb for r in results]
        
        fig, axes = plt.subplots(1, 3, figsize=(18, 6))
        
        axes[0].bar(systems, latencies, color='skyblue')
        axes[0].set_ylabel('Latency (seconds)', fontsize=12)
        axes[0].set_title('Average Latency', fontsize=12, fontweight='bold')
        axes[0].tick_params(axis='x', rotation=15)
        
        axes[1].bar(systems, throughputs, color='lightgreen')
        axes[1].set_ylabel('Throughput (logs/sec)', fontsize=12)
        axes[1].set_title('Throughput', fontsize=12, fontweight='bold')
        axes[1].tick_params(axis='x', rotation=15)
        
        axes[2].bar(systems, memory_usage, color='salmon')
        axes[2].set_ylabel('Memory Usage (MB)', fontsize=12)
        axes[2].set_title('Memory Usage', fontsize=12, fontweight='bold')
        axes[2].tick_params(axis='x', rotation=15)
        
        plt.tight_layout()
        output_path = self.output_dir / output_filename
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Efficiency metrics comparison saved to {output_path}")
    
    def plot_confusion_matrix(
        self,
        result: SystemEvaluationResult,
        output_filename: str = None
    ):
        if output_filename is None:
            output_filename = f"confusion_matrix_{result.system_name.replace(' ', '_')}.png"
        
        cm = np.array([
            [result.detection_metrics.true_negatives, result.detection_metrics.false_positives],
            [result.detection_metrics.false_negatives, result.detection_metrics.true_positives]
        ])
        
        fig, ax = plt.subplots(figsize=(8, 6))
        
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                   xticklabels=['Predicted Normal', 'Predicted Anomaly'],
                   yticklabels=['Actual Normal', 'Actual Anomaly'],
                   ax=ax, cbar_kws={'label': 'Count'})
        
        ax.set_title(f'Confusion Matrix - {result.system_name}', fontsize=14, fontweight='bold')
        
        plt.tight_layout()
        output_path = self.output_dir / output_filename
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Confusion matrix saved to {output_path}")
    
    def plot_f1_score_comparison(
        self,
        results: List[SystemEvaluationResult],
        output_filename: str = "f1_score_comparison.png"
    ):
        systems = [r.system_name for r in results]
        f1_scores = [r.detection_metrics.f1_score for r in results]
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        colors = plt.cm.viridis(np.linspace(0, 1, len(systems)))
        bars = ax.barh(systems, f1_scores, color=colors)
        
        ax.set_xlabel('F1-Score', fontsize=12)
        ax.set_title('F1-Score Comparison Across Systems', fontsize=14, fontweight='bold')
        ax.set_xlim(0, 1.1)
        
        for i, (bar, score) in enumerate(zip(bars, f1_scores)):
            ax.text(score + 0.02, i, f'{score:.4f}', va='center', fontsize=10)
        
        plt.tight_layout()
        output_path = self.output_dir / output_filename
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"F1-score comparison saved to {output_path}")
    
    def plot_statistical_significance(
        self,
        statistical_results: Dict[str, Any],
        output_filename: str = "statistical_significance.png"
    ):
        """
        Plot statistical significance test results
        
        Args:
            statistical_results: Dict with comparison results from paired t-tests
        """
        if not statistical_results:
            logger.warning("No statistical results to plot")
            return
        
        comparisons = list(statistical_results.keys())
        p_values = [statistical_results[comp]['p_value'] for comp in comparisons]
        is_significant = [statistical_results[comp]['is_significant'] for comp in comparisons]
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        colors = ['green' if sig else 'red' for sig in is_significant]
        bars = ax.barh(comparisons, p_values, color=colors, alpha=0.7)
        
        # Add significance threshold line
        ax.axvline(x=0.05, color='black', linestyle='--', linewidth=2, label='α = 0.05')
        
        ax.set_xlabel('p-value', fontsize=12)
        ax.set_title('Statistical Significance Tests (Paired t-tests)', fontsize=14, fontweight='bold')
        ax.set_xlim(0, max(p_values) * 1.1 if p_values else 0.1)
        ax.legend()
        
        # Add p-value labels
        for i, (bar, p_val) in enumerate(zip(bars, p_values)):
            ax.text(p_val + 0.002, i, f'{p_val:.4f}', va='center', fontsize=9)
        
        plt.tight_layout()
        output_path = self.output_dir / output_filename
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Statistical significance plot saved to {output_path}")
    
    def plot_performance_tradeoff(
        self,
        results: List[SystemEvaluationResult],
        output_filename: str = "performance_tradeoff.png"
    ):
        """Plot F1-score vs Latency tradeoff"""
        systems = [r.system_name for r in results]
        f1_scores = [r.detection_metrics.f1_score for r in results]
        latencies = [r.efficiency_metrics.average_latency for r in results]
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        scatter = ax.scatter(latencies, f1_scores, s=200, alpha=0.6, c=range(len(systems)), cmap='viridis')
        
        for i, system in enumerate(systems):
            ax.annotate(system, (latencies[i], f1_scores[i]), 
                       xytext=(10, 10), textcoords='offset points',
                       fontsize=10, fontweight='bold',
                       bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.3))
        
        ax.set_xlabel('Average Latency (seconds)', fontsize=12)
        ax.set_ylabel('F1-Score', fontsize=12)
        ax.set_title('Performance vs Efficiency Tradeoff', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        output_path = self.output_dir / output_filename
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Performance tradeoff plot saved to {output_path}")
    
    def generate_all_plots(self, results: List[SystemEvaluationResult], statistical_results: Dict[str, Any] = None):
        logger.info("Generating all visualization plots...")
        
        self.plot_detection_metrics_comparison(results)
        self.plot_efficiency_metrics_comparison(results)
        self.plot_f1_score_comparison(results)
        self.plot_performance_tradeoff(results)
        
        if statistical_results:
            self.plot_statistical_significance(statistical_results)
        
        for result in results:
            self.plot_confusion_matrix(result)
        
        logger.info("All plots generated successfully")
