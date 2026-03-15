"""
onboard.py — Interactive CLI onboarding wizard for Sonder.
Arrow keys to navigate, Enter to select, type to filter models.
"""
import curses
import sys
import webbrowser

PROVIDERS = [
    # (id, display_name, env_var, key_url, default_model, note)
    ("openrouter",   "OpenRouter",                    "OPENROUTER_API_KEY",     "https://openrouter.ai/keys",                 "openrouter/qwen/qwen-2.5-72b-instruct", "Many free models"),
    ("groq",         "Groq",                          "GROQ_API_KEY",           "https://console.groq.com/keys",              "groq/llama-3.1-70b-versatile",          "Fast, free tier"),
    ("gemini",       "Google Gemini",                 "GEMINI_API_KEY",         "https://aistudio.google.com/apikey",         "gemini/gemini-2.0-flash",               "Free tier"),
    ("anthropic",    "Anthropic",                     "ANTHROPIC_API_KEY",      "https://console.anthropic.com/keys",         "anthropic/claude-sonnet-4-5",           ""),
    ("openai",       "OpenAI",                        "OPENAI_API_KEY",         "https://platform.openai.com/api-keys",       "openai/gpt-4o",                         ""),
    ("mistral",      "Mistral AI",                    "MISTRAL_API_KEY",        "https://console.mistral.ai/api-keys",        "mistral/mistral-large-latest",          ""),
    ("xai",          "xAI (Grok)",                    "XAI_API_KEY",            "https://console.x.ai",                       "xai/grok-2-latest",                     ""),
    ("together",     "Together AI",                   "TOGETHER_API_KEY",       "https://api.together.xyz/settings/api-keys", "together/meta-llama/Llama-3-70b-chat-hf","Free tier"),
    ("huggingface",  "Hugging Face",                  "HUGGINGFACE_HUB_TOKEN",  "https://huggingface.co/settings/tokens",     "huggingface/meta-llama/Llama-3.1-70B",  ""),
    ("moonshot",     "Moonshot AI (Kimi)",             "MOONSHOT_API_KEY",       "https://platform.moonshot.cn",               "moonshot/moonshot-v1-8k",               ""),
    ("minimax",      "MiniMax",                       "MINIMAX_API_KEY",        "https://platform.minimaxi.com",              "minimax/abab6.5s-chat",                 ""),
    ("zai",          "Z.AI (GLM)",                    "ZAI_API_KEY",            "https://bigmodel.cn",                        "zai/glm-4-flash",                       ""),
    ("volcengine",   "Volcano Engine (Doubao)",        "VOLCANO_ENGINE_API_KEY", "https://console.volcengine.com",             "volcengine/doubao-pro-32k",              ""),
    ("venice",       "Venice AI",                     "VENICE_API_KEY",         "https://venice.ai",                          "venice/llama-3.3-70b",                  "Privacy-focused"),
    ("ollama",       "Ollama",                        None,                     None,                                         "ollama/llama3.3",                       "Local, free, no key needed"),
    ("custom",       "Custom (OpenAI-compatible)",    None,                     None,                                         "",                                      "LM Studio, vLLM, etc."),
]

OAUTH_PROVIDERS = {"qwen-portal", "openai-codex"}


# ── Curses picker ─────────────────────────────────────────────────────────────

def curses_pick(stdscr, title: str, items: list[str], search: bool = False) -> str | None:
    """Arrow-key + optional type-to-search picker. Returns selected item or None."""
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN, -1)
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN)

    query = ""
    cursor = 0
    scroll = 0

    while True:
        filtered = [x for x in items if query.lower() in x.lower()] if search else items
        if not filtered:
            filtered = ["(no matches)"]

        stdscr.erase()
        h, w = stdscr.getmaxyx()

        # Title
        stdscr.addstr(0, 0, title[:w-1], curses.A_BOLD)

        if search:
            stdscr.addstr(1, 0, f"  Search: {query}_"[:w-1], curses.color_pair(1))
            list_start = 2
        else:
            list_start = 1

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
            if idx == cursor:
                stdscr.addstr(y, 0, line, curses.color_pair(2))
            else:
                stdscr.addstr(y, 0, line)

        stdscr.addstr(h-1, 0, " ↑/↓ navigate  Enter select  Esc cancel"[:w-1], curses.A_DIM)
        stdscr.refresh()

        key = stdscr.getch()

        if key == curses.KEY_UP:
            cursor = max(0, cursor - 1)
        elif key == curses.KEY_DOWN:
            cursor = min(len(filtered) - 1, cursor + 1)
        elif key in (curses.KEY_ENTER, 10, 13):
            sel = filtered[cursor]
            return None if sel == "(no matches)" else sel
        elif key == 27:  # Esc
            return None
        elif search:
            if key in (curses.KEY_BACKSPACE, 127):
                query = query[:-1]
                cursor = 0
            elif 32 <= key <= 126:
                query += chr(key)
                cursor = 0


