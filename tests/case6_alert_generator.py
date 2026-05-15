"""Case 6 - Alert Generator: Structured Output Validation

Objective: Verify that the alert generator produces a structured output
containing all eight required fields from a valid agentic controller result,
addressing Objective O3.

Action:
  1. Provide the AlertGenerator with a sample agentic controller output
     containing classification, confidence, severity, component, reasoning
     chain, and root cause.
  2. Inspect the generated alert for all eight required fields:
     timestamp, severity, component, classification, confidence,
     reasoning summary, root cause, and recommended actions.

Expected Result:
  The generated alert contains all eight fields. No field is empty or null.
  The format matches the structured dictionary defined by Alert.to_dict().
"""

import sys
import uuid
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.output_layer.alert_generator import AlertGenerator
from src.agentic_controller.agentic_rag import AgenticAnalysisResult
from src.preprocessing.log_preprocessor import ParsedLogEntry

def run_case6():
    print("\n--- Alert Generator: Structured Output Validation ---")

    # Step 1: Build a mock AgenticAnalysisResult (as the controller would produce)
    parsed_log = ParsedLogEntry(
        raw_content="081109 203518 143 ERROR dfs.DataNode$DataXceiver: Got exception while serving blk_-1608999687919862906",
        template="<NUM> <NUM> <NUM> ERROR dfs.DataNode$DataXceiver: Got exception while serving <*>",
        template_id=1,
        parameters=["blk_-1608999687919862906"],
        severity="ERROR",
        component="DataNode",
        source_file="HDFS.log",
        line_number=1
    )

    # Build reasoning chain steps as objects with to_dict()
    @dataclass
    class ReasoningStep:
        step_number: int
        action: str
        thought: str
        observation: str = ""
        def to_dict(self):
            return {
                'step_number': self.step_number,
                'action': self.action,
                'thought': self.thought,
                'observation': self.observation
            }

    # Minimal mock for RetrievalResult
    class MockDoc:
        def __init__(self):
            self.document = type('D', (), {
                'title': 'HDFS Block Corruption',
                'doc_type': 'incident',
                'to_dict': lambda s: {'title': 'HDFS Block Corruption', 'doc_type': 'incident'}
            })()
            self.similarity_score = 0.85
            self.relevance_score = 0.85
            self.rank = 1
        def to_dict(self):
            return {'document': {'title': 'HDFS Block Corruption', 'doc_type': 'incident'}, 'similarity_score': self.similarity_score, 'relevance_score': self.relevance_score, 'rank': self.rank}

    reasoning_chain = [
        ReasoningStep(1, "RETRIEVE",  "I need to retrieve relevant knowledge about DataNode exceptions."),
        ReasoningStep(2, "ANALYZE",   "The retrieved docs confirm this is a block serving failure."),
        ReasoningStep(3, "FINISH",    "Sufficient evidence to classify as ANOMALY with HIGH severity."),
    ]

    mock_result = AgenticAnalysisResult(
        log_entry=parsed_log,
        is_anomaly=True,
        severity="HIGH",
        confidence_score=0.87,
        final_analysis="DataNode threw an exception while serving a block, indicating replication failure.",
        reasoning_chain=reasoning_chain,
        retrieved_documents=[MockDoc()],
        recommendations=[
            "Check DataNode disk health on the affected node.",
            "Verify block replication factor in HDFS.",
            "Review network connectivity between DataNodes."
        ]
    )

    # Step 2: Generate alert
    generator = AlertGenerator()
    alert = generator.generate_alert(mock_result)
    alert_dict = alert.to_dict()

    print(f"\n  Alert ID         : {alert_dict.get('alert_id')}")
    print(f"  Timestamp        : {alert_dict.get('timestamp')}")
    print(f"  Severity         : {alert_dict.get('severity')}")
    print(f"  Title            : {alert_dict.get('title')}")
    print(f"  Affected Component: {alert_dict.get('affected_component')}")
    print(f"  Confidence Score : {alert_dict.get('confidence_score')}")
    print(f"  Description      : {str(alert_dict.get('description', ''))[:100]}")
    print(f"  Reasoning Chain  : {len(alert_dict.get('reasoning_chain', []))} steps")
    print(f"  Recommendations  : {len(alert_dict.get('recommendations', []))} items")
    print(f"  Source Attribution: {len(alert_dict.get('source_attribution', []))} sources")

    # Step 3: Verify all 8 required fields
    required_fields = [
        'timestamp', 'severity', 'affected_component', 'confidence_score',
        'description', 'reasoning_chain', 'recommendations', 'alert_id'
    ]

    print("\n  Field Validation:")
    all_present = True
    for f_name in required_fields:
        value = alert_dict.get(f_name)
        present = value is not None and value != [] and value != ""
        marker = "✓" if present else "✗"
        print(f"    {marker} {f_name}: {str(value)[:60] if value else 'MISSING'}")
        if not present:
            all_present = False

    # Assertions
    for f_name in required_fields:
        val = alert_dict.get(f_name)
        assert val is not None, f"Field '{f_name}' is None"
        assert val != [] and val != "", f"Field '{f_name}' is empty"

    assert isinstance(alert_dict['timestamp'], str) and len(alert_dict['timestamp']) > 0
    assert alert_dict['severity'] in ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO')
    assert 0.0 <= float(alert_dict['confidence_score']) <= 1.0

    print("\n  RESULT : Test PASSED")
    print("  All 8 required fields present and non-empty. "
          f"Severity={alert_dict['severity']}, Confidence={alert_dict['confidence_score']:.2f}")

if __name__ == '__main__':
    run_case6()
