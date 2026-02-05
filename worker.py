"""Simple worker entrypoint for Docker/CI.
Starts in-process background workers that process queued messages.
"""
import logging
import signal
import sys
import time

try:
    from .message_queue import start_workers
except ImportError:
    from message_queue import start_workers

logger = logging.getLogger(__name__)


def _shutdown(signum, frame):
    logger.info("Worker shutdown signal received")
    sys.exit(0)


def main():
    logging.basicConfig(level=logging.INFO)
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info("Starting worker process")
    start_workers(1)

    # keep the process alive
    try:
        while True:
            time.sleep(1)
    except SystemExit:
        logger.info("Worker exiting")


if __name__ == "__main__":
    main()
