# Sonder

**Self-hosted social simulation engine.** Describe any scene and step into a world of AI agents that behave like real people.

> *Sonder (n.) — the realization that each passerby has a life as vivid and complex as your own.*

![Sonder UI](docs/screenshot.png)

---

## What it does

You describe a scene in plain language:

> *"A pub after Liverpool lost 3-0. Some Chelsea fans are celebrating nearby."*

Sonder spawns AI agents with distinct personalities, emotional states, and relationships. They talk to each other, react to what you say, ignore you, argue, laugh, go quiet — behaving like real people in that context.

**Use cases:** social anxiety practice, interview prep, creative writing, loneliness, curiosity.

---

## Install

### Docker (recommended for VPS / 24/7)
```bash
docker run -d -p 8080:8080 --restart always ghcr.io/yourusername/sonder
```
Then open `http://localhost:8080`

### Mac / Linux (one-liner)
```bash
curl -fsSL https://sonder.sh/install.sh | sh
```

### From source
```bash
git clone https://github.com/yourusername/sonder
cd sonder
pip install -r requirements.txt
python main.py
```

### Windows
Use Docker Desktop and run the Docker command above.

---

## Supported providers

Works with any LLM via [LiteLLM](https://github.com/BerriAI/litellm):

| Provider | Example model |
|----------|--------------|
| Ollama (local, free) | `ollama/llama3` |
| Anthropic | `anthropic/claude-sonnet-4-5` |
| OpenAI | `openai/gpt-4o` |
| Groq | `groq/llama-3.1-70b-versatile` |
| Any OpenAI-compatible | set `api_base` in settings |

Configure your provider in the onboarding wizard on first run, or in Settings.

---

## VPS deployment (Ubuntu)

```bash
# Clone and install
git clone https://github.com/yourusername/sonder /opt/sonder
cd /opt/sonder && python3 -m venv venv && venv/bin/pip install -r requirements.txt

# Install as systemd service
sudo cp sonder.service /etc/systemd/system/
sudo systemctl enable --now sonder

# Access at http://your-server-ip:8080
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The codebase is intentionally small and readable.

Key files:
- `simulation/agent.py` — agent personality and response logic
- `simulation/world_builder.py` — scene parsing and agent spawning
- `simulation/loop.py` — turn order and simulation tick
- `providers/llm.py` — LLM abstraction (add new providers here)

---

## License

MIT
