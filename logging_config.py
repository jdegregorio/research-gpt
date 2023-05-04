from loguru import logger
import sys

log_format = (
    "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {function} | {line} | {message}"
)

logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    format=log_format,
)
logger.add(
    "application.log",
    level="INFO",
    format=log_format,
    rotation="10 MB",  # Rotate the log file when it reaches 10 MB
    retention="10 days",  # Keep rotated log files for 10 days
)
