"""Case 9 - Non-Agentic RAG: Single-Pass Classification

Objective: Verify that the NonAgenticRAG baseline performs exactly one
retrieval step and one LLM call per log entry without any reasoning loop,
addressing Objective O4.

Action:
  1. Pass a preprocessed HDFS log to the NonAgenticRAG classifier.
  2. Monitor the number of FAISS queries and Groq API calls made.
  3. Inspect the classification output.

Expected Result:
  Exactly one FAISS query and one Groq API call are made per log entry.
  No reasoning loop executes. The output contains a valid classification
  and confidence score.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.input_layer.log_ingestion import RawLogEntry
from src.preprocessing.log_preprocessor import LogPreprocessor
from src.knowledge_base.knowledge_manager import KnowledgeBaseManager
from src.retrieval.retrieval_system import RetrievalSystem
from src.llm_engine.llm_interface import LLMEngine, LLMResponse
from src.baselines.non_agentic_rag import NonAgenticRAGSystem

def run_case9():
    print("\n--- Non-Agentic RAG: Single-Pass Classification ---")

    # Build components
    preprocessor = LogPreprocessor()
    kb_manager   = KnowledgeBaseManager()
    if kb_manager.index is None or kb_manager.index.ntotal == 0:
        kb_manager.populate_default_knowledge()
        kb_manager.build_index()
    retrieval    = RetrievalSystem(kb_manager)
    llm_engine   = LLMEngine()
    system       = NonAgenticRAGSystem(retrieval, llm_engine)

    raw_log = (
        "081109 203518 143 ERROR dfs.DataNode$DataXceiver: "
        "Got exception while serving blk_-1608999687919862906 to /10.251.31.5:54106"
    )
    print(f"\n  Input log  : {raw_log[:80]}...")

    entry  = RawLogEntry(content=raw_log, source_file="HDFS.log", line_number=1)
    parsed = preprocessor.preprocess([entry])[0]

    # Wrap retrieve and generate to count calls
    retrieve_calls = []
    llm_calls      = []

    original_retrieve = retrieval.retrieve
    original_analyze  = llm_engine.analyze_log_anomaly

    def counting_retrieve(*args, **kwargs):
        retrieve_calls.append(1)
        return original_retrieve(*args, **kwargs)

    def counting_analyze(*args, **kwargs):
        llm_calls.append(1)
        return original_analyze(*args, **kwargs)

    retrieval.retrieve              = counting_retrieve
    llm_engine.analyze_log_anomaly  = counting_analyze

    # Run analysis
    result = system.analyze(parsed)

    # Restore originals
    retrieval.retrieve             = original_retrieve
    llm_engine.analyze_log_anomaly = original_analyze

    classification = "ANOMALY" if result.is_anomaly else "NORMAL"
    confidence     = result.confidence_score

    print(f"\n  FAISS retrieve() calls : {len(retrieve_calls)}")
    print(f"  LLM API calls          : {len(llm_calls)}")
    print(f"  Reasoning loop         : NONE (single-pass by design)")
    print(f"  Classification         : {classification}")
    print(f"  Confidence score       : {confidence:.2f}")
    print(f"  Severity               : {result.severity}")
    print(f"  Retrieved docs         : {len(result.retrieved_documents)}")

    # Assertions
    assert len(retrieve_calls) == 1, \
        f"Expected exactly 1 FAISS call, got {len(retrieve_calls)}"
    assert len(llm_calls) == 1, \
        f"Expected exactly 1 LLM call, got {len(llm_calls)}"
    assert classification in ('ANOMALY', 'NORMAL'), "Invalid classification"
    assert 0.0 <= confidence <= 1.0, f"Confidence out of range: {confidence}"

    print(f"\n  RESULT : Test PASSED")
    print(f"  Exactly 1 FAISS query and 1 LLM call confirmed. "
          f"No reasoning loop. Classification={classification}, "
          f"Confidence={confidence:.2f}.")

if __name__ == '__main__':
    run_case9()
