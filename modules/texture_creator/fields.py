"""Continuous scalar fields for the Texture Creator (numpy only, no Qt).

A field is a periodic N×N float32 array in [0, 1] covering the 512-unit tile:
sample (row, col) sits at tile coordinates ((col + .5) * 512 / N, (row + .5) * 512 / N).
Every generator is seamless by construction (integer lattice frequencies, toroidal
distances, FFT filtering), so fields can be blended, warped and contoured without seams.
"""
from __future__ import annotations

import math

import numpy as np

TILE = 512.0


# ── helpers ────────────────────────────────────────────────────────────────
def _rng(seed):
    return np.random.default_rng(int(seed) & 0xFFFFFFFF)


def _grid(n):
    coords = (np.arange(n, dtype=np.float32) + .5) / n
    return np.meshgrid(coords, coords)  # X (columns), Y (rows), both in [0, 1)


def normalize(a):
    a = np.asarray(a, dtype=np.float32)
    lo, hi = float(a.min()), float(a.max())
    if hi - lo < 1e-9:
        return np.full_like(a, .5)
    return (a - lo) / (hi - lo)


def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / max(1e-9, e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def resample(field, n):
    """Periodic bilinear resampling to n×n."""
    if field.shape[0] == n:
        return field
    X, Y = _grid(n)
    return sample_unit(field, X, Y)


def sample_unit(field, u, v):
    """Bilinear periodic sampling at unit coordinates (u = x / 512, v = y / 512)."""
    n = field.shape[0]
    x = np.asarray(u, dtype=np.float64) * n - .5
    y = np.asarray(v, dtype=np.float64) * n - .5
    x0 = np.floor(x).astype(np.int64); y0 = np.floor(y).astype(np.int64)
    fx = (x - x0).astype(np.float32); fy = (y - y0).astype(np.float32)
    x0 %= n; y0 %= n; x1 = (x0 + 1) % n; y1 = (y0 + 1) % n
    top = field[y0, x0] * (1 - fx) + field[y0, x1] * fx
    bottom = field[y1, x0] * (1 - fx) + field[y1, x1] * fx
    return top * (1 - fy) + bottom * fy


def sample(field, x, y):
    """Sample at tile coordinates (0–512)."""
    return sample_unit(field, np.asarray(x) / TILE, np.asarray(y) / TILE)


def gradient(field):
    """Periodic central differences, per tile unit: (d/dx, d/dy)."""
    n = field.shape[0]
    gx = (np.roll(field, -1, 1) - np.roll(field, 1, 1)) * (n / (2 * TILE))
    gy = (np.roll(field, -1, 0) - np.roll(field, 1, 0)) * (n / (2 * TILE))
    return gx, gy


def blur(field, radius, angle=0.0, stretch=1.0):
    """Periodic (anisotropic) gaussian blur via FFT; radius in tile units."""
    n = field.shape[0]
    sigma = radius / TILE * n
    if sigma <= .05:
        return field
    k = np.fft.fftfreq(n)
    KX, KY = np.meshgrid(k, k)
    a = math.radians(angle)
    along = KX * math.cos(a) + KY * math.sin(a)
    across = -KX * math.sin(a) + KY * math.cos(a)
    s_along, s_across = sigma * max(1.0, stretch), sigma / max(1.0, stretch) if stretch > 1 else sigma
    kernel = np.exp(-2 * math.pi ** 2 * ((along * s_along) ** 2 + (across * s_across) ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(field) * kernel)).astype(np.float32)


# ── generators ─────────────────────────────────────────────────────────────
def _perlin_octave(n, fx, fy, rng, X, Y):
    angles = rng.random((fy, fx)) * 2 * math.pi
    gx, gy = np.cos(angles).astype(np.float32), np.sin(angles).astype(np.float32)
    x = X * fx; y = Y * fy
    x0 = np.floor(x).astype(np.int64); y0 = np.floor(y).astype(np.int64)
    dx = x - x0; dy = y - y0
    def corner(ix, iy, ox, oy):
        ix %= fx; iy %= fy
        return gx[iy, ix] * ox + gy[iy, ix] * oy
    n00 = corner(x0, y0, dx, dy); n10 = corner(x0 + 1, y0, dx - 1, dy)
    n01 = corner(x0, y0 + 1, dx, dy - 1); n11 = corner(x0 + 1, y0 + 1, dx - 1, dy - 1)
    u = dx * dx * dx * (dx * (dx * 6 - 15) + 10); v = dy * dy * dy * (dy * (dy * 6 - 15) + 10)
    return (n00 * (1 - u) + n10 * u) * (1 - v) + (n01 * (1 - u) + n11 * u) * v


def perlin(n, frequency=4, octaves=4, persistence=.5, lacunarity=2, mode="fbm", stretch=1, seed=0):
    """Continuous gradient noise; stretch > 1 makes streaks along X (fibres, grain)."""
    rng = _rng(seed); X, Y = _grid(n)
    total = np.zeros((n, n), np.float32); amplitude = 1.0; weight = 0.0
    fx, fy = max(1, int(round(frequency))), max(1, int(round(frequency * stretch)))
    for _ in range(int(octaves)):
        layer = _perlin_octave(n, fx, fy, rng, X, Y)
        if mode == "turbulence":
            layer = np.abs(layer)
        elif mode == "ridged":
            layer = (1 - np.abs(layer) * 1.6) ** 2
        total += layer * amplitude; weight += amplitude
        amplitude *= persistence; fx *= int(lacunarity); fy *= int(lacunarity)
        if fx > n or fy > n:
            break
    return normalize(total / max(weight, 1e-9))


def fibers(n, count=600, length=80, thickness=1.2, angle=0, spread=30, curl=.4, seed=0):
    """Thin flowing strands (paper fibres, hair, wood fibre): splatted streamlines, periodic blur."""
    rng = _rng(seed)
    count = int(count)
    flow = perlin(n, 2, 2, .5, 2, "fbm", 1, seed + 101)
    x = rng.random(count) * n; y = rng.random(count) * n
    base = np.radians(angle + (rng.random(count) - .5) * spread)
    weight = (.45 + .55 * rng.random(count)).astype(np.float32)
    acc = np.zeros(n * n, np.float32)
    steps = max(2, int(length / TILE * n))
    for _ in range(steps):
        ix = np.floor(x).astype(np.int64) % n; iy = np.floor(y).astype(np.int64) % n
        np.add.at(acc, iy * n + ix, weight)
        heading = base + (flow[iy, ix] - .5) * 2 * math.pi * curl
        x = (x + np.cos(heading)) % n; y = (y + np.sin(heading)) % n
    field = blur(acc.reshape(n, n), max(.35, thickness) * .5)
    top = float(np.percentile(field, 99.5)) or 1.0
    return np.clip(field / top, 0, 1).astype(np.float32)


def _worley(n, count, seed, jitter=1.0, warp=0.0):
    rng = _rng(seed)
    count = max(3, int(count))
    if jitter < 1:  # Jittered lattice: even cell sizes (leather grain, tiles, scales).
        side = max(2, int(round(math.sqrt(count))))
        iy, ix = np.divmod(np.arange(side * side), side)
        cells = np.stack([(ix + .5 + (rng.random(side * side) - .5) * jitter) / side,
                          (iy + .5 + (rng.random(side * side) - .5) * jitter) / side], 1) % 1
    else:
        cells = rng.random((count, 2))
    X, Y = _grid(n)
    if warp:
        X = (X + (perlin(n, 3, 3, .5, 2, "fbm", 1, seed + 7) - .5) * warp * .2) % 1
        Y = (Y + (perlin(n, 3, 3, .5, 2, "fbm", 1, seed + 8) - .5) * warp * .2) % 1
    px = X.reshape(-1, 1); py = Y.reshape(-1, 1)
    dx = np.abs(px - cells[:, 0].astype(np.float32)); dx = np.minimum(dx, 1 - dx)
    dy = np.abs(py - cells[:, 1].astype(np.float32)); dy = np.minimum(dy, 1 - dy)
    dist = np.sqrt(dx * dx + dy * dy)
    nearest = np.partition(dist, 1, axis=1)[:, :2]
    return (nearest[:, 0].reshape(n, n) * TILE, nearest[:, 1].reshape(n, n) * TILE)


def cracks(n, count=40, width=2.5, mode="cracks", jitter=1.0, warp=.5, seed=0):
    """Worley-based cracks (thin network), cells (rounded stones) or crackle (leather/paint)."""
    f1, f2 = _worley(n, count, seed, jitter, warp)
    edge = f2 - f1
    if mode == "cracks":
        return (1 - _smoothstep(0, max(.1, width), edge)).astype(np.float32)
    if mode == "cells":
        return normalize(f1)
    # crackle: domed cells separated by grooves, like leather grain or crazed paint
    return normalize(_smoothstep(0, max(.1, width) * 3, edge) * (1 - normalize(f1) * .6))


def veins(n, kind="wood", rings=12, distortion=1.0, detail=4, sharpness=2.0, direction="horizontal", seed=0):
    """Wood rings, marble veins or fine grain, all periodic (integer ring counts)."""
    X, Y = _grid(n)
    axis = Y if direction == "horizontal" else X
    other = X if direction == "horizontal" else Y
    noise = perlin(n, max(1, int(detail)), 4, .5, 2, "fbm" if kind != "marble" else "turbulence", 1, seed) - .5
    knots = perlin(n, 2, 2, .5, 2, "fbm", 1, seed + 5) - .5
    if kind == "wood":
        phase = rings * axis + distortion * noise * 2 + distortion * knots * 3 * np.sin(2 * math.pi * other)
        ring = phase - np.floor(phase)
        return normalize(ring ** max(.2, sharpness) + .15 * noise)
    if kind == "marble":
        wave = np.abs(np.sin(math.pi * (rings * axis + distortion * noise * 3)))
        return normalize((1 - wave) ** max(.2, sharpness))
    # grain: long streaks across the ring axis
    streak = perlin(n, max(1, int(detail)), 3, .55, 2, "fbm", max(1, rings), seed + 3)
    return streak if direction == "horizontal" else np.ascontiguousarray(streak.T)


_WEAVE_PERIOD = {"plain": 2, "twill": 3, "basket": 4, "satin": 5}


def weave(n, threads=16, pattern="plain", width=.82, roundness=.6, variation=.25, seed=0):
    """Woven cloth height field: warp/weft threads crossing over and under."""
    period = _WEAVE_PERIOD.get(pattern, 2)
    threads = max(period, int(math.ceil(int(threads) / period) * period))
    rng = _rng(seed)
    X, Y = _grid(n)
    cx = np.floor(X * threads).astype(np.int64); cy = np.floor(Y * threads).astype(np.int64)
    u = X * threads - cx; v = Y * threads - cy
    if pattern == "plain":
        warp_top = (cx + cy) % 2 == 0
    elif pattern == "twill":
        warp_top = (cx + cy) % 3 != 0
    elif pattern == "basket":
        warp_top = (cx // 2 + cy // 2) % 2 == 0
    else:
        warp_top = (cx * 2 + cy) % 5 == 0
    def profile(t):
        p = np.clip(1 - np.abs(2 * t - 1) / max(.05, width), 0, 1)
        return p ** (1 - .8 * roundness) * (1 - (1 - p) ** 2) ** roundness
    tone_x = 1 - variation * rng.random(threads).astype(np.float32)
    tone_y = 1 - variation * rng.random(threads).astype(np.float32)
    warp = profile(u) * tone_x[cx % threads] * (.65 + .35 * np.sin(math.pi * v))
    weft = profile(v) * tone_y[cy % threads] * (.65 + .35 * np.sin(math.pi * u))
    return normalize(np.where(warp_top, np.maximum(warp, weft * .55), np.maximum(weft, warp * .55)))


def gradient_field(n, kind="linear", angle=0, repeat=1):
    X, Y = _grid(n)
    a = math.radians(angle)
    if kind == "radial":
        value = np.sqrt((X - .5) ** 2 + (Y - .5) ** 2) / math.sqrt(.5)
    elif kind == "diamond":
        value = (np.abs(X - .5) + np.abs(Y - .5))
    elif kind == "triangle":
        # Seamless ramp: the direction is snapped to a whole number of repeats per tile.
        kx = int(round(math.cos(a) * max(1, int(repeat)))); ky = int(round(math.sin(a) * max(1, int(repeat))))
        if kx == 0 and ky == 0:
            kx = 1
        value = kx * X + ky * Y
        return (1 - np.abs(2 * (value - np.floor(value)) - 1)).astype(np.float32)
    else:
        value = (X - .5) * math.cos(a) + (Y - .5) * math.sin(a) + .5
    value = value * max(1, int(repeat))
    if repeat > 1:
        value = value - np.floor(value)
    return np.clip(value, 0, 1).astype(np.float32)


# ── operations ─────────────────────────────────────────────────────────────
def levels(a, low=0.0, high=1.0, gamma=1.0, invert="no", steps=0, contrast=1.0):
    """Curves / thresholds: input window, gamma, contrast around mid-grey, posterize."""
    t = np.clip((a - low) / max(1e-6, high - low), 0, 1)
    t = t ** (1 / max(.01, gamma))
    if contrast != 1:
        t = np.clip((t - .5) * contrast + .5, 0, 1)
    if int(steps) > 1:
        t = np.round(t * (int(steps) - 1)) / (int(steps) - 1)
    return (1 - t if invert == "yes" else t).astype(np.float32)


BLEND_MODES = ["mix", "multiply", "screen", "overlay", "soft light", "add", "subtract",
               "difference", "lighten", "darken", "height max"]


def blend(a, b, mode="multiply", opacity=1.0, mask=None):
    if mode == "multiply":
        r = a * b
    elif mode == "screen":
        r = 1 - (1 - a) * (1 - b)
    elif mode == "overlay":
        r = np.where(a < .5, 2 * a * b, 1 - 2 * (1 - a) * (1 - b))
    elif mode == "soft light":
        r = (1 - 2 * b) * a * a + 2 * b * a
    elif mode == "add":
        r = a + b
    elif mode == "subtract":
        r = a - b
    elif mode == "difference":
        r = np.abs(a - b)
    elif mode in ("lighten", "height max"):
        r = np.maximum(a, b)
    elif mode == "darken":
        r = np.minimum(a, b)
    else:
        r = b
    weight = opacity if mask is None else opacity * mask
    return np.clip(a * (1 - weight) + np.clip(r, 0, 1) * weight, 0, 1).astype(np.float32)


def warp(a, b, amount=24.0, mode="value", angle=0.0, turns=1.0):
    """Displace A by B: along an angle (value), down B's slope (gradient) or along a
    direction field where B encodes the heading (direction)."""
    n = a.shape[0]
    X, Y = _grid(n)
    if mode == "gradient":
        gx, gy = gradient(blur(b, 4))
        length = np.sqrt(gx * gx + gy * gy) + 1e-6
        dx, dy = gx / length * (b - .5) * 2, gy / length * (b - .5) * 2
    elif mode == "direction":
        heading = b * 2 * math.pi * turns + math.radians(angle)
        dx, dy = np.cos(heading), np.sin(heading)
    else:
        r = math.radians(angle)
        dx = (b - .5) * 2 * math.cos(r); dy = (b - .5) * 2 * math.sin(r)
    offset = amount / TILE
    return sample_unit(a, (X + dx * offset) % 1, (Y + dy * offset) % 1).astype(np.float32)


def multiscale(a, scales=3, falloff=.5, mode="add"):
    """Layer the same field at ×1, ×2, ×4… (tile-periodic) for multi-scale variation."""
    n = a.shape[0]
    X, Y = _grid(n)
    total = np.zeros_like(a); weight = 0.0; amplitude = 1.0
    for level in range(int(scales)):
        k = 2 ** level
        layer = sample_unit(a, (X * k) % 1, (Y * k) % 1)
        total = np.maximum(total, layer * amplitude) if mode == "max" else total + layer * amplitude
        weight += amplitude; amplitude *= falloff
    return normalize(total if mode == "max" else total / weight)


def erosion(a, strength=.6, iterations=6, angle=90.0, streak=24.0, seed=0):
    """Flow erosion: material is carried down-slope along gravity, leaving streaks and channels."""
    h = a.astype(np.float32).copy()
    r = math.radians(angle)
    for _ in range(int(iterations)):
        gx, gy = gradient(h)
        slope = np.sqrt(gx * gx + gy * gy)
        downhill = np.clip(-(gx * math.cos(r) + gy * math.sin(r)) * TILE, 0, None)
        flow = blur(slope * TILE * .02 + downhill * .02, max(1.0, streak), angle, stretch=6)
        h = h - strength * .15 * normalize(flow) * h
        h = blur(h, .6)
    detail = perlin(a.shape[0], 16, 2, .5, 2, "fbm", 1, seed) - .5
    return normalize(h + detail * .04 * strength)


def wear(a, amount=.5, edge_width=6.0, breakup=.6, seed=0):
    """Edge wear / scratches: high-pass (edges and peaks) broken up by noise, as a mask."""
    high = np.clip((a - blur(a, edge_width)) * 6 + .5, 0, 1)
    edges = _smoothstep(.55, .85, high)
    noise = perlin(a.shape[0], 8, 4, .55, 2, "fbm", 1, seed)
    scratches = _smoothstep(.75, .95, perlin(a.shape[0], 2, 3, .5, 2, "ridged", 12, seed + 4))
    mask = np.clip(edges * (1 - breakup + breakup * noise * 1.6) + scratches * breakup * .6, 0, 1)
    return _smoothstep(1 - amount, 1.0, mask * (.5 + amount)).astype(np.float32)


# ── field → contours (marching squares) ───────────────────────────────────
# Each case lists edge pairs; edges: 0 top, 1 right, 2 bottom, 3 left.
_CASES = {1: [(3, 2)], 2: [(2, 1)], 3: [(3, 1)], 4: [(0, 1)], 6: [(0, 2)], 7: [(3, 0)],
          8: [(3, 0)], 9: [(0, 2)], 11: [(0, 1)], 12: [(3, 1)], 13: [(2, 1)], 14: [(3, 2)]}


def iso_loops(field, level, margin=2):
    """Closed loops bounding {field >= level}, in tile coordinates.

    The periodic field is extended by ``margin`` wrapped samples and closed with
    a low border, so loops are closed; renderers clip to the tile. With an
    even-odd fill the union of loops is exactly the region above ``level``.
    """
    n = field.shape[0]
    ext = np.pad(field, margin, mode="wrap")
    ext = np.pad(ext, 1, mode="constant", constant_values=-1.0)
    h, w = ext.shape
    above = ext >= level
    tl, tr = above[:-1, :-1], above[:-1, 1:]
    bl, br = above[1:, :-1], above[1:, 1:]
    code = (tl.astype(np.int8) << 3) | (tr.astype(np.int8) << 2) | (br.astype(np.int8) << 1) | bl.astype(np.int8)
    cell = TILE / n
    origin = -(margin + 1) + .5  # grid index → tile coordinate offset (in cells)

    def edge_point(r, c, e):
        if e == 0:   a, b, p, q = ext[r, c], ext[r, c + 1], (r, c), (r, c + 1)
        elif e == 1: a, b, p, q = ext[r, c + 1], ext[r + 1, c + 1], (r, c + 1), (r + 1, c + 1)
        elif e == 2: a, b, p, q = ext[r + 1, c], ext[r + 1, c + 1], (r + 1, c), (r + 1, c + 1)
        else:        a, b, p, q = ext[r, c], ext[r + 1, c], (r, c), (r + 1, c)
        t = 0.5 if a == b else min(1.0, max(0.0, (level - a) / (b - a)))
        y = p[0] + (q[0] - p[0]) * t; x = p[1] + (q[1] - p[1]) * t
        return ((x + origin) * cell, (y + origin) * cell)

    def edge_key(r, c, e):
        if e == 0: return ("h", r, c)
        if e == 2: return ("h", r + 1, c)
        if e == 3: return ("v", r, c)
        return ("v", r, c + 1)

    neighbours = {}
    points = {}
    rows, cols = np.nonzero((code > 0) & (code < 15))
    for r, c in zip(rows.tolist(), cols.tolist()):
        k = int(code[r, c])
        if k in (5, 10):  # saddle: decide with the cell centre
            centre = (ext[r, c] + ext[r, c + 1] + ext[r + 1, c] + ext[r + 1, c + 1]) / 4 >= level
            pairs = ([(3, 0), (2, 1)] if centre else [(3, 2), (0, 1)]) if k == 5 else \
                    ([(0, 1), (3, 2)] if centre else [(0, 3), (2, 1)])
        else:
            pairs = _CASES[k]
        for e1, e2 in pairs:
            a, b = edge_key(r, c, e1), edge_key(r, c, e2)
            if a not in points: points[a] = edge_point(r, c, e1)
            if b not in points: points[b] = edge_point(r, c, e2)
            neighbours.setdefault(a, []).append(b)
            neighbours.setdefault(b, []).append(a)
    loops, seen = [], set()
    for start in neighbours:
        if start in seen:
            continue
        loop = [start]; seen.add(start); previous = None; current = start
        while True:
            options = [k for k in neighbours[current] if k != previous]
            nxt = next((k for k in options if k not in seen), None)
            if nxt is None:
                break
            loop.append(nxt); seen.add(nxt); previous, current = current, nxt
        if len(loop) >= 3:
            loops.append([points[k] for k in loop])
    return loops


def simplify(loop, tolerance=.35):
    """Drop nearly collinear vertices (keeps SVG compact)."""
    if len(loop) < 8:
        return loop
    out = [loop[0]]
    for i in range(1, len(loop) - 1):
        (x0, y0), (x1, y1), (x2, y2) = out[-1], loop[i], loop[i + 1]
        area = abs((x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0))
        span = math.hypot(x2 - x0, y2 - y0) or 1
        if area / span > tolerance:
            out.append(loop[i])
    out.append(loop[-1])
    return out if len(out) >= 3 else loop


# ── relief, height and normal maps ────────────────────────────────────────
def _normals(a, depth):
    """Unit surface normals (x right, y down, z towards viewer); depth = tile units for value 1."""
    gx, gy = gradient(a)
    nx, ny, nz = -gx * depth, -gy * depth, np.ones_like(a)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    return nx / length, ny / length, nz / length


def relief(a, angle=-135.0, elevation=45.0, depth=4.0, mix=1.0):
    """Light the field as a surface: angle 0 = from the right, -90 = from the top (screen axes).

    The result is shading in 0–1 (flat areas = sin(elevation)); ``mix`` keeps part of the height.
    """
    nx, ny, nz = _normals(a, depth * 16)
    az, el = math.radians(angle), math.radians(elevation)
    lx, ly, lz = math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)
    shade = np.clip(nx * lx + ny * ly + nz * lz, 0, 1)
    return np.clip(a * (1 - mix) + shade * mix, 0, 1).astype(np.float32)


def normal_map(a, depth=4.0, convention="opengl"):
    """RGB uint8 tangent-space normal map. OpenGL (Blender) = green up; DirectX = green down."""
    nx, ny, nz = _normals(a, depth * 16)
    green = -ny if convention == "opengl" else ny
    rgb = np.stack([nx, green, nz], axis=-1) * .5 + .5
    return (np.clip(rgb, 0, 1) * 255 + .5).astype(np.uint8)


def height_map16(a):
    """uint16 height map (0–65535) for 16-bit PNG export."""
    return (np.clip(a, 0, 1) * 65535 + .5).astype(np.uint16)


def ramp(t, low, high, mid=None, mid_position=.5):
    """Colour ramp on RGB triples in 0–1, t array in 0–1 → (..., 3)."""
    t = np.clip(np.asarray(t, dtype=np.float32), 0, 1)[..., None]
    low, high = np.asarray(low, np.float32), np.asarray(high, np.float32)
    if mid is None:
        return low * (1 - t) + high * t
    mid = np.asarray(mid, np.float32); m = min(.99, max(.01, float(mid_position)))
    first = low + (mid - low) * (t / m)
    second = mid + (high - mid) * ((t - m) / (1 - m))
    return np.where(t <= m, first, second)


# ── v3: structured generators ─────────────────────────────────────────────
def _profile(distance, width, shape="round"):
    """Edge profile from a distance-to-edge (tile units): 0 at the edge → 1 inside."""
    t = np.clip(distance / max(1e-6, width), 0, 1)
    if shape == "linear":
        return t
    if shape == "flat":
        return (t > 0).astype(np.float32)
    return np.sqrt(1 - (1 - t) ** 2)  # round bevel


def tiles(n, columns=6, rows=12, pattern="brick", gap=4.0, bevel=6.0, profile="round", variation=.25, seed=0):
    """Height field of tiles / bricks / hexagons with mortar gap, bevelled edges and per-tile height."""
    rng = _rng(seed)
    X, Y = _grid(n)
    columns, rows = max(1, int(columns)), max(1, int(rows))
    if pattern == "hex":
        rows += rows % 2  # even row count keeps the offset periodic
        # Nearest of a periodic hexagonal lattice (offset rows), toroidal distance.
        cy = np.arange(rows); cx = np.arange(columns)
        centers = np.array([((i + .5 + (.5 if j % 2 else 0)) / columns, (j + .5) / rows) for j in cy for i in cx], np.float32)
        px, py = X.reshape(-1, 1), Y.reshape(-1, 1)
        dx = np.abs(px - centers[:, 0]); dx = np.minimum(dx, 1 - dx)
        dy = np.abs(py - centers[:, 1]); dy = np.minimum(dy, 1 - dy)
        d = np.sqrt((dx * columns) ** 2 + (dy * rows * 1.1547) ** 2)
        order = np.argsort(d, axis=1)[:, :2]
        d1 = np.take_along_axis(d, order[:, :1], 1)[:, 0]; d2 = np.take_along_axis(d, order[:, 1:2], 1)[:, 0]
        edge = (d2 - d1) / 2 * (TILE / columns)
        ids = order[:, 0].reshape(n, n)
        edge = edge.reshape(n, n)
    else:
        u = X * columns; v = Y * rows
        row = np.floor(v).astype(np.int64)
        if pattern == "brick":
            u = u + np.where(row % 2 == 1, .5, 0)
        col = np.floor(u).astype(np.int64) % columns
        fu, fv = u - np.floor(u), v - row
        edge = np.minimum(np.minimum(fu, 1 - fu) * (TILE / columns), np.minimum(fv, 1 - fv) * (TILE / rows))
        ids = (row % rows) * columns + col
    heights = 1 - variation * rng.random(columns * rows + 1).astype(np.float32)
    inside = edge - gap / 2
    return (np.where(inside > 0, _profile(inside, bevel, profile), 0) * heights[ids % len(heights)]).astype(np.float32)


def scales(n, columns=8, rows=12, overlap=.5, roundness=.8, variation=.2, seed=0):
    """Overlapping fish / dragon scales: round discs, upper rows drawn over lower ones,
    so each scale shows a rounded lower edge (scalloped pattern)."""
    rng = _rng(seed)
    X, Y = _grid(n)
    columns, rows = max(1, int(columns)), max(2, int(rows) + int(rows) % 2)
    radius = TILE / columns * .5 * (1 + overlap)
    tone = 1 - variation * rng.random((rows, columns)).astype(np.float32)
    result = np.zeros((n, n), np.float32)
    best = np.full((n, n), -np.inf, np.float32)  # the disc whose centre is highest above wins (cyclic-safe)
    for r in range(rows):
        cy = (r + .5) / rows
        shift = .5 if r % 2 else 0.0
        base = np.floor(X * columns - shift + .5).astype(np.int64)
        for k in (-1, 0, 1):  # discs spill into neighbouring columns
            ci = base + k
            cx = (ci + shift) / columns
            dx = ((X - cx + .5) % 1 - .5) * TILE
            dy = ((Y - cy + .5) % 1 - .5) * TILE
            d = np.sqrt(dx * dx + dy * dy) / radius
            dome = np.sqrt(np.clip(1 - d * d, 0, 1)) ** (1.5 - roundness)
            value = (.25 + .75 * dome * (.8 + .2 * np.clip(dy / radius, 0, 1))) * tone[r, ci % columns]
            win = (d < 1) & (dy > best)
            result = np.where(win, value, result); best = np.where(win, dy, best)
    return normalize(result)


def pebbles(n, count=60, gap=.15, roundness=.7, variation=.35, jitter=.8, seed=0):
    """Rounded stones with gaps (pebble paths, gravel, cobbles)."""
    f1, f2 = _worley(n, count, seed, jitter, .3)
    rng = _rng(seed + 1)
    edge = (f2 - f1) / np.maximum(f2 + f1, 1e-6)
    t = np.clip((edge - gap) / max(1e-6, 1 - gap), 0, 1)
    dome = t ** (1 - .8 * roundness)
    noise = perlin(n, 6, 3, .5, 2, "fbm", 1, seed + 2)
    return normalize(dome * (1 - variation * noise))


def stripes(n, count=8, angle=0, sharpness=1.0, wobble=0.0, seed=0):
    """Seamless stripes (snapped to whole repeats), optionally wobbled by noise."""
    X, Y = _grid(n)
    a = math.radians(angle)
    kx = int(round(math.cos(a) * count)); ky = int(round(math.sin(a) * count))
    if kx == 0 and ky == 0:
        kx = 1
    phase = kx * X + ky * Y
    if wobble:
        phase = phase + wobble * (perlin(n, 3, 3, .5, 2, "fbm", 1, seed) - .5)
    wave = .5 + .5 * np.cos(2 * math.pi * phase)
    return (wave ** max(.05, sharpness)).astype(np.float32)


# ── v3: operations ────────────────────────────────────────────────────────
def distance_inside(a, threshold=.5, max_distance=64.0):
    """Approximate Euclidean distance (tile units) from each point inside {a >= threshold}
    to the nearest outside point; periodic (chamfer propagation on a torus)."""
    n = a.shape[0]
    cell = TILE / n
    steps = int(min(n, max(1, max_distance / cell)))
    big = np.float32(1e6)
    dist = np.where(a >= threshold, big, 0).astype(np.float32)
    diag = np.float32(math.sqrt(2) * cell)
    for _ in range(steps):
        candidates = [np.roll(dist, 1, 0) + cell, np.roll(dist, -1, 0) + cell,
                      np.roll(dist, 1, 1) + cell, np.roll(dist, -1, 1) + cell,
                      np.roll(np.roll(dist, 1, 0), 1, 1) + diag, np.roll(np.roll(dist, 1, 0), -1, 1) + diag,
                      np.roll(np.roll(dist, -1, 0), 1, 1) + diag, np.roll(np.roll(dist, -1, 0), -1, 1) + diag]
        updated = np.minimum(dist, np.minimum.reduce(candidates))
        if np.array_equal(updated, dist):
            break
        dist = updated
    return np.minimum(dist, max_distance)


def bevel(a, threshold=.5, width=8.0, profile="round", keep_height=0.0):
    """Turn a mask / shapes into raised bevelled forms (bricks, tiles, buttons)."""
    shape = _profile(distance_inside(a, threshold, width * 1.5), width, profile)
    return np.clip(shape * (1 - keep_height) + shape * a * keep_height, 0, 1).astype(np.float32)


def slope_blur(a, b, amount=12.0, samples=8):
    """Smear A along the slope of B (drips, flow, smudged edges)."""
    n = a.shape[0]
    X, Y = _grid(n)
    gx, gy = gradient(blur(b, 3))
    length = np.sqrt(gx * gx + gy * gy) + 1e-9
    ux, uy = gx / length, gy / length
    total = np.zeros_like(a)
    for i in range(int(samples)):
        t = (i / max(1, samples - 1) - .5) * amount / TILE
        total += sample_unit(a, (X + ux * t) % 1, (Y + uy * t) % 1)
    return (total / int(samples)).astype(np.float32)


def histogram_scan(a, position=.5, contrast=.5):
    """Substance-style threshold: slide a soft step along the value range."""
    width = max(1e-3, 1 - contrast)
    return _smoothstep(position - width / 2, position + width / 2, a).astype(np.float32)


def symmetry(a, mode="mirror x"):
    """Mirror / kaleidoscope. Mirrors keep tiling; radial modes centre on the tile."""
    n = a.shape[0]
    if mode == "mirror x":
        half = a[:, : n // 2]; return np.concatenate([half, half[:, ::-1]], 1)[:, :n]
    if mode == "mirror y":
        half = a[: n // 2]; return np.concatenate([half, half[::-1]], 0)[:n]
    if mode == "mirror xy":
        return symmetry(symmetry(a, "mirror x"), "mirror y")
    segments = int(mode.split()[0]) if mode[0].isdigit() else 6
    X, Y = _grid(n)
    dx, dy = X - .5, Y - .5
    r = np.sqrt(dx * dx + dy * dy); ang = np.arctan2(dy, dx)
    wedge = 2 * math.pi / segments
    ang = np.abs((ang % wedge) - wedge / 2)
    return sample_unit(a, (.5 + r * np.cos(ang)) % 1, (.5 + r * np.sin(ang)) % 1).astype(np.float32)


def slope(a, depth=4.0):
    """Steepness 0 (flat) → 1 (vertical): masks for scree, worn ridges, moss on flats (invert)."""
    nx, ny, nz = _normals(a, depth * 16)
    return (1 - nz).astype(np.float32) / max(1e-6, float((1 - nz).max()) or 1)


def curvature(a, radius=3.0, mode="convex"):
    """Convex (ridges, edges) or concave (cavities) mask from the Laplacian."""
    high = a - blur(a, radius)
    scale = float(np.abs(high).max()) or 1.0
    value = high / scale
    return np.clip(value if mode == "convex" else -value, 0, 1).astype(np.float32)


def ambient_occlusion(a, radius=16.0, strength=1.0):
    """Cheap horizon-free AO: how far below its multi-scale neighbourhood each point sits."""
    occlusion = np.zeros_like(a)
    weight = 0.0
    for k, r in enumerate((radius / 4, radius / 2, radius)):
        occlusion += np.clip(blur(a, r) - a, 0, None) * (k + 1)
        weight += k + 1
    occlusion = occlusion / weight
    scale = float(occlusion.max()) or 1.0
    return np.clip(1 - strength * occlusion / scale, 0, 1).astype(np.float32)


def make_tileable(a, blend=.15):
    """Hide the seams of an imported image: cross-fade with a half-tile shifted copy near the edges."""
    n = a.shape[0]
    shifted = np.roll(np.roll(a, n // 2, 0), n // 2, 1)
    X, Y = _grid(n)
    edge = np.minimum(np.minimum(X, 1 - X), np.minimum(Y, 1 - Y))
    w = _smoothstep(0, max(1e-3, blend), edge)
    return (a * w + shifted * (1 - w)).astype(np.float32)


def from_image(gray, n, tileable=True, blend=.15):
    """uint8/float greyscale array (any size) → n×n field."""
    data = np.asarray(gray, dtype=np.float32)
    if data.max() > 1.0:
        data = data / 255.0
    h, w = data.shape
    ys = ((np.arange(n) + .5) / n * h - .5).clip(0, h - 1)
    xs = ((np.arange(n) + .5) / n * w - .5).clip(0, w - 1)
    y0 = np.floor(ys).astype(int); x0 = np.floor(xs).astype(int)
    y1 = np.minimum(y0 + 1, h - 1); x1 = np.minimum(x0 + 1, w - 1)
    fy = (ys - y0)[:, None]; fx = (xs - x0)[None, :]
    top = data[y0][:, x0] * (1 - fx) + data[y0][:, x1] * fx
    bottom = data[y1][:, x0] * (1 - fx) + data[y1][:, x1] * fx
    field = (top * (1 - fy) + bottom * fy).astype(np.float32)
    return make_tileable(field, blend) if tileable else field
