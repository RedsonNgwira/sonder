"""
onboard.py — Interactive CLI setup wizard for Sonder.
Arrow keys to navigate, type to search models, Enter to confirm.
"""
import curses
import getpass
import sys
import webbrowser

PROVIDERS = [
    # (id, display_name, env_var, key_url, default_model, note)
    ("qwen-portal", "Qwen",                     None,                     None,                                         "qwen-portal/coder-model",               "Free OAuth login"),
    ("openrouter",  "OpenRouter",               "OPENROUTER_API_KEY",     "https://openrouter.ai/keys",                 "openrouter/qwen/qwen-2.5-72b-instruct", "Many free models"),
    ("groq",        "Groq",                     "GROQ_API_KEY",           "https://console.groq.com/keys",              "groq/llama-3.1-70b-versatile",          "Fast, free tier"),
    ("gemini",      "Google Gemini",             "GEMINI_API_KEY",         "https://aistudio.google.com/apikey",         "gemini/gemini-2.0-flash",               "Free tier"),
    ("anthropic",   "Anthropic",                "ANTHROPIC_API_KEY",      "https://console.anthropic.com/keys",         "anthropic/claude-sonnet-4-5",           ""),
    ("openai",      "OpenAI",                   "OPENAI_API_KEY",         "https://platform.openai.com/api-keys",       "openai/gpt-4o",                         ""),
    ("mistral",     "Mistral AI",               "MISTRAL_API_KEY",        "https://console.mistral.ai/api-keys",        "mistral/mistral-large-latest",          ""),
    ("xai",         "xAI (Grok)",               "XAI_API_KEY",            "https://console.x.ai",                       "xai/grok-2-latest",                     ""),
    ("together",    "Together AI",              "TOGETHER_API_KEY",       "https://api.together.xyz/settings/api-keys", "together/meta-llama/Llama-3-70b-chat-hf","Free tier"),
    ("huggingface", "Hugging Face",             "HUGGINGFACE_HUB_TOKEN",  "https://huggingface.co/settings/tokens",     "huggingface/meta-llama/Llama-3.1-70B",  ""),
    ("moonshot",    "Moonshot AI (Kimi)",        "MOONSHOT_API_KEY",       "https://platform.moonshot.cn",               "moonshot/moonshot-v1-8k",               ""),
    ("minimax",     "MiniMax",                  "MINIMAX_API_KEY",        "https://platform.minimaxi.com",              "minimax/abab6.5s-chat",                 ""),
    ("zai",         "Z.AI (GLM)",               "ZAI_API_KEY",            "https://bigmodel.cn",                        "zai/glm-4-flash",                       ""),
    ("volcengine",  "Volcano Engine (Doubao)",   "VOLCANO_ENGINE_API_KEY", "https://console.volcengine.com",             "volcengine/doubao-pro-32k",              ""),
    ("venice",      "Venice AI",                "VENICE_API_KEY",         "https://venice.ai",                          "venice/llama-3.3-70b",                  "Privacy-focused"),
    ("ollama",      "Ollama",                   None,                     None,                                         "ollama/llama3.3",                       "Local, free, no key needed"),
    ("custom",      "Custom (OpenAI-compatible)",None,                    None,                                         "",                                      "LM Studio, vLLM, etc."),
]


# ── Terminal colours ──────────────────────────────────────────────────────────

def _c(code, s): return f"\033[{code}m{s}\033[0m"
def cyan(s):   return _c(96, s)
def green(s):  return _c(92, s)
def yellow(s): return _c(93, s)
def red(s):    return _c(91, s)
def bold(s):   return _c(1, s)
def dim(s):    return _c(2, s)
def masked(k): return k[:4] + "****" + k[-4:] if len(k) > 8 else "****"


# ── Curses interactive picker ─────────────────────────────────────────────────

