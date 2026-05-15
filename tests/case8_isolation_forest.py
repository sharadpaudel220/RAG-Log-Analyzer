"""Case 8 - Isolation Forest: Feature Extraction

Objective: Verify that the IsolationForestClassifier correctly extracts a
numeric feature vector from a preprocessed log entry, addressing Objective O4.

Action:
  1. Pass a preprocessed HDFS log entry to the feature extraction method of
     the IsolationForestClassifier.
  2. Inspect the returned feature vector for shape, data type, and value ranges.

Expected Result:
  The returned feature vector has a fixed number of numeric features, dtype
  float, and all values are non-negative. The dimensions correspond to:
  log length, digit ratio, uppercase ratio, and severity one-hot encoding.

Actual Result:
  Feature vector returned with correct shape and dtype float32/float64.
  All values were non-negative and within expected ranges.
"""

import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.input_layer.log_ingestion import RawLogEntry
from src.preprocessing.log_preprocessor import LogPreprocessor
from src.baselines.isolation_forest import IsolationForestSystem

def run_case8():
    print("\n--- Isolation Forest: Feature Extraction ---")

    preprocessor = LogPreprocessor()
    clf          = IsolationForestSystem()

    raw_log = (
        "081109 203518 143 ERROR dfs.DataNode$DataXceiver: "
        "Got exception while serving blk_-1608999687919862906 to /10.251.31.5:54106"
    )
    print(f"\n  Input log  : {raw_log[:80]}...")

    entry  = RawLogEntry(content=raw_log, source_file="HDFS.log", line_number=1)
    parsed = preprocessor.preprocess([entry])[0]

    # Call _numeric_features directly to inspect the hand-crafted feature vector
    features = clf._numeric_features(parsed)
    feat_arr = np.array(features, dtype=np.float64)

    print(f"\n  Feature vector         : {np.round(feat_arr, 4).tolist()}")
    print(f"  Number of features     : {len(feat_arr)}")
    print(f"  dtype                  : {feat_arr.dtype}")
    print(f"  All non-negative       : {bool(np.all(feat_arr >= 0))}")
    print(f"  Min value              : {feat_arr.min():.4f}")
    print(f"  Max value              : {feat_arr.max():.4f}")

    # Label each dimension
    dim_labels = ['log_length', 'digit_ratio', 'upper_ratio',
                  'sev_DEBUG', 'sev_INFO', 'sev_WARNING',
                  'sev_ERROR', 'sev_CRITICAL', 'sev_FATAL']
    print(f"\n  Dimension breakdown:")
    for i, (label, val) in enumerate(zip(dim_labels, feat_arr)):
        print(f"    [{i}] {label:<14} = {val:.4f}")

    # Assertions
    assert len(feat_arr) == len(dim_labels), \
        f"Expected {len(dim_labels)} features, got {len(feat_arr)}"
    assert feat_arr.dtype in (np.float32, np.float64), \
        f"Expected float dtype, got {feat_arr.dtype}"
    assert np.all(feat_arr >= 0), \
        f"Negative feature values found: {feat_arr}"
    assert feat_arr[0] > 0, "log_length should be > 0"
    assert 0.0 <= feat_arr[1] <= 1.0, "digit_ratio should be in [0, 1]"
    assert 0.0 <= feat_arr[2] <= 1.0, "upper_ratio should be in [0, 1]"
    assert sum(feat_arr[3:]) == 1.0, "Severity one-hot should sum to 1.0"

    print(f"\n  RESULT : Test PASSED")
    print(f"  Feature vector shape=({len(feat_arr)},), dtype={feat_arr.dtype}, "
          f"all non-negative, severity one-hot correct.")

if __name__ == '__main__':
    run_case8()
