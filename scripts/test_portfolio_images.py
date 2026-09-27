import contextlib, io, json, os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import importlib
pi = importlib.import_module("portfolio-images")

def write_selects(tmp, items):
    p = Path(tmp) / "selects.json"; p.write_text(json.dumps(items)); return p

class LoadSelects(unittest.TestCase):
    def test_excludes_reserve_and_keeps_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = write_selects(tmp, [
                {"id": "b", "category": "studio", "source": "x/b.jpg", "caption": "B", "note": "", "width": 10, "height": 10},
                {"id": "a", "category": "reserve", "source": "x/a.jpg", "caption": "A", "note": "", "width": 10, "height": 10},
                {"id": "c", "category": "private", "source": "x/c.jpg", "caption": "C", "note": "", "width": 10, "height": 10},
            ])
            ids = [it["id"] for it in pi.load_selects(p)]
            self.assertEqual(ids, ["b", "c"])

    def test_rejects_unknown_category_and_missing_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = write_selects(tmp, [{"id": "a", "category": "weddingz", "source": "a.jpg", "caption": "A"}])
            with self.assertRaises(ValueError): pi.load_selects(p)
            p = write_selects(tmp, [{"id": "a", "category": "studio"}])
            with self.assertRaises(ValueError): pi.load_selects(p)

    def test_rejects_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = write_selects(tmp, [
                {"id": "a", "category": "studio", "source": "a.jpg", "caption": "A"},
                {"id": "a", "category": "private", "source": "b.jpg", "caption": "B"}])
            with self.assertRaises(ValueError): pi.load_selects(p)

class ResolveSource(unittest.TestCase):
    def test_missing_source_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                pi.resolve_source({"id": "a", "source": "nope/x.jpg"}, Path(tmp))

    def test_existing_source_resolves(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "s").mkdir(); (Path(tmp) / "s" / "x.jpg").write_bytes(b"0")
            self.assertEqual(pi.resolve_source({"id": "a", "source": "s/x.jpg"}, Path(tmp)), Path(tmp) / "s" / "x.jpg")

from PIL import Image

def make_jpeg(path, w, h, color=(200, 120, 90)):
    Image.new("RGB", (w, h), color).save(path, "JPEG", quality=90)

