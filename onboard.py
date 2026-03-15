"""
onboard.py — Sonder setup wizard.
Clack-style UX: intro/outro, spinners, select, text, confirm.
"""
import asyncio
import getpass
import sys
import webbrowser

import questionary
from questionary import Style

PROVIDERS = [
    # (id, display_name, env_var, key_url, default_model, note)
    ("qwen-portal", "Qwen",                      None,                     None,                                          "qwen-portal/coder-model",                "Free OAuth"),
    ("openrouter",  "OpenRouter",                "OPENROUTER_API_KEY",     "https://openrouter.ai/keys",                  "openrouter/qwen/qwen-2.5-72b-instruct",  "Many free models"),
    ("groq",        "Groq",                      "GROQ_API_KEY",           "https://console.groq.com/keys",               "groq/llama-3.1-70b-versatile",           "Fast, free tier"),
    ("cerebras",    "Cerebras",                  "CEREBRAS_API_KEY",       "https://cloud.cerebras.ai",                   "cerebras/llama3.1-8b",                   "Fastest, free tier"),
    ("gemini",      "Google Gemini",              "GEMINI_API_KEY",         "https://aistudio.google.com/apikey",          "gemini/gemini-2.0-flash",                "Free tier"),
    ("anthropic",   "Anthropic",                 "ANTHROPIC_API_KEY",      "https://console.anthropic.com/keys",          "anthropic/claude-sonnet-4-5",            ""),
    ("openai",      "OpenAI",                    "OPENAI_API_KEY",         "https://platform.openai.com/api-keys",        "openai/gpt-4o",                          ""),
    ("mistral",     "Mistral AI",                "MISTRAL_API_KEY",        "https://console.mistral.ai/api-keys",         "mistral/mistral-large-latest",           ""),
    ("xai",         "xAI (Grok)",                "XAI_API_KEY",            "https://console.x.ai",                        "xai/grok-2-latest",                      ""),
    ("together",    "Together AI",               "TOGETHER_API_KEY",       "https://api.together.xyz/settings/api-keys",  "together/meta-llama/Llama-3-70b-chat-hf","Free tier"),
    ("huggingface", "Hugging Face",              "HUGGINGFACE_HUB_TOKEN",  "https://huggingface.co/settings/tokens",      "huggingface/meta-llama/Llama-3.1-70B",   ""),
    ("moonshot",    "Moonshot AI (Kimi)",         "MOONSHOT_API_KEY",       "https://platform.moonshot.cn",                "moonshot/moonshot-v1-8k",                ""),
    ("minimax",     "MiniMax",                   "MINIMAX_API_KEY",        "https://platform.minimaxi.com",               "minimax/abab6.5s-chat",                  ""),
    ("zai",         "Z.AI (GLM)",                "ZAI_API_KEY",            "https://bigmodel.cn",                         "zai/glm-4-flash",                        ""),
    ("volcengine",  "Volcano Engine (Doubao)",    "VOLCANO_ENGINE_API_KEY", "https://console.volcengine.com",              "volcengine/doubao-pro-32k",               ""),
    ("venice",      "Venice AI",                 "VENICE_API_KEY",         "https://venice.ai",                           "venice/llama-3.3-70b",                   "Privacy-focused"),
    ("ollama",      "Ollama",                    None,                     None,                                          "ollama/llama3.3",                        "Local, no key needed"),
    ("custom",      "Custom (OpenAI-compatible)", None,                    None,                                          "",                                       "LM Studio, vLLM, etc."),
]

STYLE = Style([
    ("qmark",     "fg:#00d7ff bold"),
    ("question",  "bold"),
    ("answer",    "fg:#00d7ff bold"),
    ("pointer",   "fg:#00d7ff bold"),
    ("highlighted","fg:#00d7ff bold"),
    ("selected",  "fg:#00d7ff"),
    ("separator", "fg:#444444"),
    ("instruction","fg:#444444"),
])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _c(code, s): return f"\033[{code}m{s}\033[0m"
def cyan(s):  return _c("96", s)
def green(s): return _c("92", s)
def yellow(s):return _c("93", s)
def red(s):   return _c("91", s)
def dim(s):   return _c("2",  s)
def bold(s):  return _c("1",  s)

def _sep():   print(dim("  " + "─" * 48))

def intro(title: str, subtitle: str = ""):
    print()
    print(f"  {bold(cyan('◆'))} {bold(title)}")
    if subtitle:
        print(f"  {dim(subtitle)}")
    _sep()

def outro(msg: str):
    _sep()
    print(f"  {green('◆')} {bold(msg)}")
    print()

def note(title: str, body: str):
    _sep()
    print(f"  {cyan('│')} {bold(title)}")
    for line in body.splitlines():
        print(f"  {cyan('│')} {line}")
    _sep()

def spinner_start(msg: str):
    print(f"  {cyan('◇')} {msg}", end="", flush=True)

def spinner_stop(msg: str = ""):
    if msg:
        print(f"\r  {green('◆')} {msg}          ")
    else:
        print()

def masked(k: str) -> str:
    return k[:4] + "••••" + k[-4:] if len(k) > 8 else "••••"


# ── Model fetching ────────────────────────────────────────────────────────────

