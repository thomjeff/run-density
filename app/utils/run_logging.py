"""
Run-level logging for analysis: runflow/analysis/{run_id}/logs/app.log

Issue #527: file log per run.
Issue #682: runflow/analysis/{run_id} layout.
Issue #870: attach to the ``app`` logger (not root) so dashboard polls and
uvicorn access lines do not land in the run log.
"""

import logging
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

APP_LOGGER_NAME = "app"


class OmitHttpPollsFilter(logging.Filter):
    """Keep analysis logs; drop HTTP / dashboard poll noise from the run file."""

    def filter(self, record: logging.LogRecord) -> bool:
        name = record.name
        if name.startswith("app.routes") or name.startswith("uvicorn"):
            return False
        return True


class RunLogHandler:
    """
    Context manager that writes analysis logs to
    runflow/analysis/{run_id}/logs/app.log.
    """

    def __init__(self, run_id: str, runflow_root: Optional[Path] = None):
        self.run_id = run_id
        if runflow_root is None:
            from app.utils.run_id import get_runflow_root
            runflow_root = get_runflow_root()
        self.runflow_root = runflow_root
        self.log_dir = runflow_root / "analysis" / run_id / "logs"
        self.log_file = self.log_dir / "app.log"
        self.file_handler: Optional[logging.FileHandler] = None
        self.app_logger = logging.getLogger(APP_LOGGER_NAME)

    def __enter__(self):
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)

            self.file_handler = logging.FileHandler(
                self.log_file,
                mode="w",
                encoding="utf-8",
            )
            formatter = logging.Formatter(
                fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            self.file_handler.setFormatter(formatter)
            self.file_handler.setLevel(logging.DEBUG)
            self.file_handler.addFilter(OmitHttpPollsFilter())

            self.app_logger.addHandler(self.file_handler)
            if self.app_logger.level == logging.NOTSET:
                self.app_logger.setLevel(logging.INFO)

            start_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            self.app_logger.info(
                "Run %s started at %s", self.run_id, start_time
            )
            logger.debug("Run logging initialized: %s", self.log_file)

        except Exception as e:
            logger.warning("Failed to initialize run logging for %s: %s", self.run_id, e)
            self.file_handler = None

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.file_handler:
            try:
                end_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                if exc_type is None:
                    self.app_logger.info(
                        "Run %s completed at %s", self.run_id, end_time
                    )
                else:
                    self.app_logger.error(
                        "Run %s failed at %s: %s: %s",
                        self.run_id,
                        end_time,
                        exc_type.__name__,
                        exc_val,
                    )

                self.file_handler.flush()
                self.file_handler.close()
                self.app_logger.removeHandler(self.file_handler)
                logger.debug("Run logging finalized: %s", self.log_file)

            except Exception as e:
                logger.warning("Failed to finalize run logging for %s: %s", self.run_id, e)
            finally:
                self.file_handler = None

    def get_log_path(self) -> Optional[Path]:
        if self.log_file and self.log_file.exists():
            return self.log_file
        return None
