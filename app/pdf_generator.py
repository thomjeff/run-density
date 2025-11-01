"""
PDF Report Generation Module

Generates professional PDF reports from Markdown content using Pandoc.
This module provides functions for converting existing Markdown reports to PDF
with custom LaTeX templates for professional presentation.
"""

from __future__ import annotations
import os
import tempfile
from typing import Dict, List, Any, Optional
from datetime import datetime
import subprocess
import shutil

try:
    import pypandoc
    PYPANDOC_AVAILABLE = True
except ImportError:
    PYPANDOC_AVAILABLE = False

from app.utils.constants import DEFAULT_STEP_KM, DEFAULT_TIME_WINDOW_SECONDS


def validate_pandoc_installation() -> bool:
    """Validate that Pandoc is properly installed and accessible."""
    try:
        result = subprocess.run(['pandoc', '--version'], 
                              capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return False


def clean_markdown_for_latex(md_content: str) -> str:
    """Clean markdown content to be LaTeX-compatible."""
    # Replace Unicode emojis with LaTeX-safe alternatives
    replacements = {
        '🟢': '[GREEN]',
        '🟡': '[YELLOW]', 
        '🔴': '[RED]',
        '✅': '[CHECK]',
        '⚠️': '[WARNING]',
        '❓': '[UNKNOWN]',
        '📖': '[BOOK]',
        '📊': '[CHART]',
        '🔍': '[SEARCH]',
        '📝': '[NOTE]',
        '📄': '[DOCUMENT]',
        '📂': '[FOLDER]',
        '🎯': '[TARGET]',
        '🚀': '[ROCKET]',
        '⚡': '[LIGHTNING]',
        '🔧': '[WRENCH]',
        '📋': '[CLIPBOARD]',
        '💡': '[BULB]',
        '🌟': '[STAR]',
        '🎉': '[PARTY]'
    }
    
    cleaned = md_content
    for emoji, replacement in replacements.items():
        cleaned = cleaned.replace(emoji, replacement)
    
    return cleaned


def convert_markdown_to_pdf(
    md_content: str, 
    output_path: str, 
    template_path: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None
) -> bool:
    """
    Convert Markdown content to PDF using Pandoc.
    
    Args:
        md_content: Markdown content to convert
        output_path: Path where PDF should be saved
        template_path: Optional custom LaTeX template path
        metadata: Optional metadata for PDF (title, author, date)
    
    Returns:
        bool: True if conversion successful, False otherwise
    """
    if not validate_pandoc_installation():
        print("Error: Pandoc is not installed or not accessible")
        return False
    
    try:
        # Clean markdown content for LaTeX compatibility
        cleaned_content = clean_markdown_for_latex(md_content)
        
        # Create temporary file for markdown content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as temp_md:
            temp_md.write(cleaned_content)
            temp_md_path = temp_md.name
        
        # Prepare pandoc arguments for PDF generation
        args = [
            'pandoc',
            temp_md_path,
            '-o', output_path,
            '--pdf-engine=pdflatex',
            '--standalone',
            '--variable', 'geometry:margin=1in',
            '--variable', 'fontsize=11pt'
        ]
        
        # Add template if provided
        if template_path and os.path.exists(template_path):
            args.extend(['--template', template_path])
        
        # Add metadata if provided
        if metadata:
            for key, value in metadata.items():
                args.extend(['-M', f'{key}={value}'])
        
        # Run pandoc conversion
        result = subprocess.run(args, capture_output=True, text=True, timeout=60)
        
        # Clean up temporary file
        os.unlink(temp_md_path)
        
        if result.returncode == 0:
            print(f"✅ PDF generated successfully: {output_path}")
            return True
        else:
            print(f"❌ PDF generation failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error during PDF generation: {e}")
        return False


def generate_pdf_report(
    report_data: Dict[str, Any], 
    layout: str = 'brief',
    output_path: Optional[str] = None
) -> Optional[str]:
    """
    Generate PDF report from report data.
    
    Args:
        report_data: Report data dictionary
        layout: Layout type ('brief' or 'detailed')
        output_path: Optional custom output path
    
    Returns:
        str: Path to generated PDF, or None if failed
    """
    if not validate_pandoc_installation():
        print("Error: Pandoc is not installed or not accessible")
        return None
    
    # Generate markdown content (reuse existing functions)
    from app.density_report import generate_markdown_report
    from app.flow_report import generate_markdown_report as generate_flow_markdown
    
    # Determine report type and generate markdown
    if 'segments' in report_data:
        # Density report
        md_content = generate_markdown_report(
            report_data, 
            report_data.get('start_times', {}),
            include_per_event=True
        )
        report_type = 'density'
    else:
        # Flow report
        md_content = generate_flow_markdown(report_data)
        report_type = 'flow'
    
    # Generate output path if not provided
    if not output_path:
        timestamp = datetime.now().strftime('%Y-%m-%d-%H%M')
        output_path = f"reports/{datetime.now().strftime('%Y-%m-%d')}/{timestamp}-{report_type}-{layout}.pdf"
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Prepare metadata
    metadata = {
        'title': f'Run Density Analysis Report - {report_type.title()}',
        'author': 'Run Density Analysis System',
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Convert to PDF
    success = convert_markdown_to_pdf(md_content, output_path, metadata=metadata)
    
    if success:
        return output_path
    else:
        return None


def create_basic_latex_template() -> str:
    """Create a basic LaTeX template for PDF generation."""
    template = r"""
\documentclass[11pt]{article}
\usepackage[utf8]{inputenc}
\usepackage[margin=1in]{geometry}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{array}
\usepackage{parskip}
\usepackage{graphicx}
\usepackage{xcolor}
\usepackage{hyperref}

% Custom colors for LOS indicators
\definecolor{losgreen}{RGB}{34, 197, 94}
\definecolor{losyellow}{RGB}{234, 179, 8}
\definecolor{losred}{RGB}{239, 68, 68}

% Header and footer
\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{Run Density Analysis}
\fancyhead[R]{\today}
\fancyfoot[C]{\thepage}

% Title formatting
\title{\textbf{Run Density Analysis Report}}
\author{Run Density Analysis System}
\date{\today}

\begin{document}

\maketitle

% Content will be inserted here
$body$

\end{document}
"""
    return template


def save_latex_template(template_content: str, template_name: str) -> str:
    """Save LaTeX template to file."""
    templates_dir = "templates"
    os.makedirs(templates_dir, exist_ok=True)
    
    template_path = os.path.join(templates_dir, f"{template_name}.latex")
    
    with open(template_path, 'w') as f:
        f.write(template_content)
    
    return template_path


def setup_pdf_templates() -> Dict[str, str]:
    """Set up basic PDF templates."""
    templates = {}
    
    # Create basic template
    basic_template = create_basic_latex_template()
    basic_path = save_latex_template(basic_template, "pdf_basic")
    templates['basic'] = basic_path
    
    return templates


def test_pdf_generation() -> bool:
    """Test PDF generation with sample content."""
    if not validate_pandoc_installation():
        print("❌ Pandoc not available - cannot test PDF generation")
        return False
    
    # Create sample markdown content
    sample_md = """# Test PDF Generation

This is a test of the PDF generation system.

## Features

- Markdown to PDF conversion
- Custom LaTeX templates
- Professional formatting

## Status

✅ PDF generation is working correctly!
"""
    
    # Test conversion
    output_path = "test_output.pdf"
    success = convert_markdown_to_pdf(sample_md, output_path)
    
    # Check for PDF output
    if success and os.path.exists(output_path):
        print(f"✅ PDF report test successful: {output_path}")
        # Clean up test file
        os.remove(output_path)
        return True
    else:
        print("❌ PDF generation test failed")
        return False


if __name__ == "__main__":
    # Test PDF generation when run directly
    print("Testing PDF generation...")
    
    if validate_pandoc_installation():
        print("✅ Pandoc is available")
        test_pdf_generation()
    else:
        print("❌ Pandoc is not available")
        print("Please install Pandoc: https://pandoc.org/installing.html")
