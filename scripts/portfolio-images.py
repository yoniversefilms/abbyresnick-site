#!/usr/bin/env python3
"""Portfolio image pipeline for abbyresnick.com.

Reads a private selects manifest, writes web derivatives + a public manifest into
assets/portfolio/, and regenerates the chips + grid between the markers in portfolio.html.
Run:  python3 scripts/portfolio-images.py            (build everything)
      python3 scripts/portfolio-images.py --check    (verify, no writes)
See README.md → "Portfolio pipeline".
"""
from __future__ import annotations
import argparse, html, io, json, math, os, subprocess, sys, tempfile
from pathlib import Path

CATEGORY_ORDER = ["installations", "corporate", "private", "studio", "weddings"]
CATEGORY_LABEL = {"installations": "Installations", "corporate": "Corporate",
                  "private": "Private Events", "studio": "Studio", "weddings": "Weddings"}
SIZES = (1600, 800)
BUDGET = {1600: 450_000, 800: 150_000}
QUALITY_LADDER = (82, 78, 74, 70, 66, 62)   # never below q62: fail loudly instead
EAGER_BUDGET = 1_200_000
EAGER_COUNT = 6
START, END = "<!-- PORTFOLIO:START -->", "<!-- PORTFOLIO:END -->"
REQUIRED = ("id", "category", "source", "caption")

SITE = Path(__file__).resolve().parent.parent
PATHS_FILE = Path(__file__).resolve().parent / "portfolio-paths.json"   # git-ignored, local only


def local_paths() -> dict:
    """Where the private inputs live on this machine: env PORTFOLIO_SELECTS / PORTFOLIO_PHOTOS,
    else scripts/portfolio-paths.json ({"selects": "...", "photos": "..."}). Never committed."""
    cfg = json.loads(PATHS_FILE.read_text()) if PATHS_FILE.exists() else {}
    return {"selects": os.environ.get("PORTFOLIO_SELECTS") or cfg.get("selects"),
            "photos": os.environ.get("PORTFOLIO_PHOTOS") or cfg.get("photos")}


def load_selects(path: Path) -> list[dict]:
    items = json.loads(Path(path).read_text())
    out, seen = [], set()
    for it in items:
        missing = [k for k in REQUIRED if k not in it]
        if missing:
            raise ValueError(f"select {it.get('id', '?')}: missing {missing}")
        if it["category"] == "reserve":
            continue
        if it["category"] not in CATEGORY_LABEL:
            raise ValueError(f"select {it['id']}: unknown category {it['category']!r}")
        if it["id"] in seen:
            raise ValueError(f"duplicate id {it['id']!r}")
        seen.add(it["id"])
        out.append(it)
    return out


def resolve_source(item: dict, photos_root: Path) -> Path:
    p = Path(photos_root) / item["source"]
    if not p.is_file():
        raise FileNotFoundError(f"select {item['id']}: source not found: {p}")
    return p


from PIL import Image, ImageCms, ImageOps  # Pillow 12 (system python3)

_SRGB = ImageCms.createProfile("sRGB")


def decode(path: Path) -> Image.Image:
    """Open any source as an EXIF-oriented RGB image. Canon .CR3 goes through sips first."""
    path = Path(path)
    if path.suffix.lower() == ".cr3":
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / (path.stem + ".jpg")
            r = subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "95",
                                "-Z", "3200", str(path), "--out", str(tmp)], capture_output=True, text=True)
            if r.returncode != 0 or not tmp.exists():
                raise RuntimeError(f"sips failed on {path}: {r.stderr.strip()}")
            im = Image.open(tmp); im.load()
    else:
        im = Image.open(path)
    im = to_srgb(im, path)
    im = ImageOps.exif_transpose(im)
    return im.convert("RGB")


def to_srgb(im: Image.Image, path: Path) -> Image.Image:
    """Convert through the embedded ICC profile (Display P3, Adobe RGB, ...) to sRGB so browsers,
    which treat an untagged JPEG as sRGB, show the colours the camera recorded. No profile → as-is."""
    icc = im.info.get("icc_profile")
    if not icc:
        return im
    try:
        src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        out = ImageCms.profileToProfile(im, src, _SRGB, outputMode="RGB")
        if im.getexif():                   # profileToProfile drops info/exif; keep orientation for exif_transpose
            out.info["exif"] = im.getexif().tobytes()
        return out
    except (ImageCms.PyCMSError, OSError) as e:
        print(f"  warning: {Path(path).name}: embedded ICC profile unusable ({e}); treating as sRGB")
        return im.convert("RGB")


