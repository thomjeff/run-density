"""
Run-level logging utility for Issue #527

Provides file-based logging to runflow/analysis/{run_id}/logs/app.log
for each analysis run, enabling QA/ops to review logs without Docker access.

Issue #682: Updated to use runflow/analysis/{run_id} structure
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class RunLogHandler:
    """
    Context manager for run-level file logging.
    
    Creates and manages a file handler that writes to runflow/analysis/{run_id}/logs/app.log
    during the execution of a single run.
    
    Issue #682: Updated to use runflow/analysis/{run_id} structure
    """
    
    def __init__(self, run_id: str, runflow_root: Optional[Path] = None):
        """
        Initialize run log handler.
        
        Args:
            run_id: Unique run identifier
            runflow_root: Root directory for runflow (defaults to get_runflow_root())
        """
        self.run_id = run_id
        if runflow_root is None:
            from app.utils.run_id import get_runflow_root
            runflow_root = get_runflow_root()
        self.runflow_root = runflow_root
        # Issue #682: Update log directory path to use analysis subdirectory
        self.log_dir = runflow_root / "analysis" / run_id / "logs"
        self.log_file = self.log_dir / "app.log"
        self.file_handler: Optional[logging.FileHandler] = None
        self.root_logger = logging.getLogger()
        
    def __enter__(self):
        """Set up file logging for this run."""
        try:
            # Create logs directory if missing
            self.log_dir.mkdir(parents=True, exist_ok=True)
            
            # Create file handler with same format as console logging
            self.file_handler = logging.FileHandler(
                self.log_file,
                mode='w',  # Overwrite existing log (new run)
                encoding='utf-8'
            )
            
            # Use same format as root logger (or default if not set)
            formatter = logging.Formatter(
                fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            self.file_handler.setFormatter(formatter)
            
            # Set level to match root logger (or INFO if not set)
            self.file_handler.setLevel(self.root_logger.level or logging.INFO)
            
            # Add handler to root logger to capture all application logs
            self.root_logger.addHandler(self.file_handler)
            
            # Write run start marker
            start_time = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            self.root_logger.info(f"=" * 80)
            self.root_logger.info(f"Run started: {self.run_id}")
            self.root_logger.info(f"Start time: {start_time}")
            self.root_logger.info(f"Log file: {self.log_file}")
            self.root_logger.info(f"=" * 80)
            
            logger.info(f"Run logging initialized: {self.log_file}")
            
        except Exception as e:
            # Non-blocking: if log setup fails, warn and continue
            logger.warning(f"Failed to initialize run logging for {self.run_id}: {e}")
            self.file_handler = None
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up file logging for this run."""
        if self.file_handler:
            try:
                # Write run end marker
                end_time = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                self.root_logger.info(f"=" * 80)
                if exc_type is None:
                    self.root_logger.info(f"Run completed successfully: {self.run_id}")
                else:
                    self.root_logger.error(f"Run failed: {self.run_id} - {exc_type.__name__}: {exc_val}")
                self.root_logger.info(f"End time: {end_time}")
                self.root_logger.info(f"=" * 80)
                
                # Flush and close handler
                self.file_handler.flush()
                self.file_handler.close()
                
                # Remove handler from root logger to avoid leaking handlers
                self.root_logger.removeHandler(self.file_handler)
                
                logger.info(f"Run logging finalized: {self.log_file}")
                
            except Exception as e:
                logger.warning(f"Failed to finalize run logging for {self.run_id}: {e}")
            finally:
                self.file_handler = None
    
    def get_log_path(self) -> Optional[Path]:
        """Get the path to the log file (for metadata updates)."""
        if self.log_file and self.log_file.exists():
            return self.log_file
        return None

