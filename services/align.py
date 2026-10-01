"""Timings mot à mot précis de la voix off (sous-titres calés), via faster-whisper en local.

Les timings renvoyés par certains TTS (Algrow : SRT approximatif) arrivent ~0,3 s en retard en moyenne,
jusqu'à 1 s. Whisper (modèle « base.en », ~145 Mo, téléchargé une fois dans data/models/) les mesure
sur l'audio réel : ~13 s de calcul pour 3 min de voix sur un CPU ordinaire.

Optionnel : sans `pip install faster-whisper`, ou si le modèle est introuvable, words_from_audio()
renvoie None et le pipeline garde les timings du TTS.
"""
import os
import urllib.request

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FILES = ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt")
_model = None


def _model_dir(language="en"):
    name = "faster-whisper-base.en" if language == "en" else "faster-whisper-base"
    root = os.getenv("WHISPER_MODEL_DIR") or os.path.join(APP_DIR, "data", "models", name)
    if all(os.path.isfile(os.path.join(root, f)) for f in _FILES):
        return root
    os.makedirs(root, exist_ok=True)
    repo = "Systran/" + name
    for f in _FILES:  # téléchargement direct des fichiers (pas l'API du Hub, souvent limitée)
        dest = os.path.join(root, f)
        if not os.path.isfile(dest):
            urllib.request.urlretrieve(f"https://huggingface.co/{repo}/resolve/main/{f}", dest + ".part")
            os.replace(dest + ".part", dest)
    return root


def available():
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def words_from_audio(path, language="en"):
    """[{w, s, e}] mesurés sur l'audio, ou None si l'alignement n'est pas disponible."""
    global _model
    if not available():
        return None
    try:
        from faster_whisper import WhisperModel
        if _model is None:
            _model = WhisperModel(_model_dir(language), device="cpu", compute_type="int8")
        segs, _ = _model.transcribe(path, word_timestamps=True, language=language, beam_size=1)
        out = [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)} for s in segs for w in s.words]
        return out or None
    except Exception as e:  # noqa: BLE001 — jamais bloquant : on garde les timings du TTS
        print(f"[align] whisper indisponible : {e}", flush=True)
        return None
