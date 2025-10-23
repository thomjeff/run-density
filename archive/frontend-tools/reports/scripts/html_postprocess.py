"""
Runflow HTML Post-Processor

Replaces tokens in HTML with embedded visuals and links.

Supported tokens:
- {{mini_map:S001}} → <img src="mini_maps/S001.png" ...>
- {{sparkline:S001}} → <img src="sparklines/S001.svg" ...>
- {{open_map:S001}} → <a href="../../map/output/map.html?focus=S001">Open on Map</a>

Author: AI Assistant (Cursor)
Issue: #265 - Phase 4: Report Integration & Storytelling
"""

from pathlib import Path
import re


def replace_tokens(html: str) -> str:
    """
    Replace visual and link tokens in HTML content.
    
    Args:
        html: HTML string with tokens
        
    Returns:
        str: HTML with tokens replaced by actual img/link tags
    """
    # {{mini_map:S001}} → <img src="mini_maps/S001.png" ...>
    html = re.sub(
        r"\{\{mini_map:([A-Za-z0-9_\-]+)\}\}",
        r'<img src="mini_maps/\1.png" alt="Mini map \1" width="200" height="120" style="border-radius:6px;"/>',
        html
    )
    
    # {{sparkline:S001}} → <img src="sparklines/S001.svg" ...>
    html = re.sub(
        r"\{\{sparkline:([A-Za-z0-9_\-]+)\}\}",
        r'<img src="sparklines/\1.svg" alt="Density sparkline \1" width="300" height="90"/>',
        html
    )
    
    # {{open_map:S001}} → deep link
    html = re.sub(
        r"\{\{open_map:([A-Za-z0-9_\-]+)\}\}",
        r'<a href="../../map/output/map.html?focus=\1" target="_blank" style="display:inline-block;padding:6px 12px;background:#2196F3;color:#fff;text-decoration:none;border-radius:4px;font-size:13px;font-weight:600;">Open on Map →</a>',
        html
    )
    
    return html

