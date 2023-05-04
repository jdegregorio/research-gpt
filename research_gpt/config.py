import os

CONFIG_SEARCH = {
    'api_key': os.environ.get('GOOGLE_API_KEY'),
    'cx': os.environ.get('GOOGLE_CX'),
    'max_retries': 3,
    'retry_delay': 60  # seconds
}