def pick(title: str, items: list[str], search: bool = False) -> str | None:
    return curses.wrapper(curses_pick, title, items, search)


# ── Provider model fetching ───────────────────────────────────────────────────

def fetch_models(provider_id: str, api_key: str) -> list[str]:
    """Fetch live model list from provider. Returns [] on failure."""
    import urllib.request, urllib.error, json as _json

    try:
        if provider_id == "openrouter":
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                data = _json.loads(r.read())
            return [f"openrouter/{m['id']}" for m in data.get("data", [])]

        elif provider_id == "groq":
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                data = _json.loads(r.read())
            return [f"groq/{m['id']}" for m in data.get("data", [])]

        elif provider_id == "ollama":
            with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5) as r:
                data = _json.loads(r.read())
            return [f"ollama/{m['name']}" for m in data.get("models", [])]

        elif provider_id == "openai":
            req = urllib.request.Request(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                data = _json.loads(r.read())
            return sorted([f"openai/{m['id']}" for m in data.get("data", []) if "gpt" in m["id"]])

    except Exception:
        pass
    return []


# ── Helpers ───────────────────────────────────────────────────────────────────

def cyan(s):   return f"\033[96m{s}\033[0m"
def green(s):  return f"\033[92m{s}\033[0m"
def yellow(s): return f"\033[93m{s}\033[0m"
def bold(s):   return f"\033[1m{s}\033[0m"
def dim(s):    return f"\033[2m{s}\033[0m"


def masked(key: str) -> str:
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


# ── Main flow ─────────────────────────────────────────────────────────────────

def run():
    print()
    print(bold("🌐 Sonder — Setup"))
    print(dim("Self-hosted social simulation engine"))
    print()

    # ── Step 1: pick provider ─────────────────────────────────────────────────
    provider_labels = []
    for pid, name, _, _, _, note in PROVIDERS:
        badge = f" {yellow('[free]')}" if note and "free" in note.lower() else ""
        note_str = f"  {dim(note)}" if note else ""
        provider_labels.append(f"{name}{badge}{note_str}")

    choice = pick("Select AI provider", provider_labels)
    if choice is None:
        print("Cancelled.")
        sys.exit(0)

    idx = provider_labels.index(choice)
    provider_id, provider_name, env_var, key_url, default_model, _ = PROVIDERS[idx]

    print(f"\n{cyan('▶')} {bold(provider_name)}")

    api_key = ""
    model = default_model
    base_url = ""

    # ── Step 2: auth ──────────────────────────────────────────────────────────
    if provider_id == "ollama":
        print(f"  {green('✓')} No API key needed — make sure Ollama is running.")

    elif provider_id == "custom":
        base_url = input("\n  Base URL (e.g. http://localhost:1234/v1): ").strip()
        pname = input("  Provider name (e.g. lmstudio): ").strip() or "custom"
        model_id = input("  Model ID: ").strip()
        model = f"{pname}/{model_id}"
        api_key = input("  API key (leave blank if not required): ").strip()

    else:
        if key_url:
            open_b = input(f"\n  Open {cyan(key_url)} in browser? [Y/n]: ").strip().lower()
            if open_b != "n":
                webbrowser.open(key_url)

        import getpass
        api_key = getpass.getpass(f"  Paste {provider_name} API key: ").strip()
        if not api_key:
            print("  No key entered. Exiting.")
            sys.exit(1)
        print(f"  Key: {dim(masked(api_key))}")

    # ── Step 3: pick model ────────────────────────────────────────────────────
    print(f"\n  Fetching models from {provider_name}…", end="", flush=True)
    models = fetch_models(provider_id, api_key)

    if models:
        print(f" {green(str(len(models)) + ' found')}")
        picked = pick(f"Select model ({provider_name})", models, search=True)
        model = picked if picked else default_model
    else:
        print(f" {dim('(could not fetch — enter manually)')}")
        model_input = input(f"  Model [{default_model}]: ").strip()
        model = model_input or default_model

    # ── Step 4: save ──────────────────────────────────────────────────────────
    from config import save_config
    updates: dict = {"model": model}

    if api_key and provider_id not in ("custom", "ollama"):
        updates["keys"] = {provider_id: api_key}
    elif provider_id == "custom" and base_url:
        pname = model.split("/")[0]
        updates["custom_providers"] = {
            pname: {"base_url": base_url, "api_key": api_key, "models": []}
        }

    save_config(updates)

    print(f"\n{green('✓')} Configured.")
    print(f"  Model : {cyan(model)}")
    print(f"\n  Start : {cyan('python main.py')}\n")


if __name__ == "__main__":
    run()
