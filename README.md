# Power Code Studio

Power Code Studio is a local-first, Ollama-first code studio for translation, prompt-to-code generation, prompt-to-project scaffolding, assistant-style coding workflows, project analysis, local validation, and repair loops.

It is designed for users who want strong local development workflows without depending on hosted model APIs.

---

## What it does

### Translation studio
Translate between mainstream languages and framework-aware targets such as:
- Python
- JavaScript
- TypeScript
- Node.js
- Node + Express.js
- NestJS
- Next.js
- React.js
- Vue.js
- PHP
- PHP Laravel
- PHP Yii2
- .NET C#
- Java
- SQL
- Go
- Rust
- C++
- Ruby

### AI builder
Generate either:
- a strong primary file from a natural-language prompt
- a compact multi-file project blueprint from a natural-language prompt

### AI assistant
Use the studio like a local coding assistant for:
- generate
- debug
- explain
- refactor
- review
- test
- fix

### Batch / multi-file translation
Upload multiple files, infer source profiles where possible, and translate them into one selected target profile. Download the results as a ZIP.

### Project analyzer
Inspect uploaded project files for:
- language counts
- inferred profiles
- framework hints
- dependency summary
- setup hints
- risk flags
- per-file insights

### Local validation
Best-effort local checks are supported when the toolchain exists on the machine.

### Compile-and-fix loop
When the generated target code fails validation, the system can re-prompt the model and retry fixes for a few rounds.

---

## Recommended Ollama model stack

This repository is built to work best with a task-aware routing setup instead of forcing one model for every task.

Recommended stack:
- `qwen2.5-coder:14b` for translation
- `qwen2.5-coder:14b` for compile-fix loops
- `qwen2.5-coder:14b` for assistant and code generation
- `llama3.1:8b` for semantic review
- `qwen2.5-coder:7b` as default lightweight fallback

If you share this repo with someone else, they must install Ollama and pull these models locally.

---

## Quick start

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd power_code_studio
```

### 2. Create a Python environment

Using venv:

```bash
python -m venv .venv
source .venv/bin/activate
```

Using Conda:

```bash
conda create -n power_code_studio python=3.11 -y
conda activate power_code_studio
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Ollama

On Linux:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Then start Ollama:

```bash
ollama serve
```

Open a second terminal for model pulls.

### 5. Pull the recommended models

```bash
ollama pull qwen2.5-coder:7b
ollama pull qwen2.5-coder:14b
ollama pull llama3.1:8b
```

Or use the helper script included in this repo:

```bash
bash setup_ollama_models.sh
```

### 6. Verify Ollama models

```bash
ollama list
```

### 7. Configure the app

```bash
cp .env.example .env
```

Default `.env`:

```env
OLLAMA_BASE_URL=http://localhost:11434
USE_OLLAMA=true
OLLAMA_TIMEOUT_SECONDS=180
OLLAMA_MODEL=qwen2.5-coder:7b
OLLAMA_TRANSLATION_MODEL=qwen2.5-coder:14b
OLLAMA_FIX_MODEL=qwen2.5-coder:14b
OLLAMA_REVIEW_MODEL=llama3.1:8b
OLLAMA_ASSISTANT_MODEL=qwen2.5-coder:14b
OLLAMA_CODEGEN_MODEL=qwen2.5-coder:14b
OLLAMA_PROJECT_MODEL=qwen2.5-coder:14b
```

### 8. Run the GUI

```bash
streamlit run app.py
```

Or:

```bash
bash start_gui.sh
```

### 9. Run the API

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

Or:

```bash
bash start_api.sh
```

---

## One-command onboarding flow for other users

This is the simplest setup flow to put in front of anyone using your repo:

```bash
cp .env.example .env
pip install -r requirements.txt
bash setup_ollama_models.sh
streamlit run app.py
```

---

## How model routing works

The app can work in two modes:
- **single model mode**: one model is used for everything
- **auto / routed mode**: different models are used for translation, fix, review, assistant, and project generation

Recommended routed assignments:
- translation: `qwen2.5-coder:14b`
- fix loops: `qwen2.5-coder:14b`
- review: `llama3.1:8b`
- assistant: `qwen2.5-coder:14b`
- code generation: `qwen2.5-coder:14b`
- project generation: `qwen2.5-coder:14b`
- fallback/default: `qwen2.5-coder:7b`

---

## Local validation support

The studio attempts validation when toolchains are present:
- Python: `py_compile`
- JavaScript: `node --check`
- TypeScript: `tsc --noEmit`
- Java: `javac`
- C#: `csc` or `mcs`
- C++: `g++ -fsyntax-only` or `clang++ -fsyntax-only`
- Go: `go build` or `gofmt -e`
- Rust: `rustc --emit metadata`
- PHP: `php -l`
- Ruby: `ruby -wc`
- SQL: best-effort SQLite syntax check

For full framework validation, install the real toolchains. Examples:
- Next.js still needs the actual Next.js toolchain
- Laravel and Yii2 still need Composer and framework context
- Java multi-file projects still need Maven or Gradle
- .NET projects still need `dotnet` or another proper compiler workflow

---

## API and health checks

Useful checks after startup:

```bash
curl http://localhost:11434/api/tags
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/models
```

These help confirm:
- Ollama is running
- the API is running
- the app can see the local models

---

## Recommended repository additions

To make the repo easier for others to use, keep these files committed:
- `README.md`
- `requirements.txt`
- `.env.example`
- `setup_ollama_models.sh`
- `.gitignore`

A practical `.gitignore` should include:

```gitignore
__pycache__/
*.pyc
.pytest_cache/
.streamlit/secrets.toml
.env
.venv/
venv/
node_modules/
dist/
build/
coverage/
*.log
.DS_Store
```

---

## Minimal run commands

### GUI only

```bash
pip install -r requirements.txt
cp .env.example .env
bash setup_ollama_models.sh
streamlit run app.py
```

### API only

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

---

## Recommended models for shared-repo users

If someone asks, “Which models do I need to pull?”, the answer for this repo is:

```bash
ollama pull qwen2.5-coder:7b
ollama pull qwen2.5-coder:14b
ollama pull llama3.1:8b
```

That is the intended default local stack for this project.
