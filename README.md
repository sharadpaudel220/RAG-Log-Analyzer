# Agentic RAG Framework for Real-Time System Log Analysis

This is the implementation of the dissertation project: **"Design and Evaluation of an Agentic Retrieval-Augmented Generation Framework for Real-Time System Log Analysis and Alerting"**

## Overview

This system implements an agentic RAG (Retrieval-Augmented Generation) framework that uses multi-step reasoning to analyze system logs, detect anomalies, and generate actionable alerts. The framework is compared against three baseline approaches:

1. **Rule-Based System** - Pattern matching with predefined rules
2. **Isolation Forest** - Classical ML anomaly detection
3. **Non-Agentic RAG** - Single-pass RAG without iterative reasoning
4. **Agentic RAG** (Proposed) - Multi-step reasoning with ReAct-style agent

## System Architecture

```
Input Layer → Preprocessing Layer → Core Processing Layer → Output Layer
                                    ├─ Agentic Controller
                                    ├─ Retrieval System
                                    └─ LLM Engine
```

### Key Components

- **Log Preprocessor**: Drain3-based log parsing and normalization
- **Knowledge Base**: FAISS vector store with historical incidents
- **Retrieval System**: Hybrid semantic + keyword retrieval
- **LLM Engine**: Mistral 7B via Ollama
- **Agentic Controller**: ReAct-style multi-step reasoning (max 5 steps)
- **Alert Generator**: Structured alerts with explanations

## Installation

### Prerequisites

- Python 3.12+
- Ollama (for LLM inference)
- 8GB+ RAM recommended
- macOS, Linux, or Windows

### Step 1: Clone and Setup

```bash
cd "Log Analyzer"
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Install and Setup Ollama

```bash
# Install Ollama (macOS)
brew install ollama

# Or download from https://ollama.ai

# Start Ollama service
ollama serve

# Pull Mistral model (in another terminal)
chmod +x scripts/setup_ollama.sh
./scripts/setup_ollama.sh
```

### Step 3: Setup Datasets

```bash
python scripts/download_datasets.py
```

This will create sample logs and provide instructions for downloading HDFS and BGL datasets.

### Step 4: Initialize Knowledge Base

```bash
python main.py setup
```

## Usage

### 1. Check System Health

```bash
python main.py health
```

### 2. Analyze Logs (Agentic RAG)

```bash
python main.py analyze --log-file data/datasets/sample/sample_logs.log --output-dir results
```

### 3. Run Comparative Evaluation

```bash
python main.py evaluate --log-file data/datasets/sample/sample_logs.log --ground-truth data/datasets/sample/ground_truth.json
```

This will:
- Evaluate all 4 systems (Rule-Based, Isolation Forest, Non-Agentic RAG, Agentic RAG)
- Generate performance metrics (Precision, Recall, F1-Score, Latency, Memory)
- Create visualization plots in `results/figures/`
- Save evaluation report to `results/evaluation_report.json`

### 4. Rebuild Knowledge Base

```bash
python main.py setup --rebuild-kb
```

## Project Structure

```
Log Analyzer/
├── config/
│   └── config.yaml              # System configuration
├── src/
│   ├── input_layer/
│   │   └── log_ingestion.py     # Log file ingestion
│   ├── preprocessing/
│   │   └── log_preprocessor.py  # Drain3 parsing
│   ├── knowledge_base/
│   │   └── knowledge_manager.py # FAISS vector store
│   ├── retrieval/
│   │   └── retrieval_system.py  # Hybrid retrieval
│   ├── llm_engine/
│   │   └── llm_interface.py     # Ollama/Mistral interface
│   ├── agentic_controller/
│   │   └── agentic_rag.py       # ReAct agent
│   ├── output_layer/
│   │   └── alert_generator.py   # Alert generation
│   ├── baselines/
│   │   ├── rule_based.py        # Rule-based baseline
│   │   ├── isolation_forest.py  # ML baseline
│   │   └── non_agentic_rag.py   # Non-agentic RAG
│   ├── evaluation/
│   │   ├── metrics.py           # Metrics calculation
│   │   ├── evaluator.py         # System evaluation
│   │   └── visualizer.py        # Result visualization
│   └── utils/
│       ├── config_loader.py     # Configuration management
│       └── logger.py            # Logging utilities
├── scripts/
│   ├── download_datasets.py     # Dataset setup
│   └── setup_ollama.sh          # Ollama setup
├── main.py                      # Main entry point
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## Configuration

Edit `config/config.yaml` to customize:

- **LLM settings**: Model, temperature, max tokens
- **Retrieval settings**: Top-k, similarity threshold
- **Agentic settings**: Max reasoning steps, confidence threshold
- **Baseline settings**: Rule patterns, contamination rate

## Evaluation Metrics

### Detection Performance
- Precision
- Recall
- F1-Score
- False Positive Rate (FPR)
- False Negative Rate (FNR)
- Accuracy

### Efficiency
- Average Latency (seconds per log)
- Throughput (logs per second)
- Memory Usage (MB)
- Total Processing Time

## Research Questions

**RQ1**: Does agentic RAG improve detection accuracy compared to non-agentic RAG and rule-based approaches?

**RQ2**: What are the computational costs of agentic RAG compared to baseline approaches?

## Expected Results

Based on the dissertation proposal, the system should demonstrate:

1. **Higher F1-scores** for Agentic RAG (target: >0.90 on HDFS/BGL)
2. **Better interpretability** through reasoning chains
3. **Increased latency** due to multi-step reasoning
4. **Trade-off analysis** between accuracy and computational cost

## Sample Output

```
================================================================================
ALERT: HIGH: Error Detected in DataNode
================================================================================
Alert ID: ALERT-20260212-00001
Timestamp: 2026-02-12 18:45:23
Severity: HIGH
Confidence: 87.50%

Description:
Log Content: 2024-01-15 10:23:47 ERROR [DataNode] Exception in receiveBlock...

Analysis:
Issue Identification: Block reception failure in DataNode
Root Cause: Network connectivity or corrupted block data
Impact: Data replication may be affected

Recommended Actions:
  1. Check network connectivity between DataNode and NameNode
  2. Verify block integrity using fsck
  3. Review DataNode logs for additional errors
  4. Monitor replication status

Reasoning Chain:
  Step 1: I need to analyze this log entry with severity ERROR...
  Step 2: I have retrieved relevant knowledge about block corruption...
  Step 3: I have sufficient confidence in my analysis...
================================================================================
```

## Troubleshooting

### Ollama Connection Error
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve
```

### Memory Issues
- Reduce batch size in `config.yaml`
- Use quantized models (4-bit)
- Process logs in smaller chunks

### FAISS Index Error
```bash
# Rebuild knowledge base
python main.py setup --rebuild-kb
```

## Citation

If you use this system in your research, please cite:

```
Paudel, S. C. (2026). Design and Evaluation of an Agentic Retrieval-Augmented 
Generation Framework for Real-Time System Log Analysis and Alerting. 
Master's Dissertation, London Metropolitan University.
```

## License

This project is developed for academic research purposes as part of a Master's dissertation.

## Author

**Sharad Chandra Paudel**
- London Met ID: 23057169
- College ID: NP01MS7S240007
- Supervisor: Aadesh Tandukar

## Acknowledgments

- Drain3 for log parsing
- FAISS for vector similarity search
- Ollama for local LLM inference
- LogHub for benchmark datasets
