"""Ouvre le studio dans le navigateur dès que le serveur répond."""
import socket
import sys
import time
import webbrowser

port = int(sys.argv[1]) if len(sys.argv) > 1 else 5057
for _ in range(240):  # jusqu'à 2 minutes
    try:
        socket.create_connection(("127.0.0.1", port), 1).close()
        break
    except OSError:
        time.sleep(0.5)
webbrowser.open(f"http://127.0.0.1:{port}")
