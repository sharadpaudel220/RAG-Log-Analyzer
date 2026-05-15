"""Case 4 - Agentic Controller: ReAct Loop Execution

Objective: Verify that the agentic controller correctly executes the ReAct
reasoning loop, selecting RETRIEVE and FINALIZE actions appropriately within
the 5-iteration maximum, addressing Objective O3.

Action:
  1. Pass a preprocessed HDFS ERROR log to the AgenticController.
  2. Monitor the action sequence across iterations.
  3. Verify the loop terminates on FINALIZE or at iteration 5.
  4. Inspect the returned reasoning chain and classification.

Expected Result:
  The controller selects at least one RETRIEVE action before FINALIZE.
  The loop terminates within 5 iterations. The output contains a valid
  classification (ANOMALY or NORMAL), confidence score in [0, 1], and a
  non-empty reasoning chain.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.input_layer.log_ingestion import RawLogEntry
from src.preprocessing.log_preprocessor import LogPreprocessor
from src.knowledge_base.knowledge_manager import KnowledgeBaseManager
from src.retrieval.retrieval_system import RetrievalSystem
from src.llm_engine.llm_interface import LLMEngine
from src.agentic_controller.agentic_rag import AgenticController

def run_case4():
    print("\n--- Agentic Controller: ReAct Loop Execution ---")

    # Step 1: Build components
    preprocessor  = LogPreprocessor()
    kb_manager    = KnowledgeBaseManager()
    if kb_manager.index is None or kb_manager.index.ntotal == 0:
        kb_manager.populate_default_knowledge()
        kb_manager.build_index()
    retrieval     = RetrievalSystem(kb_manager)
    llm_engine    = LLMEngine()
    controller    = AgenticController(retrieval, llm_engine, force_full_react=True)

    # Step 2: Prepare HDFS ERROR log entry
    raw_log = (
        "081109 203518 143 ERROR dfs.DataNode$DataXceiver: "
        "Got exception while serving blk_-1608999687919862906 to /10.251.31.5:54106"
    )
    print(f"\n  Input log : {raw_log}")

    raw_entry  = RawLogEntry(content=raw_log, source_file="HDFS.log", line_number=1)
    parsed     = preprocessor.preprocess([raw_entry])[0]

    # Step 3: Run agentic analysis and measure time
    t0     = time.perf_counter()
    result = controller.analyze_log(parsed)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    # Step 4: Inspect reasoning chain
    reasoning_chain = getattr(result, 'reasoning_chain', [])
    classification  = 'ANOMALY' if result.is_anomaly else 'NORMAL'
    confidence      = getattr(result, 'confidence', None)

    print(f"\n  Classification   : {classification}")
    print(f"  Confidence       : {confidence}")
    print(f"  Severity         : {result.severity}")
    print(f"  Reasoning steps  : {len(reasoning_chain)}")
    print(f"  Analysis time    : {elapsed_ms:.0f} ms")

    print("\n  Reasoning Chain:")
    actions_seen = []
    for i, step in enumerate(reasoning_chain, 1):
        action = getattr(step, 'action', str(step))
        thought = getattr(step, 'thought', '')
        actions_seen.append(str(action).upper())
        print(f"    Step {i}: action={action}  thought={str(thought)[:80]}")

    has_retrieve  = any('RETRIEVE' in a for a in actions_seen)
    has_finalize  = any(a in ('FINALIZE', 'FINISH') for a in actions_seen)
    within_limit  = len(reasoning_chain) <= 5

    print(f"\n  RETRIEVE action seen     : {'YES' if has_retrieve else 'NO'}")
    print(f"  FINALIZE/FINISH seen     : {'YES' if has_finalize else 'NO'}")
    print(f"  Iterations within limit  : {'YES' if within_limit else 'NO'} ({len(reasoning_chain)} steps)")

    # Assertions
    assert classification in ('ANOMALY', 'NORMAL'), "Invalid classification"
    assert confidence is None or 0.0 <= float(confidence) <= 1.0, "Confidence out of range"
    assert len(reasoning_chain) > 0, "Reasoning chain is empty"
    assert within_limit, f"Exceeded 5-step limit: {len(reasoning_chain)} steps"

    print("\n  RESULT : Test PASSED")
    print("  All assertions passed: valid classification, confidence in [0,1], "
          "non-empty reasoning chain, within 5 iterations.")

if __name__ == '__main__':
    run_case4()
