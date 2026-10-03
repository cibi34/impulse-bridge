"""Generate the demo assets of the `bridge-demo` source (data/fallback/assets/).

Three glTF 2.0 models and their previews, built from plain geometry with
the Python standard library only — reproducible, and free of third-party
rights (CC0):

  demo-cube.glb     1 m cube with an embedded checker texture (tests UVs and textures)
  demo-sphere.glb   sphere, 1 m across, smooth normals, metallic blue
  demo-column.glb   2.24 m column with plinth, fluted shaft and capital (stone)
  demo-*.png        512 × 512 previews, drawn by a small software rasterizer
  demo-image.png    a 1200 × 900 "still life" of all three, for the image asset

Units are metres, +Y is up; every model stands on y = 0, centred on x/z.

    python scripts/make_demo_assets.py
"""

from __future__ import annotations

import json
import math
import struct
import zlib
from array import array
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

OUT = Path(__file__).resolve().parent.parent / "data" / "fallback" / "assets"

Vec = tuple[float, float, float]


# ---------------------------------------------------------------------------
# Small vector helpers
# ---------------------------------------------------------------------------

def sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def norm(a: Vec) -> Vec:
    length = math.sqrt(dot(a, a)) or 1.0
    return (a[0] / length, a[1] / length, a[2] / length)


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c: float) -> float:
    c = 0.0 if c < 0 else 1.0 if c > 1 else c
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def hex_linear(code: str) -> Vec:
    r, g, b = (int(code[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b))


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

@dataclass
class Mesh:
    positions: list[Vec] = field(default_factory=list)
    normals: list[Vec] = field(default_factory=list)
    uvs: list[tuple[float, float]] = field(default_factory=list)
    triangles: list[tuple[int, int, int]] = field(default_factory=list)

    def vertex(self, p: Vec, n: Vec, uv: tuple[float, float]) -> int:
        self.positions.append(p)
        self.normals.append(norm(n))
        self.uvs.append(uv)
        return len(self.positions) - 1

    def triangle(self, a: int, b: int, c: int) -> None:
        """Adds a triangle wound counter-clockwise seen from outside (the glTF
        front face), whatever order the corners come in."""
        pa, pb, pc = self.positions[a], self.positions[b], self.positions[c]
        face = cross(sub(pb, pa), sub(pc, pa))
        if dot(face, face) < 1e-14:
            return  # degenerate
        n = self.normals[a]
        outward = (n[0] + self.normals[b][0] + self.normals[c][0],
                   n[1] + self.normals[b][1] + self.normals[c][1],
                   n[2] + self.normals[b][2] + self.normals[c][2])
        self.triangles.append((a, b, c) if dot(face, outward) > 0 else (a, c, b))

    def quad(self, a: int, b: int, c: int, d: int) -> None:
        self.triangle(a, b, c)
        self.triangle(a, c, d)

    def extend(self, other: Mesh) -> None:
        offset = len(self.positions)
        self.positions += other.positions
        self.normals += other.normals
        self.uvs += other.uvs
        self.triangles += [(a + offset, b + offset, c + offset) for a, b, c in other.triangles]

    def transformed(self, angle_y: float, move: Vec) -> Mesh:
        c, s = math.cos(angle_y), math.sin(angle_y)

        def rot(v: Vec) -> Vec:
            return (c * v[0] + s * v[2], v[1], -s * v[0] + c * v[2])

        out = Mesh(
            [tuple(a + b for a, b in zip(rot(p), move)) for p in self.positions],  # type: ignore[misc]
            [rot(n) for n in self.normals],
            list(self.uvs),
            list(self.triangles),
        )
        return out


def box(sx: float, sy: float, sz: float, y0: float = 0.0) -> Mesh:
    """An axis-aligned box standing on y0, centred on x/z; UVs 0..1 per face."""
    mesh = Mesh()
    hx, hz = sx / 2, sz / 2
    y1 = y0 + sy
    faces = [  # normal, four corners
        ((1, 0, 0), [(hx, y0, hz), (hx, y0, -hz), (hx, y1, -hz), (hx, y1, hz)]),
        ((-1, 0, 0), [(-hx, y0, -hz), (-hx, y0, hz), (-hx, y1, hz), (-hx, y1, -hz)]),
        ((0, 1, 0), [(-hx, y1, hz), (hx, y1, hz), (hx, y1, -hz), (-hx, y1, -hz)]),
        ((0, -1, 0), [(-hx, y0, -hz), (hx, y0, -hz), (hx, y0, hz), (-hx, y0, hz)]),
        ((0, 0, 1), [(-hx, y0, hz), (hx, y0, hz), (hx, y1, hz), (-hx, y1, hz)]),
        ((0, 0, -1), [(hx, y0, -hz), (-hx, y0, -hz), (-hx, y1, -hz), (hx, y1, -hz)]),
    ]
    for n, corners in faces:
        ids = [mesh.vertex(p, n, uv) for p, uv in zip(corners, [(0, 1), (1, 1), (1, 0), (0, 0)])]
        mesh.quad(*ids)
    return mesh


def sphere(radius: float, centre_y: float, rings: int = 32, segments: int = 64) -> Mesh:
    mesh = Mesh()
    for i in range(rings + 1):
        phi = math.pi * i / rings
        for j in range(segments + 1):
            theta = 2 * math.pi * j / segments
            n = (math.sin(phi) * math.cos(theta), math.cos(phi), math.sin(phi) * math.sin(theta))
            mesh.vertex((radius * n[0], centre_y + radius * n[1], radius * n[2]), n,
                        (j / segments, i / rings))
    row = segments + 1
    for i in range(rings):
        for j in range(segments):
            a, b = i * row + j, (i + 1) * row + j
            mesh.quad(a, b, b + 1, a + 1)
    return mesh


def lathe(profile: Callable[[float, float], float], y0: float, y1: float,
          segments: int, steps: int) -> Mesh:
    """A surface of revolution: radius = profile(t, theta) for t in 0..1
    between y0 and y1. Normals from the surface's partial derivatives."""
    mesh = Mesh()

    def point(t: float, theta: float) -> Vec:
        r = profile(t, theta)
        return (r * math.cos(theta), y0 + (y1 - y0) * t, r * math.sin(theta))

    eps = 1e-4
    for i in range(steps + 1):
        t = i / steps
        for j in range(segments + 1):
            theta = 2 * math.pi * j / segments
            p = point(t, theta)
            d_theta = sub(point(t, theta + eps), point(t, theta - eps))
            d_t = sub(point(min(1, t + eps), theta), point(max(0, t - eps), theta))
            n = norm(cross(d_theta, d_t))
            if dot(n, (p[0], 0, p[2])) < 0:
                n = (-n[0], -n[1], -n[2])
            mesh.vertex(p, n, (j / segments, 1 - t))
    row = segments + 1
    for i in range(steps):
        for j in range(segments):
            a, b = i * row + j, (i + 1) * row + j
            mesh.quad(a, b, b + 1, a + 1)
    return mesh


def column() -> Mesh:
    """Plinth, fluted and slightly tapering shaft, echinus, abacus: 2.24 m."""
    mesh = box(0.8, 0.18, 0.8)
    flutes = 20

    def shaft(t: float, theta: float) -> float:
        radius = 0.26 - 0.03 * t  # entasis-free taper
        groove = 0.5 + 0.5 * math.cos(flutes * theta)
        return radius * (1 - 0.035 * groove ** 2)

    mesh.extend(lathe(shaft, 0.18, 2.0, segments=flutes * 8, steps=8))
    mesh.extend(lathe(lambda t, _: 0.23 + 0.13 * math.sin(t * math.pi / 2), 2.0, 2.12, 96, 6))
    mesh.extend(box(0.82, 0.12, 0.82, y0=2.12))
    return mesh


# ---------------------------------------------------------------------------
# Materials and textures
# ---------------------------------------------------------------------------

@dataclass
class Material:
    name: str
    colour: Vec  # linear
    metallic: float
    roughness: float
    texture: Callable[[float, float], Vec] | None = None
    texture_png: bytes | None = None


MAGENTA = hex_linear("#ec008c")
PAPER = hex_linear("#f2f0ec")


def checker(u: float, v: float) -> Vec:
    return MAGENTA if (math.floor(u * 8) + math.floor(v * 8)) % 2 else PAPER


def png(width: int, height: int, rgb: bytes) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    stride = width * 3
    raw = b"".join(b"\x00" + rgb[y * stride : (y + 1) * stride] for y in range(height))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def texture_png(fn: Callable[[float, float], Vec], size: int = 256) -> bytes:
    data = bytearray()
    for y in range(size):
        for x in range(size):
            c = fn((x + 0.5) / size, (y + 0.5) / size)
            data += bytes(round(linear_to_srgb(v) * 255) for v in c)
    return png(size, size, bytes(data))


# ---------------------------------------------------------------------------
# glTF binary
# ---------------------------------------------------------------------------

def glb(name: str, mesh: Mesh, material: Material) -> bytes:
    blob = bytearray()
    views: list[dict] = []
    accessors: list[dict] = []

    def add_view(data: bytes, target: int | None) -> int:
        while len(blob) % 4:
            blob.append(0)
        view = {"buffer": 0, "byteOffset": len(blob), "byteLength": len(data)}
        if target:
            view["target"] = target
        blob.extend(data)
        views.append(view)
        return len(views) - 1

    def add_accessor(values: list, kind: str, extra: dict | None = None) -> int:
        flat = [c for v in values for c in v]
        view = add_view(struct.pack(f"<{len(flat)}f", *flat), 34962)
        accessors.append({"bufferView": view, "componentType": 5126, "count": len(values),
                          "type": kind, **(extra or {})})
        return len(accessors) - 1

    xs, ys, zs = zip(*mesh.positions)
    position = add_accessor(mesh.positions, "VEC3",
                            {"min": [min(xs), min(ys), min(zs)], "max": [max(xs), max(ys), max(zs)]})
    normal = add_accessor(mesh.normals, "VEC3")
    attributes = {"POSITION": position, "NORMAL": normal}
    if material.texture_png:  # texture coordinates only where a texture uses them
        attributes["TEXCOORD_0"] = add_accessor(mesh.uvs, "VEC2")
    flat_ids = [i for tri in mesh.triangles for i in tri]
    wide = len(mesh.positions) > 65535
    index_view = add_view(struct.pack(f"<{len(flat_ids)}{'I' if wide else 'H'}", *flat_ids), 34963)
    accessors.append({"bufferView": index_view, "componentType": 5125 if wide else 5123,
                      "count": len(flat_ids), "type": "SCALAR"})

    pbr: dict = {
        "baseColorFactor": [*material.colour, 1.0],
        "metallicFactor": material.metallic,
        "roughnessFactor": material.roughness,
    }
    doc: dict = {
        "asset": {"version": "2.0", "generator": "IMPULSE Curator demo assets",
                  "copyright": "CC0 1.0 — IMPULSE Curator"},
        "scene": 0,
        "scenes": [{"name": name, "nodes": [0]}],
        "nodes": [{"name": name, "mesh": 0}],
        "meshes": [{"name": name, "primitives": [{
            "attributes": attributes,
            "indices": len(accessors) - 1, "material": 0, "mode": 4}]}],
        "materials": [{"name": material.name, "pbrMetallicRoughness": pbr}],
    }
    if material.texture_png:
        image_view = add_view(material.texture_png, None)
        doc["images"] = [{"bufferView": image_view, "mimeType": "image/png"}]
        doc["samplers"] = [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}]
        doc["textures"] = [{"sampler": 0, "source": 0}]
        pbr["baseColorTexture"] = {"index": 0}
        pbr["baseColorFactor"] = [1.0, 1.0, 1.0, 1.0]
    while len(blob) % 4:
        blob.append(0)
    doc["accessors"] = accessors
    doc["bufferViews"] = views
    doc["buffers"] = [{"byteLength": len(blob)}]

    text = json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode()
    text += b" " * (-len(text) % 4)
    total = 12 + 8 + len(text) + 8 + len(blob)
    return (struct.pack("<III", 0x46546C67, 2, total)
            + struct.pack("<II", len(text), 0x4E4F534A) + text
            + struct.pack("<II", len(blob), 0x004E4942) + bytes(blob))


