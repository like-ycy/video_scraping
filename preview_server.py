"""Serve the preview directory with HTTP byte-range support."""

from __future__ import annotations

import argparse
import os
import re
import shutil
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class RangeRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def send_head(self):
        self._range = None
        header = self.headers.get("Range") if self.command == "GET" else None
        if not header:
            return super().send_head()

        match = re.fullmatch(r"bytes=(\d*)-(\d*)", header.strip())
        path = self.translate_path(self.path)
        if not match or os.path.isdir(path):
            return super().send_head()

        try:
            file = open(path, "rb")
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return None

        size = os.fstat(file.fileno()).st_size
        start_text, end_text = match.groups()
        if start_text:
            start = int(start_text)
            end = min(int(end_text), size - 1) if end_text else size - 1
        elif end_text:
            length = int(end_text)
            start, end = max(0, size - length), size - 1
        else:
            file.close()
            return super().send_head()

        if start >= size or start > end:
            file.close()
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None

        self._range = (start, end)
        self.send_response(HTTPStatus.PARTIAL_CONTENT)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Last-Modified", self.date_time_string(os.path.getmtime(path)))
        self.end_headers()
        return file

    def copyfile(self, source, outputfile) -> None:
        if self._range is None:
            shutil.copyfileobj(source, outputfile)
            return

        start, end = self._range
        seek = getattr(source, "seek", None)
        if seek is None:
            raise TypeError("Range source must be seekable")
        seek(start)
        remaining = end - start + 1
        while remaining:
            chunk = source.read(min(64 * 1024, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)


def main() -> None:
    parser = argparse.ArgumentParser(description="启动支持视频快进的本地预览服务")
    parser.add_argument("--port", type=int, default=8005)
    args = parser.parse_args()
    ThreadingHTTPServer(("127.0.0.1", args.port), RangeRequestHandler).serve_forever()


if __name__ == "__main__":
    main()
