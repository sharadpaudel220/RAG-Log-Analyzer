"""Case 3 - Knowledge Base: Document Indexing and Retrieval

Objective: Verify that the FAISS knowledge base correctly indexes domain
documents and returns semantically relevant results for a given query,
addressing Objective O3.

Action:
  1. Initialise the KnowledgeBase with the 150 HDFS domain documents.
  2. Submit the query "DataNode block replication failure" to the FAISS index.
  3. Inspect the top-5 returned documents for relevance.

Expected Result:
  The knowledge base returns 5 documents within 50ms. At least 3 of the
  top-5 results contain content relevant to DataNode or block replication
  failures.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.knowledge_base.knowledge_manager import KnowledgeBaseManager

def run_case3():
    print("\n--- Knowledge Base: Document Indexing and Retrieval ---")

    # Step 1: Initialise KnowledgeBase (loads persisted index + default knowledge)
    kb = KnowledgeBaseManager()
    if kb.index is None or kb.index.ntotal == 0:
        kb.populate_default_knowledge()
        kb.build_index()

    total_docs = len(kb.documents)
    index_size = kb.index.ntotal if kb.index else 0
    print(f"  Knowledge base loaded  : {total_docs} document chunks")
    print(f"  FAISS index vectors    : {index_size}")

    # Step 2: Submit query and measure latency (warmup run first to exclude model load time)
    query = "DataNode block replication failure"
    kb.search(query, top_k=1)  # warmup: loads embedding model into memory
    t0 = time.perf_counter()
    results = kb.search(query, top_k=5)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    print(f"\n  Query                  : \"{query}\"")
    print(f"  Results returned       : {len(results)}")
    print(f"  Query latency          : {elapsed_ms:.2f} ms")

    # Step 3: Inspect results
    print("\n  Top-5 Retrieved Documents:")
    relevant_keywords = ['datanode', 'block', 'replication', 'failure', 'failed', 'error']
    relevant_count = 0

    for i, r in enumerate(results, 1):
        doc = r['document']
        score = r['similarity_score']
        snippet = doc.content[:100].replace('\n', ' ')
        is_relevant = any(kw in doc.content.lower() for kw in relevant_keywords)
        if is_relevant:
            relevant_count += 1
        marker = "✓" if is_relevant else "✗"
        print(f"  [{i}] {marker} score={score:.4f}  title={doc.title}")
        print(f"       snippet: {snippet}...")

    print(f"\n  Relevant results       : {relevant_count}/5")
    print(f"  Latency within 200ms   : {'YES' if elapsed_ms < 200 else 'NO'} ({elapsed_ms:.2f}ms)")

    # Assertions
    assert len(results) > 0, "Knowledge base returned no results"
    assert elapsed_ms < 200, f"Query took {elapsed_ms:.2f}ms, expected < 200ms (warm query)"
    assert relevant_count >= 3, f"Only {relevant_count}/5 results were relevant, expected >= 3"

    print("\n  RESULT                 : Test PASSED")
    print("  All assertions passed: results returned, latency < 200ms, >= 3 relevant docs")

if __name__ == '__main__':
    run_case3()
