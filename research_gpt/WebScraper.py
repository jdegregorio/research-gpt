import os
import re
import time
import json
import requests
from typing import List, Dict, Tuple, Callable, Optional
from bs4 import BeautifulSoup
import html2text
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from tqdm import tqdm
from pydantic import BaseModel

try:
    from research_gpt.utils import generate_hash
    from research_gpt.logging_config import logger
except ImportError:
    from utils import generate_hash
    from logging_config import logger


class HtmlFetcher(BaseModel):
    max_retries: int = 3
    initial_retry_delay: int = 3
    request_timeout: int = 15

    def calculate_retry_delay(self, retries: int) -> int:
        return self.initial_retry_delay * (2 ** (retries - 1))

    @staticmethod
    def clean_text(text: str) -> str:
        cleaned_text = re.sub(r'\s+', ' ', text).strip()
        return cleaned_text

    @staticmethod
    def check_html_incomplete_load(html: str) -> bool:
        keywords = ['Please enable JS', 'captcha', 'data-cfasync', 'g-recaptcha']
        return any(keyword in html for keyword in keywords)

    def calculate_retry_delay(self, retries: int) -> int:
        """
        Calculate the delay before the next retry based on the current number of retries.

        Args:
            retries: The current number of retries.

        Returns:
            The delay before the next retry.
        """
        return self.initial_retry_delay * (2 ** (retries - 1))

    @staticmethod
    def clean_text(text: str) -> str:
        """
        Clean up text by removing excessive whitespace and trimming leading/trailing spaces.

        Args:
            text: The input text to be cleaned.

        Returns:
            Cleaned up text.
        """
        cleaned_text = re.sub(r'\s+', ' ', text).strip()
        return cleaned_text

    @staticmethod
    def check_html_incomplete_load(html: str) -> bool:
        """
        Check if the fetched HTML content indicates an incomplete load, e.g., due to CAPTCHA or JavaScript challenges.

        Args:
            html: The fetched HTML content.

        Returns:
            True if the HTML content indicates an incomplete load, False otherwise.
        """
        keywords = ['Please enable JS', 'captcha', 'data-cfasync', 'g-recaptcha']
        return any(keyword in html for keyword in keywords)

    def fetch_with_retry(self, fetch_func: Callable, url: str) -> Optional[str]:

        retries = 0
        while retries <= self.max_retries:
            try:
                return fetch_func(url)
            except Exception as e:
                retries += 1
                if retries <= self.max_retries:
                    logger.warning(f"Failed to fetch content for {url} (attempt {retries}): {e}")
                    retry_delay = self.calculate_retry_delay(retries)
                    time.sleep(retry_delay)
 
        return None

    def fetch_without_retry(self, fetch_func: Callable, url: str) -> Optional[str]:

        try:
            return fetch_func(url)
        except Exception as e:
            logger.warning(f"Failed to fetch content for {url}: {e}")
            return None

    def fetch_html_requests(self, url: str) -> Optional[str]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36"
        }

        try:
            response = requests.get(url, headers=headers, timeout=self.request_timeout)
            return response.text
        except Exception as e:
            raise e

    def fetch_html_selenium(self, url: str) -> Optional[str]:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36")

        try:
            with webdriver.Chrome(options=chrome_options) as driver:
                driver.get(url)
                return driver.page_source
        except Exception as e:
            raise e

    def fetch_html(self, url: str,  use_retries: bool = True) -> Optional[str]:
        logger.info(f"Fetching HTML content for {url}")

        if use_retries:
            fetch_method = self.fetch_with_retry
        else:
            fetch_method = self.fetch_without_retry
            
        # Attempt to fetch HTML content using the requests package
        logger.debug("Attempting to fetch HTML content using requests")
        html_content = fetch_method(self.fetch_html_requests, url)

        # If the fetched content is incomplete or not fetched, fall back to using Selenium
        if html_content is None or self.check_html_incomplete_load(html_content):
            logger.warning("Failed to fetch complete HTML content using requests, falling back to Selenium")
            html_content = fetch_method(self.fetch_html_selenium, url)

        if html_content is None:
            logger.warning(f"Failed to fetch HTML content for {url} using both requests and Selenium")
        else:
            logger.info(f"Successfully fetched HTML content for {url}")

        return html_content

    
    def save_html_to_disk(self, url: str, raw_html: str, output_dir: str) -> None:
        """
        Save the input raw HTML content to a file in the specified output directory.

        Args:
            url: The URL from which the raw HTML content was fetched.
            raw_html: The input raw HTML content.
            output_dir: The output directory to save the file in.
        """
        file_name = f"{generate_hash(url)}.html"
        file_path = os.path.join(output_dir, file_name)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(raw_html)

        metadata = {
            "url": url,
            "file_name": file_name
        }

        metadata_path = os.path.join(output_dir, f"{generate_hash(url)}.json")

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f)

    def fetch_and_save_html_from_urls(self, urls: List[str], output_dir: str) -> List[str]:
        """
        Fetch and save raw HTML content for the input URLs to the specified output directory.

        Args:
            urls: A list of URLs to fetch raw HTML content from.
            output_dir: The output directory to save the fetched raw HTML content.

        Returns:
            A list of URLs for which fetching the raw HTML content failed.
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

                    retry_delay = self.calculate_retry_delay(metadata["retries"])

                    if metadata["last_attempt_timestamp"] is None or (current_time - metadata["last_attempt_timestamp"]) >= retry_delay:
                        raw_html = self.fetch_html(url, use_retries=False)

                        if raw_html is not None:
                            self.save_html_to_disk(url, raw_html, output_dir)
                            remaining_urls.remove(url)
                            progress_bar.update(1)
                            logger
                            logger.debug(f"Successfully scraped and saved raw HTML for {url}")
                        else:
                            metadata["retries"] += 1
                            metadata["last_attempt_timestamp"] = current_time

                            if metadata["retries"] >= self.max_retries:
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



class HtmlProcessor(BaseModel):
    input_dir: str
    output_dir: str

    def load_html_from_disk(self, input_dir: str) -> List[Dict[str, str]]:
        """
        Load raw HTML content and associated metadata from files in the specified input directory.

        Args:
            input_dir: The input directory containing the raw HTML files and metadata.

        Returns:
            A list of dictionaries containing the URL and raw HTML content for each loaded file.
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

    def process_html(self, html: str, remove_elements: List[str] = None) -> str:
        """
        Process the input HTML content by removing specific elements, and convert the result to Markdown.

        Args:
            html: The input HTML content.
            remove_elements: A list of HTML elements to remove, if any.

        Returns:
            The processed HTML content converted to Markdown.
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
    
    def extract_links(self, html: str) -> List[str]:
        """
        Extract href links from the input HTML.

        Args:
            html: The input HTML content.

        Returns:
            A list of href links found in the input HTML content.
        """
        if html is None:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        href_links = [a['href'] for a in soup.find_all('a', href=True)]

        return href_links

    def write_markdown_to_file(self, url: str, markdown_text: str, output_dir: str):
        """
        Write the input Markdown text to a file in the specified output directory.

        Args:
            url: The URL from which the Markdown text was generated.
            markdown_text: The input Markdown text.
            output_dir: The output directory to save the file in.
        """
        if not markdown_text or not url or not output_dir:
            return

        # Generate a unique file name based on the URL
        file_name = f"{generate_hash(url)}.md"

        # Write markdown text to file
        with open(f"{output_dir}/{file_name}", "w") as f:
            f.write(markdown_text)

    def process_html_files_to_markdown(self, input_dir: str, output_dir: str) -> None:
        """
        Load raw HTML files from the specified directory, process them into markdown files,
        and save the markdown files to the specified markdown output directory.

        :param input_dir: The directory containing the raw HTML files.
        :param output_dir: The directory where the processed markdown files will be saved.
        """
        # Load raw HTML data from the specified directory
        html_data = self.load_html_from_disk(input_dir)

        # Process each raw HTML file into a markdown file
        for data in html_data:
            url = data["url"]
            raw_html = data["raw_html"]

            # Process the raw HTML into markdown
            markdown_text = self.process_html(raw_html)

            # Save the markdown file to the specified output directory
            self.write_markdown_to_file(url, markdown_text, output_dir)

            logger.info(f"Processed and saved markdown for {url}")


if __name__ == "__main__":

    # Example usage:
    urls_to_scrape = [
        "https://www.si.com/fantasy/2023/05/03/updated-fantasy-football-rankings-after-nfl-draft",
        "https://www.pff.com/news/fantasy-football-post-2023-nfl-draft-dynasty-rookie-superflex-rankings",
        "https://www.example.com/page1",
        "https://www.example.com/page2"
    ]

    dir_html = "./output/html"
    dir_markdown = "./output/source"

    for dir in [dir_html, dir_markdown]:
        if not os.path.exists(dir):
            os.makedirs(dir)

    html_fetcher = HtmlFetcher()
    html_fetcher.fetch_and_save_html_from_urls(urls_to_scrape, dir_html)

    failed = fetch_and_save_html_from_urls(urls_to_scrape, output_directory)
    if failed:
        logger.warning(f"Failed to scrape the following URLs: {failed}")

    loaded_data = load_html_from_disk(output_directory)
    print(loaded_data)
