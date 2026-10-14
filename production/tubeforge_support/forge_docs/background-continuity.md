# Background continuity and camera policy

Each channel preset has two independent visual settings:

- `background_mode`: `free` allows new scenery per shot; `consistent` requires inspected location masters.
- `camera_policy`: `stable` keeps the established side/axis through continuous action; `varied` retains the multiple-view planning rules used by survival channels.

The default remains `varied` for existing presets. Set `stable` for the fictional-life episodes; do not globally remove survival-channel angle variety. Character identity references remain independent of both settings.

User clarification: the stable-axis choice applies to Oddly Fictional Lives. Zombie and alien survival presets retain their varied-view policy. A damaged, cleared or landed state is a continuity change on the same axis, not a reason to rotate the camera. Keep that state in subsequent shots until the action changes it again.

Update a preset through `PUT /api/workspace/management/styles/{style_id}` with these fields, or through the channel/preset settings form. New projects freeze both values in `settings.visuals` and `style_snapshot`; changing a preset does not silently change existing films.

For consistent scenery, author a concrete location registry at `PUT /api/workspace/projects/{project_id}/locations` using the current `previous_hash`. Each space needs a fixed layout, world-space anchors, inspected/fingerprinted master and named views. Every selected view needs an inspected `location-view` image binding; the establishing view may bind the master image itself. A different angle is generated from the original master, inspected, named and retained before it is used in shots. Repeated stable views are permitted; inventing a reverse-side room is not.

Author shots with exact narration, real voice timestamps, location/view IDs, framing, new visual action, explicit cast variants and exact ordered image references. Include the saved location/camera contract and the indexed location/identity bindings in the saved prompt. The executor sends that prompt and those references unchanged. Empty registries, missing view images, changed image bytes and stale contracts block before generation. Free-background presets remain available.

Damage, repair, time and light are explicit story states of the same location, not replacements of its topology. Preserve original rejected frames/receipts and voices when rebuilding. Inspect every new output against its location reference before recording a review or rendering; hashes establish provenance, not visual correctness.

When the original geometry master and selected view differ, the selected view determines this shot's camera, framing, light and damage state. The original master only anchors permanent world geometry. Never tell the executor to copy "Image 1" as the camera without checking which indexed image is the selected view. For close shots, an inspected uniform crop of the master can prevent furniture from being enlarged or moved independently. A parked vehicle, cleared obstacle or broken railing stays in its subsequent state until a narrated action changes it.
