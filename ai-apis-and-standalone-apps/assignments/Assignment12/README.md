# Multi-LLM Chat Application

A modern, multi-model chat interface built with Streamlit that supports OpenAI, Anthropic, and Google AI models.

## 📁 Project Structure

```
multi-llm-chat/
├── app.py                  # Main application file
├── llm_manager.py          # LLM provider management
├── config.py               # Configuration and model definitions
├── requirements.txt        # Python dependencies
├── static/
│   └── styles.css         # Custom CSS styling
└── README.md              # This file
```

## 🚀 Setup

1. **Clone or download the project**

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Set up API keys** (at least one):
   - **OpenAI**: https://platform.openai.com/api-keys
   - **Anthropic**: https://console.anthropic.com/
   - **Google**: https://makersuite.google.com/app/apikey

4. **Run the application:**
```bash
streamlit run app.py
```

## 🎨 Features

- Support for 12+ AI models across 3 providers
- Modern, theme-adaptive UI (light/dark mode)
- Customizable temperature settings
- System message configuration
- Persistent chat history
- Clean project structure

## 🤖 Supported Models

**OpenAI:**
- GPT-4o, GPT-4o Mini, GPT-4 Turbo, GPT-4, GPT-3.5 Turbo

**Anthropic:**
- Claude 3.5 Sonnet, Claude 3 Opus, Claude 3 Sonnet, Claude 3 Haiku

**Google:**
- Gemini 1.5 Pro, Gemini 1.5 Flash, Gemini Pro

## 📝 Usage

1. Select a model from the sidebar
2. Enter your API key (or set as environment variable)
3. Adjust settings (temperature, system message)
4. Start chatting!

## 🔑 Environment Variables (Optional)

Set these to avoid entering API keys each time:

```bash
export OPENAI_API_KEY="your-key-here"
export ANTHROPIC_API_KEY="your-key-here"
export GOOGLE_API_KEY="your-key-here"
```

## 📄 License

MIT License - Feel free to use and modify!