import os
import time
from typing import List, Optional, Dict, Any
import requests
import pandas as pd
from research_gpt.logging_config import logger
from research_gpt.config import CONFIG_SEARCH


def search_google(query: str, last_n_days: Optional[int] = None, **kwargs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Fetch search results using Google Custom Search JSON API.

    Args:
        query (str): The search query.
        last_n_days (Optional[int]): The number of last days to restrict the search results.
        **kwargs: Additional parameters to be passed to the Google Search API.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries containing the search results.
    """
    if CONFIG_SEARCH['api_key'] is None:
        raise ValueError("The Google API key is missing. Please set the 'GOOGLE_API_KEY' environment variable.")
    
    if CONFIG_SEARCH['cx'] is None:
        raise ValueError("The Google CX value is missing. Please set the 'GOOGLE_CX' environment variable.")

    retries = 0
    retry_delay = CONFIG_SEARCH['retry_delay']
    results = []

    while retries < CONFIG_SEARCH['max_retries']:
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": CONFIG_SEARCH['api_key'],
                "cx": CONFIG_SEARCH['cx'],
                "q": query,
            }

            if last_n_days is not None:
                params["dateRestrict"] = f"d[{last_n_days}]"

            # Add additional parameters to the request
            params.update(kwargs)

            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if "items" in data:
                results = [{"title": item["title"],
                            "link": item["link"],
                            "snippet": item["snippet"],
                            "rank": index + 1}
                           for index, item in enumerate(data["items"])]
            
            logger.info(f"Successful query: {query} - {len(results)} results")
            break
        except Exception as e:
            logger.warning(f"Failed to complete google search (attempt {retries + 1}): {query} -  {e}")
            retries += 1
            time.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff

    return results

def results_to_dataframe(results: List[Dict[str, Any]]) -> pd.DataFrame:
    """Convert the search results to a pandas DataFrame."""
    return pd.DataFrame(results)
