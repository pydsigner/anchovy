import contextlib
import pathlib
import socket
import threading

import pytest
import requests

from anchovy.server import main, ThreadedHTTPServer
from anchovy.test_harness import run_example


EXAMPLE_PATH = pathlib.Path(__file__).parent.parent / 'examples/' / 'basic_site.py'


def get_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('localhost', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@contextlib.contextmanager
def run_server(directory: pathlib.Path, port: int):
    server = ThreadedHTTPServer(('localhost', port), directory)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield
    server.shutdown()
    thread.join()


@contextlib.contextmanager
def run_server_cli(directory: pathlib.Path, port: int):
    args = [
        '--port', str(port),
        '--directory', str(directory)
    ]
    thread = threading.Thread(target=main, args=(args,), daemon=True)
    thread.start()
    yield


@pytest.fixture(scope='module', params=[False, True])
def server(request, tmp_path_factory: pytest.TempPathFactory):
    tmp_path = tmp_path_factory.mktemp('server')
    context = run_example(EXAMPLE_PATH, tmp_path)
    directory = context['output_dir']
    port = get_port()
    runner = run_server if not request.param else run_server_cli
    with runner(directory, port):
        yield port


def test_server(server: int):
    response = requests.get(f'http://localhost:{server}/')
    assert response.status_code == 200
    assert response.headers['content-type'] == 'text/html'


def test_server_etag(server: int):
    response = requests.get(f'http://localhost:{server}/')
    assert response.status_code == 200
    assert response.headers['content-type'] == 'text/html'
    etag = response.headers['etag']
    new_response = requests.get(f'http://localhost:{server}/', headers={'If-None-Match': etag})
    assert new_response.status_code == 304


def test_server_stale_etag(server: int):
    response = requests.get(f'http://localhost:{server}/')
    assert response.status_code == 200
    assert response.headers['content-type'] == 'text/html'
    etag = response.headers['etag']
    new_response = requests.get(f'http://localhost:{server}/', headers={'If-None-Match': etag + '0'})
    assert new_response.status_code == 200


def test_server_404(server: int):
    response = requests.get(f'http://localhost:{server}/does_not_exist')
    assert response.status_code == 404
