# IT equipment requests

MCP server and local ReAct agent for employee equipment requests. Policy rules are in [docs/requirements.md](docs/requirements.md).

The server exposes `get_employee_info`, `get_policy_limits`, `check_request_eligibility`, and `flag_for_human_review`. The agent uses Ollama (`qwen3:8b` by default) to choose tool calls, then checks its draft against those results before approving, denying, or escalating.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Tests

```bash
pytest
```

## One-tool client check

```bash
python agent/smoke_client.py
```

## Four demo requests

Ollama must be running locally with the model pulled.

```bash
python agent/demo.py
```

`OLLAMA_MODEL` overrides the model. `OLLAMA_HOST` overrides the server URL. `OLLAMA_THINK=false` skips the model's thinking trace and keeps only the assistant text.