def fetch_models(provider_id: str, api_key: str) -> list[str]:
    import urllib.request, json as _j
    headers = {"User-Agent": "sonder/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    def get(url):
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as r:
            return _j.loads(r.read())
    try:
        if provider_id == "openrouter":
            return [f"openrouter/{m['id']}" for m in get("https://openrouter.ai/api/v1/models").get("data", [])]
        if provider_id == "groq":
            return [f"groq/{m['id']}" for m in get("https://api.groq.com/openai/v1/models").get("data", [])]
        if provider_id == "cerebras":
            return [f"cerebras/{m['id']}" for m in get("https://api.cerebras.ai/v1/models").get("data", [])]
        if provider_id == "openai":
            return sorted([f"openai/{m['id']}" for m in get("https://api.openai.com/v1/models").get("data", []) if "gpt" in m["id"]])
        if provider_id == "ollama":
            return [f"ollama/{m['name']}" for m in get("http://localhost:11434/api/tags").get("models", [])]
    except Exception:
        pass
    return []


# ── Wizard ────────────────────────────────────────────────────────────────────

def run():
    from config import get_config, save_config
    from providers.oauth import OAUTH_PROVIDERS, get_access_token, login as oauth_login

    cfg = get_config()

    intro("Sonder", "Self-hosted social simulation engine")

    if cfg.is_setup():
        print(f"  Provider : {cyan(cfg.get_provider())}")
        print(f"  Model    : {cyan(cfg.model)}")
        print()
        if not questionary.confirm("  Reconfigure?", default=False, style=STYLE).ask():
            outro(f"Run  python main.py  to start.")
            return
        print()

    # ── Provider ──────────────────────────────────────────────────────────────
    choices = []
    for pid, name, _, _, _, note_txt in PROVIDERS:
        badge = f"  [{note_txt}]" if note_txt else ""
        choices.append(questionary.Choice(title=f"{name}{badge}", value=pid))

    provider_id = questionary.select(
        "  Choose a provider",
        choices=choices,
        style=STYLE,
        use_shortcuts=False,
    ).ask()

    if provider_id is None:
        print("Cancelled.")
        sys.exit(0)

    row = next(r for r in PROVIDERS if r[0] == provider_id)
    _, provider_name, env_var, key_url, default_model, _ = row
    print()

    api_key, model, base_url = "", default_model, ""

    # ── Auth ──────────────────────────────────────────────────────────────────
    if provider_id in OAUTH_PROVIDERS:
        existing = get_access_token(provider_id)
        if existing:
            print(f"  {green('✓')} Already logged in to {provider_name}.")
            if not questionary.confirm("  Re-authenticate?", default=False, style=STYLE).ask():
                save_config({"model": default_model})
                outro(f"Saved. Run  python main.py  to start.")
                return
        spinner_start(f"Starting {provider_name} OAuth…")
        print()
        ok = asyncio.run(oauth_login(provider_id))
        if not ok:
            print(f"\n  {red('✗')} OAuth failed.")
            sys.exit(1)
        spinner_stop(f"{provider_name} authenticated")
        model = default_model

    elif provider_id == "ollama":
        print(f"  {green('✓')} No API key needed.")
        print(f"  Make sure Ollama is running: {cyan('ollama serve')}")

    elif provider_id == "custom":
        base_url = questionary.text("  Base URL (e.g. http://localhost:1234/v1)", style=STYLE).ask().strip()
        pname    = questionary.text("  Provider name (e.g. lmstudio)", style=STYLE).ask().strip() or "custom"
        model_id = questionary.text("  Model ID", style=STYLE).ask().strip()
        model    = f"{pname}/{model_id}"
        api_key  = getpass.getpass("  API key (blank if not required): ").strip()

    else:
        if key_url:
            if questionary.confirm(f"  Open {key_url} in browser?", default=True, style=STYLE).ask():
                webbrowser.open(key_url)
        api_key = getpass.getpass(f"  Paste {provider_name} API key: ").strip()
        if not api_key:
            print(f"  {red('✗')} No key entered.")
            sys.exit(1)
        print(f"  Key: {dim(masked(api_key))}")

        spinner_start("Validating key…")
        valid = bool(fetch_models(provider_id, api_key))
        spinner_stop("Key valid ✓" if valid else "Could not verify (continuing anyway)")

    # ── Model picker ──────────────────────────────────────────────────────────
    if provider_id not in OAUTH_PROVIDERS:
        spinner_start("Fetching models…")
        models = fetch_models(provider_id, api_key)
        spinner_stop(f"{len(models)} models found" if models else "offline — enter manually")

        if models:
            picked = questionary.autocomplete(
                "  Select model",
                choices=models,
                default=default_model if default_model in models else (models[0] if models else ""),
                style=STYLE,
                validate=lambda v: v in models or "Pick from the list",
            ).ask()
        else:
            picked = questionary.text(f"  Model", default=default_model, style=STYLE).ask()

        if picked is None:
            print("Cancelled.")
            sys.exit(0)
        model = picked.strip() or default_model

    # ── Save ──────────────────────────────────────────────────────────────────
    updates: dict = {"model": model}
    if api_key and provider_id not in ("custom", "ollama"):
        updates["keys"] = {provider_id: api_key}
    elif provider_id == "custom" and base_url:
        pname = model.split("/")[0]
        updates["custom_providers"] = {pname: {"base_url": base_url, "api_key": api_key, "models": []}}

    save_config(updates)

    note("Saved", f"Provider : {provider_name}\nModel    : {model}")
    outro(f"Run  python main.py  to start.")


if __name__ == "__main__":
    run()
