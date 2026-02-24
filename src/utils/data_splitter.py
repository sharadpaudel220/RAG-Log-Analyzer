import numpy as np
from typing import List, Tuple, Dict, Any
from pathlib import Path
import json

from src.preprocessing.log_preprocessor import ParsedLogEntry
from src.utils.logger import get_logger
from src.utils.config_loader import config

logger = get_logger(__name__)

class DataSplitter:
    """Handles train/test splitting for log datasets"""
    
    def __init__(self, train_ratio: float = 0.7, random_seed: int = 42):
        self.train_ratio = train_ratio
        self.random_seed = random_seed
        np.random.seed(random_seed)
        
        logger.info(f"DataSplitter initialized with train_ratio={train_ratio}, seed={random_seed}")
    
    def split_data(
        self,
        log_entries: List[ParsedLogEntry],
        ground_truth: List[bool]
    ) -> Tuple[List[ParsedLogEntry], List[bool], List[ParsedLogEntry], List[bool]]:
        """
        Split log entries and ground truth into train and test sets
        
        Args:
            log_entries: List of parsed log entries
            ground_truth: List of boolean labels (True=anomaly, False=normal)
        
        Returns:
            Tuple of (train_logs, train_labels, test_logs, test_labels)
        """
        if len(log_entries) != len(ground_truth):
            raise ValueError(f"Mismatch: {len(log_entries)} logs but {len(ground_truth)} labels")
        
        n_samples = len(log_entries)
        n_train = int(n_samples * self.train_ratio)
        
        # Create indices and shuffle
        indices = np.arange(n_samples)
        np.random.shuffle(indices)
        
        train_indices = indices[:n_train]
        test_indices = indices[n_train:]
        
        train_logs = [log_entries[i] for i in train_indices]
        train_labels = [ground_truth[i] for i in train_indices]
        test_logs = [log_entries[i] for i in test_indices]
        test_labels = [ground_truth[i] for i in test_indices]
        
        logger.info(f"Split data: {len(train_logs)} train, {len(test_logs)} test")
        logger.info(f"Train anomalies: {sum(train_labels)}/{len(train_labels)} ({sum(train_labels)/len(train_labels)*100:.1f}%)")
        logger.info(f"Test anomalies: {sum(test_labels)}/{len(test_labels)} ({sum(test_labels)/len(test_labels)*100:.1f}%)")
        
        return train_logs, train_labels, test_logs, test_labels
    
    def stratified_split(
        self,
        log_entries: List[ParsedLogEntry],
        ground_truth: List[bool]
    ) -> Tuple[List[ParsedLogEntry], List[bool], List[ParsedLogEntry], List[bool]]:
        """
        Stratified split to maintain class distribution in train/test
        
        Args:
            log_entries: List of parsed log entries
            ground_truth: List of boolean labels
        
        Returns:
            Tuple of (train_logs, train_labels, test_logs, test_labels)
        """
        if len(log_entries) != len(ground_truth):
            raise ValueError(f"Mismatch: {len(log_entries)} logs but {len(ground_truth)} labels")
        
        # Separate normal and anomaly indices
        normal_indices = [i for i, label in enumerate(ground_truth) if not label]
        anomaly_indices = [i for i, label in enumerate(ground_truth) if label]
        
        # Shuffle each class
        np.random.shuffle(normal_indices)
        np.random.shuffle(anomaly_indices)
        
        # Split each class
        n_train_normal = int(len(normal_indices) * self.train_ratio)
        n_train_anomaly = int(len(anomaly_indices) * self.train_ratio)
        
        train_indices = normal_indices[:n_train_normal] + anomaly_indices[:n_train_anomaly]
        test_indices = normal_indices[n_train_normal:] + anomaly_indices[n_train_anomaly:]
        
        # Shuffle combined indices
        np.random.shuffle(train_indices)
        np.random.shuffle(test_indices)
        
        train_logs = [log_entries[i] for i in train_indices]
        train_labels = [ground_truth[i] for i in train_indices]
        test_logs = [log_entries[i] for i in test_indices]
        test_labels = [ground_truth[i] for i in test_indices]
        
        logger.info(f"Stratified split: {len(train_logs)} train, {len(test_logs)} test")
        logger.info(f"Train anomalies: {sum(train_labels)}/{len(train_labels)} ({sum(train_labels)/len(train_labels)*100:.1f}%)")
        logger.info(f"Test anomalies: {sum(test_labels)}/{len(test_labels)} ({sum(test_labels)/len(test_labels)*100:.1f}%)")
        
        return train_logs, train_labels, test_logs, test_labels
    
    def save_split(
        self,
        train_logs: List[ParsedLogEntry],
        train_labels: List[bool],
        test_logs: List[ParsedLogEntry],
        test_labels: List[bool],
        output_dir: str
    ):
        """Save train/test split to files"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save split metadata
        split_info = {
            'train_size': len(train_logs),
            'test_size': len(test_logs),
            'train_ratio': self.train_ratio,
            'random_seed': self.random_seed,
            'train_anomaly_count': sum(train_labels),
            'test_anomaly_count': sum(test_labels)
        }
        
        with open(output_path / 'split_info.json', 'w') as f:
            json.dump(split_info, f, indent=2)
        
        # Save labels
        with open(output_path / 'train_labels.json', 'w') as f:
            json.dump({'labels': train_labels}, f)
        
        with open(output_path / 'test_labels.json', 'w') as f:
            json.dump({'labels': test_labels}, f)
        
        logger.info(f"Split data saved to {output_path}")
