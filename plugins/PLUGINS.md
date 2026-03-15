# Sonder Plugin Interface

Sonder is designed to stay minimal at its core. Voice, avatars, memory backends, export — these are plugin territory.

## Voice

The voice interface is the most requested extension point. The contract is simple:

```python
# A voice plugin is any module that exposes this function:
async def speak(agent_name: str, text: str, config: dict) -> None:
    """Play or stream audio for an agent utterance."""
    ...
```

Place it at `plugins/voice_{name}.py` and set in your config:

```yaml
voice:
  enabled: true
  provider: elevenlabs   # matches plugins/voice_elevenlabs.py
```

### Providers people are building toward

| Provider | Cost | Quality |
|----------|------|---------|
| Browser Web Speech API | Free | Robotic but works |
| Piper | Free, local | Good |
| Coqui TTS | Free, local | Very good |
| OpenAI TTS | ~$0.015/1k chars | Excellent |
| ElevenLabs | Paid | Best |

Browser TTS requires no plugin — it runs in the frontend via `window.speechSynthesis`. Everything else needs a backend plugin.

## Other extension points

- `plugins/avatar_{name}.py` — generate agent portrait images (`async def generate(agent: Agent) -> str` returns image URL)
- `plugins/memory_{name}.py` — persistent memory backend (replace in-process list with vector DB, etc.)
- `plugins/export_{name}.py` — export a simulation session (`async def export(world: World, turns: list) -> None`)

## Contributing a plugin

1. Create `plugins/your_plugin.py`
2. Add a section here documenting the config keys it reads
3. Open a PR — plugins don't need to touch core code
