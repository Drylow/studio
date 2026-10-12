"""Explicit cast references: author once, validate without rewriting on execution.

Ports the project-over-style cast merge, visible-cast filtering and indexed identity
bindings of services/pov_engine.py (cast_list, _in_scene, _style_parts and character_sheet).
No legacy cast/reference truncation, provider substitution or services.ai dependency:
the author chooses every variant; execution sends the saved ordered references unchanged.
"""
import copy
import json

from fastapi import HTTPException
from app import store
from . import workspace_api as api


def registry(p):
    """A project entry explicitly replaces the same exact name's style entry."""
    merged = {}
    style = store.get_style(p.get("style_id")) or {}
    if "style_cast_snapshot" in p:
        style = {"workspace_cast_registry": p["style_cast_snapshot"]}
    for source in (style, p):
        entries = source.get("workspace_cast_registry") or {}
        if not isinstance(entries, dict):
            raise HTTPException(422, "Le registre des personnages doit être un objet")
        merged.update(copy.deepcopy(entries))
    if len({name.casefold() for name in merged if isinstance(name, str)}) != len(merged):
        raise HTTPException(422, "Le registre doit distinguer chaque identité par un nom unique")
    for name, entry in merged.items():
        if (not isinstance(name, str) or not name.strip() or name != name.strip()
                or not isinstance(entry, dict) or type(entry.get("required", True)) is not bool
                or not isinstance(entry.get("variants"), dict) or not entry["variants"]):
            raise HTTPException(422, "Une identité du registre est invalide")
        if "prompt_label" in entry and (not isinstance(entry["prompt_label"], str)
                or not entry["prompt_label"].strip() or entry["prompt_label"] != entry["prompt_label"].strip()):
            raise HTTPException(422, "Le libellé visuel du personnage doit être un texte non vide, sans espaces aux extrémités")
        for key, variant in entry["variants"].items():
            if (not isinstance(key, str) or not key.strip() or key != key.strip()
                    or not isinstance(variant, dict) or not isinstance(variant.get("description"), str)
                    or not variant["description"].strip() or not isinstance(variant.get("references"), list)
                    or not variant["references"]):
                raise HTTPException(422, "Une variante de personnage est incomplète")
    return merged


def style_summary(style):
    """Expose identities separately from scenery/style references."""
    output = []
    base = store.style_dir(style["id"])
    for name, entry in (style.get("workspace_cast_registry") or {}).items():
        variants = []
        for key, variant in entry.get("variants", {}).items():
            refs = []
            for ref in variant.get("references", []):
                digest = api._file_digest(base, ref.get("path"))
                refs.append({**copy.deepcopy(ref), "url": f"/style-media/{style['id']}/{ref['path']}",
                             "exists": bool(digest), "valid": bool(digest and digest == ref.get("sha256")
                                                                    and ref.get("review_state") == "verified")})
            variants.append({"id": key, "description": variant.get("description", ""), "references": refs})
        output.append({"name": name, "required": entry.get("required", True),
                       "main": name == style.get("workspace_main_character"), "variants": variants})
    return output


def summary(p):
    output = {name: {"required": entry.get("required", True), "variants": {
        key: variant["description"] for key, variant in entry["variants"].items()}}
        for name, entry in registry(p).items()}
    for name, entry in registry(p).items():
        if "prompt_label" in entry:
            output[name]["prompt_label"] = entry["prompt_label"]
    return output


def _reference(p, ref, name, key):
    if (not isinstance(ref, dict) or ref.get("owner") not in ("style", "project")
            or ref.get("character") != name or ref.get("variant") != key or ref.get("role") != "identity"
            or ref.get("review_state") != "verified" or not isinstance(ref.get("sha256"), str)
            or len(ref["sha256"]) != 64):
        raise HTTPException(422, "La référence d’identité doit être explicite, vérifiée et liée à sa variante")
    base = store.style_dir(p["style_id"]) if ref["owner"] == "style" else store.project_dir(p["id"])
    if api._file_digest(base, ref.get("path")) != ref["sha256"]:
        raise HTTPException(409, "Une référence d’identité est absente ou a changé")
    return copy.deepcopy(ref)


