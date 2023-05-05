import os
import re
import json
import time
from bs4 import BeautifulSoup
from typing import List, Tuple, Dict
import requests
from tqdm import tqdm

try:
    from research_gpt.logging_config import logger
except ImportError:
    from logging_config import logger


def calculate_retry_delay(retries: int, initial_retry_delay: int = 5) -> int:
    """Calculate the retry delay using exponential backoff."""
    return initial_retry_delay * (2 ** (retries - 1))


def clean_text(text: str) -> str:
    """Clean up the extracted text by removing extra spaces, newlines, and other common "junk" characters."""
    cleaned_text = re.sub(r'\s+', ' ', text).strip()
    return cleaned_text

def fetch_html(url: str, max_retries: int = 3, initial_retry_delay: int = 3, request_timeout: int = 15) -> str:
    """
    Fetch the raw HTML content of a given URL.

    :param url: URL to fetch
    :param max_retries: Maximum number of retries for fetching a URL (default: 3)
    :param initial_retry_delay: Initial delay between retries in seconds, doubles with each retry (default: 3)
    :param request_timeout: Timeout for the GET request in seconds (default: 15)
    :return: Raw HTML content or None if the URL could not be fetched
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36"
    }
    retries = 0

    while retries <= max_retries:
        try:
            response = requests.get(url, headers=headers, timeout=request_timeout)
            return response.text
        except Exception as e:
            retries += 1
            if retries <= max_retries:
                logger.warning(f"Failed to fetch content for {url} (attempt {retries}): {e}")
                retry_delay = calculate_retry_delay(retries, initial_retry_delay)
                time.sleep(retry_delay)

    return None


def process_html(html: str, remove_elements: List[str] = None) -> Tuple[str, List[str]]:
    """
    Process the HTML content and return the extracted text and list of href links.

    :param html: HTML content to process
    :param remove_elements: List of HTML tags to remove (default: ['header', 'footer', 'script', 'style', 'nav'])
    :return: Extracted text and a list of href links, or (None, []) if the HTML content is None
    """
    if html is None:
        return None, []

    if remove_elements is None:
        remove_elements = ['header', 'footer', 'script', 'style', 'nav']

    soup = BeautifulSoup(html, 'html.parser')

    for elem in soup(remove_elements):
        elem.decompose()

    text = clean_text(soup.get_text(separator=' '))
    href_links = [a['href'] for a in soup.find_all('a', href=True)]

    return text, href_links


def scrape(url: str, max_retries: int = 3, initial_retry_delay: int = 3, request_timeout: int = 15, remove_elements: List[str] = None) -> Tuple[str, List[str]]:
    """
    Scrape the content of a given URL and return the extracted text and list of href links.

    :param url: URL to scrape
    :param max_retries: Maximum number of retries for scraping a URL (default: 3)
    :param initial_retry_delay: Initial delay between retries in seconds, doubles with each retry (default: 3)
    :param request_timeout: Timeout for the GET request in seconds (default: 15)
    :param remove_elements: List of HTML tags to remove (default: ['header', 'footer', 'script', 'style', 'nav'])
    :return: Extracted text and a list of href links, or (None, []) if the URL could not be scraped
    """
    raw_html = fetch_html(url, max_retries=max_retries, initial_retry_delay=initial_retry_delay, request_timeout=request_timeout)
    text, href_links = process_html(raw_html, remove_elements=remove_elements)
    return text, href_links


def save_html_to_disk(url: str, raw_html: str, output_dir: str) -> None:
    """
    Save raw HTML content to disk.

    :param url: The URL from which the raw HTML was fetched
    :param raw_html: The raw HTML content
    :param output_dir: The directory to save the raw HTML file
    """
    file_name = f"{hash(url)}.html"
    file_path = os.path.join(output_dir, file_name)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(raw_html)

    metadata = {
        "url": url,
        "file_name": file_name
    }

    metadata_path = os.path.join(output_dir, f"{hash(url)}.json")

    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f)


def load_html_from_disk(input_dir: str) -> List[Dict[str, str]]:
    """
    Load raw HTML files from disk and construct a list of dictionaries with their corresponding URLs.

    :param input_dir: The directory containing the raw HTML files and their metadata
    :return: A list of dictionaries with the original URL and the raw HTML content
    """
    html_data = []

    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.endswith('.html'):
                metadata_path = os.path.join(root, file.replace('.html', '.json'))

                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)

                html_file_path = os.path.join(root, file)

                with open(html_file_path, 'r', encoding='utf-8') as f:
                    raw_html = f.read()

                html_data.append({
                    "url": metadata["url"],
                    "raw_html": raw_html
                })

    return html


def scrape_urls(urls: List[str], max_retries: int = 3, initial_retry_delay: int = 3, request_timeout: int = 15, remove_elements: List[str] = None) -> Tuple[List[Dict[str, str]], List[str]]:
    """
    Scrape a list of URLs and extract text and href links using BeautifulSoup.

    :param urls: List of URLs to scrape
    :param max_retries: Maximum number of retries for scraping a URL (default: 3)
    :param initial_retry_delay: Initial delay between retries in seconds, doubles with each retry (default: 3)
    :param request_timeout: Timeout for the GET request in seconds (default: 15)
    :param remove_elements: List of HTML tags to remove (default: ['header', 'footer', 'script', 'style', 'nav'])
    :return: A tuple containing two lists: the first list contains dictionaries with the original URL,
             extracted text, and href links, and the second list contains the URLs that failed to be scraped
    """
    scraped_data = []
    failed_urls = []

    url_metadata = {url: {"retries": 0, "last_attempt_timestamp": None} for url in urls}

    remaining_urls = set(urls)

    logger.info(f"Starting to scrape {len(urls)} URLs.")

    progress_bar_format = "{l_bar}{bar}| {n}/{total} [Elapsed: {elapsed}, Remaining: {remaining}]"

    with tqdm(total=len(urls), desc="Scraping URLs", bar_format=progress_bar_format) as progress_bar:
        while remaining_urls:
            for url in list(remaining_urls):
                metadata = url_metadata[url]
                current_time = time.time()

                retry_delay = calculate_retry_delay(metadata["retries"])

                if metadata["last_attempt_timestamp"] is None or (current_time - metadata["last_attempt_timestamp"]) >= retry_delay:
                    scraped_text, href_links = scrape(url, max_retries=0, initial_retry_delay=0, request_timeout=request_timeout, remove_elements=remove_elements)

                    if scraped_text is not None:
                        scraped_entry = {
                            "url": url,
                            "text": scraped_text,
                            "links": href_links
                        }
                        scraped_data.append(scraped_entry)
                        remaining_urls.remove(url)
                        progress_bar.update(1)
                        logger.debug(f"Successfully scraped {url}")
                    else:
                        metadata["retries"] += 1
                        metadata["last_attempt_timestamp"] = current_time

                        if metadata["retries"] >= max_retries:
                            failed_urls.append(url)
                            remaining_urls.remove(url)
                            progress_bar.update(1)                          
