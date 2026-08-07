#!/usr/bin/env python3
"""Validate and render a PR Brief as a single self-contained HTML file."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import urlparse


STANCES = {"Ship it", "Ship with follow-ups", "Hold"}

STANCE_BADGE = {
    "Ship it": "badge-success",
    "Ship with follow-ups": "badge-outline",
    "Hold": "badge-danger",
}


# Octicon paths (MIT, GitHub) — the same five families rendered here as in the
# review artifact, kept to the icons this document actually uses.
ICON_SPRITE = """<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>\
<symbol id="i-external" viewBox="0 0 16 16"><path d="M3.75 2h3.5a.75.75 0 0 1 0 1.5h-3.5a.25.25 0 0 0-.25.25v8.5c0 .138.112.25.25.25h8.5a.25.25 0 0 0 .25-.25v-3.5a.75.75 0 0 1 1.5 0v3.5A1.75 1.75 0 0 1 12.25 14h-8.5A1.75 1.75 0 0 1 2 12.25v-8.5C2 2.784 2.784 2 3.75 2Zm6.854-1h4.146a.25.25 0 0 1 .25.25v4.146a.25.25 0 0 1-.427.177L13.03 4.03 9.28 7.78a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042l3.75-3.75-1.543-1.543A.25.25 0 0 1 10.604 1Z"/></symbol>\
<symbol id="i-sun" viewBox="0 0 16 16"><path d="M8 12a4 4 0 1 1 0-8 4 4 0 0 1 0 8Zm0-1.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Zm5.657-8.157a.75.75 0 0 1 0 1.061l-1.061 1.06a.749.749 0 0 1-1.275-.326.749.749 0 0 1 .215-.734l1.06-1.06a.75.75 0 0 1 1.06 0Zm-9.193 9.193a.75.75 0 0 1 0 1.06l-1.06 1.061a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042l1.06-1.06a.75.75 0 0 1 1.06 0ZM8 0a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 1-1.5 0V.75A.75.75 0 0 1 8 0ZM3 8a.75.75 0 0 1-.75.75H.75a.75.75 0 0 1 0-1.5h1.5A.75.75 0 0 1 3 8Zm13 0a.75.75 0 0 1-.75.75h-1.5a.75.75 0 0 1 0-1.5h1.5A.75.75 0 0 1 16 8ZM8 13a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 1-1.5 0v-1.5A.75.75 0 0 1 8 13ZM2.343 2.343a.75.75 0 0 1 1.061 0l1.06 1.061a.751.751 0 0 1-.018 1.042.751.751 0 0 1-1.042.018l-1.06-1.06a.75.75 0 0 1 0-1.06Zm9.193 9.193a.75.75 0 0 1 1.06 0l1.061 1.06a.751.751 0 0 1-.018 1.042.751.751 0 0 1-1.042.018l-1.06-1.06a.75.75 0 0 1 0-1.06Z"/></symbol>\
<symbol id="i-moon" viewBox="0 0 16 16"><path d="M9.598 1.591a.749.749 0 0 1 .785-.175 7.001 7.001 0 1 1-8.967 8.967.75.75 0 0 1 .961-.96 5.5 5.5 0 0 0 7.046-7.046.75.75 0 0 1 .175-.786Zm1.616 1.945a7 7 0 0 1-7.678 7.678 5.499 5.499 0 1 0 7.678-7.678Z"/></symbol>\
<symbol id="i-star" viewBox="0 0 16 16"><path d="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Zm0 2.445L6.615 5.5a.75.75 0 0 1-.564.41l-3.097.45 2.24 2.184a.75.75 0 0 1 .216.664l-.528 3.084 2.769-1.456a.75.75 0 0 1 .698 0l2.77 1.456-.53-3.084a.75.75 0 0 1 .216-.664l2.24-2.183-3.096-.45a.75.75 0 0 1-.564-.41L8 2.694Z"/></symbol>\
<symbol id="i-tick" viewBox="0 0 16 16"><path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"/></symbol>\
<symbol id="i-alert" viewBox="0 0 16 16"><path d="M6.457 1.047c.659-1.234 2.427-1.234 3.086 0l6.082 11.378A1.75 1.75 0 0 1 14.082 15H1.918a1.75 1.75 0 0 1-1.543-2.575Zm1.763.707a.25.25 0 0 0-.44 0L1.698 13.132a.25.25 0 0 0 .22.368h12.164a.25.25 0 0 0 .22-.368Zm.53 3.996v2.5a.75.75 0 0 1-1.5 0v-2.5a.75.75 0 0 1 1.5 0ZM9 11a1 1 0 1 1-2 0 1 1 0 0 1 2 0Z"/></symbol>\
<symbol id="i-book" viewBox="0 0 16 16"><path d="M0 1.75A.75.75 0 0 1 .75 1h4.253c1.227 0 2.317.59 3 1.501A3.743 3.743 0 0 1 11.006 1h4.245a.75.75 0 0 1 .75.75v10.5a.75.75 0 0 1-.75.75h-4.507a2.25 2.25 0 0 0-1.591.659l-.622.621a.75.75 0 0 1-1.06 0l-.622-.621A2.25 2.25 0 0 0 5.258 13H.75a.75.75 0 0 1-.75-.75Zm7.251 10.324.004-5.073-.002-2.253A2.25 2.25 0 0 0 5.003 2.5H1.5v9h3.757a3.75 3.75 0 0 1 1.994.574ZM8.755 4.75l-.004 7.322a3.752 3.752 0 0 1 1.992-.572H14.5v-9h-3.495a2.25 2.25 0 0 0-2.25 2.25Z"/></symbol>\
</defs></svg>"""


def icon(name: str, css_class: str = "icon") -> str:
    return f'<svg class="{css_class}" viewBox="0 0 16 16" aria-hidden="true"><use href="#i-{name}"/></svg>'


