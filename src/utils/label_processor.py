import pandas as pd
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple

from src.utils.logger import get_logger

logger = get_logger(__name__)

class LabelProcessor:
    """Process ground truth labels from LogHub datasets"""
    
    def __init__(self):
        logger.info("LabelProcessor initialized")
    
    def load_loghub_labels(self, csv_path: str, label_column: str = 'Label') -> List[bool]:
        """
        Load labels from LogHub structured CSV file
        
        Args:
            csv_path: Path to the CSV file with labels
            label_column: Name of the label column (default: 'Label')
        
        Returns:
            List of boolean labels (True=anomaly, False=normal)
        """
        csv_file = Path(csv_path)
        
        if not csv_file.exists():
            raise FileNotFoundError(f"Label file not found: {csv_path}")
        
        try:
            df = pd.read_csv(csv_file)
            
            if label_column not in df.columns:
                # Try alternative column names
                possible_columns = ['Label', 'label', 'Anomaly', 'anomaly', 'EventId']
                for col in possible_columns:
                    if col in df.columns:
                        label_column = col
                        break
                else:
                    raise ValueError(f"No label column found. Available columns: {df.columns.tolist()}")
            
            # Convert labels to boolean
            # Typically: '-' or 'Normal' = False (normal), anything else = True (anomaly)
            labels = []
            for label in df[label_column]:
                if pd.isna(label):
                    labels.append(False)
                elif isinstance(label, str):
                    # '-' or 'Normal' indicates normal log
                    is_normal = label.strip() in ['-', 'Normal', 'normal', '']
                    labels.append(not is_normal)
                else:
                    # Numeric: 0 = normal, non-zero = anomaly
                    labels.append(bool(label))
            
            logger.info(f"Loaded {len(labels)} labels from {csv_path}")
            logger.info(f"Anomalies: {sum(labels)}/{len(labels)} ({sum(labels)/len(labels)*100:.1f}%)")
            
            return labels
            
        except Exception as e:
            logger.error(f"Error loading labels from {csv_path}: {e}")
            raise
    
    def load_json_labels(self, json_path: str) -> List[bool]:
        """
        Load labels from JSON file
        
        Args:
            json_path: Path to JSON file with 'labels' key
        
        Returns:
            List of boolean labels
        """
        json_file = Path(json_path)
        
        if not json_file.exists():
            raise FileNotFoundError(f"Label file not found: {json_path}")
        
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        if 'labels' not in data:
            raise ValueError(f"JSON file must contain 'labels' key")
        
        labels = data['labels']
        logger.info(f"Loaded {len(labels)} labels from {json_path}")
        logger.info(f"Anomalies: {sum(labels)}/{len(labels)} ({sum(labels)/len(labels)*100:.1f}%)")
        
        return labels
    
    def create_labels_from_severity(self, log_entries: List[Any]) -> List[bool]:
        """
        Create labels based on log severity (fallback method)
        ERROR, FATAL, CRITICAL = anomaly
        
        Args:
            log_entries: List of parsed log entries
        
        Returns:
            List of boolean labels
        """
        anomaly_severities = {'ERROR', 'FATAL', 'CRITICAL', 'EXCEPTION'}
        
        labels = []
        for entry in log_entries:
            severity = getattr(entry, 'severity', 'INFO').upper()
            is_anomaly = severity in anomaly_severities
            labels.append(is_anomaly)
        
        logger.info(f"Created {len(labels)} labels from severity")
        logger.info(f"Anomalies: {sum(labels)}/{len(labels)} ({sum(labels)/len(labels)*100:.1f}%)")
        
        return labels
    
    def save_labels(self, labels: List[bool], output_path: str):
        """Save labels to JSON file"""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'labels': labels,
            'total': len(labels),
            'anomalies': sum(labels),
            'normal': len(labels) - sum(labels),
            'anomaly_rate': sum(labels) / len(labels) if labels else 0
        }
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved {len(labels)} labels to {output_path}")
    
    def convert_csv_to_json(self, csv_path: str, json_path: str, label_column: str = 'Label'):
        """Convert LogHub CSV labels to JSON format"""
        labels = self.load_loghub_labels(csv_path, label_column)
        self.save_labels(labels, json_path)
        logger.info(f"Converted {csv_path} to {json_path}")
