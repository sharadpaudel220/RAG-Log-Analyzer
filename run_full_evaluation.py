"""
DISSERTATION FULL EVALUATION PIPELINE
======================================
Runs all four systems (Rule-Based, Isolation Forest, Non-Agentic RAG,
Agentic RAG) on both HDFS and BGL benchmark datasets, computes the full
suite of detection + efficiency metrics, runs paired t-tests for
statistical significance, and writes four output artifacts ready for
inclusion in Chapter 6 of the dissertation:

    1. evaluation_results.json       (full per-dataset / per-model metrics)
    2. evaluation_metrics.csv         (flat tabular form for easy import)
    3. evaluation_report.txt          (formatted results tables)
    4. evaluation_run_log.txt         (timestamped execution log)

Also writes evaluation_status.json continuously so the web UI can poll
progress, and evaluation_checkpoint.json so an interrupted run can
resume.

Run standalone:
    python3 run_full_evaluation.py

Or import and call run_full_evaluation(callback=...).
"""

from __future__ import annotations

import csv
import io
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from scipy import stats

# Make repo importable when run as a script
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.dataset_loader import load_bgl_dataset, load_hdfs_dataset
from src.preprocessing.log_preprocessor import LogPreprocessor

# ---------- Output paths ----------
RESULTS_JSON = PROJECT_ROOT / 'evaluation_results.json'
RESULTS_CSV = PROJECT_ROOT / 'evaluation_metrics.csv'
RESULTS_TXT = PROJECT_ROOT / 'evaluation_report.txt'
RUN_LOG = PROJECT_ROOT / 'evaluation_run_log.txt'
STATUS_FILE = PROJECT_ROOT / 'evaluation_status.json'
CHECKPOINT_FILE = PROJECT_ROOT / 'evaluation_checkpoint.json'

SYSTEMS = ['Rule-Based', 'Isolation Forest', 'Non-Agentic RAG', 'Agentic RAG']
DATASETS = ['HDFS', 'BGL']
RANDOM_SEED = 42
TEST_SIZE = 0.30
MAX_AGENTIC_TEST = 5000  # cap per Section 14 if dataset is huge


# ============================================================
#  PROGRESS / STATUS  (consumed by the web UI)
# ============================================================
class StatusTracker:
    def __init__(self, total_units: int = 0):
        self.state = {
            'state': 'idle',
            'started_at': None,
            'finished_at': None,
            'current_system': None,
            'current_dataset': None,
            'processed': 0,
            'total': total_units,
            'percent': 0.0,
            'message': '',
            'errors': [],
            'timeouts': 0,
            'completed_combos': [],
            'partial_results': {},
        }
        self._log_lines: List[str] = []

    def log(self, msg: str) -> None:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = f'[{ts}] {msg}'
        self._log_lines.append(line)
        print(line, flush=True)
        try:
            with open(RUN_LOG, 'a') as f:
                f.write(line + '\n')
        except Exception:
            pass

    def update(self, **kwargs) -> None:
        self.state.update(kwargs)
        if self.state['total']:
            self.state['percent'] = round(
                100.0 * self.state['processed'] / self.state['total'], 2
            )
        self._flush()

    def increment(self, n: int = 1) -> None:
        self.state['processed'] += n
        if self.state['total']:
            self.state['percent'] = round(
                100.0 * self.state['processed'] / self.state['total'], 2
            )
        # flush every ~50 increments to keep the file fresh without thrashing
        if self.state['processed'] % 50 == 0:
            self._flush()

    def _flush(self) -> None:
        try:
            # Atomic write: write to temp file, then rename to avoid race conditions
            temp_file = STATUS_FILE.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
            temp_file.replace(STATUS_FILE)
        except Exception:
            pass


