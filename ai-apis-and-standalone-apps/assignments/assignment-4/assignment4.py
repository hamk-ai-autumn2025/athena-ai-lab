#Code created by Gemini 2.5 pro, temp 1

import os
import argparse
# We import 'App' differently to use a custom configuration
from embedchain import App
import sys

def main():
    """
    Main function to run the command-line utility.
    """
    # 1. Setup Command-Line Argument Parser (No changes here)
    parser = argparse.ArgumentParser(
        description="A command-line utility to query LLMs with various data sources.",
        epilog="Example: python assignment4.py https://en.wikipedia.org/wiki/Python_(programming_language) my_notes.txt -q \"When was Python first released?\""
    )

    parser.add_argument(
        "sources",
        nargs='+',
        help="One or more data sources (URL, pdf, docx, csv, or text file path)."
    )

    parser.add_argument(
        "-q", "--query",
        type=str,
        help="The query to ask the LLM. If not provided, the program will summarize the content."
    )

    parser.add_argument(
        "-o", "--output",
        type=str,
        help="File path to save the output. If not provided, the output is printed to the console."
    )

    args = parser.parse_args()

    # 2. Check for OpenAI API Key (No changes here)
    if not os.getenv("OPENAI_API_KEY"): #Use environment variable for API key -> If not set, exit with instructions
        print("Error: The OPENAI_API_KEY environment variable is not set.")
        print("Please set it before running the program.")
        sys.exit(1)

    # 3. Initialize Embedchain App with a specific model (THIS PART IS UPDATED)
    try:
        # Define the configuration to use the gpt-4o-mini model
        app_config = {
            'llm': {
                'provider': 'openai', #Change these to use somethign else than OpenAI
                'config': {
                    'model': 'gpt-4o-mini' #Here you can change the model to any other available OpenAI model
                }
            }
        }
        # Create the App instance from the configuration
        app = App.from_config(config=app_config)

        app.reset()  # Clear any existing data in the app -> RESETS DB
        print("Using model: gpt-4o-mini")

    except Exception as e:
        print(f"Error initializing the Embedchain App: {e}")
        sys.exit(1)


    # 4. Add all provided sources to the app's knowledge base (No changes here)
    print("Adding data sources...")
    for source in args.sources:
        try:
            print(f"-> Adding: {source}")
            app.add(source)
        except Exception as e:
            print(f"Warning: Could not add source '{source}'. Error: {e}")
            continue
    print("All sources processed.\n")

    # 5. Determine the query (No changes here)
    query_prompt = args.query if args.query else "Summarize the provided content in a comprehensive manner."

    print(f"Executing query: \"{query_prompt}\"")
    
    # 6. Run the query (No changes here)
    try:
        result = app.query(query_prompt)
    except Exception as e:
        print(f"An error occurred while executing the query: {e}")
        sys.exit(1)


    # 7. Handle the output (No changes here)
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"\n✅ Output successfully saved to: {args.output}")
        except IOError as e:
            print(f"Error writing to file {args.output}: {e}")
            sys.exit(1)
    else:
        print("\n--- Result ---")
        print(result)
        print("--------------")

if __name__ == "__main__":
    main()