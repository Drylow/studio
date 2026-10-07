# Chocolate crunch — approved Watermelon world

Concept: the cute chef turns a giant fork into an absurd chocolate crunch test.

Vertical 1080×1920 at 60fps. Entire frame, including type, is drawn on a 216×384
pixel grid and enlarged exactly 5× with nearest-neighbour sampling. Warm cream
field, oak cutting board, dark green titles, white chef sleeve and tan mitten
hand are reused from Watermelon. A fixed three-quarter viewpoint keeps the
fork, slab contact and accumulating chocolate pieces readable.

Focal element: moulded chocolate slabs above a four-tined silver fork. Supporting
detail: rough brown fracture surfaces, short shadow, oak grain. Top anchor:
small chocolate icon, CHOCOLATE, large bar count, GIANT FORK. Bottom anchor:
CRUNCH TEST and the five quantity markers. Closing phrase: CHEF APPROVED.

Typography: the approved embedded 5×7 bitmap glyphs, 3× scale for count and 1×
for labels; no system font substitution. Tiny labels correspond to 35px output
height. Titles stay inside their own cream field.

Output palette inherited from Watermelon:
#f1e7d6 #203c2a #244c37 #47714a #6e9852 #a5bb76 #ef5867 #ff8291 #b93751
#f9af9f #f2f0c4 #c79565 #dfb27e #eacd9b #b4ac91 #6b6c51 #b7c2ba #def2e1
#352922 #16201f #efb07a #ffd09b #ffe59a.
Food-specific brown extension: #704530 #a46b46 #563426 #885438.
Lighting may use intermediate values; final quantisation always uses these 27.

Physical animation is computed offline at 240Hz, recorded at 120Hz and sampled
by absolute time. All slabs remain intact until actual fork contact. Debris
retains downward momentum and separates in uneven wedges; no glass tint, no
neat cubes, no fruit replaced by crystal. Stronger trials add more contacts,
not a faster playback clock. Audio follows the contact ledger.

Gentle camera drift and bounded pull-back allow the whole stack to fit, followed
by a closer view of the crunch. A brief clearing/reloading interval separates
trials in the same continuous tabletop scene. Spatula finish reuses the approved
small hop and seeded bitmap confetti. No motion blur, gradients, web UI or music.
