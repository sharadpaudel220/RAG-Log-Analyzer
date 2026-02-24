# Agentic RAG Framework for Real-Time System Log Analysis

**Dissertation Project**: Design and Evaluation of an Agentic Retrieval-Augmented Generation Framework for Real-Time System Log Analysis and Alerting

## Overview

Agentic RAG framework with multi-step reasoning to analyze system logs, detect anomalies, and generate actionable alerts. Compares 4 approaches:

1. **Rule-Based System** - Pattern matching
2. **Isolation Forest** - ML anomaly detection
3. **Non-Agentic RAG** - Single-pass RAG
4. **Agentic RAG** (Proposed) - Multi-step ReAct reasoning

**Key Components**: Drain3 log parsing | FAISS vector store | Hybrid retrieval | Mistral 7B (Ollama) | ReAct agent

## Quick Start

### 1. Install Dependencies

```bash
cd log-analyzer
pip install -r requirements.txt
```

### 2. Setup Ollama

```bash
# Install Ollama
brew install ollama  # macOS
# Or download from https://ollama.ai

# Start Ollama & pull model
ollama serve
ollama pull mistral:7b-instruct
```

### 3. Initialize System

```bash
python scripts/download_datasets.py
python main.py setup
python main.py health
```

## Usage

### CLI Analysis

```bash
# Analyze logs
python main.py analyze --log-file data/datasets/sample/sample_logs.log

# Run evaluation
python main.py evaluate --log-file data/datasets/sample/sample_logs.log --ground-truth data/datasets/sample/ground_truth.json
```

### Web Interface

```bash
python web_app_enhanced.py
# Access: http://localhost:5001
```

**Features**: Dashboard | Chat Interface | Log Sources | Comparative Evaluation | Real-time Monitoring

## Configuration

Edit `config/config.yaml` for LLM settings, retrieval parameters, and baseline configurations.

## Evaluation Metrics

**Performance**: Precision, Recall, F1-Score, Accuracy  
**Efficiency**: Latency, Throughput, Memory Usage

## Troubleshooting

```bash
# Ollama not running
ollama serve

# Rebuild knowledge base
python main.py setup --rebuild-kb
```

## Author

**Sharad Chandra Paudel** - London Metropolitan University (ID: 23057169)  




# Stream real-time logs                                                 
log stream --predicate 'eventMessage contains "error" OR eventMessage contains "fail"' --style syslog

# Export recent logs to file
log show --predicate 'processImagePath contains "kernel"' --last 1h --style syslog > /tmp/system_logs.txt