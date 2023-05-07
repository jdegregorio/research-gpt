import os
import re
import json
import time
from bs4 import BeautifulSoup
from typing import List, Tuple, Dict, Optional, Callable
import requests
from tqdm import tqdm
import hashlib
import html2text
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

try:
    from research_gpt.logging_config import logger
except ImportError:
    from logging_config import logger


def calculate_retry_delay(retries: int, initial_retry_delay: int = 5) -> int:
    """
    Calculate the retry delay based on the number of retries and the initial retry delay.

    :param retries: The number of retries that have been attempted.
    :param initial_retry_delay: The initial delay between retries in seconds.
    :return: The calculated retry delay in seconds.
    """
    return initial_retry_delay * (2 ** (retries - 1))


def clean_text(text: str) -> str:
    """Clean up the extracted text by removing extra spaces, newlines, and other common "junk" characters."""
    cleaned_text = re.sub(r'\s+', ' ', text).strip()
    return cleaned_text


def generate_url_hash(url: str) -> str:
    """
    Generate a file name based on the SHA-256 hash of the URL.
    
    :param url: The URL for which to generate a file name
    :return: The generated file name as a string
    """
    sha256_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return sha256_hash


def check_html_incomplete_load(html: str) -> bool:
    keywords = ['Please enable JS', 'captcha', 'data-cfasync', 'g-recaptcha']
    return any(keyword in html for keyword in keywords)


def fetch_with_retry(fetch_func: Callable, url: str, max_retries: int = 3, initial_retry_delay: int = 3, request_timeout: int = 15) -> Optional[str]:
    """
    Fetch the raw HTML content of a given URL using the specified fetch function, with retry logic.

    :param fetch_func: The fetch function to use (e.g., fetch_html_requests or fetch_html_selenium).
    :param url: URL to fetch.
    :param max_retries: Maximum number of retries for fetching a URL (default: 3).
    :param initial_retry_delay: Initial delay between retries in seconds, doubles with each retry (default: 3).
    :param request_timeout: Timeout for the request in seconds (default: 15).
    :return: Raw HTML content or None if the URL could not be fetched.
    """
    retries = 0
    while retries <= max_retries:
        try:
            return fetch_func(url, request_timeout)
        except Exception as e:
            retries += 1
            if retries <= max_retries:
                logger.warning(f"Failed to fetch content for {url} (attempt {retries}): {e}")
                retry_delay = calculate_retry_delay(retries, initial_retry_delay)
                time.sleep(retry_delay)
    return None


def fetch_html_requests(url: str, max_retries: int = 3, initial_retry_delay: int = 3, request_timeout: int = 15) -> str:
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

def fetch_html_selenium(url: str, max_retries: int = 3, initial_retry_delay: int = 3, request_timeout: int = 15) -> Optional[str]:
    """
    Fetch the raw HTML content of a given URL.

    :param url: URL to fetch
    :param max_retries: Maximum number of retries for fetching a URL (default: 3)
    :param initial_retry_delay: Initial delay between retries in seconds, doubles with each retry (default: 3)
    :param request_timeout: Timeout for the GET request in seconds (default: 15)
    :return: Raw HTML content or None if the URL could not be fetched
    """
    retries = 0
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36")
    # chrome_options.set_page_load_timeout(request_timeout)

    while retries <= max_retries:
        try:
            with webdriver.Chrome(options=chrome_options) as driver:
                driver.get(url)
                return driver.page_source
        except Exception as e:
            retries += 1
            if retries <= max_retries:
                logger.warning(f"Failed to fetch content for {url} (attempt {retries}): {e}")
                retry_delay = calculate_retry_delay(retries, initial_retry_delay)
                time.sleep(retry_delay)

    return None


def fetch_html(url: str, max_retries: int = 3, initial_retry_delay: int = 3, request_timeout: int = 15) -> Optional[str]:
    """
    Fetch the raw HTML content of a given URL, first attempting to use the requests package, and then falling back to using selenium.

    :param url: URL to fetch.
    :param max_retries: Maximum number of retries for fetching a URL (default: 3).
    :param initial_retry_delay: Initial delay between retries in seconds, doubles with each retry (default: 3).
    :param request_timeout: Timeout for the request in seconds (default: 15).
    :return: Raw HTML content or None if the URL could not be fetched.
    """
    logger.info(f"Fetching HTML content for {url}")
    
    # Attempt to fetch HTML content using the requests package
    logger.debug("Attempting to fetch HTML content using requests")
    html_content = fetch_with_retry(fetch_html_requests, url, max_retries, initial_retry_delay, request_timeout)
    
    # If the fetched content is incomplete or not fetched, fall back to using selenium
    if html_content is None or check_html_incomplete_load(html_content):
        logger.warning("Failed to fetch complete HTML content using requests, falling back to selenium")
        html_content = fetch_with_retry(fetch_html_selenium, url, max_retries, initial_retry_delay, request_timeout)
    
    if html_content is None:
        logger.warning(f"Failed to fetch HTML content for {url} using both requests and selenium")
    else:
        logger.info(f"Successfully fetched HTML content for {url}")
    
    return html_content


