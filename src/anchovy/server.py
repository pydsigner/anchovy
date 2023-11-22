from __future__ import annotations

import argparse
import hashlib
import http.server
import mimetypes
import os
import pathlib
import typing
if typing.TYPE_CHECKING:
    from socketserver import _AfInetAddress


INDEX_FILE = 'index.html'
# Default used by nginx
DEFAULT_MIME_TYPE = 'application/octet-stream'


class ThreadedHTTPServer(http.server.ThreadingHTTPServer):
    """
    A simple HTTP server that handles each request in a separate thread.
    """
    RequestHandlerClass: typing.Type[http.server.SimpleHTTPRequestHandler]
    def __init__(self,
                  server_address: _AfInetAddress,
                  RequestHandlerClass: typing.Type[http.server.SimpleHTTPRequestHandler],
                  directory: str | pathlib.Path = '.',
                  bind_and_activate: bool = True) -> None:
        super().__init__(server_address, RequestHandlerClass, bind_and_activate)
        self.directory = str(directory)

    def finish_request(self, request, client_address) -> None:
        self.RequestHandlerClass(request, client_address, self, directory=self.directory)


class Handler(http.server.SimpleHTTPRequestHandler):
    def get_etag(self, file_path):
        """
        Generate an etag for a file based on its path and modification time.
        """
        mtime = os.path.getmtime(file_path)
        file_size = os.path.getsize(file_path)
        file_info = f"{file_size}-{mtime}"
        return hashlib.md5(file_info.encode('utf-8')).hexdigest()

    def do_GET(self):
        try:
            # Get the etag for the file
            file_path = pathlib.Path(self.translate_path(self.path))
            if file_path.is_dir():
                file_path /= INDEX_FILE

            # Double-check that we haven't escaped the directory.
            # self.translate_path() should discard any suspicious path
            # components, but it's better to be safe.
            if not file_path.is_relative_to(self.directory):
                return self.send_error(403, 'Forbidden')

            etag = self.get_etag(file_path)
            # Check if the client already has the file
            if 'If-None-Match' in self.headers and self.headers['If-None-Match'] == etag:
                self.send_response(304)
                self.end_headers()
            else:
                # Get the file extension and set the MIME type accordingly
                mime_type, _enc = mimetypes.guess_type(file_path)
                self.send_response(200)
                self.send_header('Content-type', mime_type or DEFAULT_MIME_TYPE)
                self.send_header('ETag', etag)
                self.end_headers()
                # Serve the file
                with open(file_path, 'rb') as file:
                    # Serve the file in chunks to avoid reading the entire file
                    # into memory
                    chunk_size = 8192
                    while True:
                        chunk = file.read(chunk_size)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
        except FileNotFoundError:
            self.send_error(404, f'File Not Found: {self.path}')


def serve(port: int, directory: str | pathlib.Path, host: str = 'localhost'):
    with ThreadedHTTPServer((host, port), Handler, directory=directory) as httpd:
        print(f'Serving at http://localhost:{port}')
        httpd.serve_forever()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port',
                        help='port to serve from',
                        type=int,
                        default=8080)
    parser.add_argument('-d', '--directory',
                        help='directory to serve',
                        type=pathlib.Path,
                        default='.')
    args = parser.parse_args()
    serve(args.port, args.directory)


if __name__ == '__main__':
    main()
