import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from sklearn.ensemble import IsolationForest
from sklearn.feature_extraction.text import TfidfVectorizer

from src.preprocessing.log_preprocessor import ParsedLogEntry
from src.utils.logger import get_logger
from src.utils.config_loader import config

logger = get_logger(__name__)

@dataclass
class IsolationForestResult:
    log_entry: ParsedLogEntry
    is_anomaly: bool
    anomaly_score: float
    severity: str
    confidence_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'log_entry': self.log_entry.to_dict(),
            'is_anomaly': self.is_anomaly,
            'anomaly_score': self.anomaly_score,
            'severity': self.severity,
            'confidence_score': self.confidence_score
        }

class IsolationForestSystem:
    def __init__(self):
        self.contamination = config.get('baselines.isolation_forest.contamination', 0.1)
        self.n_estimators = config.get('baselines.isolation_forest.n_estimators', 100)
        self.max_samples = config.get('baselines.isolation_forest.max_samples', 256)
        self.random_state = config.get('baselines.isolation_forest.random_state', 42)
        
        self.model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            max_samples=self.max_samples,
            random_state=self.random_state,
            n_jobs=-1
        )
        
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            ngram_range=(1, 2),
            min_df=2
        )
        
        self.is_trained = False
        
        logger.info("IsolationForestSystem initialized")
    
    def train(self, log_entries: List[ParsedLogEntry]):
        if not log_entries:
            logger.warning("No log entries provided for training")
            return
        
        texts = [entry.raw_content for entry in log_entries]
        
        X = self.vectorizer.fit_transform(texts)
        
        self.model.fit(X)
        
        self.is_trained = True
        logger.info(f"Trained IsolationForest on {len(log_entries)} log entries")
    
    def analyze(self, log_entry: ParsedLogEntry) -> IsolationForestResult:
        if not self.is_trained:
            logger.warning("Model not trained, returning default result")
            return IsolationForestResult(
                log_entry=log_entry,
                is_anomaly=False,
                anomaly_score=0.0,
                severity='INFO',
                confidence_score=0.0
            )
        
        text = log_entry.raw_content
        X = self.vectorizer.transform([text])
        
        prediction = self.model.predict(X)[0]
        is_anomaly = prediction == -1
        
        anomaly_score = -self.model.score_samples(X)[0]
        
        severity = self._score_to_severity(anomaly_score, is_anomaly)
        
        confidence_score = min(abs(anomaly_score), 1.0)
        
        return IsolationForestResult(
            log_entry=log_entry,
            is_anomaly=is_anomaly,
            anomaly_score=float(anomaly_score),
            severity=severity,
            confidence_score=float(confidence_score)
        )
    
    def analyze_batch(self, log_entries: List[ParsedLogEntry]) -> List[IsolationForestResult]:
        if not self.is_trained:
            logger.warning("Model not trained, training on provided data")
            self.train(log_entries)
        
        results = []
        
        texts = [entry.raw_content for entry in log_entries]
        X = self.vectorizer.transform(texts)
        
        predictions = self.model.predict(X)
        scores = -self.model.score_samples(X)
        
        for i, entry in enumerate(log_entries):
            is_anomaly = predictions[i] == -1
            anomaly_score = float(scores[i])
            severity = self._score_to_severity(anomaly_score, is_anomaly)
            confidence_score = min(abs(anomaly_score), 1.0)
            
            results.append(IsolationForestResult(
                log_entry=entry,
                is_anomaly=is_anomaly,
                anomaly_score=anomaly_score,
                severity=severity,
                confidence_score=float(confidence_score)
            ))
        
        anomaly_count = sum(1 for r in results if r.is_anomaly)
        logger.info(f"IsolationForest analysis: {anomaly_count}/{len(results)} anomalies detected")
        
        return results
    
    def _score_to_severity(self, score: float, is_anomaly: bool) -> str:
        if not is_anomaly:
            return 'INFO'
        
        if score > 0.7:
            return 'CRITICAL'
        elif score > 0.5:
            return 'HIGH'
        elif score > 0.3:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def get_statistics(self) -> Dict[str, Any]:
        return {
            'is_trained': self.is_trained,
            'contamination': self.contamination,
            'n_estimators': self.n_estimators,
            'max_samples': self.max_samples,
            'vocabulary_size': len(self.vectorizer.vocabulary_) if self.is_trained else 0
        }
