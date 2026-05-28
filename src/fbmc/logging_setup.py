from datetime import datetime
import logging
from pathlib import Path


RUN_FILE_HANDLER_NAME = "pypsa_fbmc_run_file"


def configure_run_logging(save_path: Path) -> Path:
    """Attach a per-run file handler while keeping console logging enabled."""
    save_path = Path(save_path)
    save_path.mkdir(parents=True, exist_ok=True)

    log_path = save_path / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    has_stream_handler = any(
        isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler)
        for handler in root_logger.handlers
    )
    if not has_stream_handler:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

    for handler in list(root_logger.handlers):
        if isinstance(handler, logging.FileHandler) and handler.get_name() == RUN_FILE_HANDLER_NAME:
            root_logger.removeHandler(handler)
            handler.close()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.set_name(RUN_FILE_HANDLER_NAME)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    return log_path
