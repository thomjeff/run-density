#!/usr/bin/env python3
"""
Function Length Check Script for Issue #390 - Phase 4 Complexity Standards

This script enforces the maximum function length standard (≤ 50 lines)
as part of pre-commit hooks and CI validation.
"""

import ast
import sys
from pathlib import Path
from typing import List, Tuple


def check_function_length(file_path: Path, max_lines: int = 50) -> List[Tuple[int, str, int]]:
    """
    Check function length in a Python file.
    
    Args:
        file_path: Path to the Python file
        max_lines: Maximum allowed lines per function
        
    Returns:
        List of violations: (line_number, function_name, actual_lines)
    """
    violations = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.splitlines()
        
        tree = ast.parse(content, filename=str(file_path))
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Calculate function length (excluding docstring)
                start_line = node.lineno - 1
                end_line = node.end_lineno - 1 if hasattr(node, 'end_lineno') else start_line
                
                # Skip if no end_lineno (Python < 3.8)
                if not hasattr(node, 'end_lineno'):
                    continue
                
                function_lines = end_line - start_line + 1
                
                # Skip if function is too short to be meaningful
                if function_lines < 5:
                    continue
                
                if function_lines > max_lines:
                    violations.append((node.lineno, node.name, function_lines))
    
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"Warning: Could not parse {file_path}: {e}")
    
    return violations


def main():
    """Main function to check function lengths in provided files."""
    max_lines = 50
    violations_found = False
    
    for file_path in sys.argv[1:]:
        path = Path(file_path)
        if not path.exists():
            print(f"Warning: File {file_path} does not exist")
            continue
        
        if not path.suffix == '.py':
            continue
        
        violations = check_function_length(path, max_lines)
        
        if violations:
            violations_found = True
            print(f"\n❌ Function Length Violations in {file_path}:")
            for line_num, func_name, actual_lines in violations:
                print(f"  Line {line_num}: {func_name}() has {actual_lines} lines (max: {max_lines})")
    
    if violations_found:
        print(f"\n🚨 Function length violations found! Maximum allowed: {max_lines} lines")
        print("💡 Consider breaking large functions into smaller, focused functions")
        sys.exit(1)
    else:
        print("✅ All functions comply with length standards")


if __name__ == "__main__":
    main()
