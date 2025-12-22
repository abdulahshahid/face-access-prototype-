# app/core/logging.py
import logging, sys
from logging.handlers import RotatingFileHandler

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    ch = logging.StreamHandler(sys.stdout)
    fh = RotatingFileHandler("app.log", maxBytes=10_485_760, backupCount=5)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    ch.setFormatter(fmt)
    fh.setFormatter(fmt)

    logger.addHandler(ch)
    logger.addHandler(fh)
