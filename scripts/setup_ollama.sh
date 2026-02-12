#!/bin/bash

echo "=========================================="
echo "Ollama Setup Script for Log Analyzer"
echo "=========================================="
echo ""

if ! command -v ollama &> /dev/null
then
    echo "Ollama is not installed."
    echo "Please install Ollama from: https://ollama.ai"
    echo ""
    echo "Installation instructions:"
    echo "  macOS: brew install ollama"
    echo "  Linux: curl -fsSL https://ollama.ai/install.sh | sh"
    exit 1
fi

echo "✓ Ollama is installed"
echo ""

echo "Checking if Ollama service is running..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✓ Ollama service is running"
else
    echo "✗ Ollama service is not running"
    echo "Please start Ollama:"
    echo "  ollama serve"
    exit 1
fi

echo ""
echo "Pulling Mistral 7B Instruct model..."
ollama pull mistral:7b-instruct

echo ""
echo "Verifying model installation..."
if ollama list | grep -q "mistral:7b-instruct"; then
    echo "✓ Mistral 7B Instruct model is installed"
else
    echo "✗ Failed to install Mistral model"
    exit 1
fi

echo ""
echo "=========================================="
echo "Ollama setup complete!"
echo "=========================================="
echo ""
echo "You can now run the Log Analyzer system."
