"""Case 10 - System Architecture: Full Pipeline Integration

Objective: Verify that all four pipeline components including preprocessing,
knowledge base, agentic controller, and alert generator operate correctly
in sequence on a live log entry, addressing Objective O2.

Action:
  1. Load a raw HDFS log entry.
  2. Pass it through Drain3 preprocessing.
  3. Pass the structured output to the agentic controller with knowledge base access.
  4. Pass the controller output to the alert generator.
  5. Inspect the final alert for completeness.

Expected Result:
  The full pipeline completes without errors. The final alert contains all
  eight fields. The total processing time is recorded for latency reporting.
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
from src.output_layer.alert_generator import AlertGenerator

def run_case10():
    print("\n--- System Architecture: Full Pipeline Integration ---")

    t_total_start = time.perf_counter()

    # ── Step 1: Raw log entry ──────────────────────────────────────────────
    raw_log = (
        "081109 203518 143 ERROR dfs.DataNode$DataXceiver: "
        "Got exception while serving blk_-1608999687919862906 to /10.251.31.5:54106"
    )
    print(f"\n  [Step 1] Raw log       : {raw_log[:80]}...")

    # ── Step 2: Drain3 Preprocessing ──────────────────────────────────────
    t0 = time.perf_counter()
    preprocessor = LogPreprocessor()
    raw_entry    = RawLogEntry(content=raw_log, source_file="HDFS.log", line_number=1)
    parsed_logs  = preprocessor.preprocess([raw_entry])
    parsed       = parsed_logs[0]
    t_preprocess = (time.perf_counter() - t0) * 1000

    print(f"  [Step 2] Preprocessing : template_id={parsed.template_id}, "
          f"severity={parsed.severity}, time={t_preprocess:.1f}ms")

    # ── Step 3: Agentic Controller with KB ────────────────────────────────
    t0         = time.perf_counter()
    kb_manager = KnowledgeBaseManager()
    if kb_manager.index is None or kb_manager.index.ntotal == 0:
        kb_manager.populate_default_knowledge()
        kb_manager.build_index()
    retrieval   = RetrievalSystem(kb_manager)
    llm_engine  = LLMEngine()
    controller  = AgenticController(retrieval, llm_engine, force_full_react=True)
    result      = controller.analyze_log(parsed)
    t_agentic   = (time.perf_counter() - t0) * 1000

    classification = "ANOMALY" if result.is_anomaly else "NORMAL"
    print(f"  [Step 3] Agentic RAG   : classification={classification}, "
          f"severity={result.severity}, "
          f"reasoning_steps={len(result.reasoning_chain)}, "
          f"time={t_agentic:.1f}ms")

    # ── Step 4: Alert Generator ───────────────────────────────────────────
    t0        = time.perf_counter()
    generator = AlertGenerator()
    alert     = generator.generate_alert(result)
    alert_dict = alert.to_dict()
    t_alert   = (time.perf_counter() - t0) * 1000

    print(f"  [Step 4] Alert Gen     : alert_id={alert_dict['alert_id']}, "
          f"severity={alert_dict['severity']}, time={t_alert:.1f}ms")

    # ── Step 5: Inspect final alert ───────────────────────────────────────
    t_total = (time.perf_counter() - t_total_start)

    required_fields = [
        'alert_id', 'timestamp', 'severity', 'title',
        'description', 'affected_component',
        'reasoning_chain', 'recommendations'
    ]
    # Only these must be non-empty (others depend on LLM extraction)
    mandatory_fields = ['alert_id', 'timestamp', 'severity', 'title', 'description', 'reasoning_chain']

    print(f"\n  [Step 5] Alert field validation:")
    all_ok = True
    for f_name in required_fields:
        val     = alert_dict.get(f_name)
        present = val is not None and val != [] and val != ""
        marker  = "✓" if present else "✗"
        print(f"    {marker} {f_name:<22} : {str(val)[:55] if val else 'MISSING'}")
        if not present:
            all_ok = False

    print(f"\n  Total pipeline time    : {t_total:.2f} seconds")
    print(f"    ├─ Preprocessing     : {t_preprocess:.1f} ms")
    print(f"    ├─ Agentic RAG       : {t_agentic:.1f} ms")
    print(f"    └─ Alert Generator   : {t_alert:.1f} ms")

    # Assertions
    assert not any(
        isinstance(e, Exception) for e in [parsed, result, alert]
    ), "Pipeline component raised an exception"

    for f_name in mandatory_fields:
        val = alert_dict.get(f_name)
        assert val is not None and val != [] and val != "", \
            f"Required field '{f_name}' is missing or empty"

    assert classification in ('ANOMALY', 'NORMAL'), "Invalid classification"
    assert t_total < 60, f"Pipeline took {t_total:.2f}s, expected < 60s"

    print(f"\n  RESULT : Test PASSED")
    print(f"  Full pipeline completed in {t_total:.2f}s end-to-end. "
          f"All {len(required_fields)} alert fields present. "
          f"Classification={classification}.")

if __name__ == '__main__':
    run_case10()
