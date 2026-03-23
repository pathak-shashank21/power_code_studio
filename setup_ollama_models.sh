#!/usr/bin/env bash
set -euo pipefail

echo "Installing recommended Ollama models for Power Code Studio..."
ollama pull qwen2.5-coder:7b
ollama pull qwen2.5-coder:14b
ollama pull llama3.1:8b

echo
echo "Installed models:"
ollama list
