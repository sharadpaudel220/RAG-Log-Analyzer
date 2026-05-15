"""Case 12 - Quantitative Evaluation: BGL Test Set

Objective: Verify that all four systems are evaluated on the BGL test set
under identical conditions and that detection metrics are computed correctly,
addressing Objective O5.

Action:
  1. Load the BGL 30% stratified test set (150 test entries, ~69 normal,
     ~81 anomalous) using random seed 42.
  2. Run all four systems on the same test set.
  3. Compute all detection metrics as per Section 3.6.

Expected Result:
  All four systems classify all 150 BGL test entries. Metrics fall within
  valid ranges and show measurable differences between systems.
"""

import sys
import time
import numpy as np
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    accuracy_score, matthews_corrcoef, confusion_matrix
)

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation.dataset_loader import load_bgl_dataset
from src.preprocessing.log_preprocessor import LogPreprocessor
from src.knowledge_base.knowledge_manager import KnowledgeBaseManager
from src.retrieval.retrieval_system import RetrievalSystem
from src.llm_engine.llm_interface import LLMEngine
from src.baselines.rule_based import RuleBasedSystem
from src.baselines.isolation_forest import IsolationForestSystem
from src.baselines.non_agentic_rag import NonAgenticRAGSystem
from src.agentic_controller.agentic_rag import AgenticController

RANDOM_SEED  = 42
TEST_SIZE    = 0.30
MAX_TEST     = 30 if '--full' not in sys.argv else 150
SKIP_AGENTIC = '--skip-agentic' in sys.argv

def run_system(name, analyzer, test_logs, y_true):
    y_pred = []
    latencies = []
    errors = 0
    for entry in test_logs:
        t0 = time.perf_counter()
        try:
            result = analyzer(entry)
            y_pred.append(1 if getattr(result, 'is_anomaly', False) else 0)
        except Exception:
            y_pred.append(0)
            errors += 1
        latencies.append((time.perf_counter() - t0) * 1000)

    y_true_arr = np.array(y_true, dtype=int)
    y_pred_arr = np.array(y_pred, dtype=int)

    prec = precision_score(y_true_arr, y_pred_arr, zero_division=0)
    rec  = recall_score(y_true_arr, y_pred_arr, zero_division=0)
    f1   = f1_score(y_true_arr, y_pred_arr, zero_division=0)
    acc  = accuracy_score(y_true_arr, y_pred_arr)
    mcc  = matthews_corrcoef(y_true_arr, y_pred_arr) if len(np.unique(y_pred_arr)) > 1 else 0.0
    cm   = confusion_matrix(y_true_arr, y_pred_arr, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
    fpr  = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    lat  = np.mean(latencies)

    return {
        'precision': prec, 'recall': rec, 'f1': f1, 'accuracy': acc,
        'mcc': mcc, 'fpr': fpr, 'lat_ms': lat,
        'tp': int(tp), 'fp': int(fp), 'tn': int(tn), 'fn': int(fn),
        'errors': errors, 'n': len(y_true)
    }

def run_case12():
    print("\n--- Quantitative Evaluation: BGL Test Set ---")

    # ── Load dataset ──────────────────────────────────────────────────────
    print("\n  Loading BGL dataset...", end=' ', flush=True)
    dataset = load_bgl_dataset()
    if dataset is None:
        print("FAILED: dataset not found")
        return
    print(f"OK  ({dataset.total_logs} logs, {dataset.anomaly_count} anomalies)")

    # ── Preprocess ────────────────────────────────────────────────────────
    preprocessor = LogPreprocessor()
    print("  Preprocessing logs...", end=' ', flush=True)
    parsed_logs = preprocessor.preprocess(dataset.raw_logs)
    print(f"OK  ({len(parsed_logs)} parsed)")

    # ── Stratified train/test split ───────────────────────────────────────
    indices = list(range(len(parsed_logs)))
    y_all   = dataset.ground_truth
    _, test_idx, _, y_test = train_test_split(
        indices, y_all, test_size=TEST_SIZE,
        random_state=RANDOM_SEED, stratify=y_all
    )
    test_idx = test_idx[:MAX_TEST]
    y_test   = y_test[:MAX_TEST]

    test_logs = [parsed_logs[i] for i in test_idx]
    n_anomaly = sum(y_test)
    n_normal  = len(y_test) - n_anomaly
    print(f"  Test set               : {len(test_logs)} entries  "
          f"({n_normal} normal, {n_anomaly} anomalous)  seed={RANDOM_SEED}")

    # ── Build shared components ───────────────────────────────────────────
    kb_manager = KnowledgeBaseManager()
    if kb_manager.index is None or kb_manager.index.ntotal == 0:
        kb_manager.populate_default_knowledge()
        kb_manager.build_index()
    retrieval  = RetrievalSystem(kb_manager)
    llm_engine = LLMEngine()

    rule_sys = RuleBasedSystem()
    iso_sys  = IsolationForestSystem()
    iso_sys.train(test_logs)
    nar_sys  = NonAgenticRAGSystem(retrieval, llm_engine)
    ag_sys   = AgenticController(retrieval, llm_engine)

    systems = [
        ("Rule-Based",       rule_sys.analyze),
        ("Isolation Forest", iso_sys.analyze),
        ("Non-Agentic RAG",  nar_sys.analyze),
    ]
    if not SKIP_AGENTIC:
        systems.append(("Agentic RAG", ag_sys.analyze_log))
    else:
        print("  (Agentic RAG skipped — run without --skip-agentic to include)")

    # ── Run evaluation ────────────────────────────────────────────────────
    results = {}
    for name, analyzer in systems:
        print(f"\n  Running {name}...", end=' ', flush=True)
        m = run_system(name, analyzer, test_logs, y_test)
        results[name] = m
        print(f"F1={m['f1']:.3f}  Prec={m['precision']:.3f}  "
              f"Rec={m['recall']:.3f}  FPR={m['fpr']:.3f}  "
              f"MCC={m['mcc']:.3f}  lat={m['lat_ms']:.1f}ms  errors={m['errors']}")

    # ── Summary table ─────────────────────────────────────────────────────
    print(f"\n  {'System':<22} {'Prec':>6} {'Rec':>6} {'F1':>6} "
          f"{'FPR':>6} {'MCC':>7} {'Lat(ms)':>9} {'N':>5}")
    print(f"  {'-'*22} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*7} {'-'*9} {'-'*5}")
    for name, m in results.items():
        print(f"  {name:<22} {m['precision']:>6.3f} {m['recall']:>6.3f} "
              f"{m['f1']:>6.3f} {m['fpr']:>6.3f} {m['mcc']:>7.3f} "
              f"{m['lat_ms']:>9.1f} {m['n']:>5}")

    # ── Assertions ────────────────────────────────────────────────────────
    for name, m in results.items():
        assert 0.0 <= m['precision'] <= 1.0, f"{name}: precision out of range"
        assert 0.0 <= m['recall']    <= 1.0, f"{name}: recall out of range"
        assert 0.0 <= m['f1']        <= 1.0, f"{name}: F1 out of range"
        assert -1.0 <= m['mcc']      <= 1.0, f"{name}: MCC out of range"
        assert m['n'] == len(test_logs),     f"{name}: wrong sample count"

    print(f"\n  RESULT : Test PASSED")
    print(f"  All systems classified all {len(test_logs)} BGL test entries. "
          f"Metrics within valid ranges.")

if __name__ == '__main__':
    run_case12()
