"""
logging_config.py

Configure a simple TimedRotatingFileHandler for local audit logs.
"""
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def configure_logging(log_dir: str = None, level=logging.INFO):
    log_dir = Path(log_dir or Path(__file__).parent / 'logs')
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'chat_agents.log'

    root = logging.getLogger()
    if root.handlers:
        return  # already configured

    root.setLevel(level)

    fmt = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # Rotating log file per day, keep 14 days
    fh = TimedRotatingFileHandler(str(log_file), when='midnight', interval=1, backupCount=14, utc=True)
    fh.setFormatter(fmt)
    root.addHandler(fh)


__all__ = ['configure_logging']