def selected(p, scene):
    entries = registry(p)
    cast = scene.get("characters") or []
    variants = scene.get("character_variants") or {}
    if (not isinstance(cast, list) or any(not isinstance(name, str) for name in cast)
            or not isinstance(variants, dict) or any(name not in cast or name not in entries for name in variants)):
        raise HTTPException(422, "Choisissez les variantes uniquement pour les personnages présents dans ce plan")
    if (len({name.strip().casefold() for name in cast}) != len(cast)
            or any(name not in entries and name.strip().casefold() in {key.casefold() for key in entries} for name in cast)):
        raise HTTPException(422, "Utilisez les noms exacts du registre, une fois par identité")
    output = []
    for name in cast:
        entry = entries.get(name)
        if not entry:
            continue
        key = variants.get(name)
        if key is None and not entry.get("required", True):
            continue
        if not isinstance(key, str) or key not in entry["variants"]:
            raise HTTPException(422, "Une variante explicite manque pour le personnage " + name)
        for ref in entry["variants"][key]["references"]:
            output.append(_reference(p, ref, name, key))
    return output


def _identity_key(ref):
    return tuple(ref.get(key) for key in ("owner", "path", "character", "variant", "role", "sha256", "review_state"))


def binding(p, scene):
    entries = registry(p)
    positional = (p.get("model_snapshot") or {}).get("image_provider") == "google_flow"
    lines = []
    for index, ref in enumerate(scene.get("references") or [], 1):
        if ref.get("role") != "identity":
            continue
        name, key = ref.get("character"), ref.get("variant")
        label = entries[name].get("prompt_label") or (
            "the round-white-headed warrior protagonist" if name == "Kratos" else name)
        description = entries[name]["variants"][key]["description"].strip()
        slot = f"Image {index} (@reference_{index})" if positional else f"Image {index}"
        lines.append(f"{slot}: {label}; variant {json.dumps(key)}; {description}")
    if not lines:
        return ""
    return ("IDENTITY REFERENCE BINDINGS (exact ordered attachments):\n" + "\n".join(lines)
            + "\nEach identity image depicts that same single named individual, not another person. "
              "Match the assigned costume and appearance only to its bound identity. "
              "Multiple views on an identity sheet show ONE person from different angles: "
              "choose the scene's angle and draw that identity exactly once, never copy the "
              "sheet layout, its second portrait or its plain background. "
              "Draw only this scene's listed cast; reference backgrounds never add people.")


def author(p, scene, base_refs=()):
    """Authoring helper; it does not save or generate media and is never called by execution."""
    identities = selected(p, scene)
    refs = copy.deepcopy(identities)
    seen = {(ref.get("owner"), ref.get("path")) for ref in refs}
    for ref in base_refs:
        if not isinstance(ref, dict):
            raise HTTPException(422, "La liste ordonnée de références est invalide")
        if (ref.get("role") == "identity" or ref.get("character") and ref["character"] not in scene.get("characters", [])
                or registry(p) and ref.get("role") == "protagonist-identity"):
            continue
        key = (ref.get("owner"), ref.get("path"))
        if key not in seen:
            refs.append(copy.deepcopy(ref))
            seen.add(key)
    return refs, binding(p, dict(scene, references=refs))


def validate(p, scene):
    """Fail before an image call; do not append references or change the saved prompt."""
    entries = registry(p)
    if not entries:
        return
    required = selected(p, scene)
    actual = [ref for ref in scene.get("references", []) if ref.get("role") == "identity"]
    if [_identity_key(ref) for ref in actual] != [_identity_key(ref) for ref in required]:
        raise HTTPException(422, "Les références d’identité du plan ne correspondent pas à son casting et ses variantes")
    # Both registry and actual attachment must remain reviewed and fingerprinted.
    for ref in actual:
        _reference(p, ref, ref["character"], ref["variant"])
    block = binding(p, scene)
    if block and block not in (scene.get("prompt") or ""):
        raise HTTPException(422, "Le prompt enregistré doit lier les indices des références aux bonnes identités et tenues")
