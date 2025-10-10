"""
Configuration file for Multi-LLM Chat Application
Contains model definitions and settings
"""

# Check available libraries
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import google.generativeai as genai
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False


# Model configurations
MODELS = {
    "OpenAI GPT-4o": {
        "available": OPENAI_AVAILABLE,
        "model": "gpt-4o",
        "api_key_env": "OPENAI_API_KEY",
        "provider": "openai"
    },
    "OpenAI GPT-4o Mini": {
        "available": OPENAI_AVAILABLE,
        "model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
        "provider": "openai"
    },
    "OpenAI GPT-4 Turbo": {
        "available": OPENAI_AVAILABLE,
        "model": "gpt-4-turbo-preview",
        "api_key_env": "OPENAI_API_KEY",
        "provider": "openai"
    },
    "OpenAI GPT-4": {
        "available": OPENAI_AVAILABLE,
        "model": "gpt-4",
        "api_key_env": "OPENAI_API_KEY",
        "provider": "openai"
    },
    "OpenAI GPT-3.5 Turbo": {
        "available": OPENAI_AVAILABLE,
        "model": "gpt-3.5-turbo",
        "api_key_env": "OPENAI_API_KEY",
        "provider": "openai"
    },
    "Claude 3.5 Sonnet": {
        "available": ANTHROPIC_AVAILABLE,
        "model": "claude-3-5-sonnet-20241022",
        "api_key_env": "ANTHROPIC_API_KEY",
        "provider": "anthropic"
    },
    "Claude 3 Opus": {
        "available": ANTHROPIC_AVAILABLE,
        "model": "claude-3-opus-20240229",
        "api_key_env": "ANTHROPIC_API_KEY",
        "provider": "anthropic"
    },
    "Claude 3 Sonnet": {
        "available": ANTHROPIC_AVAILABLE,
        "model": "claude-3-sonnet-20240229",
        "api_key_env": "ANTHROPIC_API_KEY",
        "provider": "anthropic"
    },
    "Claude 3 Haiku": {
        "available": ANTHROPIC_AVAILABLE,
        "model": "claude-3-haiku-20240307",
        "api_key_env": "ANTHROPIC_API_KEY",
        "provider": "anthropic"
    },
    "Google Gemini 1.5 Pro": {
        "available": GOOGLE_AVAILABLE,
        "model": "gemini-1.5-pro",
        "api_key_env": "GOOGLE_API_KEY",
        "provider": "google"
    },
    "Google Gemini 1.5 Flash": {
        "available": GOOGLE_AVAILABLE,
        "model": "gemini-1.5-flash",
        "api_key_env": "GOOGLE_API_KEY",
        "provider": "google"
    },
    "Google Gemini Pro": {
        "available": GOOGLE_AVAILABLE,
        "model": "gemini-pro",
        "api_key_env": "GOOGLE_API_KEY",
        "provider": "google"
    }
}

# Default settings
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 2000
DEFAULT_SYSTEM_MESSAGE = "You are a helpful assistant."