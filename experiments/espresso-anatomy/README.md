# Espresso — visual example, V1 archive

Silent 36-second 1920×1080 film, 30 fps. Custom dimensional espresso-machine study with an opening housing, connected circuit, boiler cutaway, moving flow markers and extraction into a cup. A generic simplified mechanism, not a manufacturer's engineering model. Editorial timing is compressed.

Visual reference: https://github.com/wheresryan22/anatomy . This project uses its own Three.js geometry and does not claim to be an Anatomy-toolkit output. No third-party video or generative image assets.

## Reproduce

```powershell
npm ci
npm run build
npm run check
npx hyperframes@0.8.147 preview --background
npx hyperframes@0.8.147 render --fps 30 --quality delivery --browser-gpu --gpu --workers 2 --output espresso-visual-36s.mp4
```

The composition is deterministic and all runtime dependencies are bundled locally. Font licenses are in assets/. The MP4 and runtime bundle are build artifacts, excluded from Git.

Review: opening, exploded pose, boiler and extraction snapshots inspected. HyperFrames check passes layout, runtime errors and contrast; NVIDIA's shader compiler emits a numeric-precision warning during environment-map setup. This warning did not prevent the inspected render.

## Current version: V2, following user feedback

Silent **48-second** explainer. The V1 camera-driven object study did not communicate the mechanism clearly. V2 holds four named components in a fixed cutaway, shows a moving pump piston, water heating, directed water flow, wet coffee grounds, then the rising drink level in the cup.

`node build.mjs` now copies `index-v2.html.source` to the single runtime entry `index.html` and bundles `scene-v2.js`. Render to `espresso-explication-v2.mp4` with the same render command above, changing only the output name. Original V1 source files are preserved in `versions/v1/`, and the original V1 MP4 is untouched. For V1 reproduction, copy those three source files back to a separate project with the same assets and package dependencies.

Technical basis: [La Marzocco GS3 manual](https://lamarzocco.com/ie/en/wp-content/uploads/2023/06/MAN.2.1.01_GS3_EN_V1.3-1.pdf) for heating before brewing and pump-driven water through the coffee boiler; [La Marzocco explanation of the three-way valve](https://www.lamarzoccousa.com/news/blog/3-way-solenoid-valve/) for the controlled boiler-to-group circuit. The drawing is a generic teaching model, not a GS3 reconstruction. Pump internals are schematic. Control valves, thermostat, overpressure circuit and steam circuit are omitted. Geometry, color and time are explanatory simplifications.

V2 QA: HyperFrames check passes lint, runtime errors, layout and text contrast at 2, 12, 21, 31, 40 and 46 seconds. The existing NVIDIA environment shader warning remains. The exported MP4 was decoded end to end without errors and inspected through its contact sheet and full-resolution pump/extraction frames: 1920×1080 H.264, 30 fps, 1440 frames, exactly 48 seconds, no audio stream. Labels were moved above the parts after the first inspection; the cup glaze and caption contrast were strengthened. Inspection files live in ignored `qa/` and `snapshots/` folders.
