import json
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

from src.utils.logger import get_logger
from src.utils.config_loader import config

logger = get_logger(__name__)

@dataclass
class KnowledgeDocument:
    id: str
    content: str
    title: str
    doc_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[np.ndarray] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'content': self.content,
            'title': self.title,
            'doc_type': self.doc_type,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat()
        }

class KnowledgeBaseManager:
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path or config.get('knowledge_base.storage_path', 'data/knowledge_base'))
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.embedding_model_name = config.get('knowledge_base.embedding_model', 'sentence-transformers/all-MiniLM-L6-v2')
        self.embedding_dim = config.get('knowledge_base.embedding_dimension', 384)
        self.chunk_size = config.get('knowledge_base.chunk_size', 512)
        self.chunk_overlap = config.get('knowledge_base.chunk_overlap', 50)
        
        logger.info(f"Initializing embedding model: {self.embedding_model_name}")
        self.embedding_model = SentenceTransformer(self.embedding_model_name)
        
        self.documents: List[KnowledgeDocument] = []
        self.index: Optional[faiss.Index] = None
        
        self._load_knowledge_base()
        
        logger.info(f"KnowledgeBaseManager initialized with {len(self.documents)} documents")
    
    def add_document(self, content: str, title: str, doc_type: str, metadata: Optional[Dict[str, Any]] = None) -> KnowledgeDocument:
        doc_id = f"{doc_type}_{len(self.documents)}_{datetime.now().timestamp()}"
        
        chunks = self._chunk_text(content)
        
        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{i}"
            
            doc = KnowledgeDocument(
                id=chunk_id,
                content=chunk,
                title=f"{title} (Part {i+1})",
                doc_type=doc_type,
                metadata=metadata or {}
            )
            
            doc.embedding = self._generate_embedding(chunk)
            self.documents.append(doc)
        
        logger.info(f"Added document '{title}' with {len(chunks)} chunks")
        return self.documents[-1]
    
    def add_documents_batch(self, documents: List[Dict[str, Any]]) -> int:
        count = 0
        for doc_data in documents:
            self.add_document(
                content=doc_data['content'],
                title=doc_data['title'],
                doc_type=doc_data.get('doc_type', 'general'),
                metadata=doc_data.get('metadata', {})
            )
            count += 1
        
        logger.info(f"Added {count} documents in batch")
        return count
    
    def build_index(self):
        if not self.documents:
            logger.warning("No documents to index")
            return
        
        embeddings = np.array([doc.embedding for doc in self.documents if doc.embedding is not None])
        
        if len(embeddings) == 0:
            logger.warning("No embeddings found")
            return
        
        embeddings = embeddings.astype('float32')
        
        self.index = faiss.IndexFlatL2(self.embedding_dim)
        self.index.add(embeddings)
        
        logger.info(f"Built FAISS index with {self.index.ntotal} vectors")
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if self.index is None or self.index.ntotal == 0:
            logger.warning("Index is empty, rebuilding...")
            self.build_index()
        
        if self.index is None or self.index.ntotal == 0:
            return []
        
        query_embedding = self._generate_embedding(query)
        query_embedding = np.array([query_embedding]).astype('float32')
        
        distances, indices = self.index.search(query_embedding, min(top_k, self.index.ntotal))
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < len(self.documents):
                doc = self.documents[idx]
                results.append({
                    'document': doc,
                    'similarity_score': float(1 / (1 + dist)),
                    'distance': float(dist)
                })
        
        return results
    
    def _chunk_text(self, text: str) -> List[str]:
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
            chunk_words = words[i:i + self.chunk_size]
            chunk = ' '.join(chunk_words)
            chunks.append(chunk)
        
        return chunks if chunks else [text]
    
    def _generate_embedding(self, text: str) -> np.ndarray:
        embedding = self.embedding_model.encode(text, convert_to_numpy=True)
        return embedding
    
    def save_knowledge_base(self):
        docs_file = self.storage_path / 'documents.pkl'
        index_file = self.storage_path / 'faiss.index'
        
        with open(docs_file, 'wb') as f:
            pickle.dump(self.documents, f)
        
        if self.index is not None:
            faiss.write_index(self.index, str(index_file))
        
        logger.info(f"Saved knowledge base to {self.storage_path}")
    
    def _load_knowledge_base(self):
        docs_file = self.storage_path / 'documents.pkl'
        index_file = self.storage_path / 'faiss.index'
        
        if docs_file.exists():
            with open(docs_file, 'rb') as f:
                self.documents = pickle.load(f)
            logger.info(f"Loaded {len(self.documents)} documents")
        
        if index_file.exists():
            self.index = faiss.read_index(str(index_file))
            logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors")
    
    def populate_default_knowledge(self):
        default_knowledge = [
            {
                'title': 'HDFS Block Corruption',
                'content': 'HDFS block corruption occurs when data blocks become unreadable or corrupted. Common causes include hardware failures, network issues, or software bugs. Symptoms include "Replica not found" errors and "Block is corrupt" messages. Resolution: Run fsck to identify corrupted blocks, remove corrupted replicas, and restore from backup.',
                'doc_type': 'incident',
                'metadata': {'severity': 'HIGH', 'system': 'HDFS'}
            },
            {
                'title': 'Connection Timeout Errors',
                'content': 'Connection timeout errors indicate network connectivity issues or service unavailability. Common patterns include "Connection timed out", "Unable to connect", or "Connection refused". Troubleshooting steps: Check network connectivity, verify service is running, check firewall rules, and review resource limits.',
                'doc_type': 'troubleshooting',
                'metadata': {'severity': 'MEDIUM', 'category': 'network'}
            },
            {
                'title': 'Out of Memory Errors',
                'content': 'Out of Memory (OOM) errors occur when applications exhaust available memory. Indicators include "OutOfMemoryError", "Cannot allocate memory", or sudden process termination. Resolution: Increase heap size, optimize memory usage, identify memory leaks, and implement proper garbage collection tuning.',
                'doc_type': 'incident',
                'metadata': {'severity': 'CRITICAL', 'category': 'resource'}
            },
            {
                'title': 'Disk Space Exhaustion',
                'content': 'Disk space exhaustion prevents new data writes and can cause system instability. Warning signs include "No space left on device", "Disk quota exceeded", or write failures. Immediate actions: Clean up temporary files, rotate logs, archive old data, and expand storage capacity.',
                'doc_type': 'incident',
                'metadata': {'severity': 'HIGH', 'category': 'storage'}
            },
            {
                'title': 'Authentication Failures',
                'content': 'Authentication failures indicate credential issues or permission problems. Common messages include "Authentication failed", "Access denied", "Invalid credentials", or "Permission denied". Resolution: Verify credentials, check user permissions, review authentication configuration, and check for expired certificates.',
                'doc_type': 'troubleshooting',
                'metadata': {'severity': 'MEDIUM', 'category': 'security'}
            },
            {
                'title': 'Service Unavailable Errors',
                'content': 'Service unavailable errors indicate backend services are not responding. Patterns include "503 Service Unavailable", "Service temporarily unavailable", or "Backend service down". Troubleshooting: Check service health, verify dependencies, review resource utilization, and check for cascading failures.',
                'doc_type': 'incident',
                'metadata': {'severity': 'HIGH', 'category': 'availability'}
            },
            {
                'title': 'Database Connection Pool Exhaustion',
                'content': 'Connection pool exhaustion occurs when all database connections are in use. Symptoms include "Cannot get connection from pool", "Connection pool timeout", or slow query performance. Resolution: Increase pool size, optimize query performance, fix connection leaks, and implement connection timeout policies.',
                'doc_type': 'troubleshooting',
                'metadata': {'severity': 'HIGH', 'category': 'database'}
            },
            {
                'title': 'SSL Certificate Errors',
                'content': 'SSL certificate errors prevent secure connections. Common messages include "Certificate expired", "Certificate not trusted", "Hostname mismatch", or "Invalid certificate chain". Resolution: Renew expired certificates, update certificate trust store, verify certificate configuration, and check certificate validity period.',
                'doc_type': 'troubleshooting',
                'metadata': {'severity': 'MEDIUM', 'category': 'security'}
            }
        ]
        
        logger.info("Populating knowledge base with default documents")
        self.add_documents_batch(default_knowledge)
        self.build_index()
        self.save_knowledge_base()
        logger.info("Default knowledge base populated successfully")
    
    def get_statistics(self) -> Dict[str, Any]:
        doc_types = {}
        for doc in self.documents:
            doc_types[doc.doc_type] = doc_types.get(doc.doc_type, 0) + 1
        
        return {
            'total_documents': len(self.documents),
            'document_types': doc_types,
            'index_size': self.index.ntotal if self.index else 0,
            'embedding_dimension': self.embedding_dim
        }
