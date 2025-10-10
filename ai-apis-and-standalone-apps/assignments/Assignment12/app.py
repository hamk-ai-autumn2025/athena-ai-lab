"""
Multi-LLM Chat Application
A modern web interface supporting multiple AI models
"""

import streamlit as st
import os
from pathlib import Path

# Import local modules
from llm_manager import LLMManager
from config import DEFAULT_TEMPERATURE, DEFAULT_SYSTEM_MESSAGE


# Page configuration
st.set_page_config(
    page_title="Multi-LLM Chat",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)


def load_css():
    """Load custom CSS from file"""
    css_file = Path(__file__).parent / "static" / "styles.css"
    
    if css_file.exists():
        with open(css_file) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        st.warning("⚠️ CSS file not found. Make sure static/styles.css exists.")


def render_sidebar(llm_manager: LLMManager):
    """Render the sidebar with settings"""
    with st.sidebar:
        st.header("⚙️ Settings")
        
        # Model selection
        available_models = llm_manager.get_available_models()
        
        if not available_models:
            st.error("⚠️ No LLM libraries installed!")
            st.info("Install with: pip install -r requirements.txt")
            return None, None, None, None
        
        selected_model = st.selectbox(
            "Select Model",
            available_models,
            help="Choose which AI model to chat with"
        )
        
        # Get model info
        model_info = llm_manager.get_model_info(selected_model)
        api_key_env = model_info["api_key_env"]
        
        # API Key input
        api_key = st.text_input(
            f"API Key ({api_key_env})",
            type="password",
            value=os.getenv(api_key_env, ""),
            help=f"Enter your API key or set {api_key_env} environment variable"
        )
        
        # Temperature slider
        temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=2.0,
            value=DEFAULT_TEMPERATURE,
            step=0.1,
            help="Higher values make output more random"
        )
        
        # System message
        system_message = st.text_area(
            "System Message (Optional)",
            value=DEFAULT_SYSTEM_MESSAGE,
            help="Set the behavior of the AI"
        )
        
        # Clear chat button
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
        
        # Info section
        st.markdown("---")
        st.markdown("### 📊 Model Info")
        st.markdown(f"**Provider:** {model_info.get('provider', 'Unknown').title()}")
        st.markdown(f"**Model:** `{model_info['model']}`")
        
        # Setup instructions
        st.markdown("---")
        st.markdown("### 📚 Quick Setup")
        st.markdown("""
        **Get API Keys:**
        - [OpenAI](https://platform.openai.com)
        - [Anthropic](https://console.anthropic.com)
        - [Google AI](https://makersuite.google.com)
        
        **Environment Variables:**
        ```bash
        export OPENAI_API_KEY="sk-..."
        export ANTHROPIC_API_KEY="sk-ant-..."
        export GOOGLE_API_KEY="AI..."
        ```
        """)
        
        return selected_model, api_key, temperature, system_message


def render_chat_message(role: str, content: str, model_name: str = ""):
    """Render a single chat message"""
    if role == "user":
        st.markdown(
            f'<div class="chat-message user-message">'
            f'<div class="message-header">👤 You</div>'
            f'<div>{content}</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<div class="chat-message assistant-message">'
            f'<div class="message-header">🤖 {model_name}</div>'
            f'<div>{content}</div>'
            f'</div>',
            unsafe_allow_html=True
        )


def main():
    """Main application logic"""
    # Load custom CSS
    load_css()
    
    # Title
    st.title("🤖 Multi-LLM Chat Interface")
    st.markdown("Chat with multiple AI models in one place!")
    
    # Initialize LLM manager
    llm_manager = LLMManager()
    
    # Render sidebar and get settings
    selected_model, api_key, temperature, system_message = render_sidebar(llm_manager)
    
    # Stop if no models available
    if selected_model is None:
        return
    
    # Initialize chat history in session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Display chat history
    for message in st.session_state.messages:
        render_chat_message(
            message["role"],
            message["content"],
            selected_model
        )
    
    # Chat input
    if prompt := st.chat_input("Type your message here..."):
        # Check for API key
        if not api_key:
            model_info = llm_manager.get_model_info(selected_model)
            st.error(f"⚠️ Please enter your {model_info['api_key_env']} in the sidebar!")
            return
        
        # Add user message to history
        st.session_state.messages.append({
            "role": "user",
            "content": prompt
        })
        
        # Display user message
        render_chat_message("user", prompt)
        
        # Prepare messages for API
        api_messages = []
        if system_message and system_message != DEFAULT_SYSTEM_MESSAGE:
            api_messages.append({
                "role": "system",
                "content": system_message
            })
        api_messages.extend(st.session_state.messages)
        
        # Generate response
        with st.spinner(f"🤔 {selected_model} is thinking..."):
            response = llm_manager.generate_response(
                selected_model,
                api_messages,
                api_key,
                temperature
            )
        
        # Add assistant response to history
        st.session_state.messages.append({
            "role": "assistant",
            "content": response
        })
        
        # Rerun to display the new message
        st.rerun()


if __name__ == "__main__":
    main()