# Same dark palette as the review artifact, declared once and emitted twice: under the
# OS preference for readers who never touch the toggle, and under an explicit
# [data-theme] for those who do.
DARK_VARS = r"""
--canvas: #0a0a0a;
    --surface: #171717;
    --paper: #262626;
    --ink: #fafafa;
    --ink-soft: #d4d4d4;
    --muted: #a3a3a3;
    --line: #262626;
    --line-strong: #404040;
    --sidebar: #171717;
    --primary: #fafafa;
    --primary-hover: #ffffff;
    /* interactive */
    --accent: #35b894;
    --accent-hover: #4fd0ac;
    --accent-soft: rgba(53, 184, 148, .16);
    --accent-line: rgba(53, 184, 148, .38);
    --accent-ink: #7fe0c4;
    --focus: #35b894;
    --active: #35b894;
    --glass-accent: rgba(53, 184, 148, .14);
    --glass-accent-hover: rgba(53, 184, 148, .24);
    --glass-accent-line: rgba(53, 184, 148, .40);
    /* semantic */
    --success: #34d399;
    --warning: #cbd5e1;
    --lookup: #38bdf8;
    --lookup-soft: rgba(56, 189, 248, .12);
    --lookup-line: rgba(56, 189, 248, .38);
    --logic: #c4b5fd;
    --agent: #f0abfc;
    --destructive: #f87171;
    --destructive-soft: rgba(248, 113, 113, .12);
    --slate-soft: rgba(148, 163, 184, .12);
    --slate-line: #475569;
    --p0: #f87171;
    --p1: #e2e8f0;
    --p2: #cbd5e1;
    --p3: #94a3b8;
    /* diff */
    --add: rgba(52, 211, 153, .10);
    --add-strong: #34d399;
    --add-ink: #6ee7b7;
    --del: rgba(248, 113, 113, .10);
    --del-strong: #f87171;
    --del-ink: #fca5a5;
    --code: #e4e4e7;
    --code-muted: #737373;
    /* the sheen inverts: light lands on a dark edge far more faintly */
    --sheen: rgba(255, 255, 255, .04);
    --sheen-mid: rgba(255, 255, 255, .06);
    --sheen-strong: rgba(255, 255, 255, .08);
    --wash: rgba(255, 255, 255, .05);
    --wash-strong: rgba(255, 255, 255, .08);
    --fill-raised: linear-gradient(to bottom, #1f1f1f, #171717);
    --fill-glass: linear-gradient(to bottom, rgba(32,32,32,.86), rgba(23,23,23,.72));
    --fill-glass-soft: linear-gradient(to bottom, rgba(32,32,32,.78), rgba(23,23,23,.64));
    --fill-glass-solid: linear-gradient(to bottom, rgba(38,38,38,.94), rgba(28,28,28,.86));
    --fill-accent: linear-gradient(to bottom, rgba(32,32,32,.86), rgba(20,54,45,.66));
    --fill-accent-on: linear-gradient(to bottom, rgba(20,54,45,.80), rgba(16,44,37,.90));
    --fill-accent-hover: linear-gradient(to bottom, rgba(24,66,55,.86), rgba(18,50,42,.94));
    --fill-lookup: linear-gradient(to bottom, rgba(32,32,32,.84), rgba(12,42,60,.62));
    --fill-danger: linear-gradient(to bottom, rgba(32,32,32,.84), rgba(56,20,20,.62));
    --fill-danger-strong: linear-gradient(to bottom, rgba(36,36,36,.90), rgba(66,24,24,.70));
    --fill-icon: linear-gradient(to bottom, rgba(53,184,148,.28) 0%, var(--accent-soft) 58%, rgba(53,184,148,.10) 100%);
    /* casts go darker and deeper; a light-mode shadow disappears on near-black */
    --shadow-soft: inset 0 1px 0 0 var(--sheen), 0 1px 2px 0 rgba(0,0,0,.40), 0 10px 28px -10px rgba(0,0,0,.55);
    --shadow: var(--shadow-soft);
    --shadow-float: inset 0 1px 0 0 var(--sheen-mid), 0 1px 2px 0 rgba(0,0,0,.45), 0 16px 40px -16px rgba(0,0,0,.65);
    --shadow-accent: 0 2px 8px -2px rgba(53,184,148,.30), inset 0 1px 0 0 var(--sheen);
    --glass-bg: rgba(23, 23, 23, .74);
    --glass-line: rgba(64, 64, 64, .70);
    --glass-blur: blur(14px) saturate(1.7);
    --panel-bg: rgba(23, 23, 23, .84);
    --panel-line: rgba(64, 64, 64, .80);
    /* grain reads as noise on dark; drop it well back */
    --logo: url('data:image/png;base64,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');
  --grain: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3'/%3E%3C/filter%3E%3Crect width='120' height='120' filter='url(%23n)' opacity='.06'/%3E%3C/svg%3E");
"""


def theme_css() -> str:
    """Emit the dark declarations for both the OS-preference and toggled paths."""
    return (
        '@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {'
        + DARK_VARS + "} }\n"
        + ':root[data-theme="dark"] {' + DARK_VARS + "}\n"
    )


