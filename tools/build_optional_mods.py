"""Prepare a Proper Fixes payload from an extracted mobile asset pack."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import proper_world_effects

SAFE = re.compile(r"[a-z0-9_./-]+\Z")


def safe_path(name):
    name = name.replace('\\', '/').lower()
    if not SAFE.fullmatch(name) or name.startswith('/') or any(
            p in ('', '.', '..') for p in name.split('/')):
        raise ValueError(f'Unsafe asset path: {name!r}')
    return name


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def proper_allowed(name):
    parts = name.split('/')
    suffix = Path(name).suffix
    if name in ('anim/cuts.img', 'audio/streams/cutscene.osw', 'audio/streams/cutscene.osw.idx'):
        return True
    if name.startswith('data/maps/') and suffix in ('.ide', '.ipl'):
        return True
    if name.startswith('data/decision/allowed/') and suffix == '.ped':
        return True
    if name in ('data/carcols.dat', 'data/carmods.dat', 'data/furnitur.dat',
                'data/object.dat', 'data/plants.dat', 'data/procobj.dat',
                'data/vehicles.ide', 'data/water.dat'):
        return True
    if name.startswith('models/grass/') and suffix == '.dff':
        return True
    if len(parts) == 2 and parts[0] == 'texdb' and parts[1] in ('gta3.img', 'gta_int.img', 'cutscene.img'):
        return True
    return len(parts) == 3 and parts[0] == 'texdb' and parts[1] in ('gta3', 'gta_int', 'cutscene') and parts[2] in (
        parts[1] + '.txt', parts[1] + '.dxt.dat', parts[1] + '.dxt.tmb', parts[1] + '.dxt.toc', parts[1] + '.unc.tmb')


def validate_img(path):
    size = path.stat().st_size
    with path.open('rb') as f:
        tag, count = struct.unpack('<4sI', f.read(8))
        if tag != b'VER2' or not 0 < count <= 30000 or 8 + count*32 > size:
            raise ValueError(f'Invalid IMG header: {path}')
        names = set()
        for _ in range(count):
            offset, sectors, archive, raw = struct.unpack('<IHH24s', f.read(32))
            name = raw.split(b'\0')[0].decode('ascii').lower()
            if name in names or not re.fullmatch(r'[ -~]+', name) or '/' in name or '\\' in name or not sectors or archive not in (0, sectors) or offset*2048 < 8+count*32 or (offset+sectors)*2048 > size:
                raise ValueError(f'Invalid IMG entry: {path}: {name}')
            names.add(name)
    return count


def validate_texture_database(out, db, optional=False):
    base = out / 'texdb' / db / db
    paths = [Path(str(base) + s) for s in ('.txt', '.dxt.dat', '.dxt.toc', '.dxt.tmb', '.unc.tmb')]
    present = [p.is_file() for p in paths]
    # 2.1.1 omits cutscene textures; partial replacement databases still fail.
    if optional and not any(present):
        return False
    if not all(present):
        raise ValueError(f'Incomplete texture database: {db}')
    toc = paths[2].read_bytes()
    if len(toc) < 8 or len(toc) % 4 or struct.unpack_from('<I', toc)[0] != paths[1].stat().st_size:
        raise ValueError(f'Invalid texture offsets: {db}')
    limit = paths[1].stat().st_size
    for offset, in struct.iter_unpack('<I', toc[4:]):
        if offset != 0xffffffff and offset + 16 > limit:
            raise ValueError(f'Texture offset outside DAT: {db}')
    return True


def build_proper(root, out):
    roots = [p.parent.parent for p in root.rglob('gta3.img') if p.parent.name.lower() == 'texdb']
    if len(roots) != 1:
        raise ValueError('Expected one Proper Fixes mobile files directory')
    game = roots[0]
    copied = set()
    for path in sorted(game.rglob('*')):
        if not path.is_file():
            continue
        if path.is_symlink():
            raise ValueError('Symlink in mod')
        name = safe_path(path.relative_to(game).as_posix()).replace('.rename.', '.dxt.')
        if not proper_allowed(name) or name in copied:
            raise ValueError(f'Unsupported/duplicate Proper Fixes asset: {name}')
        copied.add(name)
        dest = out / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
        if name.endswith('.img'):
            validate_img(dest)
    databases = [db for db in ('gta3', 'gta_int', 'cutscene')
                 if validate_texture_database(out, db, optional=(db == 'cutscene'))]
    for required in ('anim/cuts.img', 'texdb/gta3.img', 'texdb/gta_int.img', 'texdb/cutscene.img'):
        if required not in copied:
            raise ValueError(f'Missing {required}')
    effects = proper_world_effects.apply(out / 'texdb/gta3.img')
    validate_img(out / 'texdb/gta3.img')
    return {'files': len(copied), 'texture_format': 'dxt',
            'texture_databases': databases, 'savr_world_effects': effects}


def build(root, out, kind):
    if kind != "properfixes":
        raise ValueError("Unsupported pack")
    roots = list(root) if isinstance(root, (list, tuple)) else [root]
    roots, out = [Path(p).resolve() for p in roots], out.resolve()
    if len(roots) != 1:
        raise ValueError('Proper Fixes requires exactly one extracted pack')
    if out.exists() or any(out == p or p in out.parents or out in p.parents for p in roots):
        raise ValueError('Output must be a new directory outside the source pack')
    if any(not p.exists() for p in roots):
        raise ValueError('Source pack does not exist')
    if any(root.is_symlink() or any(p.is_symlink() for p in root.rglob('*')) for root in roots):
        raise ValueError('Links are not supported inside a mod pack')
    out.mkdir(parents=True)
    info = build_proper(roots[0], out)
    # Keep the pack's original attribution alongside, never in the game lookup map.
    credits = out / '_credits'
    for i, path in enumerate(sorted(p for root in roots for p in root.rglob('*.txt'))):
        if 'credit' in path.name.lower() or 'readme' in path.name.lower():
            credits.mkdir(exist_ok=True)
            shutil.copyfile(path, credits / f'{i:03d}.txt')
    return seal_payload(out, kind, info)


def seal_payload(out, kind, info):
    files = [p for p in sorted(out.rglob('*')) if p.is_file() and p.name not in ('manifest.tsv', 'install.json', 'SHA256SUMS')]
    records = [{'path': p.relative_to(out).as_posix(), 'size': p.stat().st_size, 'sha256': digest(p)} for p in files]
    text = f'SAVR_OPTIONAL_V1 {kind}\n' + ''.join(f"{r['size']}\t{r['path']}\n" for r in records if not r['path'].startswith('_credits/'))
    (out / 'manifest.tsv').write_text(text, encoding='ascii', newline='\n')
    manifest = out / 'manifest.tsv'
    records.append({'path': manifest.name, 'size': manifest.stat().st_size, 'sha256': digest(manifest)})
    report = {'schema': 1, 'kind': kind, 'details': info, 'files': records}
    generation = hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()[:24]
    report['generation'] = generation
    (out / 'install.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (out / 'SHA256SUMS').write_text(''.join(f"{r['sha256']}  {r['path']}\n" for r in records), encoding='ascii', newline='\n')
    summary = {'files': info['files']}
    print(json.dumps({'generation': generation, 'kind': kind,
                      'report': str((out/'install.json').resolve()), **summary}))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=('properfixes',))
    parser.add_argument('pack', type=Path, nargs='+')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build(args.pack, args.out, args.kind)
