# logging_config.py
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

# Create a custom formatter
class CustomFormatter(logging.Formatter):
    def format(self, record):
        log_format = {
            "level": record.levelname,
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.%f%z"),
            "msg": record.getMessage(),
            "error": record.exc_info[1].__str__() if record.exc_info else ""
        }
        return str(log_format)

# Custom TimedRotatingFileHandler to format log file name
class CustomTimedRotatingFileHandler(TimedRotatingFileHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

# Function to setup the logger
def setup_logger():
    # Create a logger
    logger = logging.getLogger("customLogger")
    logger.setLevel(logging.DEBUG)
    current_time = datetime.now().strftime("%Y-%m-%d")

    # Create a timed rotating file handler
    file_handler = CustomTimedRotatingFileHandler(
        filename=f"{current_time}-log.log",
        when="midnight",
        interval=1,
        backupCount=30,
        utc=True
    )

    # Set the custom formatter to the file handler
    formatter = CustomFormatter()
    file_handler.setFormatter(formatter)

    # Add the file handler to the logger
    logger.addHandler(file_handler)

    return logger

# Initialize the logger
logger = setup_logger()
