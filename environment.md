`Settings` class,  **Ollama** models:

- **Qwen 2.5 3B (4-bit quantized):** Authoring agent.
- **Mistral 3.2B (4-bit quantized):** Reviewer/judge agent.

Your existing `ROLE_DEFAULTS` already assigns Qwen to authors and Mistral to reviewers, so you don't need to change your Python settings code.

ollama pull qwen2.5:3b-instruct-q4_K_M
ollama pull llama3.2:3b-instruct-q4_K_M

## 1\. Create your `.env` file

Place this file in your project root, alongside `main.py`.

Create the following `.env`:

dotenv

```dotenv
# ==========================================
# Ollama Configuration
# ==========================================

OLLAMA_BASE_URL=http://localhost:11434

# ==========================================
# Model Configuration
# ==========================================
# Qwen 2.5 - 3B - Q4_K_M (Author)
QWEN_MODEL=qwen2.5:3b-instruct-q4_K_M

# Llama 3.2 - 3B - Q4_K_M (Reviewer)
MISTRAL_MODEL=llama3.2:3b-instruct-q4_K_M


# ==========================================
# Model Parameters
# ==========================================

MODEL_TEMPERATURE=0.2
MODEL_NUM_CTX=4096
MODEL_TIMEOUT_SECONDS=600

# ==========================================
# Agent Configuration
# ==========================================

MAX_AGENT_ITERATIONS=3

# ==========================================
# Application Configuration
# ==========================================

OUTPUT_DIR=output
LOG_LEVEL=INFO
```

These are valid Ollama model tags.  Ollama+1

## 2\. Download the models

First, make sure Ollama is running.

Then execute:

**Download Qwen 3B:**

bash

```bash
ollama pull qwen2.5:3b-instruct-q4_K_M
```

**Download Mistral 3B:**

bash

```bash
ollama pull llama3.2:3b-instruct-q4_K_M
```

Model references:

- [Qwen 2.5 3B Q4\_K\_M](<https://ollama.com/library/qwen2.5%3A3b-instruct-q4_K_M?utm_source=chatgpt.com>)
- [Mistral 7B Q4\_K\_M](<https://ollama.com/library/mistral/tags?utm_source=chatgpt.com>)

## 3\. Verify downloaded models

Run:

bash

```bash
ollama list
```

You should see both models:

text

```text
NAME
qwen2.5:3b-instruct-q4_K_M
llama3.2:3b-instruct-q4_K_M
```

Test them individually:

bash

```bash
ollama run qwen2.5:3b-instruct-q4_K_M
```

And:

bash

```bash
ollama pull llama3.2:3b-instruct-q4_K_M
```

## 4\. Your existing Python configuration

You don't need to modify your `Settings` class.

Your existing defaults:

python

```python
ROLE_DEFAULTS = {
    "author": "qwen",
    "reviewer": "mistral"
}
```

Will automatically assign:

| Agent role | Model | Quantization |
| --- | --- | --- |
| Author | Qwen 2.5 3B | Q4\_K\_M |
| Reviewer | Mistral 3.2 3B | Q4\_K\_M |

This applies to PRD, SYSRS, SRS, Architecture, LLD, Development, Testing, and Profile.

## 5\. Run your application

bash

```bash
python main.py profile --client react --server python --orm sqlalchemy --database postgresql
```

Then:

bash

```bash
python main.py prd "Build a simple task management application with user authentication, task creation, task updates, deletion, and status tracking."
```

**One performance recommendation:** Both models together require approximately 6–7 GB of model memory, excluding runtime overhead and context memory. Ideally, have at least 12 GB RAM available for comfortable CPU-based testing.

Also, `MODEL_NUM_CTX=4096` is a reasonable starting point for your initial tests. You can increase it later if your artifact-generation prompts require more context.