"""
onboard.py — CLI onboarding wizard for Sonder.
Run: python onboard.py
"""
import sys
import webbrowser

# (id, display_name, env_var, key_url, default_model, note)
PROVIDERS = [
    ("qwen-portal",   "Qwen (free OAuth — no API key)",    None,                    "https://qianwen.aliyun.com",                  "qwen-portal/coder-model",                    "Free via browser login"),
    ("openrouter",    "OpenRouter",                         "OPENROUTER_API_KEY",    "https://openrouter.ai/keys",                  "openrouter/qwen/qwen-2.5-72b-instruct",      "Many free models"),
    ("openai-codex",  "OpenAI Codex (ChatGPT OAuth)",       None,                    "https://chatgpt.com",                         "openai-codex/gpt-4o",                        "Free via ChatGPT subscription"),
    ("anthropic",     "Anthropic",                          "ANTHROPIC_API_KEY",     "https://console.anthropic.com/keys",          "anthropic/claude-sonnet-4-5",                ""),
    ("openai",        "OpenAI",                             "OPENAI_API_KEY",        "https://platform.openai.com/api-keys",        "openai/gpt-4o",                              ""),
    ("groq",          "Groq",                               "GROQ_API_KEY",          "https://console.groq.com/keys",               "groq/llama-3.1-70b-versatile",               "Fast, free tier"),
    ("gemini",        "Google Gemini",                      "GEMINI_API_KEY",        "https://aistudio.google.com/apikey",          "gemini/gemini-2.0-flash",                    "Free tier"),
    ("mistral",       "Mistral AI",                         "MISTRAL_API_KEY",       "https://console.mistral.ai/api-keys",         "mistral/mistral-large-latest",               ""),
    ("xai",           "xAI (Grok)",                         "XAI_API_KEY",           "https://console.x.ai",                        "xai/grok-2-latest",                          ""),
    ("together",      "Together AI",                        "TOGETHER_API_KEY",      "https://api.together.xyz/settings/api-keys",  "together/meta-llama/Llama-3-70b-chat-hf",    "Free tier"),
    ("huggingface",   "Hugging Face",                       "HUGGINGFACE_HUB_TOKEN", "https://huggingface.co/settings/tokens",      "huggingface/meta-llama/Llama-3.1-70B",       ""),
    ("moonshot",      "Moonshot AI (Kimi)",                 "MOONSHOT_API_KEY",      "https://platform.moonshot.cn",                "moonshot/kimi-k2.5",                         ""),
    ("minimax",       "MiniMax",                            "MINIMAX_API_KEY",       "https://platform.minimaxi.com",               "minimax/MiniMax-M2.5",                       ""),
    ("zai",           "Z.AI (GLM)",                         "ZAI_API_KEY",           "https://bigmodel.cn",                         "zai/glm-5",                                  ""),
    ("volcengine",    "Volcano Engine (Doubao)",             "VOLCANO_ENGINE_API_KEY","https://console.volcengine.com",              "volcengine/doubao-seed-1-8-251228",           ""),
    ("venice",        "Venice AI",                          "VENICE_API_KEY",        "https://venice.ai",                           "venice/llama-3.3-70b",                        "Privacy-focused"),
    ("ollama",        "Ollama",                             None,                    "https://ollama.com/download",                 "ollama/llama3.3",                            "Local, free, no key needed"),
    ("custom",        "Custom (OpenAI-compatible)",         None,                    None,                                          "",                                           "LM Studio, vLLM, LiteLLM, etc."),
]

OAUTH_PROVIDERS = {"qwen-portal", "openai-codex"}


def cyan(s):  return f"\033[96m{s}\033[0m"
def green(s): return f"\033[92m{s}\033[0m"
def bold(s):  return f"\033[1m{s}\033[0m"
def dim(s):   return f"\033[2m{s}\033[0m"
def yellow(s):return f"\033[93m{s}\033[0m"


def run():
    print()
    print(bold("🌐 Sonder — Onboarding"))
    print(dim("Self-hosted social simulation engine"))
    print()
    print("Choose your AI provider:\n")

    for i, (pid, name, _, _, _, note) in enumerate(PROVIDERS, 1):
        note_str = f"  {dim(note)}" if note else ""
        free_badge = f" {yellow('[free]')}" if "free" in note.lower() else ""
        print(f"  {cyan(str(i).rjust(2))}. {name}{free_badge}{note_str}")

    print()
    choice = input("Enter number: ").strip()

    try:
        idx = int(choice) - 1
        provider_id, provider_name, env_var, key_url, default_model, _ = PROVIDERS[idx]
    except (ValueError, IndexError):
        print("Invalid choice.")
        sys.exit(1)

    api_key = ""
    model = default_model
    base_url = ""

    # ── OAuth providers (browser login, no API key) ──────────────────────────
    if provider_id in OAUTH_PROVIDERS:
        print(f"\n{yellow('→')} {provider_name} uses browser-based login.")
        print(f"  Opening: {cyan(key_url)}")
        input("  Press Enter to open browser…")
        webbrowser.open(key_url)
        print(f"\n{dim('After logging in, Sonder will use your session via the provider portal.')}")
        print(f"{yellow('Note:')} OAuth token storage for {provider_name} is not yet implemented.")
        print(f"      For now, use OpenRouter or an API key provider.")
        input("\nPress Enter to go back and choose another provider…")
        run()
        return

    # ── Ollama ───────────────────────────────────────────────────────────────
    elif provider_id == "ollama":
        print(f"\n{green('✓')} Ollama — no API key needed.")
        print(f"  Make sure Ollama is running: {cyan('ollama serve')}")
        model_input = input(f"\nModel [{default_model}]: ").strip()
        model = model_input or default_model

    # ── Custom provider ──────────────────────────────────────────────────────
    elif provider_id == "custom":
        base_url = input("\nBase URL (e.g. http://localhost:1234/v1): ").strip()
        model_id = input("Model ID: ").strip()
        pname = input("Provider name (e.g. lmstudio): ").strip() or "custom"
        model = f"{pname}/{model_id}"
        api_key = input("API key (leave blank if not required): ").strip()

    # ── API key providers ────────────────────────────────────────────────────
    else:
        print(f"\nGet your {provider_name} API key:")
        print(f"  {cyan(key_url)}")
        open_b = input("Open in browser? [Y/n]: ").strip().lower()
        if open_b != "n":
            webbrowser.open(key_url)

        api_key = input(f"\nPaste {provider_name} API key: ").strip()
        if not api_key:
            print("No key entered. Exiting.")
            sys.exit(1)

        model_input = input(f"Model [{default_model}]: ").strip()
        model = model_input or default_model

    # ── Save ─────────────────────────────────────────────────────────────────
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

    print(f"\n{green('✓')} Sonder configured.")
    print(f"  Model : {cyan(model)}")
    print(f"\nStart with: {cyan('python main.py')}")
    print()


if __name__ == "__main__":
    run()