# ---------------------------------------------------------------------------
# A small software rasterizer for the previews
# ---------------------------------------------------------------------------

KEY = (norm((-0.55, 0.8, 0.65)), (1.05, 1.0, 0.95))
FILL = (norm((0.75, 0.35, -0.45)), (0.28, 0.31, 0.38))
RIM = (norm((0.1, 0.5, -1.0)), (0.35, 0.33, 0.45))
BG_TOP, BG_BOTTOM = hex_linear("#2c2c33"), hex_linear("#121214")
FLOOR = hex_linear("#3a3a42")


@dataclass
class Item:
    mesh: Mesh
    material: Material
    shadow: tuple[float, float, float]  # centre x, z and radius of a soft contact shadow


def render(items: list[Item], width: int, height: int, *, azimuth: float, elevation: float,
           ss: int = 2, fit: float = 1.12) -> bytes:
    W, H = width * ss, height * ss
    pts = [p for item in items for p in item.mesh.positions]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    centre = tuple((a + b) / 2 for a, b in zip(lo, hi))
    radius = math.dist(lo, hi) / 2
    fov = math.radians(30)
    aspect = W / H
    tan_v = math.tan(fov / 2)
    distance = radius / math.sin(min(fov, 2 * math.atan(tan_v * aspect)) / 2) * fit
    az, el = math.radians(azimuth), math.radians(elevation)
    eye = (centre[0] + distance * math.cos(el) * math.sin(az),
           centre[1] + distance * math.sin(el),
           centre[2] + distance * math.cos(el) * math.cos(az))
    forward = norm(sub(centre, eye))  # type: ignore[arg-type]
    right = norm(cross(forward, (0, 1, 0)))
    up = cross(right, forward)
    focal = (H / 2) / tan_v

    colour = array("f", bytes(4 * 3 * W * H))
    depth = array("f", [math.inf]) * (W * H)

    # Background, floor glow and contact shadows, by casting a ray per pixel.
    shadows = [item.shadow for item in items]
    floor_r = radius * 2.2
    for y in range(H):
        sy = (H / 2 - (y + 0.5)) / focal
        t_row = y / (H - 1)
        bg = tuple(a + (b - a) * t_row for a, b in zip(BG_TOP, BG_BOTTOM))
        for x in range(W):
            sx = ((x + 0.5) - W / 2) / focal
            d = (forward[0] + sx * right[0] + sy * up[0],
                 forward[1] + sx * right[1] + sy * up[1],
                 forward[2] + sx * right[2] + sy * up[2])
            c = bg
            if d[1] < 0:
                t = -eye[1] / d[1]
                hx, hz = eye[0] + t * d[0], eye[2] + t * d[2]
                glow = math.exp(-((hx - centre[0]) ** 2 + (hz - centre[2]) ** 2) / floor_r ** 2)
                shade = 1.0
                for cx, cz, r in shadows:
                    shade *= 1 - 0.7 * math.exp(-((hx - cx) ** 2 + (hz - cz) ** 2) / (r * r))
                c = tuple((b + (f - b) * glow) * shade for b, f in zip(bg, FLOOR))
            i = 3 * (y * W + x)
            colour[i], colour[i + 1], colour[i + 2] = c

    def to_camera(p: Vec) -> Vec:
        v = sub(p, eye)
        return (dot(v, right), dot(v, up), -dot(v, forward))

    for item in items:
        m, mat = item.mesh, item.material
        cam = [to_camera(p) for p in m.positions]
        screen = [(W / 2 + c[0] / -c[2] * focal, H / 2 - c[1] / -c[2] * focal, 1 / -c[2]) for c in cam]
        spec_colour = tuple(0.04 + (a - 0.04) * mat.metallic for a in mat.colour)
        shininess = max(4.0, (1 - mat.roughness) ** 2 * 160)
        spec_scale = (1 - mat.roughness) * 0.9 + 0.1
        for a, b, c in m.triangles:
            pa = m.positions[a]
            face = cross(sub(m.positions[b], pa), sub(m.positions[c], pa))
            if dot(face, sub(eye, pa)) <= 0:
                continue  # back face
            (x0, y0, w0), (x1, y1, w1), (x2, y2, w2) = screen[a], screen[b], screen[c]
            area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
            if area == 0:
                continue
            if area < 0:
                b, c = c, b
                (x1, y1, w1), (x2, y2, w2) = (x2, y2, w2), (x1, y1, w1)
                area = -area
            min_x, max_x = max(0, int(min(x0, x1, x2))), min(W - 1, int(max(x0, x1, x2)) + 1)
            min_y, max_y = max(0, int(min(y0, y1, y2))), min(H - 1, int(max(y0, y1, y2)) + 1)
            na, nb, nc = m.normals[a], m.normals[b], m.normals[c]
            pb, pc = m.positions[b], m.positions[c]
            ua, ub, uc = m.uvs[a], m.uvs[b], m.uvs[c]
            for py in range(min_y, max_y + 1):
                fy = py + 0.5
                for px in range(min_x, max_x + 1):
                    fx = px + 0.5
                    e0 = (x2 - x1) * (fy - y1) - (y2 - y1) * (fx - x1)
                    e1 = (x0 - x2) * (fy - y2) - (y0 - y2) * (fx - x2)
                    e2 = (x1 - x0) * (fy - y0) - (y1 - y0) * (fx - x0)
                    if e0 < 0 or e1 < 0 or e2 < 0:
                        continue
                    b0, b1, b2 = e0 / area * w0, e1 / area * w1, e2 / area * w2
                    iw = b0 + b1 + b2
                    z = 1 / iw
                    k = py * W + px
                    if z >= depth[k]:
                        continue
                    depth[k] = z
                    b0, b1, b2 = b0 * z, b1 * z, b2 * z
                    n = norm((b0 * na[0] + b1 * nb[0] + b2 * nc[0],
                              b0 * na[1] + b1 * nb[1] + b2 * nc[1],
                              b0 * na[2] + b1 * nb[2] + b2 * nc[2]))
                    p = (b0 * pa[0] + b1 * pb[0] + b2 * pc[0],
                         b0 * pa[1] + b1 * pb[1] + b2 * pc[1],
                         b0 * pa[2] + b1 * pb[2] + b2 * pc[2])
                    if mat.texture:
                        albedo = mat.texture(b0 * ua[0] + b1 * ub[0] + b2 * uc[0],
                                             b0 * ua[1] + b1 * ub[1] + b2 * uc[1])
                    else:
                        albedo = mat.colour
                    view = norm(sub(eye, p))
                    sky = 0.5 + 0.5 * n[1]
                    light = [0.20 * sky + 0.05, 0.21 * sky + 0.05, 0.25 * sky + 0.05]
                    spec = [0.0, 0.0, 0.0]
                    for direction, tint in (KEY, FILL, RIM):
                        lambert = dot(n, direction)
                        if lambert <= 0:
                            continue
                        h = norm((direction[0] + view[0], direction[1] + view[1], direction[2] + view[2]))
                        s = max(0.0, dot(n, h)) ** shininess * spec_scale * lambert
                        for ch in range(3):
                            light[ch] += lambert * tint[ch]
                            spec[ch] += s * tint[ch]
                    i = 3 * k
                    for ch in range(3):
                        colour[i + ch] = albedo[ch] * (1 - mat.metallic * 0.7) * light[ch] + spec[ch] * spec_colour[ch]

    out = bytearray()
    for y in range(height):
        for x in range(width):
            acc = [0.0, 0.0, 0.0]
            for dy in range(ss):
                for dx in range(ss):
                    i = 3 * ((y * ss + dy) * W + x * ss + dx)
                    for ch in range(3):
                        v = colour[i + ch]
                        acc[ch] += v / (1 + 0.25 * v)  # soft highlight roll-off
            out += bytes(round(linear_to_srgb(v / (ss * ss) * 1.12) * 255) for v in acc)
    return png(width, height, bytes(out))


