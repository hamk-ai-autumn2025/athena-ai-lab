"""
Ensimmäinen yksinkertainen versio, joka käyttää GPT4.1

Scientific Paper Generator
==========================
Generates academic papers using OpenAI GPT and converts them to PDF.

Requirements:
------------
pip install openai markdown-pdf python-dotenv

Setup:
------
1. Create a .env file in the same directory with your OpenAI API key:
    OPENAI_API_KEY=your_api_key_here
2. Run: python scientific_paper_write.py
3. Enter the paper topic when prompted
4. PDF will be saved in the same directory

Author: Generated with GitHub Copilot
"""

import os
import time
from pathlib import Path
from typing import Optional
import logging

from openai import OpenAI
from markdown_pdf import MarkdownPdf, Section
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Luo OpenAI-client (vaatii OPENAI_API_KEY ympäristömuuttujan)
client = OpenAI()

# 1. Käyttäjän syöte
topic = input("Anna artikkelin aihe: ")

# 2. Prompti GPT:lle

system_prompt = """
You are a scientific article generator. 
Structure the article with Abstract, Introduction, Chapters, Subchapters, and Conclusion. 
Include relevant figures and tables where appropriate.
Do not include any personal opinions or subjective statements.
Use formal academic language.
Generate a comprehensive scientific article of approximately 7000 tokens with the following structure and requirements:

**STRUCTURE:**
1. **Title**: Clear, specific, and informative
2. **Abstract** (200-250 words): Concise summary including background, methods, key findings, and conclusions
3. **Keywords**: 5-7 relevant academic keywords
4. **Introduction** (800-1000 words): 
    - Background and context
    - Literature review with current state of knowledge
    - Research gap identification
    - Clear research question/hypothesis
    - Study objectives and significance
5. **Literature Review** (1200-1500 words):
    - Comprehensive review of relevant studies
    - Theoretical framework
    - Identification of knowledge gaps
6. **Methodology** (800-1000 words):
    - Research design and approach
    - Data collection methods
    - Sample size and selection criteria
    - Data analysis procedures
    - Limitations and ethical considerations
7. **Results** (1000-1200 words):
    - Present findings clearly and objectively
    - Include statistical analysis where relevant
    - Reference to tables and figures
8. **Discussion** (1200-1500 words):
    - Interpretation of results
    - Comparison with existing literature
    - Implications and practical applications
    - Study limitations
    - Future research directions
9. **Conclusion** (300-400 words): Summary of key findings and their significance
10. **References**: Minimum 20 academic sources in APA 7 format

**CONTENT REQUIREMENTS:**
- Use formal, objective academic language
- Include relevant statistical data and research findings
- Incorporate 2-3 tables with data
- Reference 2-3 figures/charts (describe them in text)
- Maintain logical flow and coherence
- Use present tense for general statements, past tense for specific studies
- Include transitional phrases between sections
- Ensure claims are supported by evidence
- Use third person perspective throughout

**QUALITY STANDARDS:**
- Original content with no plagiarism
- Scientifically accurate information
- Proper use of academic terminology
- Clear and concise writing
- Evidence-based arguments
- Balanced presentation of different viewpoints where applicable
Add APA 7 style in-text citations and a reference list.
Respond directly without any preamble. Use markdown formatting.
"""

response = client.chat.completions.create(
    model="gpt-4.1",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Generate an article about: {topic}"}
    ]
)

article_md = response.choices[0].message.content

# 3. Tallennetaan PDF samaan kansioon kuin tämä skripti
script_dir = os.path.dirname(os.path.abspath(__file__))
#Lisätty timestamp tiedoston nimeen -> estää ylikirjoitukset
timestamp = time.strftime("%Y%m%d_%H%M%S")
pdf_filename = f"scientific_article_{topic.replace(' ', '_')}_{timestamp}.pdf"
pdf_path = os.path.join(script_dir, pdf_filename)

# 4. Muunna markdown → PDF
pdf = MarkdownPdf()
pdf.add_section(Section(article_md, toc=False))
pdf.save(pdf_path)

print(f"PDF valmis: {pdf_path}")
