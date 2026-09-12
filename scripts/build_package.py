#!/usr/bin/env python3
"""Build a standalone, disclosed audit ZIP from an explicit source allowlist."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def build(destination, profile='router', marker='1314520'):
    if destination.exists():
        raise ValueError('Output exists; preserve prior experiment packages')
    if profile not in ('zero', 'router') or not marker.isdecimal() or len(marker) > 16:
        raise ValueError('Unsupported profile or marker')
    files = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in [
        ROOT / 'agent.py', ROOT / 'bindings.json', ROOT / 'requirements.txt',
        *sorted((ROOT / 'answers').glob('*.html')), *sorted((ROOT / 'runtime').glob('*.cjs'))]}
    files['main.py'] = ("from agent import main\nif __name__ == '__main__':\n    raise SystemExit(main(profile="
                        + repr(profile) + ', marker=' + repr(marker) + '))\n').encode()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            item = zipfile.ZipInfo(name, date_time=(2026, 9, 13, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o644 << 16
            archive.writestr(item, content)
    return {'profile': profile, 'marker': marker, 'bytes': destination.stat().st_size,
            'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
            'archive': str(destination.resolve()), 'members': sorted(files)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--profile', choices=('zero', 'router'), default='router')
    parser.add_argument('--marker', default='1314520')
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.profile, args.marker), indent=2))
