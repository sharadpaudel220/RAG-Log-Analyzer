"""
Benchmark dataset loader with validated ground truth for thesis-level evaluation.

Supports HDFS, BGL, and custom labeled datasets from loghub.
Ground truth is loaded from pre-labeled files, NOT inferred from severity keywords.
"""

import json
import csv
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
import numpy as np

from src.utils.logger import get_logger
from src.input_layer.log_ingestion import RawLogEntry

logger = get_logger(__name__)

DATASETS_DIR = Path('data/datasets')


@dataclass
class BenchmarkDataset:
    """A benchmark dataset with pre-labeled ground truth."""
    name: str
    raw_logs: List[RawLogEntry]
    ground_truth: List[bool]
    metadata: Dict[str, Any]
    
    def __post_init__(self):
        assert len(self.raw_logs) == len(self.ground_truth), \
            f"Logs ({len(self.raw_logs)}) and labels ({len(self.ground_truth)}) must match"
    
    @property
    def total_logs(self) -> int:
        return len(self.raw_logs)
    
    @property
    def anomaly_count(self) -> int:
        return sum(self.ground_truth)
    
    @property
    def normal_count(self) -> int:
        return self.total_logs - self.anomaly_count
    
    @property
    def anomaly_ratio(self) -> float:
        return self.anomaly_count / self.total_logs if self.total_logs > 0 else 0.0
    
    def get_fold(self, fold_idx: int, n_folds: int = 5) -> Tuple[List[RawLogEntry], List[bool], List[RawLogEntry], List[bool]]:
        """Get train/test split for k-fold cross-validation."""
        indices = np.arange(self.total_logs)
        np.random.seed(42)  # reproducible
        np.random.shuffle(indices)
        
        fold_size = self.total_logs // n_folds
        start = fold_idx * fold_size
        end = start + fold_size if fold_idx < n_folds - 1 else self.total_logs
        
        test_idx = indices[start:end]
        train_idx = np.concatenate([indices[:start], indices[end:]])
        
        train_logs = [self.raw_logs[i] for i in train_idx]
        train_labels = [self.ground_truth[i] for i in train_idx]
        test_logs = [self.raw_logs[i] for i in test_idx]
        test_labels = [self.ground_truth[i] for i in test_idx]
        
        return train_logs, train_labels, test_logs, test_labels
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'total_logs': self.total_logs,
            'anomaly_count': self.anomaly_count,
            'normal_count': self.normal_count,
            'anomaly_ratio': round(self.anomaly_ratio, 4),
            'metadata': self.metadata
        }


def load_hdfs_dataset(max_logs: Optional[int] = None) -> Optional[BenchmarkDataset]:
    """Load HDFS dataset with labeled ground truth."""
    dataset_dir = DATASETS_DIR / 'hdfs'
    log_file = dataset_dir / 'HDFS_2k.log'
    label_file = dataset_dir / 'ground_truth.json'
    
    if not log_file.exists() or not label_file.exists():
        logger.warning(f"HDFS dataset files not found at {dataset_dir}")
        return None
    
    # Load ground truth labels
    with open(label_file, 'r') as f:
        label_data = json.load(f)
    
    ground_truth = label_data.get('labels', [])
    
    # Load log lines
    with open(log_file, 'r') as f:
        log_lines = [line.strip() for line in f if line.strip()]
    
    if max_logs:
        log_lines = log_lines[:max_logs]
        ground_truth = ground_truth[:max_logs]
    
    # Ensure alignment
    min_len = min(len(log_lines), len(ground_truth))
    log_lines = log_lines[:min_len]
    ground_truth = ground_truth[:min_len]
    
    raw_logs = []
    for i, line in enumerate(log_lines):
        raw_logs.append(RawLogEntry(
            content=line,
            line_number=i + 1,
            source_file=str(log_file),
            metadata={'dataset': 'hdfs', 'line_id': i + 1}
        ))
    
    dataset = BenchmarkDataset(
        name='HDFS',
        raw_logs=raw_logs,
        ground_truth=ground_truth,
        metadata={
            'source': 'loghub HDFS dataset',
            'total_original': label_data.get('total', min_len),
            'anomalies_original': label_data.get('anomalies', sum(ground_truth)),
            'normal_original': label_data.get('normal', len(ground_truth) - sum(ground_truth))
        }
    )
    
    logger.info(f"Loaded HDFS dataset: {dataset.total_logs} logs, {dataset.anomaly_count} anomalies ({dataset.anomaly_ratio:.2%})")
    return dataset


