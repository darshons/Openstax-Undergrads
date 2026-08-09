#!/usr/bin/env python3
"""Static file server with HTTP Range support, for review_player.html.

Chrome's <video> element requires 206 Partial Content responses to play
progressively; the stdlib's plain `python3 -m http.server` never sends
them, so video playback stalls forever even though the files are valid.
This adds Range handling with only the standard library.

Usage: python3 serve_review.py [port]  (default port 8934)
"""

import sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path


class RangeRequestHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        path = self.translate_path(self.path)
        if not Path(path).is_file():
            return super().send_head()

        file_size = Path(path).stat().st_size
        range_header = self.headers.get("Range")
        if range_header is None:
            self.send_response(200)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Content-Length", str(file_size))
            self.end_headers()
            return open(path, "rb")

        start, _, end = range_header.removeprefix("bytes=").partition("-")
        start = int(start) if start else 0
        end = int(end) if end else file_size - 1
        end = min(end, file_size - 1)
        length = end - start + 1

        self.send_response(206)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.send_header("Content-Length", str(length))
        self.end_headers()

        f = open(path, "rb")
        f.seek(start)
        return _BoundedReader(f, length)


class _BoundedReader:
    """Wraps a file object so copyfile() stops after `length` bytes."""

    def __init__(self, f, length):
        self._f = f
        self._remaining = length

    def read(self, size=-1):
        if self._remaining <= 0:
            return b""
        chunk = self._f.read(self._remaining if size < 0 else min(size, self._remaining))
        self._remaining -= len(chunk)
        return chunk

    def close(self):
        self._f.close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8934
    server = ThreadingHTTPServer(("", port), RangeRequestHandler)
    print(f"Serving on http://localhost:{port}/review_player.html")
    server.serve_forever()