STYLES = r"""
:root {
  /* type scale */
  --font-sans: "Sora", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-content: "Geist", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-mono: "JetBrains Mono", "Geist Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  --font-serif: "Playfair Display", Georgia, serif;
  --text-2xs: .625rem;
  --text-xs: .6875rem;
  --text-sm: .75rem;
  --text-md: .8125rem;
  --text-base: .875rem;
  --text-lg: 1rem;
  --text-xl: 1.25rem;
  --lead-tight: 1.06;
  --lead-snug: 1.32;
  --lead-normal: 1.6;
  --track-wide: .09em;
  --track-tight: -.015em;
  --track-display: -.042em;
  /* spacing scale */
  --space-1: .25rem;
  --space-2: .5rem;
  --space-3: .75rem;
  --space-4: 1rem;
  --space-5: 1.25rem;
  --space-6: 1.5rem;
  --space-7: 1.75rem;
  --space-8: 2rem;
  --space-10: 2.5rem;
  /* radii — derived from --radius exactly as app/globals.css does */
  --radius: .5rem;
  --radius-sm: calc(var(--radius) * .6);
  --radius-md: calc(var(--radius) * .8);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) * 1.4);
  --radius-2xl: calc(var(--radius) * 1.8);
  --radius-pill: calc(var(--radius) * 2.6);
  --ease-out: cubic-bezier(.16, 1, .3, 1);
  --dur-short: 150ms;
  --dur-medium: 250ms;
  /* Colour follows the Pulse token set on quivly-app structure: light mode only,
     white floating chrome on a near-white shell, and ONE brand accent that is
     allowed to appear on interactive and active states only, never as decoration. */
  --canvas: #fbfcfd;
  --paper: #f5f5f5;
  --surface: #ffffff;
  --ink: #0a0a0a;
  --ink-soft: #404040;
  --muted: #737373;
  --line: #e5e5e5;
  --line-strong: #d4d4d4;
  --primary: #171717;
  --primary-hover: #000000;
  /* interactive — forest green, matching the Quivly mark */
  --accent: #0e6b55;
  --accent-hover: #0a5543;
  --accent-soft: #e7f3ee;
  --accent-line: #a9d6c4;
  --accent-ink: #0a5543;
  --focus: #0e6b55;
  --glass-accent: rgba(14, 107, 85, .10);
  --glass-accent-line: rgba(14, 107, 85, .30);
  /* semantic */
  --success: #059669;
  --lookup: #0284c7;
  --lookup-soft: #f0f9ff;
  --lookup-line: #a8d6ec;
  --destructive: #ef4444;
  --destructive-soft: #fef2f2;
  --p0: #b42318;
  --add-ink: #036c48;
  --del-ink: #b42318;
  --code-muted: #737373;
  /* The signature: an inset top-edge highlight on every elevated surface, simulating
     light hitting the top edge of glass. Shadow casts are rgba(16,24,40,..), a
     blue-black, not neutral black. */
  --sheen: rgba(255, 255, 255, .60);
  --wash: rgba(255, 255, 255, .55);
  --shadow-soft: inset 0 1px 0 0 var(--sheen), 0 1px 2px 0 rgba(16,24,40,.04), 0 10px 28px -10px rgba(16,24,40,.12);
  --glass-bg: rgba(255, 255, 255, .74);
  --glass-blur: blur(14px) saturate(1.7);
  /* grain: quivly-app's paper texture on the shell, inline so nothing is fetched */
  --logo: url('data:image/png;base64,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');
  --grain: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3'/%3E%3C/filter%3E%3Crect width='120' height='120' filter='url(%23n)' opacity='.25'/%3E%3C/svg%3E");
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  background-color: var(--canvas);
  background-image: var(--grain);
  color: var(--ink);
  font-family: var(--font-sans);
  font-size: var(--text-base);
  line-height: var(--lead-normal);
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
}
h1, h2, h3 { font-family: var(--font-sans); font-weight: 600; letter-spacing: var(--track-tight); text-wrap: balance; }
a { color: var(--accent); text-underline-offset: 3px; }
code { font-family: var(--font-mono); font-variant-ligatures: none; }
.skip-link { position: fixed; left: var(--space-3); top: -60px; z-index: 100; background: var(--surface); color: var(--ink); padding: var(--space-3) var(--space-4); border-radius: var(--radius-sm); }
.skip-link:focus { top: var(--space-3); }
:focus-visible { outline: 3px solid var(--focus); outline-offset: 3px; }
.shell { display: block; min-height: 100vh; }
/* Header: a floating pill, not a bar — same idiom as the review artifact. */
.nav { position: sticky; top: 0; z-index: 20; background: transparent; }
.nav-bar { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: var(--space-3); align-items: center; padding: var(--space-3) clamp(var(--space-4), 3vw, var(--space-8)) var(--space-2); }
.pill { display: flex; align-items: center; gap: var(--space-2); min-height: 40px; padding: var(--space-1) var(--space-3); border: 1px solid var(--line); border-radius: var(--radius-pill); background: var(--glass-bg); backdrop-filter: var(--glass-blur); -webkit-backdrop-filter: var(--glass-blur); box-shadow: var(--shadow-soft); }
.brand { display: flex; align-items: center; gap: var(--space-2); font-family: var(--font-sans); font-size: var(--text-sm); font-weight: 600; color: var(--ink); white-space: nowrap; }
.brand-mark { flex: 0 0 auto; width: 26px; height: 24px; background-image: var(--logo); background-size: contain; background-repeat: no-repeat; background-position: center; }
.brand-sep { flex: 0 0 auto; width: 1px; height: 20px; background: var(--line-strong); }
.brand-name { font-family: var(--font-mono); font-size: var(--text-base); font-weight: 500; letter-spacing: -.01em; }
.meta { min-width: 0; justify-content: center; }
.meta h2 { margin: 0; font-size: var(--text-sm); font-weight: 600; letter-spacing: var(--track-tight); white-space: nowrap; }
.meta p { min-width: 0; margin: 0; overflow: hidden; color: var(--muted); font-size: var(--text-sm); text-overflow: ellipsis; white-space: nowrap; }
.nav-actions { display: flex; align-items: center; gap: var(--space-2); }
.icon { width: 1em; height: 1em; flex: 0 0 auto; fill: currentColor; vertical-align: -.125em; }
/* ── Button (components/ui/button.tsx) — same contract as the review artifact ── */
.btn { display: inline-flex; flex-shrink: 0; align-items: center; justify-content: center; gap: var(--space-2); height: 32px; padding: 0 10px; border: 1px solid transparent; border-radius: var(--radius-lg); background-clip: padding-box; font-family: var(--font-sans); font-size: var(--text-base); font-weight: 500; line-height: 1; white-space: nowrap; text-decoration: none; transition: all var(--dur-short) var(--ease-out); outline: none; cursor: pointer; }
.btn:focus-visible { border-color: var(--accent); box-shadow: 0 0 0 3px color-mix(in oklab, var(--accent) 50%, transparent); }
.btn .icon { width: 16px; height: 16px; }
.btn-ghost { color: var(--muted); }
.btn-ghost:hover { background: var(--paper); color: var(--ink); }
.btn.pill { height: 40px; padding: 0 var(--space-4); font-size: var(--text-sm); border-radius: var(--radius-pill); border-color: var(--line); }
.btn.pill:hover { border-color: var(--glass-accent-line); background: var(--glass-accent); color: var(--accent-ink); }
.pr-link { color: var(--ink); font-weight: 500; }
.pr-link .icon { width: 13px; height: 13px; }
#theme-toggle { padding: 0 var(--space-3); }
#theme-toggle .icon { width: 14px; height: 14px; }
/* whichever glyph is not the current mode is the one you can switch to */
.theme-moon { display: none; }
:root[data-theme="dark"] .theme-moon { display: none; }
:root[data-theme="dark"] .theme-sun { display: block; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .theme-sun { display: block; }
  :root:not([data-theme="light"]) .theme-moon { display: none; }
}
:root[data-theme="light"] .theme-sun { display: none; }
:root[data-theme="light"] .theme-moon { display: block; }
.page { max-width: 880px; margin: 0 auto; padding: var(--space-4) clamp(var(--space-4), 3vw, var(--space-8)) var(--space-10); }
.section { margin: 0 0 var(--space-8); }
/* ── Badge (components/ui/badge.tsx) — same contract as the review artifact ── */
.badge { display: inline-flex; height: 20px; width: fit-content; flex-shrink: 0; align-items: center; justify-content: center; gap: var(--space-1); overflow: hidden; padding: 0 var(--space-2); border: 1px solid transparent; border-radius: var(--radius-pill); font-family: var(--font-sans); font-size: var(--text-2xs); font-weight: 600; line-height: 1; letter-spacing: .08em; text-transform: uppercase; white-space: nowrap; backdrop-filter: blur(8px) saturate(1.6); -webkit-backdrop-filter: blur(8px) saturate(1.6); box-shadow: inset 0 1px 0 0 var(--sheen); background: color-mix(in oklab, currentColor 12%, transparent); border-color: color-mix(in oklab, currentColor 26%, transparent); }
.badge-outline { background: var(--wash); border-color: var(--line-strong); color: var(--ink-soft); }
.badge-success { color: var(--success); }
.badge-danger { color: var(--p0); }
/* ── Hero ── */
.hero { padding: var(--space-6) var(--space-7); margin-bottom: var(--space-6); border: 1px solid var(--line); border-radius: 22px; background: var(--glass-bg); backdrop-filter: var(--glass-blur); -webkit-backdrop-filter: var(--glass-blur); box-shadow: var(--shadow-soft); }
.hero-kicker { margin-bottom: var(--space-3); }
.headline { max-width: 34ch; margin: 0 0 var(--space-6); font-size: clamp(1.5rem, 3vw, 2.125rem); line-height: 1.18; letter-spacing: var(--track-display); }
.hero-stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-2); }
.stat-tile { padding: var(--space-3); border: 1px solid var(--line); border-radius: var(--radius-lg); background: var(--paper); text-align: center; }
.stat-tile strong { display: block; font-size: var(--text-xl); font-variant-numeric: tabular-nums; letter-spacing: var(--track-tight); }
.stat-tile span { color: var(--muted); font-size: var(--text-sm); }
.stat-tile.plus strong { color: var(--add-ink); }
.stat-tile.minus strong { color: var(--del-ink); }
/* ── Phase — the two moments a reader lands on this document ── */
.phase { padding: var(--space-6) var(--space-6) var(--space-2); margin-bottom: var(--space-8); border: 1px solid var(--line); border-radius: var(--radius-2xl); }
.phase-before { background: var(--glass-accent); border-color: var(--accent-line); }
.phase-after { background: var(--lookup-soft); border-color: rgba(2, 132, 199, .30); }
.phase-head { margin-bottom: var(--space-5); }
.phase-eyebrow { display: block; margin-bottom: var(--space-1); font-size: var(--text-sm); font-weight: 600; letter-spacing: var(--track-wide); text-transform: uppercase; }
.phase-before .phase-eyebrow { color: var(--accent-ink); }
.phase-after .phase-eyebrow { color: var(--lookup); }
.phase-head h2 { margin: 0; max-width: 46ch; font-size: clamp(1.125rem, 2vw, 1.375rem); line-height: 1.25; }
.panel { margin: 0 0 var(--space-4); padding: var(--space-5); border: 1px solid var(--line); border-radius: var(--radius-lg); background: var(--surface); box-shadow: var(--shadow-soft); }
.phase-before .panel { border-top: 3px solid var(--accent-line); }
.phase-after .panel { border-top: 3px solid var(--lookup-line); }
.panel-title { margin: 0 0 var(--space-3); font-size: var(--text-base); font-weight: 600; letter-spacing: var(--track-tight); color: var(--ink); }
/* ── Structured rows shared by changes / affected / metrics / support / docs ── */
.item-list { margin: 0; padding: 0; list-style: none; display: grid; gap: var(--space-3); }
.item-row { padding: var(--space-3); border: 1px solid var(--line); border-radius: var(--radius-md); background: var(--paper); }
.item-title { display: block; font-size: var(--text-md); font-weight: 600; }
.item-title .icon { width: 12px; height: 12px; margin-right: var(--space-1); color: var(--muted); }
.item-line { margin: var(--space-1) 0 0; color: var(--muted); font-size: var(--text-sm); }
/* Rows that sit directly on the panel, divided by a hairline instead of a boxed background. */
.row-list { margin: 0; padding: 0; list-style: none; display: grid; gap: 0; }
.row { padding: var(--space-3) 0; border-top: 1px solid var(--line-strong); }
.row:first-child { padding-top: 0; border-top: 0; }
.row:last-child { padding-bottom: 0; }
/* ── Risk (what breaks if this is wrong) ── */
.risk-list { margin: 0; padding: 0; list-style: none; display: grid; gap: var(--space-3); }
.risk-card { padding: var(--space-4); border: 1px solid var(--line); border-left: 4px solid var(--line-strong); border-radius: var(--radius-md); background: var(--paper); }
.risk-card.blocking { border-left-color: var(--destructive); background: var(--destructive-soft); box-shadow: var(--shadow-soft); }
.risk-text { margin: 0 0 var(--space-1); font-size: var(--text-md); font-weight: 600; }
.risk-consequence { margin: 0; color: var(--ink-soft); font-size: var(--text-sm); }
/* ── Plain and icon-marked lists ── */
.plain-list { margin: 0; padding-left: 1.2em; display: grid; gap: var(--space-2); color: var(--ink-soft); font-size: var(--text-md); }
.icon-list { margin: 0; padding: 0; list-style: none; display: grid; gap: var(--space-2); }
.icon-list li { display: flex; align-items: flex-start; gap: var(--space-2); color: var(--ink-soft); font-size: var(--text-md); }
.icon-list .icon { flex: 0 0 auto; margin-top: .2em; }
.icon-list.check .icon { color: var(--accent); }
.icon-list.watch .icon { color: var(--lookup); }
/* ── Tag pills (out of scope, flags) — reuses the badge outline treatment ── */
.tag-list { margin: 0; padding: 0; list-style: none; display: flex; flex-wrap: wrap; gap: var(--space-2); }
.flag-chip { padding: 2px var(--space-2); border: 1px solid var(--line-strong); border-radius: var(--radius-sm); background: var(--paper); color: var(--ink-soft); font: var(--text-sm) var(--font-mono); }
/* ── Rollout ── */
.rollout-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: var(--space-4); }
.rollout-label { display: block; margin-bottom: var(--space-1); color: var(--muted); font-size: var(--text-sm); font-weight: 600; letter-spacing: var(--track-wide); text-transform: uppercase; }
.rollout-item p { margin: 0; color: var(--ink-soft); font-size: var(--text-md); }
/* ── Evidence — what stops the brief being marketing ── */
.evidence-list { margin: 0; padding: 0; list-style: none; display: grid; gap: var(--space-3); }
.evidence-row { padding: var(--space-3); border: 1px solid var(--line); border-radius: var(--radius-md); background: var(--paper); }
.evidence-claim { margin: 0 0 var(--space-2); font-size: var(--text-md); color: var(--ink); }
.evidence-cite { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--space-2); font-family: var(--font-mono); font-size: var(--text-sm); }
.evidence-path { color: var(--accent-ink); }
.evidence-quote { color: var(--code-muted); }
.evidence-quote::before, .evidence-quote::after { content: '"'; }
/* ── Footer — copied from the review artifact so both close the same way ── */
.page-foot { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-start; gap: var(--space-2) var(--space-3); margin: var(--space-8) 0 0; padding: var(--space-4) clamp(var(--space-4), 3vw, var(--space-8)); border-top: 1px solid var(--line); color: var(--muted); font-size: var(--text-sm); }
.foot-mark { width: 17px; height: 16px; background-image: var(--logo); background-size: contain; background-repeat: no-repeat; background-position: center; opacity: .75; }
.foot-sep { width: 1px; height: 13px; background: var(--line-strong); }
.page-foot a { color: var(--ink-soft); font-weight: 500; text-decoration: none; }
.page-foot a:hover { color: var(--accent); text-decoration: underline; }
.foot-star { display: inline-flex; align-items: center; gap: var(--space-2); }
.foot-star .icon { width: 13px; height: 13px; }
@media (max-width: 720px) {
  .nav-bar { grid-template-columns: 1fr; }
  .meta { order: 3; }
  .hero-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
"""


