#!/usr/bin/env python3
# Filename: dictionary_app.py

import sys
import os
import json
import argparse
import google.generativeai as genai

def generate_dictionary_entry(word: str, api_key: str):
    """
    Generates a dictionary entry for a given word using the Gemini API.
    Outputs only the JSON to stdout.
    """
    if not api_key:
        error_msg = {"error": "GOOGLE_API_KEY environment variable not set."}
        print(json.dumps(error_msg, indent=4), file=sys.stderr)
        sys.exit(1)

    try:
        genai.configure(api_key=api_key)

        generation_config = {
            "temperature": 0.3,
            "response_mime_type": "application/json",
        }
        #Mallin määritys
        model = genai.GenerativeModel(
            model_name="models/gemini-pro-latest",
            generation_config=generation_config,
        )

        #*AI-prompti*
        prompt = f"""
        Generate a dictionary entry for the word: '{word}'.
        The output must be a single, valid JSON object with the following keys:
        - "word": The word itself, possibly in its base form.
        - "definition": A concise definition. If multiple meanings exist, provide the primary one.
        - "synonyms": A JSON array of strings containing common synonyms. If none, return an empty array [].
        - "antonyms": A JSON array of strings containing common antonyms. If none, return an empty array [].
        - "examples": A JSON array of strings, with each string being a sentence demonstrating the word's usage.
        Adapt the language of the definition, synonyms, antonyms, and examples to the language of the input word.
        """

        response = model.generate_content(prompt)
        json_data = json.loads(response.text)
        print(json.dumps(json_data, indent=4, ensure_ascii=False))

    except Exception as e:
        error_msg = {"error": f"An unexpected error occurred: {str(e)}"}
        print(json.dumps(error_msg, indent=4), file=sys.stderr)
        sys.exit(1)

def main():
    """
    Parses command-line arguments and executes the main logic.
    """
    parser = argparse.ArgumentParser(
        description="Generates a JSON dictionary entry for a word using the Gemini API.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("word", type=str, help="The word to look up.")

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()
    api_key = os.getenv("GOOGLE_API_KEY")
    generate_dictionary_entry(args.word, api_key)

if __name__ == "__main__":
    main()