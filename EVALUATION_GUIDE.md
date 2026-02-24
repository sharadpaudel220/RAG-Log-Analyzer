# Evaluation Guide - Dissertation Alignment

This guide explains how to run the complete evaluation pipeline as specified in your dissertation proposal.

## Quick Evaluation

### 1. Sample Dataset (Quick Test)
```bash
python main.py evaluate --log-file data/datasets/sample/sample_logs.log --ground-truth data/datasets/sample/ground_truth.json
```

### 2. HDFS Dataset (2k entries)
```bash
python main.py evaluate --log-file data/datasets/hdfs/HDFS_2k.log --ground-truth data/datasets/hdfs/HDFS_2k_labels.csv
```

### 3. BGL Dataset (2k entries)
```bash
python main.py evaluate --log-file data/datasets/bgl/BGL_2k.log --ground-truth data/datasets/bgl/BGL_2k_labels.csv
```

## Evaluation Features

### ✅ Implemented (100% Proposal Alignment)

1. **All 4 Systems Evaluated**:
   - Rule-Based System
   - Isolation Forest
   - Non-Agentic RAG
   - Agentic RAG (Proposed)

2. **Train/Test Split (70/30)**:
   - Stratified split maintains class distribution
   - Random seed: 42 (reproducible)
   - Automatic for datasets > 100 entries

3. **Detection Metrics**:
   - Precision
   - Recall
   - F1-Score
   - Accuracy
   - False Positive Rate (FPR)
   - False Negative Rate (FNR)
   - True Positives/Negatives
   - False Positives/Negatives

4. **Efficiency Metrics**:
   - Average Latency (seconds per log)
   - Throughput (logs per second)
   - Memory Usage (MB)
   - Total Processing Time

5. **Statistical Analysis**:
   - Paired comparisons (Agentic RAG vs each baseline)
   - Significance testing (α = 0.05)
   - F1-score differences

6. **Visualizations** (saved to `results/figures/`):
   - Detection metrics comparison (bar chart)
   - Efficiency metrics comparison (3 subplots)
   - F1-score comparison (horizontal bar)
   - Performance vs Efficiency tradeoff (scatter)
   - Statistical significance (p-values)
   - Confusion matrices (one per system)

## Output Files

After running evaluation, you'll find:

```
results/
├── evaluation_report.json          # Complete metrics for all systems
├── figures/
│   ├── detection_metrics_comparison.png
│   ├── efficiency_metrics_comparison.png
│   ├── f1_score_comparison.png
│   ├── performance_tradeoff.png
│   ├── statistical_significance.png
│   ├── confusion_matrix_Rule-Based.png
│   ├── confusion_matrix_Isolation_Forest.png
│   ├── confusion_matrix_Non-Agentic_RAG.png
│   └── confusion_matrix_Agentic_RAG.png
```

## Dissertation Requirements Checklist

### Research Question 1: Detection Accuracy
- [x] F1-Score comparison across all 4 systems
- [x] Precision/Recall analysis
- [x] Confusion matrices for interpretability
- [x] Statistical significance testing

### Research Question 2: Computational Costs
- [x] Latency measurements (per-log analysis time)
- [x] Throughput calculations
- [x] Memory usage tracking
- [x] Performance vs Efficiency tradeoff visualization

### Methodology Alignment
- [x] Waterfall SDLC followed
- [x] All baseline systems implemented
- [x] Agentic RAG with ReAct (max 5 steps)
- [x] HDFS and BGL datasets
- [x] 70/30 train-test split
- [x] Paired t-tests for significance

### Technology Stack
- [x] Python 3.9+ (compatible with 3.12)
- [x] Drain3 log parsing
- [x] FAISS vector store
- [x] Mistral 7B via Ollama
- [x] LangChain framework
- [x] Scikit-learn (Isolation Forest)
- [x] Matplotlib/Seaborn visualization

## Advanced Usage

### Convert CSV Labels to JSON
```python
from src.utils.label_processor import LabelProcessor

processor = LabelProcessor()
processor.convert_csv_to_json(
    'data/datasets/hdfs/HDFS_2k_labels.csv',
    'data/datasets/hdfs/HDFS_2k_labels.json'
)
```

### Manual Train/Test Split
```python
from src.utils.data_splitter import DataSplitter

splitter = DataSplitter(train_ratio=0.7, random_seed=42)
train_logs, train_labels, test_logs, test_labels = splitter.stratified_split(
    parsed_logs, ground_truth
)
```

### Custom Evaluation
```python
from src.evaluation.evaluator import SystemEvaluator

evaluator = SystemEvaluator()
result = evaluator.evaluate_system(
    system_name="My System",
    analysis_function=my_analysis_function,
    log_entries=test_logs,
    ground_truth=test_labels
)
```

## Expected Results (Dissertation Proposal)

Based on your proposal, expected outcomes:

1. **Agentic RAG F1-Score**: > 0.90 on HDFS/BGL
2. **Higher Accuracy**: Agentic RAG > Non-Agentic RAG > ML > Rule-Based
3. **Increased Latency**: Agentic RAG slower due to multi-step reasoning
4. **Better Interpretability**: Reasoning chains provide explanations

## Troubleshooting

### "Not enough data for split"
- Dataset has < 100 entries
- System automatically uses all data
- No train/test split performed

### "Label mismatch"
- Number of logs ≠ number of labels
- Check ground truth file format
- Verify CSV has correct structure

### "Statistical test failed"
- Need at least 2 systems to compare
- Check that evaluation completed successfully

## Full Dissertation Evaluation Workflow

```bash
# 1. Setup system
python main.py setup

# 2. Download datasets (already done)
python scripts/download_datasets.py

# 3. Run evaluation on HDFS
python main.py evaluate \
  --log-file data/datasets/hdfs/HDFS_2k.log \
  --ground-truth data/datasets/hdfs/HDFS_2k_labels.csv

# 4. Run evaluation on BGL
python main.py evaluate \
  --log-file data/datasets/bgl/BGL_2k.log \
  --ground-truth data/datasets/bgl/BGL_2k_labels.csv

# 5. Review results
ls -lh results/figures/
cat results/evaluation_report.json
```

## Notes for Dissertation

- All visualizations are publication-ready (300 DPI)
- Evaluation report contains all metrics in JSON format
- Statistical tests provide evidence for RQ1
- Efficiency metrics address RQ2
- Confusion matrices support interpretability discussion
- Performance tradeoff plot illustrates accuracy vs speed

## Next Steps for Full Datasets

To evaluate on complete HDFS (11M) and BGL (4.7M) datasets:

1. Download from: https://zenodo.org/record/3227177
2. Place in respective directories
3. Run same evaluation commands with full filenames
4. Expect longer processing time (hours for full datasets)
