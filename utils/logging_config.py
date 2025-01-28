import logging
import os


def setup_logging(log_dir=None, log_file="Logs.log"):
    if not log_dir:
        log_dir = os.path.join("logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, log_file)

    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

    logging.basicConfig(level=logging.INFO, handlers=[
                        file_handler, stream_handler])
