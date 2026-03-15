"""
onboard.py — CLI onboarding wizard for Sonder.
Run: python onboard.py
"""
import sys
import webbrowser

PROVIDERS = [
    ("openrouter", "OpenRouter",  "OPENROUTER_API_KEY", "https://openrouter.ai/keys",
     "openrouter/qwen/qwen-2.5-72b-instruct", "Free models available (Qwen, Llama, Mistral, etc.)"),
    ("anthropic",  "Anthropic",   "ANTHROPIC_API_KEY",  "https://console.anthropic.com/keys",
     "anthropic/claude-sonnet-4-5", ""),
    ("openai",     "OpenAI",      "OPENAI_API_KEY",     "https://platform.openai.com/api-keys",
     "openai/gpt-4o", ""),
    ("groq",       "Groq",        "GROQ_API_KEY",       "https://console.groq.com/keys",
     "groq/llama-3.1-70b-versatile", "Fast, free tier available"),
    ("gemini",     "Google Gemini","GEMINI_API_KEY",    "https://aistudio.google.com/apikey",
     "gemini/gemini-2.0-flash", "Free tier available"),
    ("mistral",    "Mistral",     "MISTRAL_API_KEY",    "https://console.mistral.ai/api-keys",
     "mistral/mistral-large-latest", ""),
    ("ollama",     "Ollama",      None,                 "https://ollama.com/download",
     "ollama/llama3.3", "Local, free, no API key needed"),
    ("custom",     "Custom (OpenAI-compatible)", None, None, "", "LM Studio, vLLM, etc."),
]


def cyan(s):  return f"\033[96m{s}\033[0m"
def green(s): return f"\033[92m{s}\033[0m"
def bold(s):  return f"\033[1m{s}\033[0m"
def dim(s):   return f"\033[2m{s}\033[0m"


def run():
    print()
    print(bold("🌐 Welcome to Sonder"))
    print(dim("Self-hosted social simulation engine"))
    print()
    print("Choose your AI provider:\n")

    for i, (pid, name, _, _, default_model, note) in enumerate(PROVIDERS, 1):
        note_str = f"  {dim(note)}" if note else ""
        print(f"  {cyan(str(i))}. {name}{note_str}")

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

    if provider_id == "ollama":
        print(f"\n{green('✓')} Ollama selected — no API key needed.")
        print(f"  Make sure Ollama is running: {cyan('ollama serve')}")
        model_input = input(f"\nModel [{default_model}]: ").strip()
        model = model_input or default_model

    elif provider_id == "custom":
        base_url = input("\nBase URL (e.g. http://localhost:1234/v1): ").strip()
        model_id = input("Model ID: ").strip()
        provider_name_custom = input("Provider name (e.g. lmstudio): ").strip() or "custom"
        model = f"{provider_name_custom}/{model_id}"
        api_key = input("API key (leave blank if not required): ").strip()

    else:
        print(f"\nGet your {provider_name} API key at:")
        print(f"  {cyan(key_url)}")
        open_browser = input("\nOpen in browser? [Y/n]: ").strip().lower()
        if open_browser != "n":
            webbrowser.open(key_url)

        api_key = input(f"\nPaste your {provider_name} API key: ").strip()
        if not api_key:
            print("No key entered. Exiting.")
            sys.exit(1)

        model_input = input(f"Model [{default_model}]: ").strip()
        model = model_input or default_model

    # Save config
    from config import save_config, BUILTIN_PROVIDERS
    updates: dict = {"model": model}

    if api_key and provider_id not in ("custom", "ollama"):
        updates["keys"] = {provider_id: api_key}
    elif api_key and provider_id == "custom":
        # Write custom provider
        pname = model.split("/")[0]
        updates["custom_providers"] = {
            pname: {"base_url": base_url, "api_key": api_key, "models": []}
        }

    save_config(updates)

    print(f"\n{green('✓')} Sonder configured.")
    print(f"  Model: {cyan(model)}")
    print(f"\nStart Sonder with: {cyan('python main.py')}")
    print()


if __name__ == "__main__":
    run()
