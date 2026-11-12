#!/usr/bin/env python3
"""
Turn a batik photo/scan into a coloring-page pattern file.

    python tools/make_pattern.py parang.jpg --id parang --name "Parang"

What it does
  1. Groups the image into tonal regions (k-means on colour, then smoothed).
  2. Draws the borders between regions as black line art  -> the "contour".
  3. Drops tiny specks so every region is big enough to colour.
  4. Writes patterns/<id>.js containing the line art (transparent PNG) and the
     original colour image, both as data URIs so the page also works when the
     HTML is opened straight from disk (canvas would be tainted otherwise).

Requires: numpy, pillow, scipy
"""
import argparse
import base64
import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parent.parent


def kmeans(samples, k, iters=30, seed=0):
    """Plain k-means with k-means++ initialisation."""
    rng = np.random.default_rng(seed)
    centers = [samples[rng.integers(len(samples))]]
    for _ in range(1, k):
        d2 = np.min(((samples[:, None, :] - np.array(centers)[None]) ** 2).sum(-1), axis=1)
        centers.append(samples[rng.choice(len(samples), p=d2 / d2.sum())])
    c = np.array(centers, dtype=np.float64)
    for _ in range(iters):
        lab = assign(samples, c)
        for j in range(k):
            m = lab == j
            if m.any():
                c[j] = samples[m].mean(0)
    return c


def assign(flat, centers, chunk=200_000):
    out = np.empty(len(flat), dtype=np.int64)
    for s in range(0, len(flat), chunk):
        part = flat[s:s + chunk]
        d = ((part[:, None, :] - centers[None]) ** 2).sum(-1)
        out[s:s + chunk] = d.argmin(1)
    return out


def data_uri(img, fmt, **save_kwargs):
    buf = io.BytesIO()
    img.save(buf, fmt, **save_kwargs)
    mime = "image/png" if fmt == "PNG" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def build_contour(rgb, clusters, smooth, min_region, thicken):
    h, w, _ = rgb.shape

    # 1. colour quantisation on a lightly blurred copy (removes paper/JPEG grain)
    blurred = np.stack([ndi.gaussian_filter(rgb[..., i], 1.5) for i in range(3)], -1)
    flat = blurred.reshape(-1, 3)
    rng = np.random.default_rng(1)
    sample = flat[rng.choice(len(flat), min(40_000, len(flat)), replace=False)]
    centers = kmeans(sample, clusters)
    labels = assign(flat, centers).reshape(h, w)
    print("colour clusters (RGB):")
    for j, c in enumerate(centers):
        print(f"  {j}: {c.round().astype(int).tolist()}  pixels={int((labels == j).sum())}")

    # 2. smooth the label map: each class votes with a gaussian, highest vote wins
    votes = np.stack(
        [ndi.gaussian_filter((labels == j).astype(np.float32), smooth) for j in range(clusters)]
    )
    labels = votes.argmax(0)

    # 3. borders between regions -> line art (2 px wide, 4-neighbour test)
    edge = np.zeros((h, w), dtype=bool)
    horiz = labels[:, :-1] != labels[:, 1:]
    edge[:, :-1] |= horiz
    edge[:, 1:] |= horiz
    vert = labels[:-1, :] != labels[1:, :]
    edge[:-1, :] |= vert
    edge[1:, :] |= vert

    # 4. thicken lines so they stay readable on small screens and in print
    if thicken > 0:
        edge = ndi.binary_dilation(edge, iterations=thicken)

    # 5. tiny fillable islands are unusable as colouring areas -> turn them into line
    regions, n = ndi.label(~edge)
    sizes = np.bincount(regions.ravel())
    tiny = sizes < min_region
    tiny[0] = False
    edge |= tiny[regions]

    kept = np.bincount(ndi.label(~edge)[0].ravel())[1:]
    print(f"regions kept: {len(kept)} (removed {int(tiny.sum())} tiny specks)")
    return edge


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=Path, help="input image (jpg/png)")
    ap.add_argument("--id", required=True, help="pattern id, used as file name (e.g. parang)")
    ap.add_argument("--name", required=True, help="display name")
    ap.add_argument("--clusters", type=int, default=4, help="number of colour groups (default 4)")
    ap.add_argument("--smooth", type=float, default=3.0, help="region smoothing sigma (default 3)")
    ap.add_argument("--min-region", type=int, default=150, help="min region size in px (default 150)")
    ap.add_argument("--thicken", type=int, default=1, help="line thickening in px (default 1)")
    ap.add_argument("--preview", type=Path, help="optional PNG preview of the line art")
    args = ap.parse_args()

    color_img = Image.open(args.source).convert("RGB")
    rgb = np.asarray(color_img).astype(np.float64)
    h, w, _ = rgb.shape

    edge = build_contour(rgb, args.clusters, args.smooth, args.min_region, args.thicken)

    rgba = np.zeros((h, w, 4), dtype=np.uint8)  # black lines, transparent elsewhere
    rgba[..., 3] = np.where(edge, 255, 0)
    line_img = Image.fromarray(rgba, "RGBA")

    if args.preview:
        preview = Image.new("RGB", (w, h), (255, 255, 255))
        preview.paste(line_img, (0, 0), line_img)
        preview.save(args.preview)
        print(f"preview written: {args.preview}")

    out = ROOT / "patterns" / f"{args.id}.js"
    out.parent.mkdir(parents=True, exist_ok=True)
    js = (
        "// Generated by tools/make_pattern.py from "
        f"{args.source.name} - regenerate instead of editing.\n"
        "window.BATIK_PATTERNS = window.BATIK_PATTERNS || [];\n"
        "window.BATIK_PATTERNS.push({\n"
        f"  id: {args.id!r},\n"
        f"  name: {args.name!r},\n"
        f"  width: {w},\n"
        f"  height: {h},\n"
        f"  line: \"{data_uri(line_img, 'PNG', optimize=True)}\",\n"
        f"  color: \"{data_uri(color_img, 'JPEG', quality=92)}\"\n"
        "});\n"
    )
    out.write_text(js, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    sys.exit(main())
