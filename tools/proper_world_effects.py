"""Add cemetery and sign effects to supported Proper Fixes model revisions."""
import hashlib
import math
import struct

FX = 0x0253F2F8
NIGHT = 0x0253F2F9
MODELS = {
    'graveyard01_lawn.dff': 'd245ff3c560ca5aa3d86828e620ae362005238fa4e498a41d25b4a0b922f78f7',
    'sunset22_lawn.dff': '60b62697bebb4b48c2e188ecb6e9df94b7f9c0186375ed033132bd6874630ea2',
    'holsign03n_law.dff': '50e23406bc0adaf323e46ac85ee3e2f66a3f0f968f0d00bdf0a6e72a95747fce',
    'gwforum1_lae.dff': 'f85a536ae7e80212e7d8ec056296d8e80131ab2af1ef35e55ad0a353783e326d',
    'furniture_lae.dff': 'b20731271275e1ed2f7610749298bd0be3d1399a96baa6d417b3a11d90c9f830',
}


def chunks(data):
    pos = 0
    while pos < len(data):
        if pos + 12 > len(data):
            raise ValueError('Truncated RW chunk')
        kind, size, version = struct.unpack_from('<III', data, pos)
        end = pos + 12 + size
        if end > len(data):
            raise ValueError('RW chunk exceeds parent')
        yield kind, data[pos+12:end], version
        pos = end


def chunk(kind, data, version):
    return struct.pack('<III', kind, len(data), version) + data


def effect(position, kind, body):
    return struct.pack('<3fII', *position, kind, len(body)) + body


def fountain():
    # Center/top of the existing nozzle in model 5871's local coordinates.
    return [effect((16.0859375, -8.91796875, -1.30), 1,
                   b'water_fountain'.ljust(24, b'\0'))]


def neon():
    # Tiki Theatre is material 9 of Furniture_LAe (17503), not sunset22.
    # These rows follow its title panel bounds, 12cm outside the west face.
    colors = [(255, 190, 35), (65, 255, 80), (70, 115, 255), (255, 215, 45)]
    records = []
    for z in (-.4165625, 2.2134375):
        for i, rgb in enumerate(colors):
            y = -10.534 + (7.50525 * i / 3)
            # 80-byte light stream: steady, no reflection/flare/shadow, LOS
            # checked and night-only. Native pre-render owns time and fading.
            body = (bytes((*rgb, 255)) + struct.pack('<4f', 100., 0., .22, 0.) +
                    bytes((0, 0, 0, 0, 0x41)) +
                    b'coronastar'.ljust(24, b'\0') + bytes(24) + bytes(7))
            assert len(body) == 80
            records.append(effect((-33.0965625, y, z), 0, body))
    return records


