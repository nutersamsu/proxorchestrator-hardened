"""SFTP transfers must pipeline requests (they were limited to ~5 MB/s)."""

import io
import os
import tempfile
from unittest import mock

from django.test import SimpleTestCase

from apps.proxmox.sftp import ProxmoxSFTP


class _RemoteFile(io.BytesIO):
    def __init__(self, data=b""):
        super().__init__(data)
        self.prefetch_args = None
        self.pipelined = None

    def prefetch(self, file_size=None, max_concurrent_requests=None):
        self.prefetch_args = (file_size, max_concurrent_requests)

    def set_pipelined(self, pipelined=True):
        self.pipelined = pipelined

    def close(self):  # keep the buffer readable for assertions
        pass


class SftpPipeliningTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.client = ProxmoxSFTP("192.0.2.10", 22, "/nonexistent")
        self.client._sftp = mock.Mock()

    def test_get_uses_prefetching_getfo(self):
        data = os.urandom(3 * 1024 * 1024 + 5)
        self.client._sftp.stat.return_value = mock.Mock(st_size=len(data))

        def fake_getfo(path, fl, callback=None):
            fl.write(data)
            callback(len(data), len(data))
            return len(data)

        self.client._sftp.getfo.side_effect = fake_getfo
        dest = os.path.join(self.tmp.name, "disk.qcow2")
        seen = []
        self.client.get("/var/tmp/x.qcow2", dest, progress_callback=lambda d, t: seen.append((d, t)))
        self.client._sftp.open.assert_not_called()   # no slow read loop
        with open(dest, "rb") as fh:
            self.assertEqual(fh.read(), data)
        self.assertEqual(seen[-1], (len(data), len(data)))

    def test_get_detects_short_transfer(self):
        self.client._sftp.stat.return_value = mock.Mock(st_size=100)
        self.client._sftp.getfo.return_value = 50
        with self.assertRaises(IOError):
            self.client.get("/var/tmp/x", os.path.join(self.tmp.name, "x"))

    def test_put_is_pipelined(self):
        data = os.urandom(2 * 1024 * 1024 + 1)
        src = os.path.join(self.tmp.name, "disk.qcow2")
        with open(src, "wb") as fh:
            fh.write(data)
        remote = _RemoteFile()
        self.client._sftp.open.return_value = remote
        self.client.put(src, "/var/tmp/disk.qcow2")
        self.assertTrue(remote.pipelined)
        self.assertEqual(remote.getvalue(), data)
