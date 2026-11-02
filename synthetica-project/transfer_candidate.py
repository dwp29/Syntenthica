#!/usr/bin/env python3
"""Temporarily serve a hash-locked candidate to an authenticated CI job.

This is a transfer helper, not an installer, builder, or device tool. The ZIP
is opened read-only. Its SHA-256 is checked before the server starts and again
by the receiving CI job. A random bearer token is read from a private file and
never logged. GET / is only a harmless status page; GET /archive and POST
/finish require the token. The release remains a draft and the server should be
stopped when the transfer finishes.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import os
import re
import socket
import stat
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CHUNK = 1024 * 1024


def snapshot(st: os.stat_result) -> tuple[int, int, int, int, int]:
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def verify_input(path: Path, expected_size: int, expected_sha256: str) -> tuple[int, ...]:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("invalid expected SHA-256")
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size != expected_size:
        raise ValueError("candidate is not a regular file of the expected size")
    digest = hashlib.sha256()
    with path.open("rb") as f:
        opened = snapshot(os.fstat(f.fileno()))
        if opened != snapshot(before):
            raise ValueError("candidate changed while opening")
        while block := f.read(CHUNK):
            digest.update(block)
        if snapshot(os.fstat(f.fileno())) != opened or snapshot(path.lstat()) != opened:
            raise ValueError("candidate changed while hashing")
    if digest.hexdigest() != expected_sha256:
        raise ValueError("candidate SHA-256 did not match the verified build")
    return opened


def make_server(host: str, port: int, archive: Path, size: int, token: str,
                expected_snapshot: tuple[int, ...]) -> ThreadingHTTPServer:
    if len(token) < 40 or len(token) > 256 or not re.fullmatch(r"[A-Za-z0-9_-]+", token):
        raise ValueError("token must be a high-entropy URL-safe string")
    auth = "Bearer " + token

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "SyntheticaTransfer/1"
        sys_version = ""

        def log_message(self, fmt: str, *args: object) -> None:
            # Do not log the URL, authorization header, addresses, or token.
            return

        def _reply(self, code: int, data: bytes = b"", *, send_body: bool = True) -> None:
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if send_body and data:
                self.wfile.write(data)

        def _authorized(self) -> bool:
            return hmac.compare_digest(self.headers.get("Authorization", ""), auth)

        def _archive(self, send_body: bool) -> None:
            if not self._authorized():
                self._reply(401, b"Authorization required.\n", send_body=send_body)
                return
            start = 0
            range_header = self.headers.get("Range")
            if range_header:
                match = re.fullmatch(r"bytes=(\d+)-", range_header)
                if not match:
                    self._reply(416, b"Unsupported range.\n", send_body=send_body)
                    return
                start = int(match.group(1))
                if start >= size:
                    self._reply(416, b"Range outside file.\n", send_body=send_body)
                    return
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            try:
                fd = os.open(archive, flags)
                with os.fdopen(fd, "rb") as f:
                    if snapshot(os.fstat(f.fileno())) != expected_snapshot or snapshot(archive.lstat()) != expected_snapshot:
                        self._reply(409, b"Source file changed.\n", send_body=send_body)
                        return
                    self.send_response(206 if range_header else 200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Length", str(size - start))
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    if range_header:
                        self.send_header("Content-Range", f"bytes {start}-{size - 1}/{size}")
                    self.end_headers()
                    if not send_body:
                        return
                    f.seek(start)
                    remaining = size - start
                    while remaining:
                        block = f.read(min(CHUNK, remaining))
                        if not block:
                            raise OSError("source file ended unexpectedly")
                        self.wfile.write(block)
                        remaining -= len(block)
                    if snapshot(os.fstat(f.fileno())) != expected_snapshot or snapshot(archive.lstat()) != expected_snapshot:
                        print("Transfer source changed; recipient must reject via SHA-256.", flush=True)
            except (BrokenPipeError, ConnectionResetError, socket.timeout):
                print("Transfer connection interrupted; a verified receiver may retry.", flush=True)
            except OSError:
                self.close_connection = True
                print("Transfer read failed; recipient must reject incomplete data.", flush=True)

        def do_HEAD(self) -> None:
            if self.path == "/":
                self._reply(200, b"Protected temporary ROM transfer; candidate is not tested.\n", send_body=False)
            elif self.path == "/archive":
                self._archive(False)
            else:
                self._reply(404, b"Not found.\n", send_body=False)

        def do_GET(self) -> None:
            if self.path == "/":
                self._reply(200, b"Protected temporary ROM transfer; candidate is not tested.\n")
            elif self.path == "/archive":
                self._archive(True)
            else:
                self._reply(404, b"Not found.\n")

        def do_POST(self) -> None:
            if self.path != "/finish":
                self._reply(404, b"Not found.\n")
            elif not self._authorized():
                self._reply(401, b"Authorization required.\n")
            else:
                self._reply(200, b"Transfer server stopping.\n")
                threading.Thread(target=self.server.shutdown, daemon=True).start()

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--size", type=int, required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--ttl-seconds", type=int, default=7200)
    args = parser.parse_args(argv)
    if args.size <= 0 or not 1 <= args.port <= 65535 or not 60 <= args.ttl_seconds <= 7200:
        parser.error("invalid archive size, port, or transfer lifetime")
    try:
        info = args.token_file.lstat()
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError("token file must be a private regular file")
        token = args.token_file.read_text(encoding="ascii").strip()
        locked_snapshot = verify_input(args.archive, args.size, args.sha256)
        server = make_server("0.0.0.0", args.port, args.archive, args.size, token, locked_snapshot)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Transfer setup failed: {exc}", file=sys.stderr)
        return 1
    print("Protected transfer is ready; the candidate remains untested on a device.", flush=True)
    timer = threading.Timer(args.ttl_seconds, server.shutdown)
    timer.daemon = True
    timer.start()
    try:
        server.serve_forever()
    finally:
        timer.cancel()
        server.server_close()
    print("Protected transfer server stopped.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