def apply_crop(im: Image.Image, crop: list[float] | None) -> Image.Image:
    if not crop:
        return im
    l, t, r, b = crop
    if not (0 <= l < r <= 1 and 0 <= t < b <= 1):
        raise ValueError(f"bad crop {crop}")
    w, h = im.size
    return im.crop((round(l * w), round(t * h), round(r * w), round(b * h)))


WB_BAND, WB_MAX_GAIN = 0.05, 1.45


def _highlight_mean(hist: list[int], frac: float = WB_BAND) -> float:
    """Mean of a channel's brightest `frac` of pixels (value 0 ignored), read off its histogram:
    walk down from 255 until the band holds ceil(frac × pixels), taking only part of the last bin."""
    total = sum(hist[1:])
    if not total:
        return 1.0
    n = max(1, math.ceil(round(total * frac, 6)))      # round first so 500.0000000001 is 500
    need, acc = n, 0
    for v in range(255, 0, -1):
        take = min(hist[v], need)
        acc += v * take; need -= take
        if not need:
            break
    return max(acc / n, 1.0)


def _luma_band_mask(im: Image.Image, frac: float = WB_BAND) -> Image.Image:
    """Mask of the brightest `frac` of pixels BY LUMINANCE, excluding blown pixels (L >= 254) so a speck
    of clipped white cannot set the balance. Falls back to including blown pixels when almost nothing else
    is bright (an image that is mostly white)."""
    L = im.convert("L")
    h = L.histogram(); total = sum(h)
    n = max(1, math.ceil(round(total * frac, 6)))
    top = 253
    acc = 0; t = top
    for v in range(top, -1, -1):
        acc += h[v]
        if acc >= n:
            t = v; break
    if acc < max(1, total * 0.01):        # nearly everything bright is blown: use it anyway
        top, acc, t = 255, 0, 255
        for v in range(255, -1, -1):
            acc += h[v]
            if acc >= n:
                t = v; break
    lo, hi = t, top
    return L.point(lambda v: 255 if lo <= v <= hi else 0)


def auto_wb(im: Image.Image) -> Image.Image:
    """Highlight-band balance: take the brightest 5% of pixels by luminance (blown pixels excluded), aim
    every channel's mean over that band at the brightest channel's mean, gain clamped to [1.0, 1.45].
    Selecting one band by luminance (not one band per channel) keeps the three means on the same
    pixels, which is what makes the backdrop come out neutral instead of each channel chasing its own hotspot."""
    from PIL import ImageStat
    mask = _luma_band_mask(im)
    means = [max(ImageStat.Stat(ch, mask).mean[0], 1.0) for ch in im.split()]
    target = max(means)
    gains = [min(max(target / m, 1.0), WB_MAX_GAIN) for m in means]
    bands = [ch.point(lambda v, g=g: min(255, round(v * g))) for ch, g in zip(im.split(), gains)]
    return Image.merge("RGB", bands)


def derivative_path(out_dir: Path, item_id: str, size: int) -> Path:
    return Path(out_dir) / f"{item_id}-{size}.jpg"


def _save_within_budget(im: Image.Image, dest: Path, budget: int) -> tuple[int, int]:
    """Save at the first rung of QUALITY_LADDER that fits the budget; returns (bytes, quality)."""
    for q in QUALITY_LADDER:
        im.save(dest, "JPEG", quality=q, optimize=True, progressive=True)
        n = dest.stat().st_size
        if n <= budget:
            return n, q
    raise RuntimeError(f"{dest.name} is {n} bytes, over budget {budget} even at q{q}")


