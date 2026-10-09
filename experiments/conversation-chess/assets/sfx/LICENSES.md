# Sound effects provenance — Sopranos conversation pilot

All acquired through the normal cloud HTTP proxy with TLS verification; no destination-denial bypass. Downloaded 2026-10-09. Original sound files and page evidence retained under `source/` and `research/`.

## Recorded keyboard: primary typing sound

- Work: **Keyboard Soundpack #1 [Typing and Single Keystrokes]**
- Author: **unicaegames**
- Source page: https://opengameart.org/content/keyboard-soundpack-1-typing-and-single-keystrokes
- Download linked on that page: https://opengameart.org/sites/default/files/unicae_games_keyboard_soundpack_1_0.zip
- License shown on source page: **CC0 1.0 Universal** — https://creativecommons.org/publicdomain/zero/1.0/
- Included readme says free to use however you like.
- Author's description: keyboard Cherry KC 1000; recorded with Shure SM7B, post-processed with Izotope Neutron 2. These are recorded physical keystrokes, not sine-wave tones. Do not describe the switch mechanism as mechanical: manufacturer technology was not checked.
- Curated derivatives: `keyboard-clack-01.wav` to `keyboard-clack-08.wav` from single-key source recordings 006, 007, 013, 017, 019, 028, 030 and 032.
- Derivative processing: 48 kHz mono PCM16, high-pass 150 Hz, low-pass 7 kHz, onset silence trim, 2 ms fades, peak normalized to -12 dBFS. Original recordings unchanged.

## Recorded typewriter: optional alternate character

- Work: **Typewriter sounds**
- Author: **Cassie-OrbitGames**
- Source page: https://opengameart.org/content/typewriter-sounds
- Downloads linked on that page: https://opengameart.org/sites/default/files/typewriter6.wav and https://opengameart.org/sites/default/files/typewriter7.wav
- License shown on source page: **CC0 1.0 Universal** — https://creativecommons.org/publicdomain/zero/1.0/
- Author describes these as sounds recorded on their phone for a game.
- Curated derivatives: `typewriter-key-01.wav`, `typewriter-key-02.wav`.
- Derivative processing: 48 kHz mono PCM16, high-pass 140 Hz, low-pass 7 kHz, onset silence trim, 2 ms fades, peak normalized to -12 dBFS.

## Supplemental brief UI cues

- Work: **Interface Sounds (1.0)**
- Author: **Kenney**
- Source page: https://kenney.nl/assets/interface-sounds
- Download linked on that page: https://kenney.nl/media/pages/assets/interface-sounds/fa43c1dd4d-1677589452/kenney_interface-sounds.zip
- License both page and included `License.txt`: **CC0 1.0 Universal** — https://creativecommons.org/publicdomain/zero/1.0/
- Included license explicitly permits commercial use; credit is appreciated but not mandatory.
- Curated derivatives: `blunder-impact.wav` from `bong_001.ogg`; `brilliant-ui-confirmation.wav` from `confirmation_002.ogg`; `ui-tick.wav` from `click_001.ogg`.
- The confirmation is a supplemental UI cue, not a claim of a naturally recorded bell. These should not replace the recorded keyboard as the main typing sound.
- Derivative processing: 48 kHz mono PCM16, high-pass 100 Hz, low-pass 8 kHz, trimmed onset silence, 2 ms fades, restrained peak normalization. Asset-specific measurements and source hashes are in `sfx-manifest.json`.

## Inspection and scope

Source pages, archive licenses/readmes, actual PCM signal levels, duration and active onsets were checked. No audio listening tool was available; these assets are **not claimed to have been aurally auditioned**. The private preview WAVs are supplied for listening review. CC0 provenance applies to these added sounds only; it does not license The Sopranos footage or reference channel assets, and it does not guarantee absence of platform matching errors.
