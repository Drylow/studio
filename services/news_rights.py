"""Require documented reuse rights before producing or automating news briefs."""


class RightsNotEstablished(ValueError):
    pass


LICENSES = {
    "CC0": "https://creativecommons.org/publicdomain/zero/1.0",
    "CC BY 2.0": "https://creativecommons.org/licenses/by/2.0",
    "CC BY 2.5": "https://creativecommons.org/licenses/by/2.5",
    "CC BY 3.0": "https://creativecommons.org/licenses/by/3.0",
    "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0",
    "CC BY-SA 2.0": "https://creativecommons.org/licenses/by-sa/2.0",
    "CC BY-SA 2.5": "https://creativecommons.org/licenses/by-sa/2.5",
    "CC BY-SA 3.0": "https://creativecommons.org/licenses/by-sa/3.0",
    "CC BY-SA 4.0": "https://creativecommons.org/licenses/by-sa/4.0",
    "Public domain": None,
}
# The owner keeps a voice provider whose terms restrict automated use (decision
# recorded 7 Oct 2026). The manifest states that choice instead of claiming a licence.
OWNER_RISK = "owner_accepted_risk"


def image_rights(visual):
    if not visual:
        return
    rights = visual.get("rights") or {}
    license_name = rights.get("license")
    if license_name not in LICENSES:
        raise RightsNotEstablished("Droits d'image non établis : un crédit ou un lien ne suffit pas.")
    if not rights.get("author") or not rights.get("reviewed_at") or not rights.get(
            "evidence_url", "").startswith("https://"):
        raise RightsNotEstablished("Auteur, date de contrôle et preuve de licence requis pour chaque image.")
    expected = LICENSES[license_name]
    if expected and rights.get("license_url", "").rstrip("/") != expected:
        raise RightsNotEstablished("L'adresse de la licence ne correspond pas à la licence déclarée.")
    if "BY-SA" in license_name and rights.get("adaptation_license") != license_name:
        raise RightsNotEstablished("La licence de l'image adaptée doit conserver le partage à l'identique.")


def automation_rights(plan):
    """Future publication gate; this function does not upload or publish anything.

    Voice API access and commercial reuse are separate permissions. A paid API
    key and a successful Content ID check are not documentary proof of either.
    """
    for segment in plan["segments"]:
        image_rights(segment.get("visual"))
    audio = plan.get("audio_rights") or {}
    voice = audio.get("voice") or {}
    granted = lambda key: voice.get(key) is True or (
        voice.get(key) == OWNER_RISK and str(voice.get("owner_decision", "")).strip())
    if (not granted("commercial_use") or not granted("automated_access")
            or not voice.get("evidence_url", "").startswith("https://") or not voice.get("reviewed_at")):
        raise RightsNotEstablished("L'automatisation exige une autorisation documentée pour la voix et l'accès API.")
    music = audio.get("music") or {}
    if music.get("kind") != "original_synthesized" or not music.get("generation_record"):
        raise RightsNotEstablished("Origine de la musique non établie : publication automatique bloquée.")
    if plan.get("external_clips"):
        raise RightsNotEstablished("Les extraits externes nécessitent une vérification dédiée avant automatisation.")