def make_derivatives(item: dict, photos_root: Path, out_dir: Path) -> dict[int, tuple[int, int, int]]:
    src = resolve_source(item, photos_root)           # raises before anything is written
    im = apply_crop(decode(src), item.get("crop"))
    if item.get("wb"):
        im = auto_wb(im)
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    result, quality = {}, {}
    for size in SIZES:
        d = im.copy()
        d.thumbnail((size, size), Image.LANCZOS)     # never upscales
        n, quality[size] = _save_within_budget(d, derivative_path(out_dir, item["id"], size), BUDGET[size])
        result[size] = (d.width, d.height, n)
    w, h, n = result[1600]
    print(f"  {item['id']:<22} {w}x{h}  {n:>7} B q{quality[1600]}  | 800: {result[800][2]:>7} B q{quality[800]}")
    return result

def build_manifest(items: list[dict], results: dict[str, dict]) -> list[dict]:
    out = []
    for it in items:
        w, h, _ = results[it["id"]][1600]
        out.append({"id": it["id"], "category": it["category"], "caption": it["caption"],
                    "alt": it.get("alt") or it["caption"], "w": w, "h": h})
    return out


def render_block(manifest: list[dict], dims800: dict[str, tuple[int, int]] | None = None) -> str:
    """Chips + count + grid. dims800 maps id → the real (w, h) of <id>-800.jpg; without it the
    800 size is estimated from the 1600 dims (rounding can be off by a pixel)."""
    present = [c for c in CATEGORY_ORDER if any(m["category"] == c for m in manifest)]
    chips = ['<div class="chips" role="group" aria-label="Filter by category">',
             '<button class="chip" type="button" data-cat="all" aria-pressed="true">All</button>']
    chips += [f'<button class="chip" type="button" data-cat="{c}" aria-pressed="false">{CATEGORY_LABEL[c]}</button>' for c in present]
    chips.append("</div>")
    n = len(manifest)
    count = f'<p class="pf-count" aria-live="polite" data-total="{n}">{n} pieces</p>'
    tiles = ['<div class="pf-grid" id="pfGrid">']
    for i, m in enumerate(manifest):
        if dims800 and m["id"] in dims800:
            w800, h800 = dims800[m["id"]]
        else:
            w800 = min(m["w"], 800) if m["w"] >= m["h"] else round(m["w"] * min(m["h"], 800) / m["h"])
            h800 = min(m["h"], 800) if m["h"] >= m["w"] else round(m["h"] * min(m["w"], 800) / m["w"])
        cls = "pf-tile pf-tile--portrait" if m["h"] > m["w"] else "pf-tile"
        alt = html.escape(m["alt"], quote=True)
        load = "" if i < EAGER_COUNT else ' loading="lazy"'
        prio = ' fetchpriority="high"' if i < 2 else ""
        tiles.append(
            f'<a class="{cls}" id="item-{m["id"]}" data-cat="{m["category"]}" data-index="{i}" href="assets/portfolio/{m["id"]}-1600.jpg">'
            f'<img src="assets/portfolio/{m["id"]}-800.jpg" srcset="assets/portfolio/{m["id"]}-800.jpg 800w, assets/portfolio/{m["id"]}-1600.jpg 1600w" '
            f'sizes="(max-width: 900px) 50vw, 33vw" width="{w800}" height="{h800}" alt="{alt}"{load}{prio} decoding="async"></a>')
    tiles.append("</div>")
    return "\n".join(chips + [count] + tiles)


def inject(page: Path, block: str) -> bool:
    page = Path(page); text = page.read_text()
    a, b = text.find(START), text.find(END)
    if a < 0 or b < 0 or b < a:
        raise ValueError(f"{page}: markers {START} / {END} not found in order")
    new = text[: a + len(START)] + "\n" + block + "\n" + text[b:]
    if new == text:
        return False
    fd, tmp = tempfile.mkstemp(dir=page.parent, prefix=".pf-", suffix=".html")
    with os.fdopen(fd, "w") as f:
        f.write(new)
    os.replace(tmp, page)
    return True


