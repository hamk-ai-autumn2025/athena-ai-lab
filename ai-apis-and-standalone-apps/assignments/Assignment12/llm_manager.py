"""
LLM Manager - Handles communication with different AI providers
"""

from typing import List, Dict
from config import MODELS, DEFAULT_MAX_TOKENS

# Import libraries conditionally
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None


class LLMManager:
    """Manages multiple LLM providers"""
    
    def __init__(self):
        self.models = MODELS
    
    def get_available_models(self) -> List[str]:
        """Return list of available models"""
        return [name for name, info in self.models.items() if info["available"]]
    
    def get_model_info(self, model_name: str) -> Dict:
        """Get information about a specific model"""
        return self.models.get(model_name, {})
    
    def chat_with_openai(self, messages: List[Dict], model: str, api_key: str, temperature: float = 0.7) -> str:
        """Chat with OpenAI models"""
        if OpenAI is None:
            return "Error: OpenAI library not installed"
        
        try:
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=DEFAULT_MAX_TOKENS
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"OpenAI Error: {str(e)}"
    
    def chat_with_anthropic(self, messages: List[Dict], model: str, api_key: str, temperature: float = 0.7) -> str:
        """Chat with Anthropic Claude models"""
        if Anthropic is None:
            return "Error: Anthropic library not installed"
        
        try:
            client = Anthropic(api_key=api_key)
            
            # Convert messages to Claude format
            system_message = ""
            claude_messages = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                else:
                    claude_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            
            kwargs = {
                "model": model,
                "max_tokens": DEFAULT_MAX_TOKENS,
                "temperature": temperature,
                "messages": claude_messages
            }
            
            if system_message:
                kwargs["system"] = system_message
            
            response = client.messages.create(**kwargs)
            return response.content[0].text
        except Exception as e:
            return f"Anthropic Error: {str(e)}"
    
    def chat_with_google(self, messages: List[Dict], model: str, api_key: str, temperature: float = 0.7) -> str:
        """Chat with Google Gemini models"""
        if genai is None:
            return "Error: Google Generative AI library not installed"
        
        try:
            genai.configure(api_key=api_key)
            model_instance = genai.GenerativeModel(model)
            
            # Convert messages to Gemini format
            prompt = "\n".join([
                f"{msg['role']}: {msg['content']}" 
                for msg in messages
            ])
            
            response = model_instance.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=DEFAULT_MAX_TOKENS
                )
            )
            return response.text
        except Exception as e:
            return f"Google Error: {str(e)}"
    
    def generate_response(self, model_name: str, messages: List[Dict], api_key: str, temperature: float = 0.7) -> str:
        """Generate response from selected model"""
        if model_name not in self.models:
            return "Error: Model not found"
        
        model_info = self.models[model_name]
        model = model_info["model"]
        provider = model_info["provider"]
        
        if provider == "openai":
            return self.chat_with_openai(messages, model, api_key, temperature)
        elif provider == "anthropic":
            return self.chat_with_anthropic(messages, model, api_key, temperature)
        elif provider == "google":
            return self.chat_with_google(messages, model, api_key, temperature)
        else:
            return "Error: Unknown provider"