def extract_links(html: str) -> List[str]:
    """
    Extract href links from the HTML content.

    :param html: HTML content to process
    :return: A list of href links, or an empty list if the HTML content is None
    """
    if html is None:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    href_links = [a['href'] for a in soup.find_all('a', href=True)]

    return href_links


def process_html(html: str, remove_elements: List[str] = None) -> str:
    """
    Process the HTML content and return the extracted text in markdown format.

    :param html: HTML content to process
    :param remove_elements: List of HTML tags to remove (default: ['header', 'footer', 'script', 'style', 'nav'])
    :return: Extracted text in markdown format, or None if the HTML content is None
    """
    if html is None:
        return None

    if remove_elements is None:
        remove_elements = ['header', 'footer', 'script', 'style', 'nav']

    soup = BeautifulSoup(html, 'html.parser')

    for elem in soup(remove_elements):
        elem.decompose()

    # Convert HTML to markdown
    markdown_converter = html2text.HTML2Text()
    markdown_converter.ignore_links = True
    markdown_converter.ignore_images = True
    markdown_converter.ignore_tables = True
    markdown_text = markdown_converter.handle(soup.prettify())

    return markdown_text


def write_markdown_to_file(url: str, markdown_text: str, output_dir: str):
    """
    Write the markdown text to a file in the specified output directory.

    :param url: The URL used to generate the file name
    :param markdown_text: The markdown text to write
    :param output_dir: The directory where the output file should be written
    """
    if not markdown_text or not url or not output_dir:
        return

    # Generate a unique file name based on the URL
    file_name = f"{generate_url_hash(url)}.md"

    # Write markdown text to file
    with open(f"{output_dir}/{file_name}", "w") as f:
        f.write(markdown_text)


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
    file_name = f"{generate_url_hash(url)}.html"
    file_path = os.path.join(output_dir, file_name)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(raw_html)

    metadata = {
        "url": url,
        "file_name": file_name
    }

    metadata_path = os.path.join(output_dir, f"{generate_url_hash(url)}.json")

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

    return html_data                    


def fetch_and_save_html_from_urls(urls: List[str], output_dir: str, max_retries: int = 3, initial_retry_delay: int = 3, request_timeout: int = 15) -> List[str]:
    """
    Scrape a list of URLs and save the raw HTML content to disk.

    :param urls: List of URLs to scrape
    :param output_dir: The directory to save the raw HTML files and their metadata
    :param max_retries: Maximum number of retries for scraping a URL (default: 3)
    :param initial_retry_delay: Initial delay between retries in seconds, doubles with each retry (default: 3)
    :param request_timeout: Timeout for the GET request in seconds (default: 15)
    :return: A list of URLs that failed to be scraped
    """
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
                    raw_html = fetch_html(url, max_retries=0, initial_retry_delay=0, request_timeout=request_timeout)

                    if raw_html is not None:
                        save_html_to_disk(url, raw_html, output_dir)
                        remaining_urls.remove(url)
                        progress_bar.update(1)
                        logger.debug(f"Successfully scraped and saved raw HTML for {url}")
                    else:
                        metadata["retries"] += 1
                        metadata["last_attempt_timestamp"] = current_time

                        if metadata["retries"] >= max_retries:
                            failed_urls.append(url)
                            remaining_urls.remove(url)
                            progress_bar.update(1)
                            logger.debug(f"Failed to scrape {url} after 3 attempts")

            # Add a short sleep time to prevent excessive looping over the last few URLs
            time.sleep(0.1)

    if failed_urls:
        logger.warning(f"Failed to scrape {len(failed_urls)} URL(s):\n" + "\n".join(failed_urls))
    else:
        logger.info("Successfully scraped all URLs.")

    return failed_urls


if __name__ == "__main__":
    # Example usage:
    urls_to_scrape = ["https://www.si.com/fantasy/2023/05/03/updated-fantasy-football-rankings-after-nfl-draft", "https://www.pff.com/news/fantasy-football-post-2023-nfl-draft-dynasty-rookie-superflex-rankings", "https://www.example.com/page1", "https://www.example.com/page2"]
    output_directory = "./output/html"

    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    failed = fetch_and_save_html_from_urls(urls_to_scrape, output_directory)
    if failed:
        logger.warning(f"Failed to scrape the following URLs: {failed}")

    loaded_data = load_html_from_disk(output_directory)
    print(loaded_data)