# ---------------------------------------------------------------------------
# The assets
# ---------------------------------------------------------------------------

def main() -> None:
    checker_png = texture_png(checker)
    cube_mat = Material("Checker", (1.0, 1.0, 1.0), 0.0, 0.55, checker, checker_png)
    sphere_mat = Material("IMPULSE blue", hex_linear("#72a1d6"), 0.35, 0.3)
    stone = Material("Stone", hex_linear("#d9d2c4"), 0.0, 0.85)

    cube, ball, pillar = box(1, 1, 1), sphere(0.5, 0.5), column()
    models = {
        "demo-cube": (cube, cube_mat, (0.0, 0.0, 0.75)),
        "demo-sphere": (ball, sphere_mat, (0.0, 0.0, 0.45)),
        "demo-column": (pillar, stone, (0.0, 0.0, 0.6)),
    }
    for name, (mesh, material, shadow) in models.items():
        (OUT / f"{name}.glb").write_bytes(glb(name, mesh, material))
        preview = render([Item(mesh, material, shadow)], 512, 512, azimuth=35, elevation=22)
        (OUT / f"{name}.png").write_bytes(preview)
        print(f"{name}: {len(mesh.positions)} vertices, {len(mesh.triangles)} triangles")

    still_life = [
        Item(pillar.transformed(0.3, (-1.0, 0, -0.55)), stone, (-1.0, -0.55, 0.6)),
        Item(cube.transformed(-0.45, (0.95, 0, -0.35)), cube_mat, (0.95, -0.35, 0.75)),
        Item(ball.transformed(0, (0.05, 0, 0.55)), sphere_mat, (0.05, 0.55, 0.45)),
    ]
    image = render(still_life, 1200, 900, azimuth=18, elevation=14, fit=0.92)
    (OUT / "demo-image.png").write_bytes(image)
    print("demo-image: 1200 x 900")


if __name__ == "__main__":
    main()