def _picker(stdscr, title: str, items: list[str], searchable: bool) -> str | None:
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN, -1)
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(3, curses.COLOR_WHITE, -1)

    query, cursor, scroll = "", 0, 0

    while True:
        filtered = [x for x in items if query.lower() in x.lower()] if searchable else items
        if not filtered:
            filtered = ["(no matches)"]

        stdscr.erase()
        h, w = stdscr.getmaxyx()

        stdscr.addstr(0, 0, title[:w-1], curses.A_BOLD | curses.color_pair(1))

        list_start = 1
        if searchable:
            stdscr.addstr(1, 0, f"  / {query}_"[:w-1], curses.color_pair(3))
            list_start = 2

        list_h = h - list_start - 1
        cursor = max(0, min(cursor, len(filtered) - 1))
        if cursor < scroll:
            scroll = cursor
        elif cursor >= scroll + list_h:
            scroll = cursor - list_h + 1

        for i, item in enumerate(filtered[scroll:scroll + list_h]):
            idx = i + scroll
            y = list_start + i
            if y >= h - 1:
                break
            prefix = " ● " if idx == cursor else "   "
            line = (prefix + item)[:w-1]
            attr = curses.color_pair(2) if idx == cursor else curses.color_pair(3)
            stdscr.addstr(y, 0, line, attr)

        hint = " ↑/↓  Enter:select  Esc:cancel" + ("  type:search" if searchable else "")
        stdscr.addstr(h-1, 0, hint[:w-1], curses.A_DIM)
        stdscr.refresh()

        key = stdscr.getch()
        if key == curses.KEY_UP:
            cursor = max(0, cursor - 1)
        elif key == curses.KEY_DOWN:
            cursor = min(len(filtered) - 1, cursor + 1)
        elif key in (curses.KEY_ENTER, 10, 13):
            sel = filtered[cursor]
            return None if sel == "(no matches)" else sel
        elif key == 27:
            return None
        elif searchable:
            if key in (curses.KEY_BACKSPACE, 127):
                query = query[:-1]; cursor = 0
            elif 32 <= key <= 126:
                query += chr(key); cursor = 0


def pick(title: str, items: list[str], searchable: bool = False) -> str | None:
    return curses.wrapper(_picker, title, items, searchable)


# ── Live model fetching ───────────────────────────────────────────────────────

def fetch_models(provider_id: str, api_key: str) -> list[str]:
    import urllib.request, json as _j, urllib.error

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def get(url):
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as r:
            return _j.loads(r.read())

    try:
        if provider_id == "openrouter":
            data = get("https://openrouter.ai/api/v1/models")
            # OpenRouter model IDs are already like "qwen/qwen-2.5-72b-instruct"
            # We prefix with "openrouter/" once
            return [f"openrouter/{m['id']}" for m in data.get("data", [])]

        if provider_id == "groq":
            data = get("https://api.groq.com/openai/v1/models")
            return [f"groq/{m['id']}" for m in data.get("data", [])]

        if provider_id == "openai":
            data = get("https://api.openai.com/v1/models")
            return sorted([f"openai/{m['id']}" for m in data.get("data", []) if "gpt" in m["id"]])

        if provider_id == "ollama":
            req = urllib.request.Request("http://localhost:11434/api/tags")
            with urllib.request.urlopen(req, timeout=5) as r:
                data = _j.loads(r.read())
            return [f"ollama/{m['name']}" for m in data.get("models", [])]

    except Exception:
        pass
    return []


# ── Key validation ────────────────────────────────────────────────────────────

def validate_key(provider_id: str, api_key: str) -> bool:
    """Quick check: can we list models with this key?"""
    return bool(fetch_models(provider_id, api_key))


# ── Main wizard ───────────────────────────────────────────────────────────────

