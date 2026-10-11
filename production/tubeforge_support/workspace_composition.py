"""Fictional video composition contracts, applied during authoring and preflight."""
import re


CAST_RULES = (
    "IDENTITY COUNT: Each named individual exists exactly ONCE in the entire image. "
    "If the protagonist is present, draw exactly ONE protagonist body and ONE protagonist "
    "head. The character reference depicts that SAME individual; it never adds another person. "
    "Other characters must have their own distinct costumes and markings; NEVER give another "
    "character the protagonist's red face stripe or identical hero outfit. Show one moment "
    "from one viewpoint. No clones, doubles, younger-and-older copies, mirror/reflection copies, "
    "dream versions, inset portraits or background duplicates of the same individual. "
    "Do not add the reference avatar to a scene whose cast excludes the protagonist. "
)


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
    "avatar in its explicitly assigned character identity reference, wearing the described outfit; the outfit does not introduce "
    "a separate realistic hero. Preserve the reference's circular face geometry and the hero's "
    "red painted graphic marking on the SAME anatomical side in every view; never mirror, omit "
    "or relocate the marking. The red marking is not a change in skin color. Bodies are "
    "fully clothed; all characters are solid and opaque. Use costumes, props and simple markings "
    "for identity. No anatomical human faces, noses, ears or realistic beards. No duplicated "
    "identities, floating face portraits, superimposed memories, spectral copies, collages, "
    "inset panels, letterboxing, blurred sidebars or filler borders. A past event is drawn as "
    "a normal physical scene, never as a translucent overlay. No captions or watermarks. "
) + CAST_RULES


def cast_rules(characters):
    """Record identity counts while authoring, never change a prompt during execution."""
    if characters == ["Kratos"]:
        return (CAST_RULES + "SOLO CAST: Exactly ONE person in the ENTIRE image: the round-white-headed "
                "warrior protagonist. One body, one head, two arms and two hands total. No other "
                "people anywhere, including the background, doorway, bed, reflections or pictures. ")
    cast = "; ".join(re.sub(r"\bKratos\b", "the round-white-headed warrior protagonist", c, flags=re.I)
                     for c in (characters or []))
    return CAST_RULES + ("Allowed cast identities or groups: " + cast + ". " if cast else "")


def compose(scene, style="", characters=None):
    # Authoring only: the image executor sends this already-saved prompt unchanged.
    scene = re.sub(r"\bKratos\b", "the round-white-headed warrior protagonist", scene, flags=re.I)
    style = style.removeprefix(RULES)
    style = re.sub(r"Current universe:.*?(?:\.|$)", "", style)
    return RULES + "\nDrawing style: " + style + "\nScene: " + scene.strip() + (
        "\n" + cast_rules(characters) if characters is not None else "")


def contradictory(prompt):
    patterns = (
        r"\b(?:vertical|portrait|tall)\s+(?:composition|framing|layout|panel|format)\b",
        r"\b(?:as a distant memory|memory-like|appear ghostly|double[- ]exposure|split[- ]screen|multi[- ]panel)\b",
        r"\b(?:transparent|translucent|ghostly)\s+(?:character|figure|protagonist|warrior|face|body)\b",
        r"\btwo copies of (?:the )?(?:same character|protagonist|hero|warrior)\b",
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