class Derivatives(unittest.TestCase):
    def test_writes_two_sizes_within_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "s.jpg"; make_jpeg(src, 4000, 3000)
            out = Path(tmp) / "out"
            res = pi.make_derivatives({"id": "a", "source": "s.jpg"}, Path(tmp), out)
            self.assertEqual(res[1600][:2], (1600, 1200))
            self.assertEqual(res[800][:2], (800, 600))
            self.assertLessEqual(res[1600][2], pi.BUDGET[1600])
            self.assertLessEqual(res[800][2], pi.BUDGET[800])
            self.assertTrue((out / "a-1600.jpg").exists() and (out / "a-800.jpg").exists())

    def test_never_upscales(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "s.jpg"; make_jpeg(src, 1000, 750)
            res = pi.make_derivatives({"id": "a", "source": "s.jpg"}, Path(tmp), Path(tmp) / "out")
            self.assertEqual(res[1600][:2], (1000, 750))
            self.assertEqual(res[800][:2], (800, 600))

    def test_portrait_long_edge(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "s.jpg"; make_jpeg(src, 3000, 4000)
            res = pi.make_derivatives({"id": "a", "source": "s.jpg"}, Path(tmp), Path(tmp) / "out")
            self.assertEqual(res[1600][:2], (1200, 1600))

    def test_crop_fractions(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "s.jpg"; make_jpeg(src, 2000, 1000)
            res = pi.make_derivatives({"id": "a", "source": "s.jpg", "crop": [0.25, 0, 0.75, 1]}, Path(tmp), Path(tmp) / "out")
            self.assertEqual(res[1600][:2], (1000, 1000))

    def test_strips_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "s.jpg"
            im = Image.new("RGB", (2000, 1500)); ex = im.getexif(); ex[271] = "Canon"
            im.save(src, "JPEG", exif=ex.tobytes())
            pi.make_derivatives({"id": "a", "source": "s.jpg"}, Path(tmp), Path(tmp) / "out")
            self.assertEqual(dict(Image.open(Path(tmp) / "out" / "a-1600.jpg").getexif()), {})

    def test_missing_source_fails_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            with self.assertRaises(FileNotFoundError):
                pi.make_derivatives({"id": "a", "source": "missing.jpg"}, Path(tmp), out)
            self.assertFalse(out.exists())

    def test_embedded_profile_is_honoured(self):
        from PIL import ImageCms
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "s.jpg"
            im = Image.new("RGB", (200, 200))
            im.putdata([((x * 7) % 256, (y * 5) % 256, (x + y) % 256) for y in range(200) for x in range(200)])
            srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
            im.save(src, "JPEG", quality=95, icc_profile=srgb)
            with Image.open(src) as raw:
                self.assertEqual(raw.info.get("icc_profile"), srgb)
                orig = raw.convert("RGB")           # the JPEG's own pixels, no colour management
            got = pi.decode(src)
            self.assertEqual((got.mode, got.size), ("RGB", (200, 200)))
            worst = max(abs(a - b) for a, b in zip(orig.tobytes(), got.tobytes()))
            self.assertLessEqual(worst, 1)          # sRGB → sRGB is a no-op within 1/255
            bad = Path(tmp) / "bad.jpg"
            Image.new("RGB", (200, 200), (120, 90, 60)).save(bad, "JPEG", quality=95, icc_profile=b"junk")
            with contextlib.redirect_stdout(io.StringIO()) as out:
                got = pi.decode(bad)
            self.assertEqual((got.mode, got.size), ("RGB", (200, 200)))
            self.assertIn("bad.jpg", out.getvalue())

    def test_white_patch_balance(self):
        im = Image.new("RGB", (100, 100), (200, 180, 150))
        im.paste((255, 240, 210), (0, 0, 10, 10))   # 1% of the frame
        out = pi.auto_wb(im)
        r, g, b = out.getpixel((5, 5))
        self.assertLessEqual(max(r, g, b) - min(r, g, b), 6)          # neutral: each within ±3 of the middle
        self.assertTrue(all(abs(c - (max(r, g, b) + min(r, g, b)) / 2) <= 3 for c in (r, g, b)))
        br, bg, bb = out.getpixel((50, 50))
        self.assertLessEqual(bb / 150, pi.WB_MAX_GAIN + 0.01)         # no channel gain above 1.45
        self.assertLessEqual(bg / 180, pi.WB_MAX_GAIN + 0.01)
        self.assertEqual(pi.WB_MAX_GAIN, 1.45)
        cast = Image.new("RGB", (100, 100), (250, 150, 100))          # a heavy cast is only partly corrected
        self.assertEqual(pi.auto_wb(cast).getpixel((0, 0)), (250, 218, 145))   # 1.45 × 150, 1.45 × 100
        self.assertEqual(br, 200)                                     # the brightest channel is untouched

    def test_wb_uses_highlight_band(self):
        # 100 000 px: a 0.52% speck of blown white, a 5% warm highlight band, the rest mid-tone.
        # (At exactly 0.5% white the old 99.5th percentile lands on the band too; 0.52% puts it on the speck.)
        im = Image.new("RGB", (1000, 100), (110, 100, 80))
        im.paste((240, 225, 190), (0, 0, 1000, 5))                 # 5000 px = 5%
        im.paste((255, 255, 255), (0, 5, 520, 6))                  # 520 px = 0.52%
        for hist in (im.histogram()[i * 256:(i + 1) * 256] for i in range(3)):
            acc, pct = 0, None                                     # the old 99.5th-percentile peak
            for v in range(1, 256):
                acc += hist[v]
                if acc >= 0.995 * sum(hist[1:]):
                    pct = v; break
            self.assertEqual(pct, 255)                             # → old gains all 1.0: the band stayed warm
        r, g, b = pi.auto_wb(im).getpixel((500, 2))
        mid = (max(r, g, b) + min(r, g, b)) / 2
        self.assertTrue(all(abs(c - mid) <= 4 for c in (r, g, b)), (r, g, b))

    def test_orientation_survives_icc_conversion(self):
        from PIL import ImageCms
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "s.jpg"
            im = Image.new("RGB", (300, 200), (120, 90, 60)); ex = im.getexif(); ex[0x0112] = 6
            srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
            im.save(src, "JPEG", quality=90, exif=ex.tobytes(), icc_profile=srgb)
            with Image.open(src) as raw:
                self.assertEqual((raw.size, raw.getexif().get(0x0112)), ((300, 200), 6))
                self.assertTrue(raw.info.get("icc_profile"))
            self.assertEqual(pi.decode(src).size, (200, 300))

    def test_quality_floor(self):
        self.assertEqual(pi.QUALITY_LADDER, (82, 78, 74, 70, 66, 62))
        self.assertEqual(min(pi.QUALITY_LADDER), 62)
        with tempfile.TemporaryDirectory() as tmp:               # and _save_within_budget really walks it
            noisy = Image.frombytes("RGB", (400, 400), os.urandom(3 * 400 * 400))
            with self.assertRaises(RuntimeError) as cm:
                pi._save_within_budget(noisy, Path(tmp) / "n.jpg", 1000)
            self.assertIn("even at q62", str(cm.exception))

    PHOTOS = pi.local_paths()["photos"]

    @unittest.skipUnless(PHOTOS and (Path(PHOTOS) / "2021-12_malibu-proposal/raw/6Q3A0126.CR3").exists(), "archive not present")
    def test_real_cr3_decodes(self):
        with tempfile.TemporaryDirectory() as tmp:
            res = pi.make_derivatives({"id": "cr3", "source": "2021-12_malibu-proposal/raw/6Q3A0126.CR3"}, Path(self.PHOTOS), Path(tmp))
            self.assertEqual(max(res[1600][:2]), 1600)

class Markup(unittest.TestCase):
    def _manifest(self):
        return [
            {"id": "a", "category": "private", "caption": "A cap", "alt": "A cap", "w": 800, "h": 600},
            {"id": "b", "category": "installations", "caption": "B <cap>", "alt": "B <cap>", "w": 600, "h": 800},
        ]

    def test_chips_only_for_present_categories_in_order(self):
        blk = pi.render_block(self._manifest())
        self.assertIn('data-cat="installations"', blk)
        self.assertIn('data-cat="private"', blk)
        self.assertNotIn('data-cat="studio"', blk)
        self.assertNotIn('data-cat="weddings"', blk)
        self.assertLess(blk.index('data-cat="installations"'), blk.index('data-cat="private"'))
        self.assertIn('data-cat="all" aria-pressed="true"', blk)

    def test_tile_markup(self):
        blk = pi.render_block(self._manifest())
        self.assertIn('id="item-b"', blk)
        self.assertIn('class="pf-tile pf-tile--portrait"', blk)
        self.assertIn('alt="B &lt;cap&gt;"', blk)
        self.assertIn('href="assets/portfolio/b-1600.jpg"', blk)
        self.assertIn('srcset="assets/portfolio/a-800.jpg 800w, assets/portfolio/a-1600.jpg 1600w"', blk)
        self.assertIn('data-total="2">2 pieces', blk)

    def test_first_tiles_eager(self):
        m = [dict(self._manifest()[0], id=f"i{n}") for n in range(8)]
        blk = pi.render_block(m)
        tiles = blk.split('<a class="pf-tile')[1:]
        self.assertEqual(sum('loading="lazy"' in t for t in tiles), 2)
        self.assertEqual(sum('fetchpriority="high"' in t for t in tiles), 2)

    def test_real_800_dims_used_when_given(self):
        blk = pi.render_block(self._manifest(), {"a": (799, 601), "b": (601, 799)})
        self.assertIn('src="assets/portfolio/a-800.jpg"', blk)
        self.assertIn('width="799" height="601"', blk)
        self.assertIn('width="601" height="799"', blk)
        self.assertNotIn('width="800" height="600"', blk)
        self.assertIn('width="800" height="600"', pi.render_block(self._manifest()))   # fallback unchanged

    def test_manifest_has_no_private_fields(self):
        items = [{"id": "a", "category": "studio", "source": "x.jpg", "caption": "C", "note": "secret"}]
        m = pi.build_manifest(items, {"a": {1600: (1600, 1200, 1), 800: (800, 600, 1)}})
        self.assertEqual(set(m[0]), {"id", "category", "caption", "alt", "w", "h"})
        self.assertEqual((m[0]["w"], m[0]["h"]), (1600, 1200))

class Inject(unittest.TestCase):
    def test_replaces_between_markers_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "p.html"
            page.write_text(f"<h1>x</h1>\n{pi.START}\nold\n{pi.END}\n<p>y</p>\n")
            self.assertTrue(pi.inject(page, "<div>new</div>"))
            self.assertEqual(page.read_text(), f"<h1>x</h1>\n{pi.START}\n<div>new</div>\n{pi.END}\n<p>y</p>\n")
            self.assertFalse(pi.inject(page, "<div>new</div>"))

    def test_missing_markers_raises_and_leaves_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "p.html"; page.write_text("<h1>x</h1>")
            with self.assertRaises(ValueError): pi.inject(page, "z")
            self.assertEqual(page.read_text(), "<h1>x</h1>")

class Build(unittest.TestCase):
    def _site(self, tmp):
        site = Path(tmp) / "site"; (site / "assets").mkdir(parents=True)
        (site / "portfolio.html").write_text(f"<html>{pi.START}\n{pi.END}</html>")
        photos = Path(tmp) / "photos"; photos.mkdir()
        make_jpeg(photos / "a.jpg", 2400, 1600); make_jpeg(photos / "b.jpg", 1600, 2400)
        sel = write_selects(tmp, [
            {"id": "a", "category": "corporate", "source": "a.jpg", "caption": "A", "note": "n"},
            {"id": "b", "category": "studio", "source": "b.jpg", "caption": "B", "note": "n"}])
        return site, photos, sel

    def test_second_run_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            site, photos, sel = self._site(tmp)
            argv = ["--selects", str(sel), "--photos", str(photos), "--site", str(site)]
            self.assertEqual(pi.main(argv), 0)
            snap = {p: p.read_bytes() for p in site.rglob("*") if p.is_file()}
            self.assertEqual(pi.main(argv), 0)
            self.assertEqual({p: p.read_bytes() for p in site.rglob("*") if p.is_file()}, snap)
            self.assertNotIn("note", (site / "assets/portfolio/manifest.json").read_text())
            import re
            tiles = re.findall(r'id="item-([^"]+)".*?width="(\d+)" height="(\d+)"', (site / "portfolio.html").read_text())
            self.assertEqual(sorted(t[0] for t in tiles), ["a", "b"])
            for tid, w, h in tiles:
                with Image.open(site / f"assets/portfolio/{tid}-800.jpg") as d:
                    self.assertEqual((int(w), int(h)), d.size, tid)

    def test_inject_is_atomic_on_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            site, photos, sel = self._site(tmp)
            (photos / "b.jpg").unlink()
            before = (site / "portfolio.html").read_text()
            argv = ["--selects", str(sel), "--photos", str(photos), "--site", str(site)]
            self.assertNotEqual(pi.main(argv), 0)
            self.assertEqual((site / "portfolio.html").read_text(), before)
            self.assertFalse((site / "assets/portfolio/manifest.json").exists())

class Check(unittest.TestCase):
    def test_passes_after_build_and_flags_leak(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"; (site / "assets").mkdir(parents=True)
            (site / "portfolio.html").write_text(f"<html>{pi.START}\n{pi.END}</html>")
            (site / "index.html").write_text('<a href="portfolio.html">Portfolio</a>')
            photos = Path(tmp) / "photos"; photos.mkdir(); make_jpeg(photos / "a.jpg", 2400, 1600)
            sel = write_selects(tmp, [{"id": "a", "category": "studio", "source": "a.jpg", "caption": "A", "note": ""}])
            argv = ["--selects", str(sel), "--photos", str(photos), "--site", str(site)]
            self.assertEqual(pi.main(argv), 0)
            self.assertEqual(pi.main(argv + ["--check"]), 0)
            (site / "leak.txt").write_text("/Us" + "ers/x/Abby" + "-claude/Photos")  # split so this file never holds the literal
            self.assertEqual(pi.main(argv + ["--check"]), 1)
            (site / "leak.txt").unlink()
            (site / "index.html").write_text('<a href="#work">Portfolio</a>')
            self.assertEqual(pi.main(argv + ["--check"]), 1)

    def test_flags_missing_derivative(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"; (site / "assets").mkdir(parents=True)
            (site / "portfolio.html").write_text(f"<html>{pi.START}\n{pi.END}</html>")
            (site / "index.html").write_text("")
            photos = Path(tmp) / "photos"; photos.mkdir(); make_jpeg(photos / "a.jpg", 2400, 1600)
            sel = write_selects(tmp, [{"id": "a", "category": "studio", "source": "a.jpg", "caption": "A", "note": ""}])
            argv = ["--selects", str(sel), "--photos", str(photos), "--site", str(site)]
            pi.main(argv); (site / "assets/portfolio/a-800.jpg").unlink()
            self.assertEqual(pi.main(argv + ["--check"]), 1)

    def test_check_flags_over_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"; (site / "assets").mkdir(parents=True)
            (site / "portfolio.html").write_text(f"<html>{pi.START}\n{pi.END}</html>")
            (site / "index.html").write_text("")
            photos = Path(tmp) / "photos"; photos.mkdir(); make_jpeg(photos / "a.jpg", 2400, 1600)
            sel = write_selects(tmp, [{"id": "a", "category": "studio", "source": "a.jpg", "caption": "A", "note": ""}])
            argv = ["--selects", str(sel), "--photos", str(photos), "--site", str(site)]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(pi.main(argv), 0)
            d = site / "assets/portfolio/a-800.jpg"
            with Image.open(d) as cur:
                size = cur.size
            noisy = Image.frombytes("RGB", size, os.urandom(3 * size[0] * size[1]))
            noisy.save(d, "JPEG", quality=100)                          # a q100 re-save, well over the 800 budget
            self.assertGreater(d.stat().st_size, pi.BUDGET[800])
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(pi.main(argv + ["--check"]), 1)
            self.assertIn("a-800.jpg", out.getvalue())
            self.assertIn("over 150000", out.getvalue())

    def test_flags_home_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"; (site / "assets").mkdir(parents=True)
            (site / "portfolio.html").write_text(f"<html>{pi.START}\n{pi.END}</html>")
            (site / "index.html").write_text("")
            photos = Path(tmp) / "photos"; photos.mkdir(); make_jpeg(photos / "a.jpg", 2400, 1600)
            sel = write_selects(tmp, [{"id": "a", "category": "studio", "source": "a.jpg", "caption": "A", "note": ""}])
            argv = ["--selects", str(sel), "--photos", str(photos), "--site", str(site)]
            with contextlib.redirect_stdout(io.StringIO()):
                pi.main(argv)
            (site / "notes.md").write_text("see /Us" + "ers/someone/elsewhere")
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(pi.main(argv + ["--check"]), 1)
            self.assertIn("notes.md: contains an absolute home path", out.getvalue())

    def _built(self, tmp):
        site = Path(tmp) / "site"; (site / "assets").mkdir(parents=True)
        (site / "portfolio.html").write_text(f"<html>{pi.START}\n{pi.END}</html>")
        (site / "index.html").write_text("")
        photos = Path(tmp) / "photos"; photos.mkdir(); make_jpeg(photos / "a.jpg", 2400, 1600)
        sel = write_selects(tmp, [{"id": "a", "category": "studio", "source": "a.jpg", "caption": "A", "note": ""}])
        argv = ["--selects", str(sel), "--photos", str(photos), "--site", str(site)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pi.main(argv), 0)
            self.assertEqual(pi.main(argv + ["--check"]), 0)
        return site, argv

    def test_check_flags_private_marker_without_home_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            site, argv = self._built(tmp)
            marker = "Abby" + "-claude"
            (site / "notes.txt").write_text(marker)
            self.assertNotIn("/Us" + "ers/", (site / "notes.txt").read_text())
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(pi.main(argv + ["--check"]), 1)
            self.assertIn("notes.txt: contains private path", out.getvalue())

    def test_check_flags_eager_payload_over_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            site, argv = self._built(tmp)
            saved = pi.EAGER_BUDGET
            try:
                pi.EAGER_BUDGET = 1
                with contextlib.redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(pi.main(argv + ["--check"]), 1)
            finally:
                pi.EAGER_BUDGET = saved
            self.assertIn("eager payload", out.getvalue())

if __name__ == "__main__":
    unittest.main()
