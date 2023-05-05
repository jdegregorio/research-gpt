import re
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

def scrape(url: str, max_retries: int = 3, initial_retry_delay: int = 3, request_timeout: int = 15) -> Tuple[str, List[str]]:
    """
    Scrape the content of a given URL and return the extracted text and list of href links.

    :param url: URL to scrape
    :param max_retries: Maximum number of retries for scraping a URL (default: 3)
    :param initial_retry_delay: Initial delay between retries in seconds, doubles with each retry (default: 3)
    :param request_timeout: Timeout for the GET request in seconds (default: 15)
    :return: Extracted text and a list of href links, or (None, []) if the URL could not be scraped
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36"
    }
    retries = 0

    while retries <= max_retries:
        try:
            response = requests.get(url, headers=headers, timeout=request_timeout)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Remove unnecessary elements (header, footer, scripts, styles, etc.)
            for elem in soup(['header', 'footer', 'script', 'style', 'nav']):
                elem.decompose()

            # Extract text from the remaining elements
            text = clean_text(soup.get_text(separator=' '))

            # Extract href links
            href_links = [a['href'] for a in soup.find_all('a', href=True)]

            return text, href_links
        except Exception as e:
            retries += 1
            if retries <= max_retries:
                logger.warning(f"Failed to fetch content for {url} (attempt {retries}): {e}")
                retry_delay = calculate_retry_delay(retries, initial_retry_delay)
                time.sleep(retry_delay)

    # Return None if the URL was not scraped successfully
    return None, []

def scrape_urls(urls: List[str]) -> Tuple[List[Dict[str, str]], List[str]]:
    """
    Scrape a list of URLs and extract text and href links using BeautifulSoup.

    :param urls: List of URLs to scrape
    :return: A tuple containing two lists: the first list contains dictionaries with the original URL,
             extracted text, and href links, and the second list contains the URLs that failed to be scraped
    """
    scraped_data = []
    failed_urls = []

    # Initialize the retry and delay metadata
    url_metadata = {url: {"retries": 0, "last_attempt_timestamp": None} for url in urls}

    remaining_urls = set(urls)

    logger.info(f"Starting to scrape {len(urls)} URLs.")

    progress_bar_format = "{l_bar}{bar}| {n}/{total} [Elapsed: {elapsed}, Remaining: {remaining}]"

    with tqdm(total=len(urls), desc="Scraping URLs", bar_format=progress_bar_format) as progress_bar:
        while remaining_urls:
            for url in list(remaining_urls):
                metadata = url_metadata[url]
                current_time = time.time()

                # Calculate the retry delay using exponential backoff
                retry_delay = calculate_retry_delay(metadata["retries"])

                # Check if the time since the last attempt has exceeded the target delay
                if metadata["last_attempt_timestamp"] is None or (current_time - metadata["last_attempt_timestamp"]) >= retry_delay:
                    scraped_text, href_links = scrape(url, max_retries=0, initial_retry_delay=0)

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

                        if metadata["retries"] >= 3:
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

    return scraped_data, failed_urls
