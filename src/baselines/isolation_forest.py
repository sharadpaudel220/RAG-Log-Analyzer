import numpy as np
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from sklearn.ensemble import IsolationForest
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy import sparse

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
    def __init__(self, contamination=None):
        # Allow contamination to be set per dataset, or use 'auto' for adaptive estimation
        self.contamination = contamination if contamination is not None else config.get('baselines.isolation_forest.contamination', 'auto')
        self.n_estimators = config.get('baselines.isolation_forest.n_estimators', 100)
        self.max_samples = config.get('baselines.isolation_forest.max_samples', 256)
        self.random_state = config.get('baselines.isolation_forest.random_state', 42)
        self.max_features = config.get('baselines.isolation_forest.max_features', 1500)
        self.ngram_max = config.get('baselines.isolation_forest.ngram_max', 2)
        self.min_df_default = config.get('baselines.isolation_forest.min_df', 2)
        self.small_batch_min_df = config.get('baselines.isolation_forest.small_batch_min_df', 1)
        self.small_batch_threshold = config.get('baselines.isolation_forest.small_batch_threshold', 25)
        
        # Use 'auto' if contamination is not explicitly set - this estimates from data
        model_contamination = self.contamination if self.contamination != 'auto' else 'auto'
        
        self.model = IsolationForest(
            contamination=model_contamination,
            n_estimators=self.n_estimators,
            max_samples=self.max_samples,
            random_state=self.random_state,
            n_jobs=-1
        )

        self.vectorizer: Optional[TfidfVectorizer] = None
        
        self.is_trained = False
        
        logger.info("IsolationForestSystem initialized")

    def _create_vectorizer(self, num_docs: int) -> TfidfVectorizer:
        min_df = self.min_df_default
        if num_docs < int(self.small_batch_threshold):
            min_df = int(self.small_batch_min_df)

        return TfidfVectorizer(
            max_features=int(self.max_features),
            ngram_range=(1, int(self.ngram_max)),
            min_df=min_df,
            lowercase=True
        )

    def _normalize_text(self, text: str) -> str:
        if not text:
            return ''

        t = text
        t = re.sub(r'\b\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?\b', ' <TS> ', t)
        t = re.sub(r'\b\d{1,2}:\d{2}:\d{2}(?:\.\d+)?\b', ' <TIME> ', t)
        t = re.sub(r'\b\d+\b', ' <NUM> ', t)
        t = re.sub(r'\b[0-9a-f]{8,}\b', ' <HEX> ', t, flags=re.IGNORECASE)
        t = re.sub(r'\b[\w.+-]+@[\w-]+\.[\w.-]+\b', ' <EMAIL> ', t)
        t = re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', ' <IP> ', t)
        t = re.sub(r'\s+', ' ', t).strip()
        return t

    def _severity_to_onehot(self, severity: str) -> List[float]:
        sev = (severity or '').upper().strip()
        order = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'FATAL']
        return [1.0 if sev == k else 0.0 for k in order]

    def _numeric_features(self, entry: ParsedLogEntry) -> List[float]:
        text = entry.raw_content or ''
        length = float(len(text))

        if length <= 0:
            digit_ratio = 0.0
            upper_ratio = 0.0
        else:
            digits = sum(1 for c in text if c.isdigit())
            uppers = sum(1 for c in text if c.isupper())
            digit_ratio = float(digits) / length
            upper_ratio = float(uppers) / length

        return [length, digit_ratio, upper_ratio] + self._severity_to_onehot(getattr(entry, 'severity', '') or '')

    def _build_feature_matrix(self, log_entries: List[ParsedLogEntry], fit_vectorizer: bool) -> sparse.csr_matrix:
        texts = [self._normalize_text(entry.raw_content) for entry in log_entries]

        if fit_vectorizer or self.vectorizer is None:
            self.vectorizer = self._create_vectorizer(len(texts))
            X_text = self.vectorizer.fit_transform(texts)
        else:
            X_text = self.vectorizer.transform(texts)

        num = np.array([self._numeric_features(e) for e in log_entries], dtype=np.float32)
        X_num = sparse.csr_matrix(num)

        return sparse.hstack([X_text, X_num], format='csr')
    
    def train(self, log_entries: List[ParsedLogEntry]):
        if not log_entries:
            logger.warning("No log entries provided for training")
            return

        X = self._build_feature_matrix(log_entries, fit_vectorizer=True)

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

        X = self._build_feature_matrix([log_entry], fit_vectorizer=False)
        
        prediction = self.model.predict(X)[0]
        is_anomaly = prediction == -1
        
        anomaly_score = -self.model.score_samples(X)[0]
        
        severity = self._score_to_severity(anomaly_score, is_anomaly)
        confidence_score = float(1.0 - np.exp(-max(float(anomaly_score), 0.0)))
        
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

        X = self._build_feature_matrix(log_entries, fit_vectorizer=False)
        
        predictions = self.model.predict(X)
        scores = -self.model.score_samples(X)
        
        for i, entry in enumerate(log_entries):
            is_anomaly = predictions[i] == -1
            anomaly_score = float(scores[i])
            severity = self._score_to_severity(anomaly_score, is_anomaly)
            confidence_score = float(1.0 - np.exp(-max(float(anomaly_score), 0.0)))
            
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
            'vocabulary_size': len(self.vectorizer.vocabulary_) if (self.is_trained and self.vectorizer and self.vectorizer.vocabulary_) else 0
        }
