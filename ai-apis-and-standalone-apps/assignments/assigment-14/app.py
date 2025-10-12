import streamlit as st
import os
import google.generativeai as genai
from dotenv import load_dotenv
from gnews import GNews
from newspaper import Article, ArticleException
import datetime

# --- Configuration ---
load_dotenv()

try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    GEMINI_MODEL = genai.GenerativeModel('gemini-2.5-flash')
except Exception as e:
    st.error(f"Error configuring Google AI: {e}. Is your API key set correctly in the .env file?")
    st.stop()

# --- Helper Functions ---
def get_time_period(period_string):
    if period_string == "Today": return '1d'
    elif period_string == "Last Week": return '7d'
    elif period_string == "Last Month": return '30d'
    elif period_string == "Last Year": return '1y'
    return None

def fetch_news(query, time_period):
    try:
        google_news = GNews(language='en', country='US', period=time_period)
        articles = google_news.get_news(query)
        return articles[:5]
    except Exception as e:
        st.error(f"Failed to fetch news: {e}")
        return []

# Tiivistysfunktio, joka yrittää hakea koko artikkelin tekstin newspaper3k:lla
def get_and_summarize_article(article_data):
    """
    Tämä funktio yrittää ensin hakea koko artikkelin tekstin newspaper3k:lla.
    Jos se epäonnistuu, se tiivistää gnewsin antaman lyhyen kuvauksen.
    """
    url = article_data['url']
    summary_source = "full article" # Seurataan, mistä lähteestä tiivistelmä tehtiin

    try:
        # Yritetään ensin newspaper3k-kirjastolla
        article = Article(url)
        article.download()
        article.parse()
        article_text = article.text
        
        # Jos tekstiä on liian vähän, käytetään gnewsin kuvausta
        if len(article_text) < 200:
            article_text = article_data['description']
            summary_source = "short description"

    except ArticleException:
        # Jos newspaper3k epäonnistuu, käytetään suoraan gnewsin kuvausta
        article_text = article_data['description']
        summary_source = "short description"

    # Jos artikkelin teksti on liian lyhyt, palautetaan ilmoitus
    if not article_text or len(article_text.strip()) < 50:
        return "Could not retrieve enough content to summarize.", "N/A"

    # Luodaan prompti ja pyydetään tiivistelmää Geminiltä
    prompt = f"""
    Based on the following news article, please provide a concise summary in 3-4 bullet points.
    Focus on the key facts, figures, and outcomes.

    ARTICLE:
    {article_text}

    SUMMARY:
    """
    try:
        response = GEMINI_MODEL.generate_content(prompt)
        return response.text, summary_source
    except Exception as e:
        return f"Error during summarization: {e}", "Error"


# --- Streamlit Web App Interface ---
st.set_page_config(page_title="News Search & Summarizer", layout="wide")

st.title("📰 AI-Powered News Search & Summarizer")
st.markdown("Enter a topic and select a time period to get the latest news summarized for you.")

search_term = st.text_input("Enter a search term or category (e.g., 'Artificial Intelligence', 'Ukraine'):", "Technology")
time_period_option = st.selectbox(
    "Select the time period:",
    ("Today", "Last Week", "Last Month", "Last Year")
)

if st.button("Search & Summarize"):
    if not search_term:
        st.warning("Please enter a search term.")
    else:
        period = get_time_period(time_period_option)
        
        with st.spinner(f"Searching for news about '{search_term}'..."):
            news_articles = fetch_news(search_term, period)

        if not news_articles:
            st.warning(f"No articles found for '{search_term}'. Please try another topic.")
        else:
            st.success(f"Found {len(news_articles)} articles. Now summarizing...")
            
            for article_data in news_articles:
                st.subheader(f"📄 {article_data['title']}")
                st.markdown(f"**Source:** {article_data['publisher']['title']} | [Read Full Article]({article_data['url']})")

                # Placeholder tiivistelmälle
                summary_placeholder = st.empty()
                with st.spinner("Generating summary..."):
                    summary, source = get_and_summarize_article(article_data)
                    
                    # Näytetään käyttäjälle, perustuuko tiivistelmä koko artikkeliin vai lyhyeen kuvaukseen
                    if source == "full article":
                        info_text = "**Summary (from full article):**"
                    else:
                        info_text = "**Summary (from short description):**"

                    summary_placeholder.info(f"{info_text}\n{summary}")
                
                st.divider()