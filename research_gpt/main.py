try:
    from research_gpt.logging_config import logger
    from research_gpt.generate import generate_search_queries
    from research_gpt.search import search_google
except ImportError:
    from logging_config import logger
    from research_gpt.generate import generate_search_queries
    from search import search_google