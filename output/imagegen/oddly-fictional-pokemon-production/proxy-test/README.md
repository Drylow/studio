# Separate proxy diagnostic tests — not episode selections

User requested an image-provider/style test, then chose to preserve the current
episode's visual style and repair it through Replicate with the same underlying
generation family. These diagnostic outputs are NOT inserted into the episode.

- Shot 11, shot 4, shot 145 and a simpler shot 4 prompt: API refused output,
  reporting an output-stage moderation category `other`. No usable scene returned.
- Empty-room control `000.png`: returned in 29 seconds, 1678x937. Actually viewed:
  drawn cream/red room, left window/blue bench and right mint counter retained.
  Some soft fill gradients; geometry/style broadly match the supplied master.
- Character-only control `004-identity-control.png`: returned in 23 seconds,
  1678x937. Actually viewed: large white circular head, simple eyes/mouth, red cap,
  blue jacket, dark long trousers, brown boots and white waving hand. Main costume
  and compact silhouette retained; more finger detail than a strict mitten.

This does NOT prove the cause of the four refusals, establish whole-scene
consistency or validate replacing the current episode's generator. The two
controls each use one image reference; the rejected scenes use multiple images.
No safeguard was disabled. Exact prompts are alongside these files. Full model
values, credentials, request identifiers and raw API diagnostics stay private.
