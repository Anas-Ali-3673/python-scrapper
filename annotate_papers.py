import os
import json
import csv
import requests
from time import sleep
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Constants
INPUT_CSV = "D:/scraped-pdfs/metadata.csv"  # Path to the scraped dataset
OUTPUT_JSON = "D:/scraped-pdfs/annotated_papers.json"  # Path to save annotated dataset
HF_API_KEY = os.getenv("HF_API_KEY")  # Get Hugging Face API key from environment variable
HF_API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-mnli"

# Define the five annotation labels
LABELS = [
    "Deep Learning",
    "Computer Vision",
    "Reinforcement Learning",
    "Natural Language Processing (NLP)",
    "Optimization"
]

def classify_paper(title, abstract):
    """
    Uses Hugging Face's zero-shot classification model to classify a paper into one of the predefined categories.
    """
    try:
        text = f"{title}. {abstract}"  # Combine title and abstract
        payload = {
            "inputs": text,
            "parameters": {
                "candidate_labels": LABELS,
                "multi_label": False  # Only one label per paper
            }
        }

        headers = {"Authorization": f"Bearer {HF_API_KEY}"}
        response = requests.post(HF_API_URL, headers=headers, json=payload)
        response.raise_for_status()

        result = response.json()
        predicted_label = result["labels"][0]  # Get the highest confidence label
        return predicted_label
    except Exception as e:
        print(f"❌ Error classifying paper: {e}")
        return "Unknown"

def annotate_papers():
    """
    Annotates the scraped papers using the Hugging Face API and saves in JSON format.
    """
    if not os.path.exists(INPUT_CSV):
        print(f"❌ Input CSV file not found: {INPUT_CSV}")
        return

    annotated_papers = []
    with open(INPUT_CSV, "r", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            title = row.get("title", "")
            abstract = row.get("abstract", "")
            url = row.get("url", "")
            year = row.get("year", "")

            print(f"🔍 Classifying: {title}")
            label = classify_paper(title, abstract)
            print(f"✅ Assigned label: {label}")

            # Create a JSON-like structure for each paper
            paper_entry = {
                "title": title,
                "url": url,
                "year": year,
                "abstract": abstract,
                "label": label
            }
            annotated_papers.append(paper_entry)

            sleep(3)  # To avoid rate limits

    # Save the annotated dataset in JSON format
    with open(OUTPUT_JSON, "w", encoding="utf-8") as jsonfile:
        json.dump(annotated_papers, jsonfile, indent=4, ensure_ascii=False)

    print(f"✅ Annotations saved to: {OUTPUT_JSON}")

if __name__ == "__main__":
    annotate_papers()