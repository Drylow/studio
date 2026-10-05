"""Local package entry point using the same rebuilt studio as the website."""

import os
import sys

APP = os.path.dirname(os.path.abspath(__file__))
os.chdir(APP)
sys.path.insert(0, APP)
from studio.web import create_app

# This local package only listens on loopback and rejects non-local clients.
app = create_app({"LOCAL_OWNER": True})
if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5057
    print(f"Studio : http://127.0.0.1:{port}", flush=True)
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False, threaded=True)
