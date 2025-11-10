"""
Architecture Validation Tests

Tests to enforce v1.7.0 architectural rules:
- No try/except import fallbacks
- No relative imports in entry points
- Layer boundaries enforced
"""

import pytest
import os
import re
from pathlib import Path


class TestImportPatterns:
    """Validate import patterns follow v1.7.0 rules"""
    
    def test_no_import_fallbacks_in_main(self):
        """Ensure main.py has no try/except import fallbacks"""
        main_path = Path(__file__).parent.parent / "app" / "main.py"
        content = main_path.read_text()
        
        # Should not have except ImportError for module imports
        assert 'except ImportError:' not in content, \
            "main.py should not have try/except import fallbacks in v1.7+"
    
    def test_all_imports_use_app_prefix(self):
        """Verify all imports in main.py use app.* prefix"""
        main_path = Path(__file__).parent.parent / "app" / "main.py"
        content = main_path.read_text()
        
        # Find all import lines
        import_lines = [line for line in content.split('\n') 
                       if line.strip().startswith('from ') and 'import' in line]
        
        # Filter out standard library and third-party imports
        app_imports = [line for line in import_lines 
                      if not any(lib in line for lib in [
                          'typing', 'fastapi', 'starlette', 'pydantic', 
                          '__future__', 'datetime', 'os'
                      ])]
        
        # All app imports should start with 'from app.'
        for line in app_imports:
            if 'from ' in line and not any(x in line for x in ['from app.', '# from']):
                # Allow standard library
                if not any(lib in line for lib in ['pathlib', 'logging']):
                    pytest.fail(f"Import should use 'from app.*' pattern: {line}")
    
    def test_no_stub_files(self):
        """Ensure stub redirect files have been removed"""
        app_dir = Path(__file__).parent.parent / "app"
        
        # These stub files should not exist in v1.7
        stub_files = [
            'density_api.py',
            'map_api.py',
            'gpx_processor.py',
            'report.py',
        ]
        
        for stub_file in stub_files:
            stub_path = app_dir / stub_file
            # If file exists, check if it's a stub
            if stub_path.exists():
                content = stub_path.read_text()
                assert 'DEPRECATED' not in content or 'from api.' not in content, \
                    f"Stub file should be removed: {stub_file}"


class TestLayerBoundaries:
    """Validate layer import rules are followed"""
    
    def test_utils_no_app_imports(self):
        """Utils layer should only import from standard library"""
        utils_dir = Path(__file__).parent.parent / "app" / "utils"
        
        if not utils_dir.exists():
            pytest.skip("Utils directory not found")
        
        for py_file in utils_dir.glob("*.py"):
            if py_file.name == '__init__.py':
                continue
                
            content = py_file.read_text()
            
            # Should not import from app.api or app.routes
            assert 'from app.api' not in content, \
                f"{py_file.name} should not import from app.api (utils layer)"
            assert 'from app.routes' not in content, \
                f"{py_file.name} should not import from app.routes (utils layer)"
            assert 'from app.core' not in content, \
                f"{py_file.name} should not import from app.core (utils layer)"
    
    def test_core_no_api_imports(self):
        """Core layer should not import from API layer"""
        core_dir = Path(__file__).parent.parent / "app" / "core"
        
        if not core_dir.exists():
            pytest.skip("Core directory not found")
        
        for py_file in core_dir.rglob("*.py"):
            if py_file.name == '__init__.py':
                continue
                
            content = py_file.read_text()
            
            # Should not import from app.api or app.routes
            assert 'from app.api' not in content, \
                f"{py_file.name} should not import from app.api (domain isolation)"
            assert 'from app.routes' not in content, \
                f"{py_file.name} should not import from app.routes (domain isolation)"


class TestDeprecatedFiles:
    """Validate deprecated files are properly marked"""
    
    def test_deprecated_files_have_warnings(self):
        """Deprecated files must have explicit deprecation warnings"""
        deprecated_files = [
            'new_density_report.py',
            'new_flagging.py',
            'new_density_template_engine.py',
            'storage.py',
            'conversion_audit.py',
        ]
        
        app_dir = Path(__file__).parent.parent / "app"
        
        for dep_file in deprecated_files:
            file_path = app_dir / dep_file
            if file_path.exists():
                content = file_path.read_text()
                assert 'DEPRECATED' in content or 'DeprecationWarning' in content, \
                    f"{dep_file} should have DEPRECATED marker"


class TestStructure:
    """Validate directory structure follows v1.7.0 layout"""
    
    def test_required_directories_exist(self):
        """Verify v1.7 directory structure exists"""
        app_dir = Path(__file__).parent.parent / "app"
        
        required_dirs = [
            'api',
            'core',
            'routes',
            'utils',
        ]
        
        for dir_name in required_dirs:
            dir_path = app_dir / dir_name
            assert dir_path.exists(), f"Required directory missing: app/{dir_name}"
            assert dir_path.is_dir(), f"Should be directory: app/{dir_name}"