def load_bgl_dataset(max_logs: Optional[int] = None) -> Optional[BenchmarkDataset]:
    """Load BGL dataset with labeled ground truth."""
    dataset_dir = DATASETS_DIR / 'bgl'
    log_file = dataset_dir / 'BGL_2k.log'
    label_file = dataset_dir / 'ground_truth.json'
    
    if not log_file.exists() or not label_file.exists():
        logger.warning(f"BGL dataset files not found at {dataset_dir}")
        return None
    
    # Load ground truth labels
    with open(label_file, 'r') as f:
        label_data = json.load(f)
    
    ground_truth = label_data.get('labels', [])
    
    # Load log lines
    with open(log_file, 'r') as f:
        log_lines = [line.strip() for line in f if line.strip()]
    
    if max_logs:
        log_lines = log_lines[:max_logs]
        ground_truth = ground_truth[:max_logs]
    
    # Ensure alignment
    min_len = min(len(log_lines), len(ground_truth))
    log_lines = log_lines[:min_len]
    ground_truth = ground_truth[:min_len]
    
    raw_logs = []
    for i, line in enumerate(log_lines):
        raw_logs.append(RawLogEntry(
            content=line,
            line_number=i + 1,
            source_file=str(log_file),
            metadata={'dataset': 'bgl', 'line_id': i + 1}
        ))
    
    dataset = BenchmarkDataset(
        name='BGL',
        raw_logs=raw_logs,
        ground_truth=ground_truth,
        metadata={
            'source': 'loghub BGL dataset',
            'total_original': label_data.get('total', min_len),
            'anomalies_original': label_data.get('anomalies', sum(ground_truth)),
            'normal_original': label_data.get('normal', len(ground_truth) - sum(ground_truth))
        }
    )
    
    logger.info(f"Loaded BGL dataset: {dataset.total_logs} logs, {dataset.anomaly_count} anomalies ({dataset.anomaly_ratio:.2%})")
    return dataset


def load_custom_dataset(name: str, log_file: str, label_file: str, max_logs: Optional[int] = None) -> Optional[BenchmarkDataset]:
    """Load a custom dataset with CSV labels (format: line_id,is_anomaly)."""
    log_path = Path(log_file)
    label_path = Path(label_file)
    
    if not log_path.exists():
        logger.warning(f"Log file not found: {log_file}")
        return None
    if not label_path.exists():
        logger.warning(f"Label file not found: {label_file}")
        return None
    
    # Load labels from CSV
    labels = {}
    with open(label_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            line_id = int(row.get('line_id', row.get('LineId', 0)))
            is_anomaly = row.get('is_anomaly', row.get('label', '0')).lower() in ('1', 'true', 'yes', 'anomaly')
            labels[line_id] = is_anomaly
    
    # Load log lines
    with open(log_path, 'r') as f:
        log_lines = [line.strip() for line in f if line.strip()]
    
    if max_logs:
        log_lines = log_lines[:max_logs]
    
    raw_logs = []
    ground_truth = []
    for i, line in enumerate(log_lines):
        line_id = i + 1
        raw_logs.append(RawLogEntry(
            content=line,
            line_number=line_id,
            source_file=str(log_path),
            metadata={'dataset': name, 'line_id': line_id}
        ))
        ground_truth.append(labels.get(line_id, False))
    
    dataset = BenchmarkDataset(
        name=name,
        raw_logs=raw_logs,
        ground_truth=ground_truth,
        metadata={'source': 'custom', 'label_file': str(label_path)}
    )
    
    logger.info(f"Loaded custom dataset '{name}': {dataset.total_logs} logs, {dataset.anomaly_count} anomalies")
    return dataset


def list_available_datasets() -> List[Dict[str, Any]]:
    """List all available benchmark datasets."""
    datasets = []
    
    hdfs = load_hdfs_dataset(max_logs=1)
    if hdfs:
        datasets.append(hdfs.to_dict())
    
    bgl = load_bgl_dataset(max_logs=1)
    if bgl:
        datasets.append(bgl.to_dict())
    
    return datasets


def get_dataset(name: str, max_logs: Optional[int] = None) -> Optional[BenchmarkDataset]:
    """Get a dataset by name."""
    name_lower = name.lower()
    if name_lower in ('hdfs', 'hdfs_2k'):
        return load_hdfs_dataset(max_logs)
    elif name_lower in ('bgl', 'bgl_2k'):
        return load_bgl_dataset(max_logs)
    else:
        logger.error(f"Unknown dataset: {name}")
        return None
