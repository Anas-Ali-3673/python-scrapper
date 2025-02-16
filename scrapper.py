import os
import time
import logging
import requests
import csv
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import customtkinter as ctk
from tkinter import messagebox
import threading
import queue

# Constants
BASE_URL = "https://papers.nips.cc/paper_files/paper"
OUTPUT_DIR = "D:/scraped-pdfs"
METADATA_FILE = os.path.join(OUTPUT_DIR, "metadata.csv")
THREAD_COUNT = 5 

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Global variables for UI updates
total_papers = 0
downloaded_papers = 0
is_scraping = False  # To track if scraping is in progress
log_queue = queue.Queue()  # Queue for thread-safe logging

# CustomTkinter Settings
ctk.set_appearance_mode("dark")  # Dark mode
ctk.set_default_color_theme("blue")  # Blue theme

def get_paper_links(year):
    """Extracts paper abstract links for a given year."""
    url = f"{BASE_URL}/{year}"
    logging.info(f"Fetching paper links from: {url}")

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for failed requests
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract paper links
        paper_links = []
        for a in soup.select("a[href*='-Abstract.html']"):
            paper_links.append("https://papers.nips.cc" + a["href"])
        
        logging.info(f"Found {len(paper_links)} papers for {year}")
        return paper_links
    except requests.RequestException as e:
        logging.error(f"❌ Error fetching paper links: {e}")
        return []

def fetch_metadata(paper_url):
    """Fetches metadata (title, authors) from the paper abstract page."""
    try:
        response = requests.get(paper_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract title
        title = soup.select_one("h4").text.strip() if soup.select_one("h4") else "No Title"

        # Extract authors
        authors = []
        author_elements = soup.select("h4 + p")
        if author_elements:
            authors = [author.text.strip() for author in author_elements[0].select("a")]

        return {
            "title": title,
            "authors": ", ".join(authors),
            "url": paper_url
        }
    except requests.RequestException as e:
        logging.error(f"❌ Error fetching metadata from {paper_url}: {e}")
        return None

def download_pdf(paper_url, metadata):
    """Downloads a paper PDF and saves its metadata."""
    global downloaded_papers
    try:
        response = requests.get(paper_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Find the direct PDF link
        pdf_link = soup.select_one("a[href$='.pdf']")
        if not pdf_link:
            log_queue.put(f"⚠️ No PDF found for: {paper_url}")
            return

        pdf_url = "https://papers.nips.cc" + pdf_link["href"]
        pdf_name = pdf_url.split("/")[-1]
        pdf_path = os.path.join(OUTPUT_DIR, pdf_name)

        # Download the PDF
        log_queue.put(f"📥 Downloading: {pdf_name}")
        pdf_response = requests.get(pdf_url, stream=True)
        with open(pdf_path, "wb") as pdf_file:
            for chunk in pdf_response.iter_content(chunk_size=1024):
                pdf_file.write(chunk)

        log_queue.put(f"✅ Saved: {pdf_path}")

        # Save metadata to CSV
        metadata["pdf_path"] = pdf_path
        with open(METADATA_FILE, "a", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=["title", "authors", "url", "pdf_path"])
            if csvfile.tell() == 0:  # Write header only if file is empty
                writer.writeheader()
            writer.writerow(metadata)

        # Update downloaded papers count
        downloaded_papers += 1
        log_queue.put(f"Downloaded {downloaded_papers}/{total_papers} papers")
        app.after(0, update_progress)  # Schedule UI update on the main thread

    except requests.RequestException as e:
        log_queue.put(f"❌ Error downloading {paper_url}: {e}")

def start_scraping():
    """Main function to scrape and download PDFs with metadata."""
    global total_papers, downloaded_papers, is_scraping
    downloaded_papers = 0

    start_year = int(start_year_entry.get())
    end_year = int(end_year_entry.get())

    if start_year < 1987 or end_year > 2025 or start_year > end_year:
        messagebox.showerror("Error", "❌ Invalid year range. Please enter a range between 1987 and 2025.")
        return

    # Initialize metadata CSV file
    if not os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=["title", "authors", "url", "pdf_path"])
            writer.writeheader()

    # Clear log and reset progress bar
    log_area.delete(1.0, ctk.END)
    progress_bar.set(0)
    total_papers = 0

    # Disable the start button to prevent multiple clicks
    start_button.configure(state="disabled")
    is_scraping = True

    # Run the scraping process in a separate thread
    threading.Thread(target=scrape_papers, args=(start_year, end_year), daemon=True).start()

def scrape_papers(start_year, end_year):
    """Scrapes papers in the given year range."""
    global total_papers, downloaded_papers, is_scraping

    for year in range(start_year, end_year + 1):
        # Get abstract links
        paper_links = get_paper_links(year)
        total_papers += len(paper_links)

        # Fetch metadata and download PDFs using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=THREAD_COUNT) as executor:
            futures = []
            for paper_url in paper_links:
                metadata = fetch_metadata(paper_url)
                if metadata:
                    futures.append(executor.submit(download_pdf, paper_url, metadata))

            # Wait for all futures to complete
            for future in as_completed(futures):
                future.result()  # Handle any exceptions raised in the threads

    # Re-enable the start button after scraping is complete
    is_scraping = False
    app.after(0, lambda: start_button.configure(state="normal"))

def update_progress():
    """Updates the progress bar and log area."""
    while not log_queue.empty():
        log_message = log_queue.get()
        log_area.insert(ctk.END, log_message + "\n")
        log_area.see(ctk.END)  # Auto-scroll to the latest log

    progress = (downloaded_papers / total_papers) * 100
    progress_bar.set(progress / 100)  # Progress bar expects a value between 0 and 1

    if downloaded_papers == total_papers:
        messagebox.showinfo("Success", "✅ All papers downloaded successfully!")

    # Schedule the next update
    if is_scraping:
        app.after(100, update_progress)

# CustomTkinter UI Setup
app = ctk.CTk()
app.title("NeurIPS Paper Scraper")
app.geometry("800x600")

# Year Range Input
year_frame = ctk.CTkFrame(app)
year_frame.pack(pady=20)

ctk.CTkLabel(year_frame, text="Start Year:").grid(row=0, column=0, padx=5, pady=5)
start_year_entry = ctk.CTkEntry(year_frame)
start_year_entry.grid(row=0, column=1, padx=5, pady=5)

ctk.CTkLabel(year_frame, text="End Year:").grid(row=0, column=2, padx=5, pady=5)
end_year_entry = ctk.CTkEntry(year_frame)
end_year_entry.grid(row=0, column=3, padx=5, pady=5)

# Start Button
start_button = ctk.CTkButton(app, text="Start Scraping", command=start_scraping)
start_button.pack(pady=10)

# Progress Bar
progress_bar = ctk.CTkProgressBar(app, orientation="horizontal", width=500)
progress_bar.pack(pady=10)
progress_bar.set(0)

# Log Area
log_area = ctk.CTkTextbox(app, width=700, height=300, wrap="word")
log_area.pack(pady=10)

# Run the CustomTkinter event loop
app.mainloop()