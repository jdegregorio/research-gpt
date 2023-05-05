try:
    from research_gpt.logging_config import logger
    from research_gpt.generate import generate_search_queries
    from research_gpt.search import search_google
    from research_gpt.scrape import scrape_urls
except ImportError:
    from logging_config import logger
    from generate import generate_search_queries
    from search import search_google
    from scrape import scrape_urls

search_results = search_google("Dynasty Fantasy Football Rookie Rankings Superflex")
urls = [result['link'] for result in search_results]


scraped_data, failed_urls = scrape_urls(urls)

scraped_data[0]