def patch_geometry(data, records, light_sign, eldritch=False, forum=False, tiki=False):
    sections = list(chunks(data))
    sign_vertices = set()
    blue_vertices = set()
    if light_sign or eldritch or forum or tiki:
        raw = next(body for kind, body, _ in sections if kind == 1)
        flags, triangles, vertices, morphs = struct.unpack_from('<4I', raw)
        if flags & 0x1000000 or morphs != 1:
            raise ValueError('Unsupported sign geometry')
        uv_sets = (flags >> 16) & 255
        if not uv_sets:
            uv_sets = 2 if flags & 128 else 1 if flags & 4 else 0
        uv_start = 16 + (vertices*4 if flags & 8 else 0)
        tri_start = uv_start + vertices*8*uv_sets
        vertex_start = tri_start + triangles*8 + 24
        for i in range(triangles):
            a, b, material, c = struct.unpack_from('<4H', raw, tri_start+i*8)
            if eldritch and material in (5, 7, 8, 9):  # title, vertical sign, lower marquee
                sign_vertices.update((a, b, c))
            elif forum and material == 7:  # formumsgn_lae2
                sign_vertices.update((a, b, c))
            elif forum and material == 0:
                # RW stores vertex2, vertex1, material, vertex3 on disk.
                points = [struct.unpack_from('<3f', raw, vertex_start+j*12) for j in (b,a,c)]
                center = [sum(p[k] for p in points)/3 for k in range(3)]
                radius = math.hypot(*center[:2])
                u = [points[1][k]-points[0][k] for k in range(3)]
                v = [points[2][k]-points[0][k] for k in range(3)]
                normal = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
                length = math.sqrt(sum(n*n for n in normal))
                # The arch soffits and pillar sides face across/down into the
                # bays. Keep the outward cream faces and the roof unlit.
                if radius > 69 and center[2] < 5 and length > .001:
                    radial = abs((normal[0]*center[0]+normal[1]*center[1])/(length*radius))
                    if radial < .65 and normal[2]/length < .3:
                        blue_vertices.update((a,b,c))
            elif (light_sign and material in (7, 8, 9)) or (tiki and material == 9):
                uv = [struct.unpack_from('<2f', raw, uv_start+j*8) for j in (a, b, c)]
                area = abs((uv[1][0]-uv[0][0])*(uv[2][1]-uv[0][1]) -
                           (uv[1][1]-uv[0][1])*(uv[2][0]-uv[0][0]))
                # Sunset: the four printed tower signs and their shop panels.
                # Zero-area UV faces are the dark metal edges of the boxes.
                # Tiki's atlas also contains its red wall; only the right half
                # contains the title and the smaller Live Nude Show panel.
                if area > .01 and (not tiki or min(p[0] for p in uv) > .498):
                    sign_vertices.update((a, b, c))
        if len(sign_vertices) != (96 if eldritch else 24 if forum else 11 if tiki else 92):
            raise ValueError('Sign panel topology changed')
        if forum and not blue_vertices:
            raise ValueError('Forum arch topology changed')
    output = []
    saw_extension = False
    saw_night = False
    for kind, body, version in sections:
        if kind == 3:
            saw_extension = True
            plugins = []
            saw_fx = False
            for pk, pb, pv in chunks(body):
                if pk == FX:
                    count, = struct.unpack_from('<I', pb)
                    pb = struct.pack('<I', count + len(records)) + pb[4:] + b''.join(records)
                    saw_fx = True
                if pk == NIGHT and sign_vertices:
                    saw_night = True
                    if len(pb) != 4 + vertices*4 or not struct.unpack_from('<I', pb)[0]:
                        raise ValueError('Unsupported night vertex colors')
                    pb = bytearray(pb)
                    for index in sign_vertices:
                        pb[4+index*4:7+index*4] = bytes((235, 235, 235))
                    for index in blue_vertices:
                        pb[4+index*4:7+index*4] = bytes((35, 100, 235))
                    pb = bytes(pb)
                plugins.append(chunk(pk, pb, pv))
            if records and not saw_fx:
                plugins.append(chunk(FX, struct.pack('<I', len(records)) + b''.join(records), version))
            body = b''.join(plugins)
        output.append(chunk(kind, body, version))
    if not saw_extension:
        raise ValueError('Geometry has no extension')
    if sign_vertices and not saw_night:
        raise ValueError('Sign geometry has no night colors')
    return b''.join(output)


def patch_model(data, name):
    records = (fountain() if name == 'graveyard01_lawn.dff' else
               neon() if name == 'furniture_lae.dff' else [])
    size, = struct.unpack_from('<I', data, 4)
    count = 0

    def rewrite(body):
        nonlocal count
        result = []
        for kind, payload, version in chunks(body):
            if kind in (0x10, 0x1a):
                payload = rewrite(payload)
            elif kind == 0xf:
                count += 1
                payload = patch_geometry(payload, records, name == 'sunset22_lawn.dff',
                                         name == 'holsign03n_law.dff', name == 'gwforum1_lae.dff',
                                         name == 'furniture_lae.dff')
            result.append(chunk(kind, payload, version))
        return b''.join(result)

    patched = rewrite(data[:12+size])
    if count != 1:
        raise ValueError('Expected one model geometry')
    return patched


def apply(img):
    results = []
    with img.open('r+b') as f:
        tag, count = struct.unpack('<4sI', f.read(8))
        if tag != b'VER2':
            raise ValueError('Expected mobile IMG v2')
        directory = [struct.unpack('<IHH24s', f.read(32)) for _ in range(count)]
        for index, (offset, sectors, archive, raw_name) in enumerate(directory):
            name = raw_name.split(b'\0')[0].decode('ascii')
            if name not in MODELS:
                continue
            f.seek(offset*2048)
            original = f.read(sectors*2048)
            if hashlib.sha256(original).hexdigest() != MODELS[name]:
                results.append({'model': name, 'status': 'unrecognized revision; unchanged'})
                continue
            patched = patch_model(original, name)
            needed = (len(patched)+2047)//2048
            if needed > sectors:
                f.seek(0, 2)
                offset = (f.tell()+2047)//2048
                sectors = needed
            f.seek(offset*2048)
            f.write(patched.ljust(sectors*2048, b'\0'))
            f.seek(8+index*32)
            f.write(struct.pack('<IHH24s', offset, sectors, 0, raw_name))
            results.append({'model': name, 'status': 'SAVR world effects added',
                            'effects_added': (1 if name.startswith('graveyard') else
                                              8 if name == 'furniture_lae.dff' else 0)})
    return results