def build(args) -> list[dict]:
    items = load_selects(args.selects)
    if args.only:
        items = [it for it in items if it["id"] == args.only]
        if not items:
            raise SystemExit(f"no select with id {args.only!r}")
    out_dir = Path(args.site) / "assets" / "portfolio"
    for it in items:                       # validate every source before writing anything
        resolve_source(it, args.photos)
    results = {}
    for it in items:
        results[it["id"]] = make_derivatives(it, args.photos, out_dir)   # prints its own line
    if args.only:                           # partial build: refresh derivatives only
        return []
    manifest = build_manifest(items, results)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    dims800 = {i: r[800][:2] for i, r in results.items()}
    changed = inject(Path(args.site) / "portfolio.html", render_block(manifest, dims800))
    print(f"{len(manifest)} items → manifest.json; portfolio.html {'updated' if changed else 'unchanged'}")
    return manifest


def check(args) -> list[str]:
    site = Path(args.site); out_dir = site / "assets" / "portfolio"; problems = []
    items = load_selects(args.selects); ids = [it["id"] for it in items]
    mpath = out_dir / "manifest.json"
    if not mpath.exists():
        return [f"missing {mpath}"]
    manifest = json.loads(mpath.read_text())
    if [m["id"] for m in manifest] != ids:
        problems.append("manifest ids differ from selects (rebuild)")
    for m in manifest:
        if set(m) - {"id", "category", "caption", "alt", "w", "h"}:
            problems.append(f"{m['id']}: private field in manifest")
    for i in ids:
        for size in SIZES:
            p = derivative_path(out_dir, i, size)
            if not p.exists():
                problems.append(f"missing {p.name}")
            elif p.stat().st_size > BUDGET[size]:
                problems.append(f"{p.name}: {p.stat().st_size} B over {BUDGET[size]}")
    page = site / "portfolio.html"; text = page.read_text() if page.exists() else ""
    if START not in text or END not in text:
        problems.append("portfolio.html: markers missing")
    for i in ids:
        if f'id="item-{i}"' not in text:
            problems.append(f"portfolio.html: tile item-{i} missing")
    eager = len(text.encode()) + sum(derivative_path(out_dir, i, 800).stat().st_size
                                     for i in ids[:EAGER_COUNT] if derivative_path(out_dir, i, 800).exists())
    if eager > EAGER_BUDGET:
        problems.append(f"eager payload {eager} B over {EAGER_BUDGET}")
    private_marker = "Abby" + "-claude"      # concatenated so this scanner never holds the strings it hunts
    home_marker = "/Us" + "ers/"               # any absolute macOS home path is a leak on a public repo
    for p in site.rglob("*"):
        # the one exemption is the git-ignored local path config, which names the private folder by design
        if (p.is_file() and ".git" not in p.parts and p.relative_to(site) != Path("scripts/portfolio-paths.json")
                and p.suffix in {".html", ".js", ".json", ".md", ".py", ".sh", ".txt", ".css"}):
            body = p.read_text(errors="ignore")
            if private_marker in body:
                problems.append(f"{p.relative_to(site)}: contains private path")
            elif home_marker in body:
                problems.append(f"{p.relative_to(site)}: contains an absolute home path")
    idx = site / "index.html"
    if idx.exists() and 'href="#work"' in idx.read_text():
        problems.append('index.html: still links to #work')
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selects", type=Path, default=None)
    ap.add_argument("--photos", type=Path, default=None)
    ap.add_argument("--site", type=Path, default=SITE)
    ap.add_argument("--only", help="rebuild derivatives for a single id (no page/manifest write)")
    ap.add_argument("--check", action="store_true", help="verify outputs, write nothing")
    args = ap.parse_args(argv)
    if args.selects is None or args.photos is None:
        lp = local_paths()
        args.selects = args.selects or (Path(lp["selects"]) if lp["selects"] else None)
        args.photos = args.photos or (Path(lp["photos"]) if lp["photos"] else None)
    if args.selects is None or args.photos is None:
        print("ERROR: set PORTFOLIO_SELECTS/PORTFOLIO_PHOTOS or scripts/portfolio-paths.json", file=sys.stderr)
        return 2
    try:
        if args.check:
            problems = check(args)
            for p in problems:
                print("CHECK:", p)
            print("check:", "OK" if not problems else f"{len(problems)} problem(s)")
            return 0 if not problems else 1
        build(args)
        return 0
    except (FileNotFoundError, RuntimeError, ValueError) as e:
        print("ERROR:", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
