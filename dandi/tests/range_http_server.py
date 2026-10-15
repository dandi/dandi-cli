"""
An HTTP server supporting range requests (like S3), run in a separate process
for tests streaming files from it, and counting the range requests and bytes
it served

It runs in a separate process so that no thread of the tests' process serves
requests: a garbage collection in such a thread, while the thread reading a
file over HTTP holds h5py's global lock waiting for it, would deadlock if it
ran finalizers of h5py objects.
"""

from __future__ import annotations

from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import multiprocessing
from multiprocessing.sharedctypes import Synchronized
import os
from pathlib import Path
import re
import signal
import sys
from typing import Any


class _Server(ThreadingHTTPServer):
    ranged_requests: Synchronized
    bytes_served: Synchronized


class _Handler(SimpleHTTPRequestHandler):
    """
    A handler serving files with support for ``HEAD`` and single-range ``GET``
    requests
    """

    server: _Server

    def log_message(self, format: str, *args: Any) -> None:
        pass

    def _send_headers(
        self, status: HTTPStatus, length: int, content_range: str | None = None
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        if content_range is not None:
            self.send_header("Content-Range", content_range)
        self.end_headers()

    def do_HEAD(self) -> None:
        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._send_headers(HTTPStatus.OK, os.path.getsize(path))

    def do_GET(self) -> None:
        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        size = os.path.getsize(path)
        start, end = 0, size - 1
        if m := re.fullmatch(r"bytes=(\d+)-(\d*)", self.headers.get("Range", "")):
            start = int(m[1])
            end = min(int(m[2]) if m[2] else size - 1, size - 1)
            with self.server.ranged_requests.get_lock():
                self.server.ranged_requests.value += 1
            self._send_headers(
                HTTPStatus.PARTIAL_CONTENT,
                end - start + 1,
                f"bytes {start}-{end}/{size}",
            )
        else:
            self._send_headers(HTTPStatus.OK, size)
        with self.server.bytes_served.get_lock():
            self.server.bytes_served.value += end - start + 1
        with open(path, "rb") as fp:
            fp.seek(start)
            self.wfile.write(fp.read(end - start + 1))


def _exit(_signum: int, _frame: Any) -> None:
    sys.exit(0)


def _serve(
    directory: str,
    ranged_requests: Synchronized,
    bytes_served: Synchronized,
    port: Any,
) -> None:
    # Exit normally when terminated by `RangeHTTPServer.stop()`, so that exit
    # handlers run (e.g., saving coverage data when testing with coverage)
    signal.signal(signal.SIGTERM, _exit)
    server = _Server(("127.0.0.1", 0), partial(_Handler, directory=directory))
    server.ranged_requests = ranged_requests
    server.bytes_served = bytes_served
    port.put(server.server_address[1])
    server.serve_forever()


class RangeHTTPServer:
    """
    Serve the files in ``directory`` over HTTP, with support for range
    requests, from a separate process (until `stop()` is called) at `url`
    """

    def __init__(self, directory: Path) -> None:
        ctx = multiprocessing.get_context("spawn")
        self._ranged_requests: Synchronized = ctx.Value("q", 0)
        self._bytes_served: Synchronized = ctx.Value("q", 0)
        port = ctx.Queue()
        self._process = ctx.Process(
            target=_serve,
            args=(str(directory), self._ranged_requests, self._bytes_served, port),
            daemon=True,
        )
        self._process.start()
        self.url = f"http://127.0.0.1:{port.get(timeout=60)}"

    @property
    def ranged_requests(self) -> int:
        """The number of range requests served"""
        return int(self._ranged_requests.value)

    @property
    def bytes_served(self) -> int:
        """The number of bytes served"""
        return int(self._bytes_served.value)

    def stop(self) -> None:
        self._process.terminate()
        self._process.join()
