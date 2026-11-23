#!/usr/bin/env python3
"""
slop_checker.py - Static analysis tool for detecting AI slop in HTML/CSS.

Scans generated frontend code for telltale signs of generic AI output:
blacklisted fonts, default color palettes, symmetric layouts, cliche copy,
and monotonous animations.

Python 3.8+ stdlib only. No external dependencies.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Tuple


class Severity(Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass
class Finding:
    severity: Severity
    category: str
    line: int  # 0 means no specific line
    message: str


@dataclass
class CheckResult:
    findings: List[Finding] = field(default_factory=list)

    @property
    def fail_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.FAIL)

    @property
    def warn_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.WARN)

    @property
    def pass_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.PASS)


# ---------------------------------------------------------------------------
# Blacklists
# ---------------------------------------------------------------------------

BLACKLISTED_FONTS = [
    "inter",
    "roboto",
    "arial",
    "open sans",
    "poppins",
    "space grotesk",
    "montserrat",
    "system-ui",
]

BLACKLISTED_HEX_COLORS = {
    "#6366f1": "Tailwind indigo-500",
    "#8b5cf6": "Tailwind violet-500",
    "#a855f7": "Tailwind purple-500",
    "#3b82f6": "Tailwind blue-500",
    "#818cf8": "Tailwind indigo-400",
    "#7c3aed": "Tailwind violet-600",
    "#9333ea": "Tailwind purple-600",
    "#2563eb": "Tailwind blue-600",
}

BLACKLISTED_TAILWIND_CLASSES = [
    r"bg-indigo-\d+",
    r"bg-purple-\d+",
    r"bg-violet-\d+",
    r"from-indigo-\d+",
    r"from-purple-\d+",
    r"from-violet-\d+",
    r"to-indigo-\d+",
    r"to-purple-\d+",
    r"to-violet-\d+",
    r"via-indigo-\d+",
    r"via-purple-\d+",
    r"via-violet-\d+",
    r"text-indigo-\d+",
    r"text-purple-\d+",
    r"text-violet-\d+",
    r"border-indigo-\d+",
    r"border-purple-\d+",
    r"border-violet-\d+",
    r"ring-indigo-\d+",
    r"ring-purple-\d+",
    r"ring-violet-\d+",
]

BLACKLISTED_COPY_PHRASES = [
    "revolutionize your workflow",
    "seamlessly integrate",
    "unlock the power",
    "take your .* to the next level",
    "supercharge your",
    "streamline your",
    "transform the way you",
    "cutting-edge solution",
    "game-changing",
    "leverage the power",
    "empower your team",
    "next-generation platform",
    "effortlessly manage",
    "built for the modern",
    "scale with confidence",
    "designed for developers",
    "trusted by thousands",
    "start your journey",
    "the future of",
    "everything you need",
    "all-in-one platform",
    "powerful yet simple",
    "works like magic",
    "it just works",
    "reimagine your",
    "elevate your",
]

# ---------------------------------------------------------------------------
# Checkers
# ---------------------------------------------------------------------------


def check_typography(lines: List[str]) -> List[Finding]:
    """Scan for blacklisted font families in font-family declarations and @import URLs."""
    findings: List[Finding] = []
    font_found = False

    for i, line in enumerate(lines, start=1):
        lower = line.lower()

        # Check font-family declarations
        if "font-family" in lower:
            for font in BLACKLISTED_FONTS:
                if font in lower:
                    findings.append(Finding(
                        Severity.WARN if font == "system-ui" else Severity.FAIL,
                        "TYPOGRAPHY",
                        i,
                        f"'{font.title()}' used in font-family (consider a more distinctive choice)",
                    ))
                    font_found = True

        # Check @import / link href for Google Fonts
        if "@import" in lower or "fonts.googleapis.com" in lower:
            for font in BLACKLISTED_FONTS:
                # Google Fonts URL uses + for spaces: Open+Sans
                url_font = font.replace(" ", "+")
                if url_font in lower or font.replace(" ", "") in lower:
                    findings.append(Finding(
                        Severity.WARN,
                        "TYPOGRAPHY",
                        i,
                        f"'{font.title()}' imported via Google Fonts (consider a more distinctive choice)",
                    ))
                    font_found = True

    if not font_found:
        findings.insert(0, Finding(Severity.PASS, "TYPOGRAPHY", 0, "No blacklisted display fonts detected"))

    return findings


def check_colors(lines: List[str]) -> List[Finding]:
    """Scan for blacklisted hex colors and default Tailwind color utility classes."""
    findings: List[Finding] = []
    hex_found = False
    tw_found = False

    hex_pattern = re.compile(r"#[0-9a-fA-F]{6}\b")

    for i, line in enumerate(lines, start=1):
        # Hex color check
        for match in hex_pattern.finditer(line):
            color = match.group(0).lower()
            if color in BLACKLISTED_HEX_COLORS:
                findings.append(Finding(
                    Severity.FAIL,
                    "COLOR",
                    i,
                    f"{color} ({BLACKLISTED_HEX_COLORS[color]}) — a top AI default color",
                ))
                hex_found = True

        # Tailwind class check
        for tw_re in BLACKLISTED_TAILWIND_CLASSES:
            tw_matches = re.findall(tw_re, line)
            for tw_match in tw_matches:
                findings.append(Finding(
                    Severity.FAIL,
                    "COLOR",
                    i,
                    f"Default Tailwind class '{tw_match}' — use custom colors instead",
                ))
                tw_found = True

    if not hex_found:
        findings.append(Finding(Severity.PASS, "COLOR", 0, "No blacklisted hex colors detected"))
    if not tw_found:
        findings.append(Finding(Severity.PASS, "COLOR", 0, "No default Tailwind color classes detected"))

    return findings


def check_layout(lines: List[str]) -> List[Finding]:
    """Detect symmetric grid-cols-3 as primary layout pattern."""
    findings: List[Finding] = []
    grid3_lines: List[int] = []

    for i, line in enumerate(lines, start=1):
        if "grid-cols-3" in line:
            grid3_lines.append(i)

    if grid3_lines:
        # Check if there's layout variation (grid-cols-2, grid-cols-4, etc.)
        has_variation = False
        for line in lines:
            if re.search(r"grid-cols-[^3]", line):
                has_variation = True
                break

        if not has_variation:
            lines_str = ", ".join(str(l) for l in grid3_lines)
            findings.append(Finding(
                Severity.WARN,
                "LAYOUT",
                grid3_lines[0],
                f"Symmetric grid-cols-3 at line(s) {lines_str} with no grid variation — the #1 AI layout cliche",
            ))
        else:
            findings.append(Finding(Severity.PASS, "LAYOUT", 0, "Grid layout has variation"))
    else:
        findings.append(Finding(Severity.PASS, "LAYOUT", 0, "No symmetric 3-column card grid detected"))

    return findings


def check_card_overuse(lines: List[str]) -> List[Finding]:
    """Detect excessive rounded-xl + shadow-lg combinations."""
    findings: List[Finding] = []
    combo_lines: List[int] = []

    for i, line in enumerate(lines, start=1):
        has_rounded = "rounded-xl" in line or "rounded-2xl" in line or "rounded-3xl" in line
        has_shadow = "shadow-lg" in line or "shadow-xl" in line or "shadow-2xl" in line
        if has_rounded and has_shadow:
            combo_lines.append(i)

    if len(combo_lines) > 3:
        lines_str = ", ".join(str(l) for l in combo_lines[:5])
        findings.append(Finding(
            Severity.WARN,
            "LAYOUT",
            combo_lines[0],
            f"Excessive rounded-xl + shadow-lg combos ({len(combo_lines)} instances at lines {lines_str}) — vary your card treatments",
        ))
    else:
        findings.append(Finding(Severity.PASS, "LAYOUT", 0, "No excessive rounded + shadow combinations"))

    return findings


def check_animations(lines: List[str]) -> List[Finding]:
    """Detect animation uniformity (only fade-in-up patterns, no variety)."""
    findings: List[Finding] = []
    content = "\n".join(lines)

    # Patterns that indicate fade-in-up style animations
    fade_up_patterns = [
        r"translateY\([^)]*\).*opacity",
        r"opacity.*translateY",
        r"fade-in-up",
        r"fadeInUp",
        r"fade-up",
        r"slide-up",
        r"animate-fade-in",
    ]

    # Patterns that indicate animation variety
    variety_patterns = [
        r"translateX",
        r"scale\(",
        r"rotate\(",
        r"skew\(",
        r"clip-path",
        r"slide-in-left",
        r"slide-in-right",
        r"zoom",
        r"bounce",
        r"flip",
        r"blur\(",
        r"stagger",
    ]

    has_fade_up = False
    fade_up_line = 0
    for i, line in enumerate(lines, start=1):
        for pat in fade_up_patterns:
            if re.search(pat, line, re.IGNORECASE):
                has_fade_up = True
                if fade_up_line == 0:
                    fade_up_line = i
                break

    has_variety = False
    for pat in variety_patterns:
        if re.search(pat, content, re.IGNORECASE):
            has_variety = True
            break

    if has_fade_up and not has_variety:
        findings.append(Finding(
            Severity.WARN,
            "ANIMATION",
            fade_up_line,
            "Only fade-in-up animations detected — add variety (scale, rotate, clip-path, stagger)",
        ))
    elif not has_fade_up:
        findings.append(Finding(Severity.PASS, "ANIMATION", 0, "No animation uniformity issues detected"))
    else:
        findings.append(Finding(Severity.PASS, "ANIMATION", 0, "Animations show variety"))

    return findings


def check_copy(lines: List[str]) -> List[Finding]:
    """Detect blacklisted AI copy phrases."""
    findings: List[Finding] = []
    found_any = False

    for i, line in enumerate(lines, start=1):
        lower = line.lower()
        for phrase in BLACKLISTED_COPY_PHRASES:
            if re.search(phrase, lower):
                readable = phrase.replace(r".*", "...").replace("\\", "")
                # Extract the actual matched text
                match = re.search(phrase, lower)
                if match:
                    matched_text = line[match.start():match.end()]
                else:
                    matched_text = readable
                findings.append(Finding(
                    Severity.FAIL,
                    "COPY",
                    i,
                    f'"{matched_text.strip()}" — blacklisted AI copy phrase',
                ))
                found_any = True

    if not found_any:
        findings.append(Finding(Severity.PASS, "COPY", 0, "No blacklisted AI copy phrases detected"))

    return findings


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_text(result: CheckResult, filename: str, verbose: bool = False) -> str:
    """Format findings as human-readable text output."""
    out: List[str] = []
    out.append(f"=== SLOP CHECK: {filename} ===")
    out.append("")

    # Group by category, preserving order
    categories_order = ["TYPOGRAPHY", "COLOR", "LAYOUT", "ANIMATION", "COPY"]
    grouped: Dict[str, List[Finding]] = {cat: [] for cat in categories_order}

    for f in result.findings:
        if f.category in grouped:
            grouped[f.category].append(f)

    for cat in categories_order:
        cat_findings = grouped[cat]
        if not cat_findings:
            continue

        out.append(cat)
        for f in cat_findings:
            sev = f.severity.value
            if f.line > 0:
                out.append(f"  {sev:4s}  Line {f.line}: {f.message}")
            else:
                out.append(f"  {sev:4s}  {f.message}")
        out.append("")

    out.append(f"=== RESULT: {result.fail_count} FAIL, {result.warn_count} WARN, {result.pass_count} PASS ===")

    if result.fail_count > 0:
        out.append("Overall: FAIL (must fix FAIL items before shipping)")
    elif result.warn_count > 0:
        out.append("Overall: WARN (review warnings before shipping)")
    else:
        out.append("Overall: PASS")

    return "\n".join(out)


def format_json(result: CheckResult, filename: str) -> str:
    """Format findings as machine-readable JSON."""
    data = {
        "file": filename,
        "overall": "FAIL" if result.fail_count > 0 else ("WARN" if result.warn_count > 0 else "PASS"),
        "summary": {
            "fail": result.fail_count,
            "warn": result.warn_count,
            "pass": result.pass_count,
        },
        "findings": [
            {
                "severity": f.severity.value,
                "category": f.category,
                "line": f.line if f.line > 0 else None,
                "message": f.message,
            }
            for f in result.findings
        ],
    }
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_checks(lines: List[str]) -> CheckResult:
    """Run all checks and aggregate findings."""
    result = CheckResult()
    result.findings.extend(check_typography(lines))
    result.findings.extend(check_colors(lines))
    result.findings.extend(check_layout(lines))
    result.findings.extend(check_card_overuse(lines))
    result.findings.extend(check_animations(lines))
    result.findings.extend(check_copy(lines))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check HTML/CSS files for AI slop signals.",
        epilog="Exit code: 0 = PASS (no FAILs), 1 = FAIL (one or more FAILs).",
    )
    parser.add_argument("file", help="Path to an HTML or CSS file to check")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser.add_argument("--json", dest="use_json", action="store_true", help="Output machine-readable JSON")

    args = parser.parse_args()

    filepath = Path(args.file)
    if not filepath.exists():
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        return 1

    if filepath.suffix.lower() not in (".html", ".htm", ".css", ".vue", ".svelte", ".jsx", ".tsx"):
        print(f"Warning: Unexpected file extension '{filepath.suffix}'. Proceeding anyway.", file=sys.stderr)

    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return 1

    lines = content.splitlines()
    result = run_checks(lines)

    if args.use_json:
        print(format_json(result, filepath.name))
    else:
        print(format_text(result, filepath.name, verbose=args.verbose))

    return 1 if result.fail_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
