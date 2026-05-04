import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from app.core.config import settings

# Use a logs directory at project root, NOT inside CONTENT_DIR
LOG_DIR = Path(settings.BASE_DIR) / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "cv_service.log"

logger = logging.getLogger("cv_service")
logger.setLevel(logging.INFO)

# Rotating file handler (5 MB per file, keep 3 backups)
file_handler = RotatingFileHandler(
    filename=LOG_FILE,
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Optional console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

logger.info("Logger initialized - logs stored at %s", LOG_DIR)