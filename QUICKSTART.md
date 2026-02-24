# Quick Start Guide

Get running in 5 minutes!

## Installation

```bash
cd log-analyzer
pip install -r requirements.txt

# Install & start Ollama
brew install ollama  # macOS (or download from ollama.ai)
ollama serve
ollama pull mistral:7b-instruct

# Initialize system
python scripts/download_datasets.py
python main.py setup
python main.py health
```

## Run Analysis

```bash
# CLI
python main.py analyze --log-file data/datasets/sample/sample_logs.log

# Web Interface
python web_app_enhanced.py
# Open: http://localhost:5001
```

## BYOK (Bring Your Own Key)

Set `llm.provider` in `config/config.yaml` to one of:

```text
ollama
openai   (ChatGPT)
anthropic (Claude)
gemini
```

Then provide your key via environment variable (recommended):

```bash
export OPENAI_API_KEY=...      # for openai
export ANTHROPIC_API_KEY=...   # for anthropic
export GEMINI_API_KEY=...      # for gemini
```

Also set `llm.model` in `config/config.yaml` to a model supported by your provider.

## Common Commands

```bash
python main.py health                    # Check system
python main.py analyze --log-file <path> # Analyze logs
python main.py evaluate --log-file <path> --ground-truth <path> # Run evaluation
python main.py setup --rebuild-kb        # Rebuild knowledge base
```

## Troubleshooting

```bash
ollama serve                    # If Ollama connection refused
ollama pull mistral:7b-instruct # If model not found
python main.py setup --rebuild-kb # If knowledge base empty
```

See `README.md` for full documentation.
