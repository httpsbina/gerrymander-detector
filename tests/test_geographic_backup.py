"""Check archive contents without a network request or research inputs."""
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

from paper.geographic_backup import verify_archive


class GeographicBackupTests(unittest.TestCase):
    def test_checksum_lookup_order_does_not_change_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.tar.gz'
            data = {'next100.pkl': b'one', 'next1000.pkl': b'two', 'next200.pkl': b'three'}
            with tarfile.open(path, 'x:gz') as stream:
                for name, payload in sorted(data.items()):
                    info = tarfile.TarInfo(name);info.size = len(payload)
                    stream.addfile(info, io.BytesIO(payload))
            checksums = {name: hashlib.sha256(data[name]).hexdigest() for name in reversed(list(data))}
            verify_archive(path, checksums)

    def test_corrupted_content_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.tar.gz'
            with tarfile.open(path, 'x:gz') as stream:
                info = tarfile.TarInfo('fixture');info.size = 3
                stream.addfile(info, io.BytesIO(b'bad'))
            with self.assertRaisesRegex(ValueError, 'checksum differs'):
                verify_archive(path, {'fixture': hashlib.sha256(b'old').hexdigest()})


if __name__ == '__main__':
    unittest.main()
