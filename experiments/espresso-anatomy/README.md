# Espresso — visual example

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