# ============================================================
#  CHECKPOINTING
# ============================================================
def load_checkpoint() -> Dict[str, Any]:
    if CHECKPOINT_FILE.exists():
        try:
            with open(CHECKPOINT_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {'completed': [], 'results': {}}


def save_checkpoint(ckpt: Dict[str, Any]) -> None:
    # Atomic write to prevent race conditions
    temp_file = CHECKPOINT_FILE.with_suffix('.tmp')
    with open(temp_file, 'w') as f:
        json.dump(ckpt, f, indent=2, default=str)
    temp_file.replace(CHECKPOINT_FILE)


# ============================================================
#  METRICS
# ============================================================
def compute_metrics(
    y_true: List[int], y_pred: List[int], y_score: List[float], latencies_ms: List[float]
) -> Dict[str, float]:
    y_true_arr = np.asarray(y_true, dtype=int)
    y_pred_arr = np.asarray(y_pred, dtype=int)
    y_score_arr = np.asarray(y_score, dtype=float)

    # If only one class is present in y_true, sklearn AUC functions raise.
    if len(np.unique(y_true_arr)) < 2:
        auc_roc = float('nan')
        auc_pr = float('nan')
    else:
        try:
            auc_roc = float(roc_auc_score(y_true_arr, y_score_arr))
        except Exception:
            auc_roc = float('nan')
        try:
            auc_pr = float(average_precision_score(y_true_arr, y_score_arr))
        except Exception:
            auc_pr = float('nan')

    cm = confusion_matrix(y_true_arr, y_pred_arr, labels=[0, 1])
    if cm.size == 4:
        tn, fp, fn, tp = cm.ravel()
    else:  # only one class present
        tn = fp = fn = tp = 0
        if cm.size == 1:
            if y_true_arr[0] == 0:
                tn = int(cm[0, 0])
            else:
                tp = int(cm[0, 0])

    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    lat_mean = float(np.mean(latencies_ms)) if latencies_ms else 0.0
    lat_med = float(np.median(latencies_ms)) if latencies_ms else 0.0
    lat_p95 = float(np.percentile(latencies_ms, 95)) if latencies_ms else 0.0
    throughput = (1000.0 / lat_mean) if lat_mean > 0 else 0.0

    return {
        'precision': float(precision_score(y_true_arr, y_pred_arr, zero_division=0)),
        'recall': float(recall_score(y_true_arr, y_pred_arr, zero_division=0)),
        'f1_score': float(f1_score(y_true_arr, y_pred_arr, zero_division=0)),
        'accuracy': float(accuracy_score(y_true_arr, y_pred_arr)),
        'auc_roc': auc_roc,
        'auc_pr': auc_pr,
        'mcc': float(matthews_corrcoef(y_true_arr, y_pred_arr)) if len(np.unique(y_pred_arr)) > 1 or len(np.unique(y_true_arr)) > 1 else 0.0,
        'fpr': float(fpr),
        'TP': int(tp), 'TN': int(tn), 'FP': int(fp), 'FN': int(fn),
        'latency_mean_ms': lat_mean,
        'latency_median_ms': lat_med,
        'latency_p95_ms': lat_p95,
        'throughput_per_sec': throughput,
        'n_samples': int(len(y_true_arr)),
    }


# ============================================================
#  SYSTEM RUNNERS
# ============================================================
def _safe_get_score(result: Any, default: float = 0.5) -> float:
    """Extract a confidence score in [0,1] from a result object."""
    for attr in ('confidence_score', 'score', 'anomaly_score'):
        if hasattr(result, attr):
            try:
                v = float(getattr(result, attr))
                # anomaly_score from IsolationForest can be unbounded; squash via sigmoid
                if attr == 'anomaly_score':
                    v = 1.0 / (1.0 + np.exp(-v))
                return max(0.0, min(1.0, v))
            except Exception:
                pass
    return default


def _run_single_system(
    name: str,
    analyzer: Callable[[Any], Any],
    test_logs: List[Any],
    y_true: List[int],
    tracker: StatusTracker,
    timeout_s: Optional[float] = None,
) -> Dict[str, Any]:
    y_pred: List[int] = []
    y_score: List[float] = []
    latencies_ms: List[float] = []
    errors = 0
    timeouts = 0

    tracker.update(
        current_system=name,
        message=f'{name}: analysing {len(test_logs)} entries',
    )

    # NOTE: Removed artificial rate limiting - relying on Groq's server-side limits
    # and the retry logic in llm_interface.py for 429 errors
    for i, entry in enumerate(test_logs):
        t0 = time.perf_counter()
        try:
            result = analyzer(entry)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            if timeout_s is not None and elapsed_ms > timeout_s * 1000:
                timeouts += 1
                y_pred.append(0)
                y_score.append(0.0)
            else:
                is_anom = bool(getattr(result, 'is_anomaly', False))
                y_pred.append(1 if is_anom else 0)
                # Use raw anomaly score as provided by the detection system
                # For AUC calculation, scores should reflect anomaly likelihood
                conf = _safe_get_score(result)
                y_score.append(float(conf))
            latencies_ms.append(elapsed_ms)
        except Exception as exc:  # noqa: BLE001
            errors += 1
            tracker.state['errors'].append(f'{name}[{i}]: {exc}')
            y_pred.append(0)
            y_score.append(0.0)
            latencies_ms.append((time.perf_counter() - t0) * 1000.0)

        tracker.increment(1)

    metrics = compute_metrics(y_true, y_pred, y_score, latencies_ms)
    metrics['errors'] = errors
    metrics['timeouts'] = timeouts
    tracker.log(
        f'  {name}: F1={metrics["f1_score"]:.4f}  Precision={metrics["precision"]:.4f}  '
        f'Recall={metrics["recall"]:.4f}  AUC-ROC={metrics["auc_roc"]:.4f}  '
        f'MCC={metrics["mcc"]:.4f}  Latency={metrics["latency_mean_ms"]:.2f}ms  '
        f'errors={errors} timeouts={timeouts}'
    )
    return {'metrics': metrics, 'y_pred': y_pred, 'y_true': y_true, 'y_score': y_score}


# ============================================================
#  PIPELINE
# ============================================================
def _check_ollama() -> bool:
    try:
        from src.llm_engine.llm_interface import LLMEngine
        return LLMEngine().check_health()
    except Exception:
        return False


def _build_systems(ollama_ok: bool) -> Dict[str, Any]:
    from src.baselines.rule_based import RuleBasedSystem
    from src.baselines.isolation_forest import IsolationForestSystem

    systems: Dict[str, Any] = {
        'Rule-Based': {'instance': RuleBasedSystem(), 'requires_train': False, 'requires_ollama': False},
        'Isolation Forest': {'instance': IsolationForestSystem(), 'requires_train': True, 'requires_ollama': False},
    }
    if ollama_ok:
        from src.baselines.non_agentic_rag import NonAgenticRAGSystem
        from src.agentic_controller.agentic_rag import AgenticController
        from src.knowledge_base.knowledge_manager import KnowledgeBaseManager
        from src.retrieval.retrieval_system import RetrievalSystem
        from src.llm_engine.llm_interface import LLMEngine

        km = KnowledgeBaseManager()
        if km.index is None:
            km.populate_default_knowledge()
        retrieval = RetrievalSystem(km)
        llm = LLMEngine()
        systems['Non-Agentic RAG'] = {
            'instance': NonAgenticRAGSystem(retrieval, llm),
            'requires_train': False,
            'requires_ollama': True,
        }
        systems['Agentic RAG'] = {
            'instance': AgenticController(retrieval, llm, force_full_react=True),
            'requires_train': False,
            'requires_ollama': True,
        }
    return systems


def _analyzer_for(name: str, instance: Any) -> Callable[[Any], Any]:
    if name == 'Agentic RAG':
        return instance.analyze_log
    return instance.analyze


def run_full_evaluation(
    progress_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
    max_logs_per_dataset: Optional[int] = None,
    use_checkpoint: bool = True,
) -> Dict[str, Any]:
    """Main entry point. Returns the complete results dict."""
    # Reset run log
    RUN_LOG.write_text('')
    tracker = StatusTracker(total_units=0)
    tracker.update(state='running', started_at=datetime.now().isoformat(), message='Initialising')

    tracker.log('=' * 70)
    tracker.log('COMPARATIVE EVALUATION — STARTING')
    tracker.log('=' * 70)

    # 1. Ollama check
    ollama_ok = _check_ollama()
    tracker.log(f'Ollama available: {ollama_ok}')
    if not ollama_ok:
        tracker.log('WARNING: RAG-based systems will be skipped.')

    # 2. Load datasets
    tracker.update(message='Loading datasets')
    loaders = {'HDFS': load_hdfs_dataset, 'BGL': load_bgl_dataset}
    datasets: Dict[str, Any] = {}
    for ds_name, loader in loaders.items():
        try:
            ds = loader(max_logs=max_logs_per_dataset)
            if ds is None:
                tracker.log(f'Dataset {ds_name}: NOT FOUND, skipping')
                continue
            datasets[ds_name] = ds
            tracker.log(
                f'Dataset {ds_name}: {ds.total_logs} logs, '
                f'{ds.anomaly_count} anomalies ({ds.anomaly_ratio:.2%})'
            )
        except Exception as exc:  # noqa: BLE001
            tracker.log(f'Failed to load {ds_name}: {exc}')

    if not datasets:
        tracker.update(state='error', message='No datasets available')
        return {'error': 'No datasets available'}

    # 3. Preprocess each dataset (shared across systems)
    preproc = LogPreprocessor()
    parsed: Dict[str, Tuple[List[Any], List[int]]] = {}
    for ds_name, ds in datasets.items():
        tracker.update(message=f'Preprocessing {ds_name}')
        parsed_logs = preproc.preprocess(ds.raw_logs)
        # Align labels with parsed logs (preprocess may drop entries)
        labels = ds.ground_truth[: len(parsed_logs)]
        labels_int = [1 if v else 0 for v in labels]
        parsed[ds_name] = (parsed_logs, labels_int)
        tracker.log(f'  {ds_name}: preprocessed {len(parsed_logs)} entries')

    # 4. Build systems
    systems = _build_systems(ollama_ok)
    tracker.log(f'Systems available: {list(systems.keys())}')

    # 5. Compute total work units (sum of test-set sizes per system)
    total_units = 0
    splits: Dict[str, Dict[str, Any]] = {}
    for ds_name, (logs, labels) in parsed.items():
        if len(set(labels)) < 2:
            tracker.log(f'  {ds_name}: only one class present — using all entries as test set')
            train_idx = np.array([], dtype=int)
            test_idx = np.arange(len(logs))
        else:
            train_idx, test_idx = train_test_split(
                np.arange(len(logs)),
                test_size=TEST_SIZE,
                stratify=labels,
                random_state=RANDOM_SEED,
            )
        splits[ds_name] = {
            'train_idx': train_idx,
            'test_idx': test_idx,
            'logs': logs,
            'labels': labels,
        }
        for sys_name in systems:
            test_size = len(test_idx)
            if sys_name == 'Agentic RAG':
                test_size = min(test_size, MAX_AGENTIC_TEST)
            total_units += test_size
    tracker.update(total=total_units)
    tracker.log(f'Total inference calls planned: {total_units}')

    # 6. Resume from checkpoint
    ckpt = load_checkpoint() if use_checkpoint else {'completed': [], 'results': {}}
    full_results: Dict[str, Dict[str, Any]] = ckpt.get('results', {})

    # 7. Run each system on each dataset
    for ds_name, split in splits.items():
        full_results.setdefault(ds_name, {})
        logs = split['logs']
        labels = split['labels']
        train_idx = split['train_idx']
        test_idx = split['test_idx']
        train_logs = [logs[i] for i in train_idx]
        test_logs = [logs[i] for i in test_idx]
        y_true = [labels[i] for i in test_idx]
        tracker.log(f'\n--- Dataset: {ds_name} | train={len(train_logs)} test={len(test_logs)} ---')

        # Train Isolation Forest once per dataset with dataset-specific contamination
        if 'Isolation Forest' in systems and train_logs:
            try:
                tracker.update(message=f'Training Isolation Forest on {ds_name}')
                # Calculate contamination from training data labels
                train_labels = [labels[i] for i in train_idx]
                anomaly_count = sum(train_labels)
                contamination = max(0.01, min(0.5, anomaly_count / len(train_labels))) if train_labels else 0.1
                tracker.log(f'  Training Isolation Forest on {len(train_logs)} entries (contamination={contamination:.4f})...')
                # Reinitialize Isolation Forest with correct contamination for this dataset
                from src.baselines.isolation_forest import IsolationForestSystem
                systems['Isolation Forest']['instance'] = IsolationForestSystem(contamination=contamination)
                systems['Isolation Forest']['instance'].train(train_logs)
            except Exception as exc:  # noqa: BLE001
                tracker.log(f'  Isolation Forest training failed: {exc}')

        for sys_name, info in systems.items():
            combo_key = f'{ds_name}::{sys_name}'
            if combo_key in ckpt.get('completed', []):
                tracker.log(f'  ✓ {sys_name} on {ds_name} — already complete (from checkpoint)')
                # Skip but still account for progress
                size = len(test_logs) if sys_name != 'Agentic RAG' else min(len(test_logs), MAX_AGENTIC_TEST)
                tracker.increment(size)
                continue

            sub_test = test_logs
            sub_y = y_true
            if sys_name == 'Agentic RAG' and len(sub_test) > MAX_AGENTIC_TEST:
                sub_test = sub_test[:MAX_AGENTIC_TEST]
                sub_y = sub_y[:MAX_AGENTIC_TEST]
                tracker.log(f'  Agentic RAG limited to first {MAX_AGENTIC_TEST} test entries')

            tracker.update(current_dataset=ds_name, current_system=sys_name)
            timeout_s = 120.0 if sys_name in ('Agentic RAG', 'Non-Agentic RAG') else None
            try:
                run = _run_single_system(sys_name, _analyzer_for(sys_name, info['instance']),
                                         sub_test, sub_y, tracker, timeout_s=timeout_s)
                full_results[ds_name][sys_name] = run
            except Exception as exc:  # noqa: BLE001
                tracker.log(f'  ✗ {sys_name} on {ds_name} crashed: {exc}\n{traceback.format_exc()}')
                continue

            ckpt.setdefault('completed', []).append(combo_key)
            ckpt['results'] = full_results
            save_checkpoint(ckpt)

    # 8. Paired t-tests (Agentic RAG vs each baseline)
    tracker.update(message='Running paired t-tests')
    for ds_name, by_system in full_results.items():
        ttests = {}
        if 'Agentic RAG' not in by_system:
            full_results[ds_name]['t_tests'] = {'note': 'Agentic RAG missing — skipped'}
            continue
        agentic = by_system['Agentic RAG']
        a_correct = (np.asarray(agentic['y_pred']) == np.asarray(agentic['y_true'])).astype(int)
        for baseline in ('Rule-Based', 'Isolation Forest', 'Non-Agentic RAG'):
            if baseline not in by_system:
                continue
            b = by_system[baseline]
            b_correct = (np.asarray(b['y_pred']) == np.asarray(b['y_true'])).astype(int)
            n = min(len(a_correct), len(b_correct))
            if n < 2:
                ttests[f'vs_{baseline}'] = {'t_stat': None, 'p_value': None, 'significant': False, 'note': 'insufficient samples'}
                continue
            try:
                t_stat, p_val = stats.ttest_rel(a_correct[:n], b_correct[:n])
                ttests[f'vs_{baseline}'] = {
                    't_stat': float(t_stat) if not np.isnan(t_stat) else None,
                    'p_value': float(p_val) if not np.isnan(p_val) else None,
                    'significant': bool(p_val is not None and not np.isnan(p_val) and p_val < 0.017),
                    'n_samples': int(n),
                }
            except Exception as exc:  # noqa: BLE001
                ttests[f'vs_{baseline}'] = {'error': str(exc)}
        full_results[ds_name]['t_tests'] = ttests

    # 9. False Positive Analysis - detailed breakdown for each system/dataset
    tracker.update(message='Analyzing false positives')
    for ds_name, by_system in full_results.items():
        tracker.log(f'\n--- False Positive Analysis: {ds_name} ---')
        for sys_name in SYSTEMS:
            if sys_name not in by_system:
                continue
            run = by_system[sys_name]
            y_true_arr = np.asarray(run['y_true'], dtype=int)
            y_pred_arr = np.asarray(run['y_pred'], dtype=int)
            
            # Calculate confusion matrix
            tp = int(np.sum((y_true_arr == 1) & (y_pred_arr == 1)))
            tn = int(np.sum((y_true_arr == 0) & (y_pred_arr == 0)))
            fp = int(np.sum((y_true_arr == 0) & (y_pred_arr == 1)))
            fn = int(np.sum((y_true_arr == 1) & (y_pred_arr == 0)))
            
            fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
            fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
            
            tracker.log(f'  {sys_name}: FP={fp} FN={fn} FPR={fpr:.4f} FNR={fnr:.4f}')
    tracker.log('')

    # 10. Persist outputs
    _write_outputs(full_results, tracker)

    tracker.update(state='done', finished_at=datetime.now().isoformat(),
                   message='Evaluation complete', percent=100.0)
    tracker.log('=' * 70)
    tracker.log('COMPARATIVE EVALUATION — COMPLETE')
    tracker.log(f'Outputs: {RESULTS_JSON.name}, {RESULTS_CSV.name}, {RESULTS_TXT.name}')
    tracker.log('=' * 70)

    if progress_cb:
        try:
            progress_cb(tracker.state)
        except Exception:
            pass
    return {'status': 'done', 'results': _strip_arrays(full_results)}


def _strip_arrays(results: Dict[str, Any]) -> Dict[str, Any]:
    """Remove huge per-entry arrays before returning the dict to clients."""
    out: Dict[str, Any] = {}
    for ds_name, by_system in results.items():
        out[ds_name] = {}
        for k, v in by_system.items():
            if k == 't_tests':
                out[ds_name][k] = v
            elif isinstance(v, dict) and 'metrics' in v:
                out[ds_name][k] = v['metrics']
            else:
                out[ds_name][k] = v
    return out


def _write_outputs(results: Dict[str, Any], tracker: StatusTracker) -> None:
    # ----- JSON -----
    json_payload: Dict[str, Any] = {}
    for ds_name, by_system in results.items():
        json_payload[ds_name] = {}
        for k, v in by_system.items():
            if k == 't_tests':
                json_payload[ds_name][k] = v
            else:
                json_payload[ds_name][k] = v.get('metrics', {})
    json_payload['_meta'] = {
        'generated_at': datetime.now().isoformat(),
        'random_seed': RANDOM_SEED,
        'test_size': TEST_SIZE,
        'max_agentic_test': MAX_AGENTIC_TEST,
    }
    # Atomic write to prevent corruption during concurrent reads
    temp_results = RESULTS_JSON.with_suffix('.tmp')
    with open(temp_results, 'w') as f:
        json.dump(json_payload, f, indent=2, default=str)
    temp_results.replace(RESULTS_JSON)
    tracker.log(f'  Wrote {RESULTS_JSON.name}')

    # ----- CSV -----
    csv_cols = ['dataset', 'system', 'precision', 'recall', 'f1_score', 'accuracy',
                'auc_roc', 'auc_pr', 'mcc', 'fpr',
                'latency_mean_ms', 'latency_median_ms', 'latency_p95_ms',
                'throughput_per_sec', 'TP', 'TN', 'FP', 'FN', 'n_samples']
    # Build CSV in memory, then write atomically
    csv_buffer = io.StringIO()
    w = csv.DictWriter(csv_buffer, fieldnames=csv_cols)
    w.writeheader()
    for ds_name, by_system in json_payload.items():
        if ds_name.startswith('_'):
            continue
        for sys_name in SYSTEMS:
            m = by_system.get(sys_name)
            if not isinstance(m, dict) or 'precision' not in m:
                continue
            row = {'dataset': ds_name, 'system': sys_name}
            for c in csv_cols[2:]:
                v = m.get(c, '')
                if isinstance(v, float):
                    v = round(v, 6)
                row[c] = v
            w.writerow(row)
    # Atomic write
    temp_csv = RESULTS_CSV.with_suffix('.tmp')
    with open(temp_csv, 'w', newline='') as f:
        f.write(csv_buffer.getvalue())
    temp_csv.replace(RESULTS_CSV)
    tracker.log(f'  Wrote {RESULTS_CSV.name}')

    # ----- TXT (Chapter 6 tables) -----
    lines: List[str] = []
    lines.append('=' * 78)
    lines.append('COMPARATIVE EVALUATION REPORT')
    lines.append(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    lines.append('=' * 78)
    for ds_name in DATASETS:
        if ds_name not in json_payload:
            continue
        lines.append('')
        lines.append(f'Table — {ds_name} Dataset Detection Performance')
        lines.append('-' * 78)
        header = f'{"System":<20}{"Prec":>8}{"Rec":>8}{"F1":>8}{"Acc":>8}{"AUC-ROC":>10}{"AUC-PR":>10}{"MCC":>8}{"FPR":>8}'
        lines.append(header)
        lines.append('-' * 78)
        for sys_name in SYSTEMS:
            m = json_payload[ds_name].get(sys_name)
            if not isinstance(m, dict) or 'precision' not in m:
                lines.append(f'{sys_name:<20}{"(skipped)":>70}')
                continue
            def fmt(x):
                return f'{x:>8.4f}' if isinstance(x, (int, float)) and not (isinstance(x, float) and np.isnan(x)) else f'{"N/A":>8}'
            lines.append(
                f'{sys_name:<20}'
                f'{fmt(m["precision"])}{fmt(m["recall"])}{fmt(m["f1_score"])}{fmt(m["accuracy"])}'
                f'{fmt(m["auc_roc"])}{" "*2}{fmt(m["auc_pr"])}{" "*2}{fmt(m["mcc"])}{fmt(m["fpr"])}'
            )
        lines.append('')
        lines.append(f'Table — {ds_name} Dataset Efficiency Metrics')
        lines.append('-' * 78)
        lines.append(f'{"System":<20}{"Latency μ ms":>16}{"Latency p95 ms":>18}{"Throughput/s":>16}{"Samples":>10}')
        lines.append('-' * 78)
        for sys_name in SYSTEMS:
            m = json_payload[ds_name].get(sys_name)
            if not isinstance(m, dict) or 'latency_mean_ms' not in m:
                continue
            lines.append(
                f'{sys_name:<20}{m["latency_mean_ms"]:>16.2f}{m["latency_p95_ms"]:>18.2f}'
                f'{m["throughput_per_sec"]:>16.2f}{m["n_samples"]:>10}'
            )
        lines.append('')
        lines.append(f'Paired t-tests (Agentic RAG vs baselines) — {ds_name}')
        lines.append('-' * 78)
        ttests = json_payload[ds_name].get('t_tests', {})
        for k, v in ttests.items():
            if not isinstance(v, dict):
                continue
            t = v.get('t_stat')
            p = v.get('p_value')
            sig = v.get('significant', False)
            t_str = 'N/A' if t is None else f'{t:+.4f}'
            p_str = 'N/A' if p is None else f'{p:.6f}'
            lines.append(
                f'  {k:<24} t={t_str:>9}  p={p_str:>10}  '
                f'significant_at_α=0.017: {sig}'
            )
    lines.append('')
    lines.append('=' * 78)
    lines.append('END OF REPORT')
    lines.append('=' * 78)
    # Atomic write for TXT report
    temp_txt = RESULTS_TXT.with_suffix('.tmp')
    temp_txt.write_text('\n'.join(lines))
    temp_txt.replace(RESULTS_TXT)
    tracker.log(f'  Wrote {RESULTS_TXT.name}')


# ============================================================
#  ENTRY POINT
# ============================================================
if __name__ == '__main__':
    try:
        run_full_evaluation()
        print('\n' + '=' * 60)
        print('EVALUATION COMPLETE')
        print(f'Results JSON: {RESULTS_JSON.name}')
        print(f'Metrics CSV : {RESULTS_CSV.name}')
        print(f'Report TXT  : {RESULTS_TXT.name}')
        print(f'Run log     : {RUN_LOG.name}')
        print('=' * 60)
    except KeyboardInterrupt:
        print('\nInterrupted. Checkpoint saved — re-run to resume.')
    except Exception as exc:
        print(f'FATAL: {exc}')
        traceback.print_exc()
        sys.exit(1)