SCRIPT = r"""
// Theme: an explicit choice wins and persists; with none, the OS preference stands.
const themeKey = 'pr-walkthrough:theme';
const themeToggle = document.getElementById('theme-toggle');
function isDark() {
  const set = document.documentElement.dataset.theme;
  return set ? set === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
}
function syncTheme() {
  themeToggle.setAttribute('aria-pressed', String(isDark()));
  themeToggle.title = isDark() ? 'Switch to light' : 'Switch to dark';
}
themeToggle.addEventListener('click', () => {
  const next = isDark() ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  localStorage.setItem(themeKey, next);
  syncTheme();
});
syncTheme();
"""


class GuideError(ValueError):
    pass


def expect(value: Any, expected: type, path: str) -> Any:
    if not isinstance(value, expected):
        raise GuideError(f"{path} must be {expected.__name__}")
    return value


def text(value: Any, path: str, *, allow_empty: bool = False) -> str:
    value = expect(value, str, path)
    if not allow_empty and not value.strip():
        raise GuideError(f"{path} must not be empty")
    return value


def positive_line(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise GuideError(f"{path} must be a positive integer")
    return value


def validate(data: Any) -> dict[str, Any]:
    data = expect(data, dict, "root")
    meta = expect(data.get("meta"), dict, "meta")
    for key in ("repository", "title", "head_sha", "generated_at", "headline"):
        text(meta.get(key), f"meta.{key}")
    for key in ("base_ref", "head_ref"):
        text(meta.get(key), f"meta.{key}", allow_empty=True)
    url = text(meta.get("url"), "meta.url")
    if urlparse(url).scheme != "https":
        raise GuideError("meta.url must use https")
    positive_line(meta.get("pr_number"), "meta.pr_number")
    if meta.get("stance") not in STANCES:
        raise GuideError(f"meta.stance must be one of {sorted(STANCES)}")

    stats = expect(data.get("stats"), dict, "stats")
    for key in ("files", "additions", "deletions"):
        value = stats.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise GuideError(f"stats.{key} must be a non-negative integer")

    before = expect(data.get("before_merge"), dict, "before_merge")
    for i, raw in enumerate(expect(before.get("changes_for_users", []), list, "before_merge.changes_for_users")):
        row = expect(raw, dict, f"before_merge.changes_for_users[{i}]")
        for key in ("capability", "previously"):
            text(row.get(key), f"before_merge.changes_for_users[{i}].{key}")
    for i, raw in enumerate(expect(before.get("who_is_affected", []), list, "before_merge.who_is_affected")):
        row = expect(raw, dict, f"before_merge.who_is_affected[{i}]")
        for key in ("segment", "scale", "basis"):
            text(row.get(key), f"before_merge.who_is_affected[{i}].{key}")
    for i, raw in enumerate(expect(before.get("if_this_is_wrong", []), list, "before_merge.if_this_is_wrong")):
        row = expect(raw, dict, f"before_merge.if_this_is_wrong[{i}]")
        # severity is an honest free-text label (blocking, degraded, cosmetic, ...); only the
        # literal "blocking" carries special sort order and styling, so it is not a closed enum.
        for key in ("risk", "consequence", "severity"):
            text(row.get(key), f"before_merge.if_this_is_wrong[{i}].{key}")
    for i, raw in enumerate(expect(before.get("out_of_scope", []), list, "before_merge.out_of_scope")):
        text(raw, f"before_merge.out_of_scope[{i}]")
    for i, raw in enumerate(expect(before.get("metrics", []), list, "before_merge.metrics")):
        row = expect(raw, dict, f"before_merge.metrics[{i}]")
        for key in ("name", "expect", "how_measured"):
            text(row.get(key), f"before_merge.metrics[{i}].{key}")

    after = expect(data.get("after_merge"), dict, "after_merge")
    for i, raw in enumerate(expect(after.get("shipped", []), list, "after_merge.shipped")):
        text(raw, f"after_merge.shipped[{i}]")
    for i, raw in enumerate(expect(after.get("support", []), list, "after_merge.support")):
        row = expect(raw, dict, f"after_merge.support[{i}]")
        for key in ("note", "expect"):
            text(row.get(key), f"after_merge.support[{i}].{key}")
    for i, raw in enumerate(expect(after.get("sales", []), list, "after_merge.sales")):
        text(raw, f"after_merge.sales[{i}]")
    for i, raw in enumerate(expect(after.get("docs", []), list, "after_merge.docs")):
        row = expect(raw, dict, f"after_merge.docs[{i}]")
        for key in ("artifact", "why_stale"):
            text(row.get(key), f"after_merge.docs[{i}].{key}")
    for i, raw in enumerate(expect(after.get("watch_for", []), list, "after_merge.watch_for")):
        text(raw, f"after_merge.watch_for[{i}]")

    rollout = expect(data.get("rollout"), dict, "rollout")
    text(rollout.get("strategy"), "rollout.strategy")
    text(rollout.get("rollback"), "rollout.rollback")
    for i, raw in enumerate(expect(rollout.get("flags", []), list, "rollout.flags")):
        text(raw, f"rollout.flags[{i}]")

    evidence = expect(data.get("evidence"), list, "evidence")
    if not evidence:
        raise GuideError("evidence must not be empty")
    for i, raw in enumerate(evidence):
        row = expect(raw, dict, f"evidence[{i}]")
        text(row.get("claim"), f"evidence[{i}].claim")
        text(row.get("path"), f"evidence[{i}].path")
        positive_line(row.get("line"), f"evidence[{i}].line")
        text(row.get("quote"), f"evidence[{i}].quote")

    return data


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def panel(title: str, body: str) -> str:
    # An empty body means the source array was empty: omit the whole panel, including
    # its heading, rather than printing a placeholder — the brief says nothing it can't back.
    if not body:
        return ""
    return f'<div class="panel"><h3 class="panel-title">{esc(title)}</h3>{body}</div>'


def render_changes(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""
    rows = "".join(
        f'<li class="row"><span class="item-title">{esc(i["capability"])}</span>'
        f'<p class="item-line">Before: {esc(i["previously"])}</p></li>'
        for i in items
    )
    return panel("What changes for users", f'<ul class="row-list">{rows}</ul>')


def render_affected(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""
    rows = "".join(
        f'<li class="row"><span class="item-title">{esc(i["segment"])}</span>'
        f'<p class="item-line">{esc(i["scale"])} — {esc(i["basis"])}</p></li>'
        for i in items
    )
    return panel("Who is affected", f'<ul class="row-list">{rows}</ul>')


def render_risks(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""
    # Severity is free text, so match case-insensitively: "Blocking" must not
    # quietly sort and style as an ordinary risk.
    def blocks(row: dict[str, Any]) -> bool:
        return row["severity"].strip().casefold() == "blocking"

    # Stable sort: every blocking item moves to the front, everything else keeps its order.
    ordered = sorted(items, key=lambda r: not blocks(r))
    rows = "".join(
        '<li><div class="risk-card{cls}">'
        '<span class="badge {badge}">{sev}</span>'
        '<p class="risk-text">{risk}</p>'
        '<p class="risk-consequence">{cons}</p></div></li>'.format(
            cls=" blocking" if blocks(r) else "",
            badge="badge-danger" if blocks(r) else "badge-outline",
            sev=esc(r["severity"]),
            risk=esc(r["risk"]),
            cons=esc(r["consequence"]),
        )
        for r in ordered
    )
    return panel("What breaks if this is wrong", f'<ul class="risk-list">{rows}</ul>')


def render_scope(items: list[str]) -> str:
    if not items:
        return ""
    tags = "".join(f'<li><span class="badge badge-outline">{esc(t)}</span></li>' for t in items)
    return panel("Out of scope", f'<ul class="tag-list">{tags}</ul>')


def render_metrics(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""
    rows = "".join(
        f'<li class="row"><span class="item-title">{esc(m["name"])}</span>'
        f'<p class="item-line">Expect {esc(m["expect"])} — measured by {esc(m["how_measured"])}</p></li>'
        for m in items
    )
    return panel("Metrics that should move", f'<ul class="row-list">{rows}</ul>')


def render_shipped(items: list[str]) -> str:
    if not items:
        return ""
    rows = "".join(f'<li>{icon("tick")}{esc(s)}</li>' for s in items)
    return panel("What shipped", f'<ul class="icon-list check">{rows}</ul>')


def render_support(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""
    rows = "".join(
        f'<li class="row"><p class="item-line">{esc(s["note"])}</p>'
        f'<p class="item-line">Expect: {esc(s["expect"])}</p></li>'
        for s in items
    )
    return panel("What support needs to know", f'<ul class="row-list">{rows}</ul>')


def render_sales(items: list[str]) -> str:
    if not items:
        return ""
    rows = "".join(f"<li>{esc(s)}</li>" for s in items)
    return panel("What sales needs to know", f'<ul class="plain-list">{rows}</ul>')


def render_docs(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""
    rows = "".join(
        f'<li class="item-row"><span class="item-title">{icon("book")}{esc(d["artifact"])}</span>'
        f'<p class="item-line">Stale because: {esc(d["why_stale"])}</p></li>'
        for d in items
    )
    return panel("What docs needs to know", f'<ul class="item-list">{rows}</ul>')


def render_watch(items: list[str]) -> str:
    if not items:
        return ""
    rows = "".join(f'<li>{icon("alert")}{esc(w)}</li>' for w in items)
    return panel("What to watch for", f'<ul class="icon-list watch">{rows}</ul>')


def render_rollout(rollout: dict[str, Any]) -> str:
    items = [
        f'<div class="rollout-item"><span class="rollout-label">Strategy</span><p>{esc(rollout["strategy"])}</p></div>',
        f'<div class="rollout-item"><span class="rollout-label">Rollback</span><p>{esc(rollout["rollback"])}</p></div>',
    ]
    flags = rollout.get("flags", [])
    if flags:
        chips = "".join(f'<span class="flag-chip">{esc(f)}</span>' for f in flags)
        items.append(f'<div class="rollout-item"><span class="rollout-label">Flags</span><div class="tag-list">{chips}</div></div>')
    return '<div class="rollout-grid">' + "".join(items) + "</div>"


def render_evidence(items: list[dict[str, Any]]) -> str:
    rows = "".join(
        f'<li class="evidence-row"><p class="evidence-claim">{esc(e["claim"])}</p>'
        f'<div class="evidence-cite"><span class="evidence-path">{esc(e["path"])}:{e["line"]}</span>'
        f'<span class="evidence-quote">{esc(e["quote"])}</span></div></li>'
        for e in items
    )
    return f'<ul class="evidence-list">{rows}</ul>'


def render_html(data: dict[str, Any]) -> str:
    meta = data["meta"]
    stats = data["stats"]
    before = data["before_merge"]
    after = data["after_merge"]
    evidence = data["evidence"]

    before_body = "".join((
        render_changes(before.get("changes_for_users", [])),
        render_affected(before.get("who_is_affected", [])),
        render_risks(before.get("if_this_is_wrong", [])),
        render_scope(before.get("out_of_scope", [])),
        render_metrics(before.get("metrics", [])),
    ))
    after_body = "".join((
        render_shipped(after.get("shipped", [])),
        render_support(after.get("support", [])),
        render_sales(after.get("sales", [])),
        render_docs(after.get("docs", [])),
        render_watch(after.get("watch_for", [])),
    ))

    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700&family=Geist:wght@400;500&family=JetBrains+Mono:wght@400;500;700&family=Geist+Mono:wght@400;500&family=Playfair+Display:ital,wght@1,500&display=swap" rel="stylesheet">
<title>{esc(meta['repository'])}#{meta['pr_number']} · PR Brief</title>
<style>{STYLES}{theme_css()}</style></head>
<script>try{{var t=localStorage.getItem('pr-walkthrough:theme');if(t)document.documentElement.dataset.theme=t}}catch(e){{}}</script>
<body>{ICON_SPRITE}
<a class="skip-link" href="#brief-main">Skip to brief</a>
<div class="shell">
<header class="nav"><div class="nav-bar">
<span class="pill brand">
<span class="brand-mark" role="img" aria-label="Mukul Chugh"></span>
<span class="brand-sep" aria-hidden="true"></span>
<span class="brand-name">pr-brief</span></span>
<div class="pill meta"><h2>{esc(meta['repository'])} #{meta['pr_number']}</h2><p>{esc(meta['title'])}</p></div>
<div class="nav-actions">
<button type="button" class="btn btn-ghost pill" id="theme-toggle" aria-label="Switch between light and dark" title="Switch between light and dark">{icon('sun', 'icon theme-sun')}{icon('moon', 'icon theme-moon')}</button>
<a class="btn btn-ghost pill pr-link" href="{esc(meta['url'])}">{icon('external')} Open on GitHub</a></div>
</div></header>
<main class="page" id="brief-main">
<section class="hero">
<div class="hero-kicker"><span class="badge {STANCE_BADGE[meta['stance']]}">{esc(meta['stance'])}</span></div>
<h1 class="headline">{esc(meta['headline'])}</h1>
<div class="hero-stats">
<div class="stat-tile"><strong>{stats['files']}</strong><span>files touched</span></div>
<div class="stat-tile plus"><strong>+{stats['additions']}</strong><span>added</span></div>
<div class="stat-tile minus"><strong>&minus;{stats['deletions']}</strong><span>removed</span></div>
<div class="stat-tile"><strong>{len(evidence)}</strong><span>evidence citations</span></div>
</div>
</section>
<section class="phase phase-before" id="before-merge" aria-labelledby="before-merge-h">
<div class="phase-head"><span class="phase-eyebrow">Before merge</span><h2 id="before-merge-h">What changes, who it reaches, and what breaks if we're wrong</h2></div>
{before_body}
</section>
<section class="phase phase-after" id="after-merge" aria-labelledby="after-merge-h">
<div class="phase-head"><span class="phase-eyebrow">After merge</span><h2 id="after-merge-h">What shipped, and who needs to hear about it</h2></div>
{after_body}
</section>
<section class="section panel" id="rollout" aria-labelledby="rollout-h">
<h2 class="panel-title" id="rollout-h">Rollout</h2>
{render_rollout(data['rollout'])}
</section>
<section class="section panel" id="evidence" aria-labelledby="evidence-h">
<h2 class="panel-title" id="evidence-h">Evidence</h2>
{render_evidence(evidence)}
</section>
</main>
<footer class="page-foot">
<span class="foot-mark" role="img" aria-label="Mukul Chugh"></span>
<span>Built by <a href="https://www.mukulchugh.com">Mukul Chugh</a></span>
<span class="foot-sep" aria-hidden="true"></span>
<a class="foot-star" href="https://github.com/mukulchugh/skills">{icon("star")} Star on GitHub</a>
</footer>
</div>
<script>{SCRIPT}</script></body></html>'''


def library_root(override: Path | None = None) -> Path:
    if override is not None:
        return override.expanduser()
    # Shares pr-walkthrough's root: one archive, two subtrees (reviews/ and briefs/).
    configured = os.environ.get("PR_WALKTHROUGH_HOME")
    if configured:
        return Path(configured).expanduser()
    data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(data_home).expanduser() if data_home else Path.home() / ".local" / "share"
    return base / "pr-walkthrough"


def safe_segment(value: str) -> str:
    segment = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    if not segment:
        raise GuideError(f"unsafe empty path segment from {value!r}")
    return segment


def write_private(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)


def persist_snapshot(data: dict[str, Any], brief_json: str, html_page: str, root: Path) -> Path:
    meta = data["meta"]
    try:
        owner, repository = meta["repository"].split("/", 1)
    except ValueError as error:
        raise GuideError("meta.repository must be owner/repository") from error
    pr_dir = root / "briefs" / safe_segment(owner) / safe_segment(repository) / f"pr-{meta['pr_number']}"
    brief_sha256 = hashlib.sha256(brief_json.encode("utf-8")).hexdigest()
    renderer_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    snapshot = pr_dir / safe_segment(f'{meta["head_sha"][:12]}-{brief_sha256[:8]}-{renderer_sha256[:8]}')
    snapshot.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    write_private(snapshot / "brief.html", html_page)
    write_private(snapshot / "brief.json", brief_json)
    manifest = {
        "schema_version": 1,
        "repository": meta["repository"],
        "pr_number": meta["pr_number"],
        "url": meta["url"],
        "stance": meta["stance"],
        "headline": meta["headline"],
        "generated_at": meta["generated_at"],
        "brief_sha256": brief_sha256,
        "renderer_sha256": renderer_sha256,
        "stats": data["stats"],
        "evidence": len(data["evidence"]),
        "artifacts": {"html": "brief.html", "brief": "brief.json"},
    }
    write_private(snapshot / "manifest.json", json.dumps(manifest, indent=2) + "\n")
    latest = {"head_sha": meta["head_sha"], "snapshot": snapshot.name, "generated_at": meta["generated_at"]}
    latest_path = pr_dir / "latest.json"
    temporary = pr_dir / f".latest-{os.getpid()}.tmp"
    write_private(temporary, json.dumps(latest, indent=2) + "\n")
    os.replace(temporary, latest_path)
    return snapshot


def sample_brief() -> dict[str, Any]:
    return {
        "meta": {
            "repository": "owner/repo",
            "pr_number": 42,
            "url": "https://github.com/owner/repo/pull/42",
            "title": "Escape <script>alert(1)</script> in the title",
            "base_ref": "main",
            "head_ref": "billing-csv-export",
            "head_sha": "abc123def456",
            "generated_at": "2026-08-08T00:00:00Z",
            "stance": "Ship with follow-ups",
            "headline": "Billing admins can export invoices without filing a ticket.",
        },
        "stats": {"files": 6, "additions": 340, "deletions": 12},
        "before_merge": {
            "changes_for_users": [
                {"capability": "Download the last 12 months of invoices as CSV.", "previously": "Only available by filing a support ticket."}
            ],
            "who_is_affected": [
                {"segment": "Orgs on a paid plan with billing admin access", "scale": "every paid org", "basis": "the export button is unconditional on the billing page"}
            ],
            "if_this_is_wrong": [
                {"risk": "Export date range excludes the current month.", "consequence": "admins under-report revenue for the month in progress.", "severity": "degraded"},
                {"risk": "Export includes another org's invoice rows.", "consequence": "a cross-tenant data leak on the highest-trust page in the product.", "severity": "blocking"},
            ],
            "out_of_scope": ["Scheduled export", "PDF export"],
            "metrics": [
                {"name": "Support tickets tagged 'invoice history'", "expect": "drops toward zero", "how_measured": "ticket volume by tag, week over week"}
            ],
        },
        "after_merge": {
            "shipped": ["CSV export button on the billing dashboard, scoped to the viewing org."],
            "support": [
                {"note": "Customers no longer need a ticket for invoice history.", "expect": "questions about the export's date-range limit"}
            ],
            "sales": ["Invoice history export is now self-serve, not a manual ask."],
            "docs": [
                {"artifact": "Help article: Requesting invoice history", "why_stale": "tells customers to file a ticket"}
            ],
            "watch_for": ["Export requests that time out on large accounts", "Any row scoped to the wrong org"],
        },
        "rollout": {
            "strategy": "Ships with the branch; no flag.",
            "rollback": "Revert removes the button; no data migration.",
            "flags": ["billing_csv_export"],
        },
        "evidence": [
            {"claim": "The export query is scoped by the caller's org id.", "path": "src/billing/export.ts", "line": 58, "quote": "WHERE org_id = ctx.orgId"}
        ],
    }


# "Ship it" is the one stance the single-scenario sample cannot also render, since
# meta.stance renders exactly once per document. "blocking" severity already reuses
# badge-danger, so no other class needs this allowance.
ALLOWED_UNRENDERED = {"badge-success"}


def check_css_coverage(*pages: str) -> None:
    """Fail if a class is styled but never rendered, or rendered but never styled."""
    # Strip comments and url(...) first: a hostname in a data URI or a filename in a
    # comment is not a selector.
    selectors = re.sub(r"/\*.*?\*/", "", STYLES, flags=re.S)
    selectors = re.sub(r"url\([^)]*\)", "", selectors)
    styled = set(re.findall(r"\.(-?[_a-zA-Z][\w-]*)", selectors))
    rendered: set[str] = set()
    for page in pages:
        for value in re.findall(r'class="([^"]*)"', page):
            rendered.update(value.split())
    dead = styled - rendered - ALLOWED_UNRENDERED
    unstyled = rendered - styled - ALLOWED_UNRENDERED
    assert not dead, f"CSS classes are styled but never rendered: {sorted(dead)}"
    assert not unstyled, f"rendered classes have no CSS rule: {sorted(unstyled)}"

    defined = set(re.findall(r'<symbol id="i-([a-z-]+)"', ICON_SPRITE))
    used = {name for page in pages for name in re.findall(r'href="#i-([a-z-]+)"', page)}
    assert not defined - used, f"icon symbols defined but never used: {sorted(defined - used)}"
    assert not used - defined, f"icons referenced with no symbol: {sorted(used - defined)}"


def self_check() -> None:
    data = validate(sample_brief())
    page = render_html(data)

    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page

    for heading in (
        "Before merge", "After merge", "Rollout", "Evidence",
        "What changes for users", "Who is affected", "What breaks if this is wrong",
        "Out of scope", "Metrics that should move",
        "What shipped", "What support needs to know", "What sales needs to know",
        "What docs needs to know", "What to watch for",
    ):
        assert heading in page, f"missing heading: {heading}"

    assert '<span class="badge badge-outline">Ship with follow-ups</span>' in page
    assert page.count('class="evidence-row"') == len(data["evidence"]) > 0

    # Severity ordering: the blocking risk must render before the merely degraded one.
    assert page.index("cross-tenant data leak") < page.index("under-report revenue")

    # Severity is free text, so a capitalized label must still sort and style as blocking.
    cased = json.loads(json.dumps(data))
    cased["before_merge"]["if_this_is_wrong"] = [
        {"risk": "Ordinary", "consequence": "minor", "severity": "cosmetic"},
        {"risk": "Severe", "consequence": "major", "severity": "Blocking"},
    ]
    recased = render_html(validate(cased))
    assert recased.index("Severe") < recased.index("Ordinary"), "capitalized blocking must sort first"
    assert 'risk-card blocking' in recased, "capitalized blocking must style as blocking"

    check_css_coverage(page)

    with TemporaryDirectory(prefix="pr-brief-") as directory:
        root = Path(directory) / "library"
        brief_json = json.dumps(data)
        snapshot = persist_snapshot(data, brief_json, page, root)
        assert (snapshot / "brief.html").read_text(encoding="utf-8") == page
        manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["repository"] == data["meta"]["repository"]
        assert manifest["pr_number"] == data["meta"]["pr_number"]
        pr_dir = root / "briefs" / "owner" / "repo" / "pr-42"
        latest = json.loads((pr_dir / "latest.json").read_text(encoding="utf-8"))
        assert latest["snapshot"] == snapshot.name

    print("render_brief.py self-check passed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, help="brief JSON")
    parser.add_argument("html_output", nargs="?", type=Path, help="HTML output path")
    parser.add_argument("--library-root", type=Path, help="override the shared archive root")
    parser.add_argument("--no-persist", action="store_true", help="do not archive this render in the shared library")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    if args.input is None or args.html_output is None:
        parser.error("input and html_output are required for rendering")
    brief_json = args.input.read_text(encoding="utf-8")
    data = validate(json.loads(brief_json))
    html_page = render_html(data)
    args.html_output.write_text(html_page, encoding="utf-8")
    print(f"wrote {args.html_output}")
    if not args.no_persist:
        snapshot = persist_snapshot(data, brief_json, html_page, library_root(args.library_root))
        print(f"archived {snapshot}")


if __name__ == "__main__":
    main()
