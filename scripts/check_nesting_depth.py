#!/usr/bin/env python3
"""
Nesting Depth Check Script for Issue #390 - Phase 4 Complexity Standards

This script enforces the maximum nesting depth standard (≤ 4 levels)
as part of pre-commit hooks and CI validation.
"""

import ast
import sys
from pathlib import Path
from typing import List, Tuple


def check_nesting_depth(file_path: Path, max_depth: int = 4) -> List[Tuple[int, str, int]]:
    """
    Check nesting depth in a Python file.
    
    Args:
        file_path: Path to the Python file
        max_depth: Maximum allowed nesting depth
        
    Returns:
        List of violations: (line_number, context, actual_depth)
    """
    violations = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content, filename=str(file_path))
        
        def check_node_depth(node: ast.AST, current_depth: int = 0, context: str = "module"):
            """Recursively check nesting depth of AST nodes."""
            if isinstance(node, (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                new_depth = current_depth + 1
                
                if new_depth > max_depth:
                    violations.append((node.lineno, context, new_depth))
                
                # Update context for nested structures
                if isinstance(node, ast.FunctionDef):
                    new_context = f"function {node.name}"
                elif isinstance(node, ast.AsyncFunctionDef):
                    new_context = f"async function {node.name}"
                elif isinstance(node, ast.ClassDef):
                    new_context = f"class {node.name}"
                else:
                    new_context = f"{type(node).__name__.lower()} at line {node.lineno}"
                
                # Check child nodes
                for child in ast.iter_child_nodes(node):
                    check_node_depth(child, new_depth, new_context)
            else:
                # Check child nodes without increasing depth
                for child in ast.iter_child_nodes(node):
                    check_node_depth(child, current_depth, context)
        
        check_node_depth(tree)
    
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"Warning: Could not parse {file_path}: {e}")
    
    return violations


def main():
    """Main function to check nesting depths in provided files."""
    max_depth = 4
    violations_found = False
    
    for file_path in sys.argv[1:]:
        path = Path(file_path)
        if not path.exists():
            print(f"Warning: File {file_path} does not exist")
            continue
        
        if not path.suffix == '.py':
            continue
        
        violations = check_nesting_depth(path, max_depth)
        
        if violations:
            violations_found = True
            print(f"\n❌ Nesting Depth Violations in {file_path}:")
            for line_num, context, actual_depth in violations:
                print(f"  Line {line_num}: {context} has depth {actual_depth} (max: {max_depth})")
    
    if violations_found:
        print(f"\n🚨 Nesting depth violations found! Maximum allowed: {max_depth} levels")
        print("💡 Consider using guard clauses and early returns to reduce nesting")
        sys.exit(1)
    else:
        print("✅ All code complies with nesting depth standards")


if __name__ == "__main__":
    main()
