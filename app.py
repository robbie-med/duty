#!/usr/bin/env python3
"""Double-click start for The Way: runs the server on this computer and opens it in the usual browser.

The records are kept in the user's own folder, not beside the program:
  Windows  %APPDATA%\\The Way        macOS  ~/Library/Application Support/The Way        Linux  ~/.local/share/the-way
Close this window (or press Ctrl+C) to stop it. Nothing is sent anywhere: it answers only on 127.0.0.1.
"""
import os
import socket
import sys
import threading
import time
import webbrowser


def data_dir():
    if sys.platform.startswith("win"):
        return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "The Way")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/The Way")
    return os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "the-way")


def free_port(preferred=3517):
    for port in (preferred, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue


def main():
    os.environ.setdefault("FAMILY_DATA", data_dir())
    os.makedirs(os.environ["FAMILY_DATA"], exist_ok=True)
    port = free_port()
    os.environ["FAMILY_PORT"] = str(port)
    os.environ["FAMILY_HOST"] = "127.0.0.1"
    os.environ.pop("PUBLIC_HOST", None)
    import db                                    # read their settings only now, from the environment set above
    import library
    import server
    from http.server import ThreadingHTTPServer

    if not os.path.exists(library.LIB):
        print("Building the library index (a few seconds, first time only)…", flush=True)
        library.build()
    if server.own_mode():
        db.connect().close()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:%d/" % port
    print("The Way is running at %s\nYour records are kept in %s\nClose this window to stop it." % (url, os.environ["FAMILY_DATA"]), flush=True)
    webbrowser.open(url)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        httpd.shutdown()


if __name__ == "__main__":
    main()
