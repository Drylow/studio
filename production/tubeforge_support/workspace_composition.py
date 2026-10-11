"""Fictional video composition contracts, applied during authoring and preflight."""
import re


RULES = (
    "ONE WIDE LANDSCAPE 16:9 illustration, a single physical scene filling the entire canvas "
    "edge to edge. Compose across the full width with readable environment on both sides. "
    "Every humanoid, including the protagonist, gods, companions, children, dwarves and undead, "
    "has an oversized perfectly circular smooth WHITE #FFFFFF cartoon head with a thick black "
    "outline, small black dot eyes and a tiny line mouth. NO eyebrows, nose, ears, hair or beard "
    "on ANY character. ALL exposed skin is pure bright WHITE #FFFFFF, including hands, arms "
    "and neck, exactly the same flat white as the face, with NO shading, gradients, gray, beige, "
    "cream, peach, tan or skin-tone variation. Simple rounded WHITE mitten hands, no detailed "
    "fingers. Adult-sized simplified bodies proportional to oversized heads, never tiny bodies. "
    "No children unless explicitly specified in this scene. ALL characters wear long sleeves "
    "and long pants; cloaks, armor, dresses or skirts go over covered limbs. "
    "The protagonist is the exact white round-headed "
    "avatar in reference image 1, wearing the described outfit; the outfit does not introduce "
    "a separate realistic hero. Preserve the reference's circular face geometry and the hero's "
    "red painted graphic marking; the red marking is not a change in skin color. Bodies are "
    "fully clothed; all characters are solid and opaque. Use costumes, props and simple markings "
    "for identity. No anatomical human faces, noses, ears or realistic beards. No duplicated "
    "identities, floating face portraits, superimposed memories, spectral copies, collages, "
    "inset panels, letterboxing, blurred sidebars or filler borders. A past event is drawn as "
    "a normal physical scene, never as a translucent overlay. No captions or watermarks. "
)


def compose(scene, style=""):
    # Authoring only: the image executor sends this already-saved prompt unchanged.
    scene = re.sub(r"\bKratos\b", "the round-white-headed warrior protagonist", scene, flags=re.I)
    style = style.removeprefix(RULES)
    style = re.sub(r"Current universe:.*?(?:\.|$)", "", style)
    return RULES + "\nDrawing style: " + style + "\nScene: " + scene.strip()


def contradictory(prompt):
    patterns = (
        r"\b(?:vertical|portrait|tall)\s+(?:composition|framing|layout|panel|format)\b",
        r"\b(?:as a distant memory|memory-like|appear ghostly|double[- ]exposure|split[- ]screen|multi[- ]panel)\b",
        r"\b(?:transparent|translucent|ghostly)\s+(?:character|figure|protagonist|warrior|face|body)\b",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, prompt, flags=re.I):
            clause = re.split(r"[.;\n]", prompt[:match.start()])[-1]
            if not re.search(r"\b(?:no|not|never|without|avoid)\b", clause, flags=re.I):
                return True
    return False


def ratio_matches(dimensions, aspect):
    width, height = dimensions
    a, b = (int(n) for n in aspect.split(":"))
    # Flow rounds image dimensions to its pixel grid; reject the wrong orientation/shape.
    return width > 0 and height > 0 and abs((width / height) / (a / b) - 1) <= .01
