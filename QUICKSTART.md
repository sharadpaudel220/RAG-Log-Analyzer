# Quick Start Guide

Get the Agentic RAG Log Analyzer running in 5 minutes!

## Prerequisites Check

```bash
# Check Python version (need 3.12+)
python --version

# Check if Ollama is installed
ollama --version
```

## Installation (5 Steps)

### 1. Setup Python Environment

```bash
cd "Log Analyzer"
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Install Ollama

**macOS:**
```bash
brew install ollama
```

**Linux:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**Windows:** Download from https://ollama.ai

### 3. Start Ollama and Pull Model

```bash
# Terminal 1: Start Ollama
ollama serve

# Terminal 2: Pull Mistral model
ollama pull mistral:7b-instruct
```

### 4. Setup System

```bash
# Create sample data and initialize knowledge base
python scripts/download_datasets.py
python main.py setup
```

### 5. Verify Installation

```bash
python main.py health
```

You should see:
```
llm_engine: ✓ OK
knowledge_base: ✓ OK
vector_index: ✓ OK
```

## Run Your First Analysis

### Analyze Sample Logs

```bash
python main.py analyze --log-file data/datasets/sample/sample_logs.log
```

### Run Full Evaluation

```bash
python main.py evaluate --log-file data/datasets/sample/sample_logs.log --ground-truth data/datasets/sample/ground_truth.json
```

## View Results

After running evaluation:

1. **Evaluation Report**: `results/evaluation_report.json`
2. **Visualizations**: `results/figures/`
   - `detection_metrics_comparison.png`
   - `efficiency_metrics_comparison.png`
   - `f1_score_comparison.png`
   - Confusion matrices for each system
3. **Alerts**: `results/agentic_alerts.json`

## Common Commands

```bash
# Check system health
python main.py health

# Analyze logs with Agentic RAG
python main.py analyze --log-file <path-to-logs>

# Run comparative evaluation
python main.py evaluate --log-file <path-to-logs> --ground-truth <path-to-labels>

# Rebuild knowledge base
python main.py setup --rebuild-kb
```

## Troubleshooting

### "Ollama connection refused"
```bash
# Start Ollama in another terminal
ollama serve
```

### "Model not found"
```bash
# Pull the model
ollama pull mistral:7b-instruct
```

### "Knowledge base empty"
```bash
# Rebuild knowledge base
python main.py setup --rebuild-kb
```

## Next Steps

1. **Use Your Own Logs**: Replace the sample log file with your system logs
2. **Customize Configuration**: Edit `config/config.yaml`
3. **Add Knowledge**: Add domain-specific documents to the knowledge base
4. **Tune Parameters**: Adjust retrieval top-k, reasoning steps, etc.

## Getting Help

- Check `README.md` for detailed documentation
- Review `config/config.yaml` for all configuration options
- Check logs in `logs/main.log` for debugging

## Expected Performance

On sample logs (15 entries):
- **Analysis Time**: ~30-60 seconds
- **Agentic RAG F1-Score**: ~0.85-0.95
- **Alerts Generated**: 8-10 anomalies detected

Enjoy analyzing logs with Agentic RAG! 🚀
