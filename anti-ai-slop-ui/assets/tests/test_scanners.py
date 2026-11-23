#!/usr/bin/env python3
"""Self-tests for anti-ai-slop-ui scanner scripts (stdlib unittest only)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
DEVIBE = SKILL_DIR / "scripts" / "devibe_scan.py"
SLOP = SKILL_DIR / "scripts" / "slop_checker.py"
EMBLEMS = SKILL_DIR / "assets" / "bespoke-emblems.js"

CLEAN_CSS = """\
:root {
  --bg-canvas: #f1f2ed;
  --bg-surface: #ffffff;
  --text-primary: #14171a;
  --brand-primary: #164e78;
  --cinnabar: #d14828;
  --font-sans: 'Plus Jakarta Sans', 'Noto Sans TC', sans-serif;
  --font-mono: 'IBM Plex Mono', monospace;
  --radius-sm: 7px;
}
body {
  background: var(--bg-canvas);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-variant-numeric: tabular-nums;
}
.editorial-chapter {
  display: grid;
  grid-template-columns: 270px minmax(0, 1fr);
  gap: 1.5rem;
}
"""

CLEAN_HTML = """\
<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <title>企業入口網</title>
</head>
<body>
  <header class="editorial-header">
    <h1>廠務平台目錄</h1>
  </header>
  <main class="editorial-chapter">
    <section class="chapter-poster">01</section>
    <section class="chapter-tiles-grid">
      <article class="launch-tile">
        <h2>設備保養系統</h2>
        <button type="button" class="tile-launch-keycap">開啟</button>
      </article>
    </section>
  </main>
</body>
</html>
"""

SLOP_CSS = """\
body {
  background: #faf8f5;
  font-family: 'Inter', 'Instrument Serif', sans-serif;
}
.hero-title {
  color: #6366f1;
  background-clip: text;
}
.pill-btn {
  border-radius: 9999px;
}
"""

SLOP_HTML = """\
<!doctype html>
<html>
<body>
  <section class="bg-indigo-600">
    <h1>Revolutionize your workflow today</h1>
  </section>
</body>
</html>
"""


class TestAntiAiSlopScanners(unittest.TestCase):
    def test_devibe_clean_files_zero_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "styles.css").write_text(CLEAN_CSS, encoding="utf-8")
            (root / "index.html").write_text(CLEAN_HTML, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(DEVIBE), str(root), "--json"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            report = json.loads(proc.stdout)
            self.assertEqual(report["vibe_score"], 0)
            self.assertEqual(report["findings"], [])

    def test_devibe_flags_both_generations_of_slop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "slop.css").write_text(SLOP_CSS, encoding="utf-8")
            (root / "slop.html").write_text(SLOP_HTML, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(DEVIBE), str(root), "--json"],
                capture_output=True, text=True, check=False,
            )
            self.assertGreater(proc.returncode, 0)
            report = json.loads(proc.stdout)
            rules = {f["rule"] for f in report["findings"]}
            self.assertIn("ai-purple", rules)
            self.assertIn("gradient-text", rules)
            self.assertIn("claude-default-look", rules)
            self.assertIn("rounded-everything", rules)
            self.assertIn("generic-font", rules)

    def test_devibe_bundled_emblems_are_clean(self):
        proc = subprocess.run(
            [sys.executable, str(DEVIBE), str(EMBLEMS), "--json"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual(report["vibe_score"], 0)

    def test_slop_checker_passes_clean_style_seed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, content in (("styles.css", CLEAN_CSS), ("index.html", CLEAN_HTML)):
                p = root / name
                p.write_text(content, encoding="utf-8")
                proc = subprocess.run(
                    [sys.executable, str(SLOP), "--json", str(p)],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                report = json.loads(proc.stdout)
                self.assertEqual(report["overall"], "PASS")
                self.assertEqual(report["summary"]["fail"], 0)
                self.assertEqual(report["summary"]["warn"], 0)

    def test_slop_checker_fails_on_slop_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            css = root / "slop.css"
            css.write_text(SLOP_CSS, encoding="utf-8")
            proc_css = subprocess.run(
                [sys.executable, str(SLOP), "--json", str(css)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc_css.returncode, 1)
            css_report = json.loads(proc_css.stdout)
            self.assertGreaterEqual(css_report["summary"]["fail"], 2)

            html = root / "slop.html"
            html.write_text(SLOP_HTML, encoding="utf-8")
            proc_html = subprocess.run(
                [sys.executable, str(SLOP), "--json", str(html)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc_html.returncode, 1)
            html_report = json.loads(proc_html.stdout)
            cats = {f["category"] for f in html_report["findings"] if f["severity"] == "FAIL"}
            self.assertIn("COLOR", cats)
            self.assertIn("COPY", cats)


if __name__ == "__main__":
    unittest.main()
