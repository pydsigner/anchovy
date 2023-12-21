import pathlib

import pytest
import requests
import socket
import threading

from anchovy.server import ThreadedHTTPServer
from anchovy.test_harness import run_example


EXAMPLE_PATH = pathlib.Path(__file__).parent.parent / 'examples/' / 'basic_site.py'


def get_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('localhost', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture(scope='module')
def server(tmp_path_factory: pytest.TempPathFactory):
    tmp_path = tmp_path_factory.mktemp('server')
    context = run_example(EXAMPLE_PATH, tmp_path)
    directory = context['output_dir']
    port = get_port()
    server = ThreadedHTTPServer(('localhost', port), directory)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    thread.join()


def test_server(server: ThreadedHTTPServer):
    response = requests.get(f'http://localhost:{server.server_port}/')
    assert response.status_code == 200
    assert response.headers['content-type'] == 'text/html'


def test_server_etag(server: ThreadedHTTPServer):
    response = requests.get(f'http://localhost:{server.server_port}/')
    assert response.status_code == 200
    assert response.headers['content-type'] == 'text/html'
    etag = response.headers['etag']
    new_response = requests.get(f'http://localhost:{server.server_port}/', headers={'If-None-Match': etag})
    assert new_response.status_code == 304
