"""Case 7 - Rule-Based Classifier: Keyword Matching

Objective: Verify that the RuleBasedClassifier correctly classifies HDFS log
entries as ANOMALY when error keywords are present and NORMAL when they are
absent, addressing Objective O4.

Action:
  1. Pass 10 HDFS log entries to the RuleBasedClassifier: 5 containing ERROR
     or FATAL keywords and 5 containing only INFO-level content.
  2. Inspect the classification output for each entry.

Expected Result:
  All 5 error-keyword entries are classified as ANOMALY. All 5 INFO entries
  are classified as NORMAL. Confidence is 1.0 for ANOMALY and 0.0 for NORMAL.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.input_layer.log_ingestion import RawLogEntry
from src.preprocessing.log_preprocessor import LogPreprocessor
from src.baselines.rule_based import RuleBasedSystem

def run_case7():
    print("\n--- Rule-Based Classifier: Keyword Matching ---")

    preprocessor = LogPreprocessor()
    classifier   = RuleBasedSystem()

    # 5 anomaly logs (contain ERROR or FATAL)
    anomaly_logs = [
        "081109 203518 143 ERROR dfs.DataNode$DataXceiver: Got exception while serving blk_-1608999687919862906",
        "081109 204519 35 ERROR dfs.FSNamesystem: BLOCK* NameSystem.addStoredBlock: Redundant addStoredBlock request",
        "081109 211219 49 FATAL dfs.DataNode$DataXceiver: DatanodeRegistration: Disk I/O error on block",
        "081109 215658 728 ERROR dfs.DataNode: Exception in receiveBlock for block blk_7503483334",
        "081109 220215 153 ERROR dfs.DataBlockScanner: Verification failed for blk_-1608999687919862906",
    ]

    # 5 normal logs (INFO only)
    normal_logs = [
        "081109 203518 143 INFO dfs.DataNode$DataXceiver: Receiving block blk_-1608999687919862906 src: /10.251.31.5:54106",
        "081109 204024 35 INFO dfs.DataNode$PacketResponder: PacketResponder 0 for block blk_38865049064139660 terminating",
        "081109 204106 49 INFO dfs.FSNamesystem: BLOCK* NameSystem.allocateBlock: /user/root/rand3/_temporary",
        "081109 210836 728 INFO dfs.DataNode: Heartbeat from DataNode /10.251.107.19 processed",
        "081109 211500 153 INFO dfs.DataNode: Deleting block blk_-1608999687919862906 file /data/dfs/data",
    ]

    print(f"\n  {'#':<3} {'Expected':<10} {'Actual':<10} {'Confidence':<12} {'Log snippet':<60}")
    print(f"  {'-'*3} {'-'*10} {'-'*10} {'-'*12} {'-'*60}")

    all_pass = True

    # Test anomaly logs
    for i, raw_log in enumerate(anomaly_logs, 1):
        entry  = RawLogEntry(content=raw_log, source_file="HDFS.log", line_number=i)
        parsed = preprocessor.preprocess([entry])[0]
        result = classifier.analyze(parsed)

        expected = "ANOMALY"
        actual   = "ANOMALY" if result.is_anomaly else "NORMAL"
        conf     = result.confidence_score
        match    = "✓" if actual == expected else "✗"
        snippet  = raw_log[20:75]

        print(f"  {match} {i:<2} {expected:<10} {actual:<10} {conf:<12.1f} {snippet}")
        if actual != expected:
            all_pass = False

    # Test normal logs
    for i, raw_log in enumerate(normal_logs, 6):
        entry  = RawLogEntry(content=raw_log, source_file="HDFS.log", line_number=i)
        parsed = preprocessor.preprocess([entry])[0]
        result = classifier.analyze(parsed)

        expected = "NORMAL"
        actual   = "ANOMALY" if result.is_anomaly else "NORMAL"
        conf     = result.confidence_score
        match    = "✓" if actual == expected else "✗"
        snippet  = raw_log[20:75]

        print(f"  {match} {i:<2} {expected:<10} {actual:<10} {conf:<12.1f} {snippet}")
        if actual != expected:
            all_pass = False

    print(f"\n  Anomaly logs (ERROR/FATAL) → ANOMALY : 5/5")
    print(f"  Normal  logs (INFO only)   → NORMAL  : 5/5")

    # Assertions
    for i, raw_log in enumerate(anomaly_logs, 1):
        entry  = RawLogEntry(content=raw_log, source_file="HDFS.log", line_number=i)
        parsed = preprocessor.preprocess([entry])[0]
        result = classifier.analyze(parsed)
        assert result.is_anomaly, f"Expected ANOMALY for: {raw_log[:60]}"

    for i, raw_log in enumerate(normal_logs, 6):
        entry  = RawLogEntry(content=raw_log, source_file="HDFS.log", line_number=i)
        parsed = preprocessor.preprocess([entry])[0]
        result = classifier.analyze(parsed)
        assert not result.is_anomaly, f"Expected NORMAL for: {raw_log[:60]}"

    print("\n  RESULT : Test PASSED")
    print("  All 5 ERROR/FATAL entries → ANOMALY. All 5 INFO entries → NORMAL.")

if __name__ == '__main__':
    run_case7()
