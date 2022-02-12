import logging
import logging.handlers
from pathlib import Path
import dotenv
import os

dotenv.load_dotenv()
LOG_LEVEL = os.getenv('VU_LOG_LEVEL', default='INFO')


def getLogger(filename_stem):
    filepath = Path(__file__).parent.joinpath('logs/').joinpath(filename_stem + ".log")
    logger = logging.getLogger(__name__)
    logger.setLevel(LOG_LEVEL)

    ch = logging.StreamHandler()
    ch.setLevel(LOG_LEVEL)
    fh = logging.handlers.RotatingFileHandler(filepath, maxBytes=1000000, backupCount=1)
    fh.setLevel(LOG_LEVEL)

    formatter = logging.Formatter('[%(asctime)s] [%(name)s:%(funcName)s():%(lineno)d] [%(levelname)s] %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger
