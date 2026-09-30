"""Ouvre le studio dans le navigateur dès que le serveur répond (lancé par START_STUDIO.bat)."""
import socket
import time
import webbrowser

for _ in range(240):  # jusqu'à 2 minutes (premier lancement, installation des dépendances…)
    try:
        socket.create_connection(("127.0.0.1", 5000), 1).close()
        break
    except OSError:
        time.sleep(0.5)
webbrowser.open("http://127.0.0.1:5000")
