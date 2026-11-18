"""Back up complete geographic campaign boundaries to the existing draft release."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

from paper.geographic_clustering import sha

REPOSITORY = 'httpsbina/gerrymander-detector'
RELEASE = 'continuation-snapshot-2026-11-02'


def verify_archive(archive, checksums):
    # Match the archive's member order to avoid repeated gzip seeks.
    with tarfile.open(archive) as stream:
        for name, expected in sorted(checksums.items()):
            if hashlib.file_digest(stream.extractfile(name), 'sha256').hexdigest() != expected:
                raise ValueError('Archive content checksum differs')


def backup(root, paper, campaign, manifest_path, destination):
    destination.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(manifest_path.read_text())
    release = json.loads(subprocess.check_output(['gh', 'release', 'view', RELEASE, '--repo', REPOSITORY, '--json', 'isDraft'], text=True))
    if not release['isDraft']:
        subprocess.run(['gh', 'release', 'edit', RELEASE, '--repo', REPOSITORY, '--draft'], check=True)
        release = json.loads(subprocess.check_output(['gh', 'release', 'view', RELEASE, '--repo', REPOSITORY, '--json', 'isDraft'], text=True))
    if not release['isDraft']:
        raise ValueError('Backup release is not draft')
    sources, links = {}, {}
    def add(path, checkout):
        if path.is_symlink():
            resolved = path.resolve()
            resolved.relative_to(checkout)
            links[str(Path(checkout.name) / path.relative_to(checkout))] = str(Path(checkout.name) / resolved.relative_to(checkout))
            path = resolved
        if path.is_file():
            name = str(Path(checkout.name) / path.relative_to(checkout))
            sources[name] = path
    for name in json.loads((campaign / 'manifest.json').read_text())['source_files']:
        add(root / name, root)
    for path in campaign.rglob('*'):
        if path.is_file() and path.suffix not in ('.log', '.lock'):
            add(path, root)
    for name in ['nc-baseline-freeze-23000', 'texas-baseline-freeze-70000']:
        path = root / 'deliverables' / name / 'freeze_manifest.json'
        add(path, root)
        for relative, expected in json.loads(path.read_text())['checksums'].items():
            if sha(root / relative) != expected:
                raise ValueError('Frozen checksum differs during backup')
            add(root / relative, root)
    for e in manifest['experiments'].values():
        add(root / e['dataset'], root)
    for path in (root / 'src').rglob('*.py'):
        add(path, root)
    add(root / 'main.py', root)
    add(root / 'requirements-research-macos-arm64-py312.txt', root)
    for directory in ['paper', 'docs']:
        for path in (paper / directory).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                add(path, paper)
    for path in (paper / 'outputs/analysis/geographic_measurement_20261109').iterdir():
        if path.is_file():
            add(path, paper)
    for state in ['nc', 'tx']:
        add(root / f'outputs/analysis/rdh_rebuild_2026-11-02/{state}_block_audit/blocks_master.csv', root)
    checksums = {name: sha(path) for name, path in sources.items()}
    name = 'geographic-' + destination.name + '.tar.gz'
    archive = destination / name
    with tarfile.open(archive, 'x:gz', compresslevel=1) as stream:
        for label, path in sorted(sources.items()):
            stream.add(path, arcname=label, recursive=False)
        data = (json.dumps({'files': checksums, 'symlinks': links, 'manifest': manifest,
                            'environment_asset': 'science-environment-macos-arm64-py312.tar.gz'}, indent=2) + '\n').encode()
        item = tarfile.TarInfo('BACKUP.json');item.size = len(data)
        stream.addfile(item, io.BytesIO(data))
    verify_archive(archive, checksums)
    digest = sha(archive)
    sidecar = destination / (archive.name + '.sha256')
    sidecar.write_text(digest + '  ' + archive.name + '\n')
    subprocess.run(['gh', 'release', 'upload', RELEASE, str(archive), str(sidecar), '--repo', REPOSITORY], check=True)
    assets = json.loads(subprocess.check_output(['gh', 'release', 'view', RELEASE, '--repo', REPOSITORY, '--json', 'isDraft,assets'], text=True))
    if not assets['isDraft']:
        raise ValueError('Release draft state changed')
    asset = next(a for a in assets['assets'] if a['name'] == archive.name)
    metadata = json.loads(subprocess.check_output(['gh', 'api', asset['apiUrl']], text=True))
    if metadata.get('digest') != 'sha256:' + digest:
        raise ValueError('Remote archive digest unavailable or different')
    record = {'archive': archive.name, 'sha256': digest, 'files_verified': len(checksums),
              'remote_digest_matches': True, 'isDraft': True, 'source_manifest_sha256': sha(manifest_path)}
    (destination / 'verification.json').write_text(json.dumps(record, indent=2) + '\n')
    return record
