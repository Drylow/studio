"""Install complete Git-tracked TubeForge without a private ZIP.

See README_SURVIVOR_TUBEFORGE.md. Existing installations are updated with
workspace deployment --no-seed, never overwritten by this installer.
"""
from tubeforge_setup import main


if __name__ == "__main__":
    main()
