from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import re

from src.knowledge_base.knowledge_manager import KnowledgeBaseManager, KnowledgeDocument
from src.utils.logger import get_logger
from src.utils.config_loader import config

logger = get_logger(__name__)

@dataclass
class RetrievalResult:
    document: KnowledgeDocument
    similarity_score: float
    relevance_score: float
    rank: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'document': self.document.to_dict(),
            'similarity_score': self.similarity_score,
            'relevance_score': self.relevance_score,
            'rank': self.rank
        }

class RetrievalSystem:
    def __init__(self, knowledge_manager: KnowledgeBaseManager):
        self.knowledge_manager = knowledge_manager
        self.top_k = config.get('retrieval.top_k', 5)
        self.similarity_threshold = config.get('retrieval.similarity_threshold', 0.7)
        self.retrieval_strategy = config.get('retrieval.retrieval_strategy', 'hybrid')
        self.rerank = config.get('retrieval.rerank', True)
        
        logger.info(f"RetrievalSystem initialized with strategy: {self.retrieval_strategy}")
    
    def retrieve(self, query: str, top_k: Optional[int] = None, context: Optional[Dict[str, Any]] = None) -> List[RetrievalResult]:
        top_k = top_k or self.top_k
        
        if self.retrieval_strategy == 'semantic':
            results = self._semantic_retrieval(query, top_k)
        elif self.retrieval_strategy == 'keyword':
            results = self._keyword_retrieval(query, top_k)
        elif self.retrieval_strategy == 'hybrid':
            results = self._hybrid_retrieval(query, top_k)
        else:
            logger.warning(f"Unknown strategy {self.retrieval_strategy}, using semantic")
            results = self._semantic_retrieval(query, top_k)
        
        if self.rerank and context:
            results = self._rerank_results(results, query, context)
        
        results = [r for r in results if r.similarity_score >= self.similarity_threshold]
        
        logger.info(f"Retrieved {len(results)} documents for query: {query[:100]}")
        return results
    
    def _semantic_retrieval(self, query: str, top_k: int) -> List[RetrievalResult]:
        search_results = self.knowledge_manager.search(query, top_k=top_k * 2)
        
        retrieval_results = []
        for i, result in enumerate(search_results[:top_k]):
            retrieval_results.append(RetrievalResult(
                document=result['document'],
                similarity_score=result['similarity_score'],
                relevance_score=result['similarity_score'],
                rank=i + 1
            ))
        
        return retrieval_results
    
    def _keyword_retrieval(self, query: str, top_k: int) -> List[RetrievalResult]:
        query_terms = set(query.lower().split())
        
        scored_docs = []
        for doc in self.knowledge_manager.documents:
            doc_terms = set(doc.content.lower().split())
            
            overlap = len(query_terms.intersection(doc_terms))
            score = overlap / max(len(query_terms), 1)
            
            if score > 0:
                scored_docs.append((doc, score))
        
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        
        retrieval_results = []
        for i, (doc, score) in enumerate(scored_docs[:top_k]):
            retrieval_results.append(RetrievalResult(
                document=doc,
                similarity_score=score,
                relevance_score=score,
                rank=i + 1
            ))
        
        return retrieval_results
    
    def _hybrid_retrieval(self, query: str, top_k: int) -> List[RetrievalResult]:
        semantic_results = self._semantic_retrieval(query, top_k)
        keyword_results = self._keyword_retrieval(query, top_k)
        
        doc_scores = {}
        
        for result in semantic_results:
            doc_id = result.document.id
            doc_scores[doc_id] = {
                'document': result.document,
                'semantic_score': result.similarity_score,
                'keyword_score': 0.0
            }
        
        for result in keyword_results:
            doc_id = result.document.id
            if doc_id in doc_scores:
                doc_scores[doc_id]['keyword_score'] = result.similarity_score
            else:
                doc_scores[doc_id] = {
                    'document': result.document,
                    'semantic_score': 0.0,
                    'keyword_score': result.similarity_score
                }
        
        retrieval_results = []
        for doc_id, scores in doc_scores.items():
            combined_score = 0.7 * scores['semantic_score'] + 0.3 * scores['keyword_score']
            retrieval_results.append(RetrievalResult(
                document=scores['document'],
                similarity_score=scores['semantic_score'],
                relevance_score=combined_score,
                rank=0
            ))
        
        retrieval_results.sort(key=lambda x: x.relevance_score, reverse=True)
        
        for i, result in enumerate(retrieval_results[:top_k]):
            result.rank = i + 1
        
        return retrieval_results[:top_k]
    
    def _rerank_results(self, results: List[RetrievalResult], query: str, context: Dict[str, Any]) -> List[RetrievalResult]:
        for result in results:
            boost = 0.0
            
            if 'severity' in context and 'severity' in result.document.metadata:
                if context['severity'] == result.document.metadata['severity']:
                    boost += 0.1
            
            if 'component' in context and 'system' in result.document.metadata:
                if context['component'] and context['component'].lower() in result.document.metadata['system'].lower():
                    boost += 0.1
            
            error_keywords = ['error', 'exception', 'failed', 'failure', 'critical']
            if any(keyword in query.lower() for keyword in error_keywords):
                if result.document.doc_type == 'incident':
                    boost += 0.15
            
            result.relevance_score = min(1.0, result.relevance_score + boost)
        
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        
        for i, result in enumerate(results):
            result.rank = i + 1
        
        return results
    
    def retrieve_by_template(self, template_id: int, top_k: Optional[int] = None) -> List[RetrievalResult]:
        query = f"template_{template_id}"
        return self.retrieve(query, top_k)
    
    def retrieve_by_severity(self, severity: str, top_k: Optional[int] = None) -> List[RetrievalResult]:
        top_k = top_k or self.top_k
        
        filtered_docs = [
            doc for doc in self.knowledge_manager.documents
            if doc.metadata.get('severity') == severity
        ]
        
        retrieval_results = []
        for i, doc in enumerate(filtered_docs[:top_k]):
            retrieval_results.append(RetrievalResult(
                document=doc,
                similarity_score=1.0,
                relevance_score=1.0,
                rank=i + 1
            ))
        
        return retrieval_results
    
    def format_context(self, results: List[RetrievalResult]) -> str:
        if not results:
            return "No relevant knowledge found."
        
        context_parts = []
        for result in results:
            doc = result.document
            context_parts.append(
                f"[Document {result.rank}] {doc.title}\n"
                f"Type: {doc.doc_type} | Relevance: {result.relevance_score:.2f}\n"
                f"Content: {doc.content}\n"
            )
        
        return "\n---\n".join(context_parts)
