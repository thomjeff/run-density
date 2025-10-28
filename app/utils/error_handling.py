"""
Error Handling Utilities for Issue #390 - Phase 4

This module provides standardized error handling patterns to prevent
silent failures and improve error diagnosis.
"""

import logging
from typing import Any, Dict, List, Optional, Union, Callable, Type, Tuple
from functools import wraps
import traceback

logger = logging.getLogger(__name__)


class ComplexityError(Exception):
    """Raised when complexity standards are violated."""
    pass


class ValidationError(Exception):
    """Raised when data validation fails."""
    pass


class EnvironmentError(Exception):
    """Raised when environment detection fails."""
    pass


def handle_specific_exceptions(
    exceptions: Tuple[Type[Exception], ...],
    error_context: str = "",
    log_level: int = logging.ERROR,
    reraise: bool = True
) -> Callable:
    """
    Decorator for handling specific exceptions with context.
    
    Args:
        exceptions: Tuple of exception types to catch
        error_context: Context string for error messages
        log_level: Logging level for errors
        reraise: Whether to reraise the exception
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                context = f"{error_context}: " if error_context else ""
                logger.log(log_level, f"{context}{type(e).__name__}: {e}")
                logger.debug(f"Error details for {func.__name__}: {traceback.format_exc()}")
                if reraise:
                    raise
                return None
        return wrapper
    return decorator


def safe_execute(
    func: Callable,
    *args,
    default: Any = None,
    error_context: str = "",
    **kwargs
) -> Any:
    """
    Safely execute a function with error handling.
    
    Args:
        func: Function to execute
        *args: Positional arguments
        default: Default value to return on error
        error_context: Context for error messages
        **kwargs: Keyword arguments
        
    Returns:
        Function result or default value
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        context = f"{error_context}: " if error_context else ""
        logger.error(f"{context}{type(e).__name__}: {e}")
        logger.debug(f"Error details: {traceback.format_exc()}")
        return default


def validate_data_structure(
    data: Any,
    expected_type: Type,
    required_fields: Optional[List[str]] = None,
    context: str = ""
) -> None:
    """
    Validate data structure and raise ValidationError if invalid.
    
    Args:
        data: Data to validate
        expected_type: Expected type
        required_fields: Required fields for dict types
        context: Context for error messages
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(data, expected_type):
        raise ValidationError(f"{context}: Expected {expected_type.__name__}, got {type(data).__name__}")
    
    if isinstance(data, dict) and required_fields:
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise ValidationError(f"{context}: Missing required fields: {', '.join(missing_fields)}")


def log_function_entry(func: Callable) -> Callable:
    """
    Decorator to log function entry and exit.
    
    Args:
        func: Function to log
        
    Returns:
        Wrapped function with logging
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug(f"Entering {func.__name__}")
        try:
            result = func(*args, **kwargs)
            logger.debug(f"Exiting {func.__name__} successfully")
            return result
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            raise
    return wrapper


def handle_file_operations(
    operation: str,
    file_path: str,
    error_context: str = ""
) -> Callable:
    """
    Decorator for handling file operations with specific error handling.
    
    Args:
        operation: Type of operation (read, write, delete)
        file_path: Path to file
        error_context: Context for error messages
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except FileNotFoundError as e:
                logger.error(f"{error_context}: File not found: {file_path}")
                raise
            except PermissionError as e:
                logger.error(f"{error_context}: Permission denied for {file_path}")
                raise
            except OSError as e:
                logger.error(f"{error_context}: OS error for {file_path}: {e}")
                raise
            except Exception as e:
                logger.error(f"{error_context}: Unexpected error with {file_path}: {e}")
                raise
        return wrapper
    return decorator


def handle_database_operations(
    operation: str,
    table_name: str = "",
    error_context: str = ""
) -> Callable:
    """
    Decorator for handling database operations with specific error handling.
    
    Args:
        operation: Type of operation (select, insert, update, delete)
        table_name: Name of table
        error_context: Context for error messages
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                table_info = f" on table {table_name}" if table_name else ""
                logger.error(f"{error_context}: Database {operation} error{table_info}: {e}")
                raise
        return wrapper
    return decorator


def handle_api_operations(
    endpoint: str,
    method: str = "GET",
    error_context: str = ""
) -> Callable:
    """
    Decorator for handling API operations with specific error handling.
    
    Args:
        endpoint: API endpoint
        method: HTTP method
        error_context: Context for error messages
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"{error_context}: API {method} {endpoint} error: {e}")
                raise
        return wrapper
    return decorator


def create_error_summary(errors: List[Exception]) -> str:
    """
    Create a summary of multiple errors.
    
    Args:
        errors: List of exceptions
        
    Returns:
        Formatted error summary
    """
    if not errors:
        return "No errors"
    
    error_types = {}
    for error in errors:
        error_type = type(error).__name__
        if error_type not in error_types:
            error_types[error_type] = []
        error_types[error_type].append(str(error))
    
    summary_lines = [f"Error Summary ({len(errors)} errors):"]
    for error_type, messages in error_types.items():
        summary_lines.append(f"  {error_type}: {len(messages)} occurrences")
        for message in messages[:3]:  # Show first 3 messages
            summary_lines.append(f"    - {message}")
        if len(messages) > 3:
            summary_lines.append(f"    - ... and {len(messages) - 3} more")
    
    return "\n".join(summary_lines)