def run():
    from config import get_config, save_config

    cfg = get_config()

    print()
    print(bold("🌐 Sonder — Setup"))
    print(dim("Self-hosted social simulation engine"))
    print()

    # Show current config if already set up
    if cfg.is_setup():
        print(f"  Current model : {cyan(cfg.model)}")
        print(f"  Provider      : {cyan(cfg.get_provider())}")
        ans = input("\n  Reconfigure? [y/N]: ").strip().lower()
        if ans != "y":
            print(f"\n  Run {cyan('python main.py')} to start.\n")
            return
        print()

    # ── Step 1: provider ──────────────────────────────────────────────────────
    labels = []
    for pid, name, _, _, _, note in PROVIDERS:
        badge = f" {yellow('[free]')}" if note and "free" in note.lower() else ""
        note_str = f"  {dim(note)}" if note else ""
        labels.append(f"{name}{badge}{note_str}")

    choice = pick("  Select AI provider  (↑/↓ Enter)", labels)
    if choice is None:
        print("Cancelled.")
        sys.exit(0)

    idx = labels.index(choice)
    provider_id, provider_name, env_var, key_url, default_model, _ = PROVIDERS[idx]
    print(f"\n  {cyan('▶')} {bold(provider_name)}\n")

    api_key, model, base_url = "", default_model, ""

    # ── Step 2: auth ──────────────────────────────────────────────────────────
    from providers.oauth import OAUTH_PROVIDERS, get_access_token, login as oauth_login

    if provider_id in OAUTH_PROVIDERS:
        existing = get_access_token(provider_id)
        if existing:
            print(f"  {green('✓')} Already logged in to {provider_name}.")
            reauth = input("  Re-authenticate? [y/N]: ").strip().lower()
            if reauth != "y":
                model = default_model
                # skip to save
                from config import save_config
                save_config({"model": model})
                print(f"\n  {green('✓')} Saved. Model: {cyan(model)}")
                print(f"\n  Start: {cyan('python main.py')}\n")
                return
        print(f"\n  Starting {provider_name} OAuth…")
        import asyncio
        ok = asyncio.run(oauth_login(provider_id))
        if not ok:
            print(red("  OAuth failed. Exiting."))
            sys.exit(1)
        model = default_model

    elif provider_id == "ollama":
        print(f"  {green('✓')} No API key needed.")
        print(f"  Make sure Ollama is running: {cyan('ollama serve')}")

    elif provider_id == "custom":
        base_url = input("  Base URL (e.g. http://localhost:1234/v1): ").strip()
        pname    = input("  Provider name (e.g. lmstudio): ").strip() or "custom"
        model_id = input("  Model ID: ").strip()
        model    = f"{pname}/{model_id}"
        api_key  = getpass.getpass("  API key (blank if not required): ").strip()

    else:
        if key_url:
            ans = input(f"  Open {cyan(key_url)} in browser? [Y/n]: ").strip().lower()
            if ans != "n":
                webbrowser.open(key_url)

        api_key = getpass.getpass(f"  Paste {provider_name} API key: ").strip()
        if not api_key:
            print(red("  No key entered. Exiting."))
            sys.exit(1)
        print(f"  Key: {dim(masked(api_key))}")

        print("  Validating key…", end="", flush=True)
        if validate_key(provider_id, api_key):
            print(f" {green('✓')}")
        else:
            print(f" {yellow('⚠ could not verify (continuing anyway)')}")

    # ── Step 3: model picker ──────────────────────────────────────────────────
    if provider_id not in OAUTH_PROVIDERS:
        print(f"\n  Fetching models…", end="", flush=True)
        models = fetch_models(provider_id, api_key)

        if models:
            print(f" {green(str(len(models)) + ' found')}")
            picked = pick(f"  Select model  (type to search)", models, searchable=True)
            model = picked if picked else default_model
        else:
            print(f" {dim('(offline — enter manually)')}")
            inp = input(f"  Model [{default_model}]: ").strip()
            model = inp or default_model

    # ── Step 4: save ──────────────────────────────────────────────────────────
    updates: dict = {"model": model}
    if api_key and provider_id not in ("custom", "ollama"):
        updates["keys"] = {provider_id: api_key}
    elif provider_id == "custom" and base_url:
        pname = model.split("/")[0]
        updates["custom_providers"] = {
            pname: {"base_url": base_url, "api_key": api_key, "models": []}
        }

    save_config(updates)

    print(f"\n  {green('✓')} Saved.")
    print(f"  Model : {cyan(model)}")
    print(f"\n  Start : {cyan('python main.py')}\n")


if __name__ == "__main__":
    run()
