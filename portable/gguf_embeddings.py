"""Local BGE GGUF embeddings through a managed loopback llama.cpp server."""
import http.client
import json
import socket
import subprocess
import tempfile
import time
from .intelligence import LocalTools, _vector

# Use a numeric loopback address for sockets and the server. Darwin sandbox
# policy syntax still uses "localhost"; socket addresses need not use DNS.
LOOPBACK_HOST = '127.0.0.1'


class GGUFEmbedder:
    """Use pinned bundle assets; never resolve a model name over the network.

    Context-manager lifetime owns the subprocess. Requests use a direct loopback
    connection, ignoring proxy environment variables. OS egress policy is supplied
    by the operator during strict offline qualification.
    """
    def __init__(self, manifest, startup_timeout=120):
        self.tools = LocalTools(manifest)
        executable = self.tools.asset('llama_server')
        model = self.tools.asset('bge')
        with socket.socket() as probe:
            probe.bind((LOOPBACK_HOST, 0))
            self.port = probe.getsockname()[1]
        self.log = tempfile.TemporaryFile()
        self.process = subprocess.Popen([str(executable), '-m', str(model),
            '--embedding', '--pooling', 'cls', '--host', LOOPBACK_HOST,
            '--port', str(self.port), '--offline', '-c', '512', '-ngl', '0',
            '--device', 'none', '--no-repack'],
            stdin=subprocess.DEVNULL, stdout=self.log, stderr=self.log)
        deadline = time.monotonic() + startup_timeout
        try:
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    self.log.seek(0)
                    detail = self.log.read()[-6000:].decode('utf-8', errors='replace')
                    raise RuntimeError(
                        f'Embedding server exited before readiness (code {self.process.returncode}): {detail}')
                try:
                    self._request('GET', '/health')
                    break
                except (OSError, http.client.HTTPException, RuntimeError):
                    time.sleep(0.1)
            else:
                raise TimeoutError('Embedding server readiness timeout')
        except BaseException:
            self.close()
            raise

    def _request(self, method, path, value=None):
        connection = http.client.HTTPConnection(LOOPBACK_HOST, self.port, timeout=30)
        try:
            connection.request(method, path,
                body=None if value is None else json.dumps(value),
                headers={'Content-Type': 'application/json'})
            response = connection.getresponse()
            data = response.read()
            if response.status != 200:
                raise RuntimeError('Embedding HTTP status: ' + str(response.status))
            return json.loads(data)
        finally:
            connection.close()

    def encode(self, text, query=False):
        if not isinstance(text, str) or not text.strip():
            raise ValueError('Nonempty embedding text required')
        if query:
            text = 'Represent this sentence for searching relevant passages: ' + text
        data = self._request('POST', '/v1/embeddings', {'input': text})
        return _vector(data['data'][0]['embedding'])

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.log.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
