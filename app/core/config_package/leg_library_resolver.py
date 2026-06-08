"""Resolve whether recipe legs load from org library or package segment_library."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from app.core.config_package.org_leg_library import get_org_legs_dir, load_org_leg_manifest
from app.core.config_package.segment_recipes import (
    load_package_segment_manifest,
    package_segment_library_dir,
)
from app.core.config_package.storage import resolve_config_package_path, validate_config_id
from app.core.course.segment_library import manifest_legs

LEG_SOURCE_ORG = "org"
LEG_SOURCE_PACKAGE = "package"


def effective_leg_source(package_manifest: Dict[str, Any]) -> str:
    """Org-primary for new packages; legacy packages with local legs stay on package."""
    explicit = str(package_manifest.get("leg_source") or "").strip().lower()
    if explicit in (LEG_SOURCE_ORG, LEG_SOURCE_PACKAGE):
        return explicit
    if manifest_legs(package_manifest):
        return LEG_SOURCE_PACKAGE
    return LEG_SOURCE_ORG


def recipe_leg_ids_from_package(config_id: str) -> Set[str]:
    """Leg ids referenced in any event recipe for this package."""
    manifest = load_package_segment_manifest(config_id)
    ids: Set[str] = set()
    for seq in (manifest.get("recipes") or {}).values():
        if not isinstance(seq, list):
            continue
        for raw in seq:
            lid = str(raw).strip()
            if lid:
                ids.add(lid)
    return ids


def resolve_leg_library(
    config_id: str,
) -> Tuple[Path, Dict[str, Any], str, Dict[str, Any]]:
    """
    Return (library_dir, leg_manifest, leg_source, package_manifest).

    ``leg_manifest`` holds leg GPX metadata. Recipes and flow_overrides always
    come from the package manifest when applying/exporting.
    """
    cid = validate_config_id(config_id)
    package_path = resolve_config_package_path(cid)
    pkg_manifest = load_package_segment_manifest(cid)
    source = effective_leg_source(pkg_manifest)

    if source == LEG_SOURCE_ORG:
        org_dir = get_org_legs_dir()
        org_manifest = load_org_leg_manifest()
        return org_dir, org_manifest, LEG_SOURCE_ORG, pkg_manifest

    lib_dir = package_segment_library_dir(package_path)
    return lib_dir, pkg_manifest, LEG_SOURCE_PACKAGE, pkg_manifest


def combined_manifest_for_apply(config_id: str) -> Tuple[Path, Dict[str, Any]]:
    """Org/package leg metadata + package recipes for segment export."""
    lib_dir, leg_manifest, _source, pkg_manifest = resolve_leg_library(config_id)
    combined = dict(leg_manifest)
    combined["recipes"] = pkg_manifest.get("recipes") or {}
    combined["flow_overrides"] = (
        pkg_manifest.get("flow_overrides")
        or leg_manifest.get("flow_overrides")
        or []
    )
    combined["label"] = pkg_manifest.get("label") or leg_manifest.get("label") or ""
    return lib_dir, combined
