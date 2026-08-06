#!/usr/bin/env python3
"""Validate and render a PR Walkthrough guide as self-contained HTML and Markdown."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import html
import json
import os
import re
import secrets
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
from typing import Any
from urllib.parse import urlparse


KINDS = {"change", "tests"}
RISKS = {"skim", "review", "read-closely"}
ROLES = {
    "schema_or_model",
    "core_logic",
    "consumer_or_call_site",
    "test",
    "config_or_generated",
}
LINE_TYPES = {"add", "del", "context"}
PRIORITIES = {"P0", "P1", "P2", "P3"}
SIDES = {"LEFT", "RIGHT"}
REVIEW_MODES = {"full", "incremental"}
EXECUTION_MODES = {"native_parallel", "sequential", "single"}
PASS_STATUSES = {"completed", "fallback", "failed"}


# Octicon paths (MIT, GitHub). Inlined as one sprite so the artifact stays a single
# self-contained file with no icon font and no network fetch.
ICON_SPRITE = """<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>\
<symbol id="i-pr" viewBox="0 0 16 16"><path d="M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 2.251 0 1 1-1.5 0V5a1 1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354ZM3.75 2.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm0 9.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm8.25.75a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0Z"/></symbol>\
<symbol id="i-alert" viewBox="0 0 16 16"><path d="M6.457 1.047c.659-1.234 2.427-1.234 3.086 0l6.082 11.378A1.75 1.75 0 0 1 14.082 15H1.918a1.75 1.75 0 0 1-1.543-2.575Zm1.763.707a.25.25 0 0 0-.44 0L1.698 13.132a.25.25 0 0 0 .22.368h12.164a.25.25 0 0 0 .22-.368Zm.53 3.996v2.5a.75.75 0 0 1-1.5 0v-2.5a.75.75 0 0 1 1.5 0ZM9 11a1 1 0 1 1-2 0 1 1 0 0 1 2 0Z"/></symbol>\
<symbol id="i-check" viewBox="0 0 16 16"><path d="M8 16A8 8 0 1 1 8 0a8 8 0 0 1 0 16Zm3.78-9.72a.751.751 0 0 0-.018-1.042.751.751 0 0 0-1.042-.018L6.75 9.19 5.28 7.72a.751.751 0 0 0-1.042.018.751.751 0 0 0-.018 1.042l2 2a.75.75 0 0 0 1.06 0Z"/></symbol>\
<symbol id="i-tick" viewBox="0 0 16 16"><path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"/></symbol>\
<symbol id="i-file" viewBox="0 0 16 16"><path d="M2 1.75C2 .784 2.784 0 3.75 0h6.586c.464 0 .909.184 1.237.513l2.914 2.914c.329.328.513.773.513 1.237v9.586A1.75 1.75 0 0 1 13.25 16h-9.5A1.75 1.75 0 0 1 2 14.25Zm1.75-.25a.25.25 0 0 0-.25.25v12.5c0 .138.112.25.25.25h9.5a.25.25 0 0 0 .25-.25V6h-2.75A1.75 1.75 0 0 1 9 4.25V1.5Zm6.75.062V4.25c0 .138.112.25.25.25h2.688l-.011-.013-2.914-2.914-.013-.011Z"/></symbol>\
<symbol id="i-book" viewBox="0 0 16 16"><path d="M0 1.75A.75.75 0 0 1 .75 1h4.253c1.227 0 2.317.59 3 1.501A3.743 3.743 0 0 1 11.006 1h4.245a.75.75 0 0 1 .75.75v10.5a.75.75 0 0 1-.75.75h-4.507a2.25 2.25 0 0 0-1.591.659l-.622.621a.75.75 0 0 1-1.06 0l-.622-.621A2.25 2.25 0 0 0 5.258 13H.75a.75.75 0 0 1-.75-.75Zm7.251 10.324.004-5.073-.002-2.253A2.25 2.25 0 0 0 5.003 2.5H1.5v9h3.757a3.75 3.75 0 0 1 1.994.574ZM8.755 4.75l-.004 7.322a3.752 3.752 0 0 1 1.992-.572H14.5v-9h-3.495a2.25 2.25 0 0 0-2.25 2.25Z"/></symbol>\
<symbol id="i-issue" viewBox="0 0 16 16"><path d="M8 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"/><path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Z"/></symbol>\
<symbol id="i-comment" viewBox="0 0 16 16"><path d="M1.75 1h8.5c.966 0 1.75.784 1.75 1.75v5.5A1.75 1.75 0 0 1 10.25 10H7.061l-2.574 2.573A1.458 1.458 0 0 1 2 11.543V10h-.25A1.75 1.75 0 0 1 0 8.25v-5.5C0 1.784.784 1 1.75 1ZM1.5 2.75v5.5c0 .138.112.25.25.25h1a.75.75 0 0 1 .75.75v2.19l2.72-2.72a.749.749 0 0 1 .53-.22h3.5a.25.25 0 0 0 .25-.25v-5.5a.25.25 0 0 0-.25-.25h-8.5a.25.25 0 0 0-.25.25Z"/></symbol>\
<symbol id="i-list" viewBox="0 0 16 16"><path d="M2 4a1 1 0 1 1 0-2 1 1 0 0 1 0 2Zm3.75-1.5a.75.75 0 0 0 0 1.5h8.5a.75.75 0 0 0 0-1.5h-8.5Zm0 5a.75.75 0 0 0 0 1.5h8.5a.75.75 0 0 0 0-1.5h-8.5Zm0 5a.75.75 0 0 0 0 1.5h8.5a.75.75 0 0 0 0-1.5h-8.5ZM3 8a1 1 0 1 1-2 0 1 1 0 0 1 2 0Zm-1 6a1 1 0 1 1 0-2 1 1 0 0 1 0 2Z"/></symbol>\
<symbol id="i-search" viewBox="0 0 16 16"><path d="M10.68 11.74a6 6 0 0 1-7.922-8.982 6 6 0 0 1 8.982 7.922l3.04 3.04a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215ZM11.5 7a4.499 4.499 0 1 0-8.997 0A4.499 4.499 0 0 0 11.5 7Z"/></symbol>\
<symbol id="i-tools" viewBox="0 0 16 16"><path d="M5.433 2.304A4.492 4.492 0 0 0 3.5 6c0 1.598.832 3.002 2.09 3.802.518.328.929.923.902 1.64v.008l-.164 3.337a.75.75 0 1 1-1.498-.073l.163-3.33c.002-.085-.05-.216-.207-.316A5.996 5.996 0 0 1 2 6a5.994 5.994 0 0 1 2.567-4.92 1.482 1.482 0 0 1 1.673-.04c.462.296.76.827.76 1.423v2.82c0 .082.041.16.11.206l.75.51a.25.25 0 0 0 .28 0l.75-.51A.25.25 0 0 0 9 5.283V2.463c0-.596.298-1.127.76-1.423a1.482 1.482 0 0 1 1.673.04A5.994 5.994 0 0 1 14 6a5.996 5.996 0 0 1-2.786 5.068c-.157.1-.209.23-.207.316l.163 3.33a.75.75 0 1 1-1.498.073l-.164-3.337v-.007c-.027-.718.384-1.313.902-1.64A4.495 4.495 0 0 0 12.5 6a4.492 4.492 0 0 0-1.933-3.696c-.024-.017-.043-.022-.055-.024a.09.09 0 0 0-.054.006.117.117 0 0 0-.049.04.13.13 0 0 0-.009.137v2.82a1.75 1.75 0 0 1-.765 1.446l-.75.51a1.75 1.75 0 0 1-1.97 0l-.75-.51A1.75 1.75 0 0 1 5.5 5.283v-2.82a.13.13 0 0 0-.009-.137.117.117 0 0 0-.049-.04.09.09 0 0 0-.054-.006c-.012.002-.031.007-.055.024Z"/></symbol>\
<symbol id="i-left" viewBox="0 0 16 16"><path d="M9.78 12.78a.75.75 0 0 1-1.06 0L4.47 8.53a.75.75 0 0 1 0-1.06l4.25-4.25a.751.751 0 0 1 1.042.018.751.751 0 0 1 .018 1.042L6.06 8l3.72 3.72a.75.75 0 0 1 0 1.06Z"/></symbol>\
<symbol id="i-right" viewBox="0 0 16 16"><path d="M6.22 3.22a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 0 1 0 1.06l-4.25 4.25a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042L9.94 8 6.22 4.28a.75.75 0 0 1 0-1.06Z"/></symbol>\
<symbol id="i-external" viewBox="0 0 16 16"><path d="M3.75 2h3.5a.75.75 0 0 1 0 1.5h-3.5a.25.25 0 0 0-.25.25v8.5c0 .138.112.25.25.25h8.5a.25.25 0 0 0 .25-.25v-3.5a.75.75 0 0 1 1.5 0v3.5A1.75 1.75 0 0 1 12.25 14h-8.5A1.75 1.75 0 0 1 2 12.25v-8.5C2 2.784 2.784 2 3.75 2Zm6.854-1h4.146a.25.25 0 0 1 .25.25v4.146a.25.25 0 0 1-.427.177L13.03 4.03 9.28 7.78a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042l3.75-3.75-1.543-1.543A.25.25 0 0 1 10.604 1Z"/></symbol>\
<symbol id="i-copy" viewBox="0 0 16 16"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"/><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"/></symbol>\
</defs></svg>"""


def icon(name: str, css_class: str = "icon") -> str:
    return f'<svg class="{css_class}" viewBox="0 0 16 16" aria-hidden="true"><use href="#i-{name}"/></svg>'


STYLES = r"""
:root {
  /* type scale */
  /* Sora = chrome and headings · Geist = the words you actually read ·
     Geist Mono = data artifacts ONLY (diff, code, quotes), never labels or chrome ·
     Playfair italic = exactly one accent word in a display heading. */
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
  --space-14: 3.5rem;
  /* radii — derived from --radius exactly as app/globals.css does */
  --radius: .5rem;
  --radius-sm: calc(var(--radius) * .6);
  --radius-md: calc(var(--radius) * .8);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) * 1.4);
  --radius-2xl: calc(var(--radius) * 1.8);
  --radius-pill: calc(var(--radius) * 2.6);
  /* 32px pill + nav-bar padding; every sticky offset derives from this */
  --header-h: 52px;
  --sticky-top: calc(var(--header-h) + var(--space-2));
  /* both dock pills share one height so they read as a matched pair */
  --dock-h: 38px;
  /* motion */
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
  --sidebar: #fafafa;
  --warning: #475569;
  --primary: #171717;
  --primary-hover: #000000;
  /* interactive — forest green, matching the Quivly mark */
  --accent: #0e6b55;
  --accent-hover: #0a5543;
  --accent-soft: #e7f3ee;
  --accent-line: #a9d6c4;
  --accent-ink: #0a5543;
  --focus: #0e6b55;
  --active: #0e6b55;
  /* semantic */
  --success: #059669;
  --lookup: #0284c7;
  --lookup-soft: #f0f9ff;
  --destructive: #ef4444;
  --destructive-soft: #fef2f2;
  /* diff ramp, derived from the semantic pair */
  --add: #ecfdf3;
  --add-strong: #059669;
  --add-ink: #036c48;
  --del: #fef2f2;
  --del-strong: #ef4444;
  --del-ink: #b42318;
  --code: #0a0a0a;
  --code-muted: #737373;
  --p0: #b42318;
  --p1: #1e293b;
  --p2: #475569;
  --p3: #94a3b8;
  --slate-soft: #f8fafc;
  --slate-line: #cbd5e1;
  /* The signature: an inset top-edge highlight on every elevated surface, simulating
     light hitting the top edge of glass. Opacity rises with the surface's elevation. */
  --lift: inset 0 1px 0 0 rgba(255, 255, 255, .6);
  --lift-strong: inset 0 1px 0 0 rgba(255, 255, 255, .8);
  /* Shadow casts are rgba(16,24,40,..) — a blue-black, not neutral black. */
  --shadow-soft: inset 0 1px 0 0 rgba(255,255,255,.6), 0 1px 2px 0 rgba(16,24,40,.04), 0 10px 28px -10px rgba(16,24,40,.12);
  --shadow: var(--shadow-soft);
  --shadow-float: inset 0 1px 0 0 rgba(255,255,255,.65), 0 1px 2px 0 rgba(16,24,40,.05), 0 16px 40px -16px rgba(16,24,40,.16);
  --shadow-accent: 0 2px 8px -2px rgba(14, 107, 85, .28), inset 0 1px 0 0 rgba(255, 255, 255, .18);
  /* glassmorphic accent: forest green at 10%, hairline at 30%, inset highlight on top */
  --glass-accent: rgba(14, 107, 85, .10);
  --glass-accent-hover: rgba(14, 107, 85, .17);
  --glass-accent-line: rgba(14, 107, 85, .30);
  --glass-lift: inset 0 1px 0 0 rgba(255, 255, 255, .15);
  /* top-lit fills — the "glass" read comes from gradient + highlight, not blur alone */
  --glass-bg: rgba(255, 255, 255, .74);
  --glass-line: rgba(212, 212, 212, .55);
  --glass-blur: blur(14px) saturate(1.7);
  --panel-bg: rgba(255, 255, 255, .82);
  --panel-line: rgba(212, 212, 212, .60);
  --panel-blur: blur(18px) saturate(1.8);
  --fill-raised: linear-gradient(to bottom, #ffffff, rgba(245, 245, 245, .8));
  /* grain: quivly-app's paper texture on the shell, inline so nothing is fetched */
  --grain: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3'/%3E%3C/filter%3E%3Crect width='120' height='120' filter='url(%23n)' opacity='.25'/%3E%3C/svg%3E");
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { overflow-x: clip; }
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
.accent-word { font-family: var(--font-serif); font-style: italic; font-weight: 500; }
button, input { font: inherit; }
button { -webkit-tap-highlight-color: transparent; }
a { color: var(--accent); text-underline-offset: 3px; }
code { font-family: var(--font-mono); font-variant-ligatures: none; }
.skip-link { position: fixed; left: var(--space-3); top: -60px; z-index: 100; background: white; color: var(--ink); padding: var(--space-3) var(--space-4); border-radius: var(--radius-sm); }
.skip-link:focus { top: var(--space-3); }
:focus-visible { outline: 3px solid var(--focus); outline-offset: 3px; }
[tabindex="-1"]:focus, [tabindex="-1"]:focus-visible { outline: none; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
.shell { display: block; min-height: 100vh; }
/* Header: floating pills on the shell canvas, not a bar. No divider rule. */
.nav { position: sticky; top: 0; z-index: 20; background: transparent; }
.nav-bar { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: var(--space-3); align-items: center; padding: var(--space-3) clamp(var(--space-4), 3vw, var(--space-8)) var(--space-2); }
/* Two columns under the header: a floating glass TOC docked left, content right. */
.body { display: grid; grid-template-columns: 236px minmax(0, 1fr); gap: var(--space-5); align-items: start; padding: var(--space-2) clamp(var(--space-4), 3vw, var(--space-8)) var(--space-8); }
.toc { position: sticky; top: var(--sticky-top); max-height: calc(100vh - var(--sticky-top) - var(--space-4)); overflow-y: auto; padding: var(--space-3); border: 1px solid var(--line); border-radius: var(--radius-xl); background: var(--panel-bg); backdrop-filter: var(--panel-blur); -webkit-backdrop-filter: var(--panel-blur); box-shadow: var(--shadow-float); scrollbar-width: thin; }
.toc-title { margin: 0 0 var(--space-2); padding: 0 var(--space-2); color: var(--muted); font-size: var(--text-sm); font-weight: 500; }
.toc-backdrop { display: none; }
.pill { display: flex; align-items: center; gap: var(--space-2); min-height: 32px; padding: var(--space-1) var(--space-3); border: 1px solid var(--line); border-radius: var(--radius-pill); background: var(--glass-bg); backdrop-filter: var(--glass-blur); -webkit-backdrop-filter: var(--glass-blur); box-shadow: var(--shadow-soft); }
.brand-row { display: flex; align-items: center; gap: var(--space-2); }
.brand { display: flex; align-items: center; gap: var(--space-2); font-family: var(--font-sans); font-size: var(--text-sm); font-weight: 600; color: var(--ink); white-space: nowrap; }
.brand .icon { width: 14px; height: 14px; color: var(--accent); }
.meta { min-width: 0; justify-content: center; }
.meta h2 { margin: 0; font-size: var(--text-sm); font-weight: 600; letter-spacing: var(--track-tight); white-space: nowrap; }
.meta p { min-width: 0; margin: 0; overflow: hidden; color: var(--muted); font-size: var(--text-sm); text-overflow: ellipsis; white-space: nowrap; }
.nav-actions { display: flex; align-items: center; gap: var(--space-2); }
.nav .outline-toggle { display: none; }
.stats { display: flex; flex-wrap: nowrap; gap: var(--space-3); color: var(--muted); font-size: var(--text-2xs); font-variant-numeric: tabular-nums; }
.stats .plus { color: var(--add-ink); }
.stats .minus { color: var(--del-ink); }
.pr-link { color: var(--ink); font-weight: 500; text-decoration: none; white-space: nowrap; }

.pr-link .icon, #run-info .icon { width: 13px; height: 13px; }
.progress-copy { display: flex; align-items: center; gap: var(--space-2); color: var(--muted); font-size: var(--text-2xs); font-variant-numeric: tabular-nums; white-space: nowrap; }
.progress-track { width: 76px; height: 4px; flex: 0 0 auto; overflow: hidden; background: var(--line); border-radius: var(--radius-pill); }
.progress-fill { display: block; width: 0; height: 100%; background: var(--accent); border-radius: inherit; transition: width var(--dur-medium) var(--ease-out); }
.nav-list { list-style: none; display: flex; flex-direction: column; gap: 2px; padding: 0; margin: 0; }
.unit-link {
  width: 100%;
  min-height: 36px;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2);
  border: 1px solid transparent;
  border-radius: var(--radius-lg);
  text-align: left;
  background: transparent;
  color: var(--muted);
  white-space: nowrap;
  cursor: pointer;
  transition: background var(--dur-short) var(--ease-out), border-color var(--dur-short) var(--ease-out), color var(--dur-short) var(--ease-out);
}
.unit-link:hover { color: var(--ink); background: var(--paper); }
/* the one place the brand accent is allowed: the active state */
.unit-link.active { color: var(--accent-ink); background: var(--accent-soft); border-color: var(--accent-line); font-weight: 600; }
.chapter-no {
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 1px solid var(--line-strong);
  color: var(--muted);
  font: var(--text-2xs) var(--font-mono);
  font-variant-numeric: tabular-nums;
}
.unit-link.active .chapter-no { border-color: var(--accent-line); color: var(--accent-ink); }
.home-link .chapter-no, .closing-link .chapter-no { border-color: transparent; background: var(--paper); }
.home-link .chapter-no .icon, .closing-link .chapter-no .icon { width: 11px; height: 11px; }
.unit-link.active .chapter-no .icon { color: var(--accent-ink); }
.chapter-no .tick { display: none; width: 11px; height: 11px; }
.unit-link.reviewed .chapter-num { display: none; }
.unit-link.reviewed .chapter-no .tick { display: block; color: white; }
.unit-link.reviewed .chapter-no { border-color: var(--accent); background: var(--accent); }
.unit-link.reviewed .unit-title { color: var(--muted); }
.unit-link.reviewed.active .unit-title { color: var(--accent-ink); }
.unit-title { min-width: 0; overflow: hidden; font-size: var(--text-md); font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
.unit-finding-count:empty { display: none; }
.workspace { width: 100%; min-width: 0; padding: 0 0 112px; }
.workspace-inner { width: 100%; min-width: 0; }
.summary {
  position: relative;
  overflow: hidden;
  backdrop-filter: blur(14px) saturate(130%);
  -webkit-backdrop-filter: blur(14px) saturate(130%);
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 24px;
  align-items: start;
  padding: 30px 32px;
  margin-bottom: 24px;
  border: 1px solid var(--line);
  border-radius: 22px;
  background: var(--glass-bg);
  box-shadow: var(--shadow-soft);
}

.summary-kicker { display: flex; flex-wrap: wrap; gap: var(--space-3); align-items: center; margin-bottom: var(--space-3); }
.summary .branch { color: var(--muted); font: var(--text-sm) var(--font-mono); }
.home-head h1 { max-width: 60ch; margin: 0; font-size: clamp(1.5rem, 2.6vw, 2rem); line-height: 1.15; letter-spacing: var(--track-display); }
.summary p { font-family: var(--font-content); max-width: 68ch; margin: 0; color: var(--ink-soft); font-size: var(--text-lg); line-height: 1.6; }
.section { margin: 0 0 var(--space-8); }
.section > .panel-title { margin-bottom: var(--space-3); }
.panel { margin: 0 0 var(--space-6); padding: var(--space-5) var(--space-6); border: 1px solid var(--line); border-radius: var(--radius-lg); background: var(--glass-bg); backdrop-filter: var(--glass-blur); -webkit-backdrop-filter: var(--glass-blur); box-shadow: var(--shadow-soft); }
.panel-title { margin: 0; min-width: 0; overflow-wrap: anywhere; font-size: var(--text-base); font-weight: 600; letter-spacing: var(--track-tight); color: var(--ink); }
.disproved > summary { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--space-2) var(--space-4); min-height: 30px; cursor: pointer; }
.disproved > summary .panel-title { min-width: 0; overflow-wrap: anywhere; }
.disproved-lede { margin: var(--space-3) 0 0; color: var(--muted); font-size: var(--text-sm); max-width: 78ch; }
.disproved-list { margin: var(--space-3) 0 0; padding-left: var(--space-5); display: grid; gap: var(--space-3); }
.disproved-item strong { display: block; font-size: var(--text-md); }
.disproved-item p { margin: var(--space-1) 0 0; color: var(--ink-soft); font-size: var(--text-md); max-width: 78ch; }
.disproved-evidence { margin-top: var(--space-2); }
.finding-index-head { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: var(--space-2) var(--space-4); margin-bottom: var(--space-3); }
.finding-index-head .panel-title { min-width: 0; overflow-wrap: anywhere; }
.finding-index-head > span { flex: 0 0 auto; color: var(--muted); font-size: var(--text-sm); font-variant-numeric: tabular-nums; }
.finding-jumps { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(390px, 100%), 1fr)); gap: var(--space-2); }
.finding-jump { font: inherit; height: auto; min-height: 64px; display: grid; grid-template-columns: auto minmax(0, 1fr); gap: var(--space-1) var(--space-3); align-items: start; border: 1px solid var(--line); border-radius: var(--radius-md); background: white; color: var(--ink); padding: var(--space-3); text-align: left; cursor: pointer; transition: transform var(--dur-short) var(--ease-out), border-color var(--dur-short) var(--ease-out), box-shadow var(--dur-short) var(--ease-out); }
.finding-jump:hover { transform: translateY(-2px); border-color: var(--line-strong); box-shadow: var(--shadow-soft); }
.finding-jump > span:nth-child(2) { min-width: 0; line-height: 1.35; font-weight: 600; white-space: normal; overflow-wrap: anywhere; }
.finding-jump small { grid-column: 2; min-width: 0; overflow: hidden; color: var(--muted); font: var(--text-sm) var(--font-mono); text-overflow: ellipsis; white-space: nowrap; }
.no-findings { display: flex; align-items: center; gap: var(--space-2); margin: 0; color: var(--success); }
.process-head { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--space-3); min-width: 0; margin-bottom: var(--space-3); }
.process-tags { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.process-passes { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: var(--space-2); }
.process-pass { padding: var(--space-4); border: 1px solid var(--line); border-radius: var(--radius-md); background: var(--paper); }
.process-pass strong { display: block; margin-bottom: var(--space-1); font-size: var(--text-md); }
.process-pass p { margin: 0; color: var(--muted); font-size: var(--text-sm); }
.process-status.completed { background: rgba(5, 150, 105, .12); border-color: rgba(5, 150, 105, .28); color: var(--success); }
.process-status.failed { background: rgba(239, 68, 68, .12); border-color: rgba(239, 68, 68, .28); color: var(--p0); }
.process-status.fallback { background: rgba(71, 85, 105, .10); border-color: rgba(71, 85, 105, .22); color: var(--p2); }
.process-limitations { margin: var(--space-3) 0 0; color: var(--p2); font-size: var(--text-sm); }
.next-actions { position: relative; overflow: hidden; margin: 0 0 var(--space-8); padding: var(--space-6); border: 1px solid var(--accent-line); border-radius: var(--radius-xl); color: var(--ink); background: var(--accent-soft); box-shadow: var(--shadow-soft); }
.next-actions::after { content: ""; position: absolute; top: -170px; right: -90px; width: 390px; height: 390px; border-radius: 50%; background: radial-gradient(circle, rgba(128, 221, 199, .20), rgba(128, 221, 199, .04) 55%, transparent 68%); pointer-events: none; }
.next-actions-head { position: relative; z-index: 1; display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 22px; align-items: end; margin-bottom: 18px; }
.next-actions-label { display: block; margin-bottom: var(--space-2); color: var(--accent-ink); font-size: var(--text-sm); font-weight: 500; }
.next-actions h2 { margin: 0; max-width: 40ch; font-size: clamp(1.25rem, 2.2vw, 1.625rem); line-height: 1.2; letter-spacing: var(--track-display); }
.next-actions-head p { max-width: 42ch; margin: 0; color: var(--muted); font-size: var(--text-sm); }
.action-grid { position: relative; z-index: 1; display: grid; grid-template-columns: repeat(auto-fit, minmax(215px, 1fr)); gap: 10px; }
.action-card { min-height: 148px; display: flex; flex-direction: column; align-items: flex-start; padding: var(--space-4); border: 1px solid var(--line); border-radius: var(--radius-lg); color: var(--ink); background: var(--fill-raised); box-shadow: var(--shadow-soft); text-align: left; cursor: pointer; transition: transform var(--dur-short) var(--ease-out), border-color var(--dur-short) var(--ease-out), background var(--dur-short) var(--ease-out); }
.action-card:hover { transform: translateY(-3px); border-color: rgba(128, 221, 199, .55); background: rgba(255,255,255,.09); }
.action-card.primary { border-color: var(--glass-accent-line); background: var(--glass-accent); box-shadow: var(--glass-lift), var(--shadow-soft); }
.icon { width: 1em; height: 1em; flex: 0 0 auto; fill: currentColor; vertical-align: -.125em; }
.action-icon { width: 12px; height: 12px; }
.action-card.primary .action-type { color: var(--accent-ink); border-color: var(--accent-line); background: var(--accent-soft); }
.action-card strong { display: block; margin-bottom: 5px; font-size: 15px; }
.action-card p { margin: 0; color: var(--muted); font-size: var(--text-sm); line-height: 1.45; }
.action-copy { display: flex; align-items: center; gap: var(--space-2); margin-top: auto; padding-top: var(--space-3); color: var(--accent); font: 700 var(--text-2xs) var(--font-mono); letter-spacing: .04em; }
.confirmation-note { position: relative; z-index: 1; display: flex; gap: var(--space-2); align-items: center; margin: var(--space-4) 0 0; color: var(--muted); font-size: var(--text-sm); }
.confirmation-dot { width: 7px; height: 7px; flex: 0 0 auto; border-radius: 50%; background: var(--accent); }
.copy-status { position: absolute; width: 1px; height: 1px; overflow: hidden; }
.completion { position: relative; z-index: 1; display: none; gap: var(--space-4); align-items: center; margin: 0 0 var(--space-5); padding: var(--space-4) var(--space-5); border: 1px solid var(--accent-line); border-radius: var(--radius-lg); background: var(--surface); }
.completion.done { display: flex; }
.completion-mark { display: grid; place-items: center; flex: 0 0 auto; width: 34px; height: 34px; border-radius: var(--radius-xl); color: var(--accent-ink); font-weight: 800;
  background-image: linear-gradient(to bottom, #f3faf7 0%, var(--accent-soft) 58%, #dbeee6 100%);
  border: 1px solid rgba(169, 214, 196, .75);
  box-shadow: inset 0 1px 0 0 rgba(255,255,255,.9), inset 0 -8px 14px -10px rgba(14,107,85,.45), 0 10px 22px -10px rgba(14,107,85,.40); }
.completion-body { min-width: 0; flex: 1 1 auto; }
.completion-body strong { display: block; font-size: var(--text-base); }
.completion-body p { margin: 2px 0 0; color: var(--muted); font-size: var(--text-sm); font-variant-numeric: tabular-nums; }
.unit { display: none; scroll-margin-top: var(--space-5); }
.unit.active { display: block; }
.unit-head { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--space-5); align-items: start; margin: 0 0 var(--space-5); }
.eyebrow { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: center; color: var(--muted); font-size: var(--text-sm); font-weight: 500; }
.risk.read-closely { border-color: var(--line-strong); color: var(--p0); background: var(--surface); }
.risk.review { border-color: var(--line-strong); color: var(--ink-soft); background: var(--surface); }
.unit h2 { margin: var(--space-2) 0 0; max-width: 32ch; font-size: clamp(1.375rem, 2.4vw, 1.75rem); line-height: 1.2; letter-spacing: var(--track-display); }
.unit-facts { display: flex; flex-wrap: wrap; gap: var(--space-2); padding: 0; }
.stat { display: inline-flex; align-items: baseline; gap: var(--space-1); padding: var(--space-1) var(--space-3); border: 1px solid var(--line); border-radius: var(--radius-pill); background: var(--surface); box-shadow: var(--shadow-soft); white-space: nowrap; }
.stat strong { color: var(--ink); font-size: var(--text-base); font-weight: 600; font-variant-numeric: tabular-nums; }
.stat span { color: var(--muted); font-size: var(--text-sm); }
/* Findings and watch-items read as a comment trail beside the diff, not above it. */
.unit-grid { display: grid; grid-template-columns: minmax(0, 1fr) 296px; gap: var(--space-5); align-items: start; }
.unit-main { min-width: 0; grid-column: 1; grid-row: 1; }
.trail { grid-column: 2; grid-row: 1; min-width: 0; position: sticky; top: var(--sticky-top); display: grid; gap: var(--space-3); align-self: start; max-height: calc(100vh - var(--sticky-top) - var(--space-4)); overflow-y: auto; scrollbar-width: thin; }
.context { margin: 0 0 var(--space-5); padding: 0; border: 0; background: none; box-shadow: none; }
.focus {
  margin: 0;
  min-width: 0;
  padding: var(--space-4);
  border: 1px solid rgba(169, 214, 196, .55);
  border-radius: var(--radius-2xl);
  background-image: linear-gradient(to bottom, rgba(255, 255, 255, .88), rgba(231, 243, 238, .68));
  backdrop-filter: blur(14px) saturate(1.7);
  -webkit-backdrop-filter: blur(14px) saturate(1.7);
  box-shadow:
    inset 0 1px 0 0 rgba(255, 255, 255, .92),
    inset 0 -10px 18px -14px rgba(14, 107, 85, .22),
    0 1px 2px 0 rgba(16, 24, 40, .04),
    0 10px 28px -10px rgba(14, 107, 85, .20);
}
.focus h3 { color: var(--accent-ink); }
.focus h3 .icon { color: var(--accent); }
.watch { list-style: none; display: grid; gap: 0; padding: 0; margin: 0; }
.watch-item { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: var(--space-3); align-items: start; padding: var(--space-3) 0; border-top: 1px solid rgba(169, 214, 196, .45); font-family: var(--font-content); font-size: var(--text-md); line-height: 1.5; color: var(--ink-soft); overflow-wrap: anywhere; }
.watch-item:first-child { padding-top: 0; border-top: 0; }
.watch-item:last-child { padding-bottom: 0; }
.watch-dot { width: 6px; height: 6px; margin-top: 7px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 0 3px rgba(14, 107, 85, .14); }
.context { font-family: var(--font-content); color: var(--ink-soft); font-size: var(--text-lg); line-height: 1.65; max-width: 68ch; }
.focus h3, .quiz h3 { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2); margin: 0 0 var(--space-3); min-width: 0; color: var(--ink); font-size: var(--text-md); font-weight: 600; letter-spacing: var(--track-tight); overflow-wrap: anywhere; }
/* Findings surfaced at the top of the unit. A reviewer's first job is triage:
   what is broken, where, how bad. Burying that under a 300-line diff fails it. */
.unit-findings {
  margin: 0;
  min-width: 0;
  padding: var(--space-4);
  border: 1px solid rgba(212, 212, 212, .55);
  border-radius: var(--radius-2xl);
  background-image: linear-gradient(to bottom, rgba(255, 255, 255, .82), rgba(245, 245, 245, .64));
  backdrop-filter: blur(14px) saturate(1.7);
  -webkit-backdrop-filter: blur(14px) saturate(1.7);
  box-shadow:
    inset 0 1px 0 0 rgba(255, 255, 255, .85),
    0 1px 2px 0 rgba(16, 24, 40, .04),
    0 10px 28px -10px rgba(16, 24, 40, .14);
}
.unit-findings.has-p0 {
  border-color: rgba(239, 68, 68, .34);
  background-image: linear-gradient(to bottom, rgba(255, 255, 255, .82), rgba(254, 242, 242, .66));
  box-shadow:
    inset 0 1px 0 0 rgba(255, 255, 255, .85),
    inset 0 -10px 18px -14px rgba(239, 68, 68, .28),
    0 1px 2px 0 rgba(16, 24, 40, .04),
    0 10px 28px -10px rgba(239, 68, 68, .20);
}
.unit-findings h3 { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2); margin: 0 0 var(--space-3); min-width: 0; font-size: var(--text-md); font-weight: 600; letter-spacing: var(--track-tight); color: var(--ink); overflow-wrap: anywhere; }
.unit-findings.has-p0 h3 { color: var(--p0); }
.unit-findings ol { margin: 0; padding: 0; list-style: none; display: grid; gap: 0; min-width: 0; }
.unit-findings li { min-width: 0; }
/* A deck. Collapsed it leans and nests; hovering or tabbing into the stack
   deals the cards out, staggered by depth. Motion values follow the reference
   fan-stack spec: 500ms on cubic-bezier(.16,1,.3,1) with a 50ms per-card ripple. */
.unit-findings ol { padding-bottom: var(--space-2); }
.unit-findings li {
  position: relative;
  z-index: calc(20 - var(--i));
  margin-top: calc(var(--space-3) * -1);
  transform: scale(calc(1 - var(--i) * .02)) rotate(calc(var(--i) * .45deg));
  transform-origin: 50% 0;
  transition: transform .5s var(--ease-out), margin-top .5s var(--ease-out);
  transition-delay: calc(var(--i) * 50ms);
}
.unit-findings li:first-child { margin-top: 0; }
.unit-findings ol:hover li,
.unit-findings ol:focus-within li {
  margin-top: var(--space-2);
  transform: scale(1) rotate(0deg);
}
.unit-findings ol:hover li:first-child,
.unit-findings ol:focus-within li:first-child { margin-top: 0; }
.unit-findings li:hover, .unit-findings li:focus-within { z-index: 30; }
.unit-finding-link { font: inherit; width: 100%; height: auto; display: grid; grid-template-columns: auto minmax(0, 1fr); gap: var(--space-1) var(--space-2); align-items: center; padding: var(--space-2); border: 1px solid var(--line); border-radius: var(--radius-md); background: var(--surface); color: var(--ink); text-align: left; font: inherit; cursor: pointer; transition: background var(--dur-short) var(--ease-out); }
.unit-finding-link { transition: transform .5s var(--ease-out), border-color .5s var(--ease-out), box-shadow .5s var(--ease-out); }
.unit-finding-link:hover { transform: translateY(-8px); border-color: rgba(14,107,85,.32); box-shadow: inset 0 1px 0 0 rgba(255,255,255,.95), 0 1px 2px 0 rgba(16,24,40,.05), 0 14px 28px -12px rgba(16,24,40,.26); }
.unit-finding-link > span:nth-child(2) { min-width: 0; font-size: var(--text-md); font-weight: 600; line-height: 1.4; white-space: normal; overflow-wrap: anywhere; }
.unit-finding-link small { grid-column: 2; min-width: 0; margin-top: var(--space-1); overflow: hidden; color: var(--muted); font: var(--text-2xs) var(--font-mono); text-overflow: ellipsis; white-space: nowrap; }
.file { overflow: hidden; margin: var(--space-3) 0 var(--space-5); border: 1px solid var(--line); border-radius: var(--radius-xl); background: var(--surface); box-shadow: var(--shadow); }
.file > summary { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); min-height: 44px; padding: var(--space-2) var(--space-3) var(--space-2) var(--space-4); background: var(--fill-raised); cursor: pointer; list-style: none; transition: background var(--dur-short) var(--ease-out); }
.file > summary::-webkit-details-marker { display: none; }
.file[open] > summary { border-bottom: 1px solid var(--line); }
.file-id { display: flex; align-items: center; gap: var(--space-2); min-width: 0; color: var(--muted); }
.file-id .icon { flex: 0 0 auto; }
.path-dir { color: var(--muted); font-weight: 400; }
.path-name { color: var(--ink); font-weight: 600; }
.file > summary code { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--text-md); direction: rtl; text-align: left; }
.file > summary:hover { background: var(--paper); }
.file-tools { display: flex; align-items: center; gap: var(--space-2); flex: 0 0 auto; }
.caret { width: 13px; height: 13px; color: var(--muted); transition: transform var(--dur-short) var(--ease-out); }
details[open] > summary .caret { transform: rotate(90deg); }
.file-body { min-width: 0; border-radius: 0 0 var(--radius-xl) var(--radius-xl); overflow: hidden; }
.closing .next-actions { margin-top: 0; }
.home-head { display: block; margin-bottom: var(--space-5); }
.home .summary { margin-bottom: var(--space-6); }
.notes .context { margin-bottom: var(--space-6); }
.learning-grid { display: grid; gap: var(--space-5); }
.notes-group { padding: var(--space-5); border: 1px solid var(--line); border-radius: var(--radius-2xl); background: var(--surface); box-shadow: var(--shadow-soft); }
.notes-head { margin-bottom: var(--space-4); }
.notes-head p { margin: var(--space-1) 0 0; color: var(--muted); font-size: var(--text-md); }
.claims { list-style: none; display: grid; gap: var(--space-3); padding: 0; margin: 0; }
.claim { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: var(--space-3); align-items: start; padding-top: var(--space-3); border-top: 1px solid var(--line); }
.claim:first-child { padding-top: 0; border-top: 0; }
.claim-body { min-width: 0; max-width: 82ch; font-family: var(--font-content); font-size: var(--text-md); line-height: 1.6; color: var(--ink-soft); overflow-wrap: anywhere; }
/* sky = read straight from the code · violet = reviewer reasoning on top of it */
.claim-observed { background: rgba(2, 132, 199, .12); border-color: rgba(2, 132, 199, .26); color: var(--lookup); }
.claim-inference { background: rgba(192, 38, 211, .12); border-color: rgba(192, 38, 211, .26); color: #c026d3; }
.ref { padding: 1px 4px; border-radius: var(--radius-sm); background: var(--paper); color: var(--ink); font-size: .92em; white-space: nowrap; }
.flow-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(320px, 100%), 1fr)); gap: var(--space-6); }
.flow { min-width: 0; }
.flow-title { margin: 0 0 var(--space-3); font-size: var(--text-base); font-weight: 600; letter-spacing: var(--track-tight); }
.flow-steps { list-style: none; display: flex; align-items: stretch; gap: var(--space-2); overflow-x: auto; overscroll-behavior-x: contain; padding: var(--space-1) 0 var(--space-3); margin: 0; scrollbar-width: thin; }
.flow-node { flex: 0 0 232px; display: grid; gap: var(--space-2); align-content: start; padding: var(--space-3); border: 1px solid var(--line); border-radius: var(--radius-xl); background: var(--surface); box-shadow: var(--shadow-soft); }
.flow-head { display: flex; align-items: center; gap: var(--space-2); min-width: 0; }
.flow-num { display: grid; place-items: center; flex: 0 0 auto; width: 22px; height: 22px; border-radius: var(--radius-pill); border: 1px solid rgba(14, 107, 85, .25); background: rgba(14, 107, 85, .10); color: var(--accent); font-size: var(--text-sm); font-weight: 600; font-variant-numeric: tabular-nums; }
.flow-where { min-width: 0; overflow: hidden; padding: 1px var(--space-2); border-radius: var(--radius-md); background: var(--paper); color: var(--muted); font-size: var(--text-sm); text-overflow: ellipsis; white-space: nowrap; }
.flow-text { font-family: var(--font-content); font-size: var(--text-md); line-height: 1.45; color: var(--ink-soft); overflow-wrap: anywhere; }
.flow-arrow { display: grid; place-items: center; flex: 0 0 auto; align-self: center; color: var(--line-strong); }
.flow-arrow .icon { width: 16px; height: 16px; }
@media (max-width: 900px) {
  .flow-steps { flex-direction: column; overflow-x: visible; }
  .flow-node { flex: 1 1 auto; }
  .flow-arrow { transform: rotate(90deg); }
}
.flow-files { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-3); }
.flow-files code { padding: 1px var(--space-2); border-radius: var(--radius-md); background: var(--paper); color: var(--muted); font-size: var(--text-sm); }
.quiz > summary { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); cursor: pointer; list-style: none; }
.quiz > summary::-webkit-details-marker { display: none; }
.quiz > summary h3 { margin: 0; flex: 1 1 auto; color: #075985; }
.quiz details:last-child p:last-child { margin-bottom: 0; }
.quiz .trail-count { color: var(--lookup); background: rgba(255,255,255,.75); border-color: rgba(125, 211, 252, .5); box-shadow: inset 0 1px 0 0 rgba(255,255,255,.9); }

.qa { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: var(--space-2); align-items: start; }
.qa .icon { width: 12px; height: 12px; margin-top: 3px; color: var(--lookup); }
.qa-why .icon { color: var(--muted); }
.quiz-body { margin-top: var(--space-3); }
.diff-scroll { width: 100%; min-width: 0; background: var(--surface); }
.hunk { width: 100%; min-width: 0; }
.hunk + .hunk { border-top: 1px solid var(--line); }
.hunk-resumed { border-top: 0; }
.hunk-head { width: 100%; padding: var(--space-1) var(--space-4); color: var(--muted); background: var(--paper); font: var(--text-sm) var(--font-mono); font-variant-numeric: tabular-nums; border-bottom: 1px solid var(--line); }
.diff-line { display: grid; grid-template-columns: 38px 38px 16px minmax(0, 1fr); width: auto; min-width: 100%; box-sizing: border-box; font-family: var(--font-mono); font-size: 12.5px; line-height: 1.62; font-weight: 400; font-feature-settings: 'calt' 0, 'liga' 0, 'zero' 1, 'ss02' 1; -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }
.diff-line .ln { color: #a3a3a3; font-size: var(--text-2xs); font-variant-numeric: tabular-nums; text-align: right; padding: 0 var(--space-1) 0 0; user-select: none; }
.diff-line .marker { color: #d4d4d4; text-align: center; user-select: none; }
.diff-line code { display: block; min-width: 0; padding: 0 var(--space-3) 0 var(--space-2); white-space: pre-wrap; overflow-wrap: anywhere; tab-size: 2; -moz-tab-size: 2; font-variant-ligatures: none; letter-spacing: -.008em; color: var(--code); }
.t-kw { color: #7c3aed; font-weight: 500; }
.t-st { color: #0369a1; }
.t-cm { color: #94a3b8; font-style: italic; font-weight: 400; }
.t-nu { color: #c026d3; }
.t-fn { color: #0f766e; font-weight: 500; }
.t-ty { color: #1d4ed8; font-weight: 500; }
.t-pr { color: #475569; }
.diff-line.add { background: var(--add); }
.diff-line.add .ln { color: var(--add-ink); border-right-color: rgba(5, 150, 105, .22); }
.diff-line.add .marker { color: var(--add-strong); }
.diff-line.del { background: var(--del); }
.diff-line.del .ln { color: var(--del-ink); border-right-color: rgba(239, 68, 68, .22); }
.diff-line.del .marker { color: var(--del-strong); }
.finding {
  margin: var(--space-2) var(--space-4);
  border: 1px solid rgba(212, 212, 212, .60);
  border-radius: var(--radius-xl);
  background-image: linear-gradient(to bottom, rgba(255, 255, 255, .88), rgba(245, 245, 245, .70));
  backdrop-filter: blur(14px) saturate(1.7);
  -webkit-backdrop-filter: blur(14px) saturate(1.7);
  box-shadow:
    inset 0 1px 0 0 rgba(255, 255, 255, .9),
    0 1px 2px 0 rgba(16, 24, 40, .05),
    0 10px 28px -12px rgba(16, 24, 40, .18);
  white-space: normal;
}
.finding > summary { display: flex; align-items: center; gap: var(--space-2); min-width: 0; padding: var(--space-2) var(--space-3); cursor: pointer; list-style: none; }
.finding > summary::-webkit-details-marker { display: none; }
.finding > summary:hover { background: rgba(255, 255, 255, .55); border-radius: var(--radius-xl); }
.finding-peek { flex: 1 1 auto; min-width: 0; overflow: hidden; font-size: var(--text-md); font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.finding[open] > summary { border-bottom: 1px solid rgba(212, 212, 212, .5); border-radius: var(--radius-xl) var(--radius-xl) 0 0; }
.finding[open] .finding-peek { white-space: normal; overflow: visible; }
.finding-body { padding: var(--space-3) var(--space-4) var(--space-4); }
.finding.p0 {
  border-color: rgba(239, 68, 68, .36);
  background-image: linear-gradient(to bottom, rgba(255, 255, 255, .90), rgba(254, 242, 242, .74));
  box-shadow:
    inset 0 1px 0 0 rgba(255, 255, 255, .92),
    inset 0 -10px 18px -14px rgba(239, 68, 68, .30),
    0 1px 2px 0 rgba(16, 24, 40, .05),
    0 10px 28px -12px rgba(239, 68, 68, .24);
}



.finding .anchor { flex: 0 0 auto; color: var(--muted); font: var(--text-2xs) var(--font-mono); }
.finding p { font-family: var(--font-content); margin: 0; color: var(--ink-soft); font-size: var(--text-md); max-width: 78ch; }
.finding-evidence { margin-top: var(--space-3); border-top: 1px solid var(--line); }
.finding-evidence summary { list-style: none; }
.finding-evidence summary { min-height: 38px; display: flex; align-items: center; cursor: pointer; color: var(--muted); font-size: var(--text-sm); }
.evidence-row { margin: 0 0 var(--space-2); }
.evidence-row span { display: block; color: var(--muted); font: var(--text-sm) var(--font-mono); }
.evidence-row code { display: block; overflow-x: auto; padding: var(--space-2); border-radius: var(--radius-sm); background: var(--paper); color: var(--code); font-size: var(--text-sm); font-variant-ligatures: none; white-space: pre-wrap; overflow-wrap: anywhere; }
.quiz {
  margin: 0;
  min-width: 0;
  padding: var(--space-4);
  border: 1px solid rgba(125, 211, 252, .45);
  border-radius: var(--radius-2xl);
  background-image: linear-gradient(to bottom, rgba(255, 255, 255, .78), rgba(240, 249, 255, .62));
  backdrop-filter: blur(14px) saturate(1.7);
  -webkit-backdrop-filter: blur(14px) saturate(1.7);
  box-shadow:
    inset 0 1px 0 0 rgba(255, 255, 255, .85),
    inset 0 -10px 18px -14px rgba(2, 132, 199, .35),
    0 1px 2px 0 rgba(16, 24, 40, .04),
    0 10px 28px -10px rgba(2, 132, 199, .22);
}
.quiz details { margin: 0; border-top: 1px solid rgba(125, 211, 252, .45); }
.quiz details summary { min-height: 0; display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-2); padding: var(--space-3) 0; cursor: pointer; font-size: var(--text-sm); font-weight: 600; line-height: 1.4; color: var(--ink); overflow-wrap: anywhere; list-style: none; }
.quiz details summary::-webkit-details-marker { display: none; }
.quiz details summary .caret { flex: 0 0 auto; margin-top: 2px; color: var(--lookup); }
.quiz details[open] summary { padding-bottom: var(--space-2); }
.quiz details p { font-family: var(--font-content); margin: 0 0 var(--space-2); color: var(--ink-soft); font-size: var(--text-sm); line-height: 1.5; }
.dock { position: fixed; left: 50%; transform: translateX(-50%); bottom: max(18px, env(safe-area-inset-bottom)); z-index: 30; display: flex; align-items: center; gap: var(--space-2); }
.footer-nav { display: flex; align-items: center; height: var(--dock-h); gap: var(--space-1); padding: 0 var(--space-1); border: 1px solid var(--panel-line); border-radius: var(--radius-pill); background: var(--panel-bg); box-shadow: var(--shadow-float); backdrop-filter: var(--panel-blur); -webkit-backdrop-filter: var(--panel-blur); }
.dock .reviewed-action { height: var(--dock-h); padding: 0 var(--space-4); font-size: var(--text-base); border-color: var(--panel-line); border-radius: var(--radius-pill); background: var(--panel-bg); color: var(--accent); box-shadow: var(--shadow-float); backdrop-filter: var(--panel-blur); -webkit-backdrop-filter: var(--panel-blur); }
.dock .reviewed-action:hover { background: rgba(14, 107, 85, .14); }
.dock .reviewed-action.done {
  color: var(--accent-ink);
  border-color: rgba(14, 107, 85, .38);
  background-image: linear-gradient(to bottom, rgba(255, 255, 255, .70), rgba(231, 243, 238, .82));
  box-shadow:
    inset 0 1px 0 0 rgba(255, 255, 255, .92),
    inset 0 -10px 18px -14px rgba(14, 107, 85, .34),
    0 1px 2px 0 rgba(16, 24, 40, .05),
    0 10px 28px -12px rgba(14, 107, 85, .30);
}
.dock .reviewed-action.done:hover { background-image: linear-gradient(to bottom, rgba(255, 255, 255, .60), rgba(214, 236, 227, .88)); }
.footer-state { min-width: 96px; padding: 0 var(--space-2); color: var(--ink-soft); font-size: var(--text-base); font-weight: 500; font-variant-numeric: tabular-nums; text-align: center; white-space: nowrap; }

/* ── Button (components/ui/button.tsx): base + variant + size ── */
.btn {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  height: 32px;
  padding: 0 10px;
  border: 1px solid transparent;
  border-radius: var(--radius-lg);
  background-clip: padding-box;
  font-family: var(--font-sans);
  font-size: var(--text-base);
  font-weight: 500;
  line-height: 1;
  white-space: nowrap;
  text-decoration: none;
  transition: all var(--dur-short) var(--ease-out);
  outline: none;
  user-select: none;
  cursor: pointer;
}
.btn:active { transform: translateY(1px); }
.btn:focus-visible { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(14, 107, 85, .5); }
.btn:disabled { pointer-events: none; opacity: .5; }
.btn .icon { width: 16px; height: 16px; }
/* variants */
.btn-accent { background: rgba(14, 107, 85, .10); color: var(--accent); }
.btn-accent:hover { background: rgba(14, 107, 85, .20); }
.btn-ghost { color: var(--muted); }
.btn-ghost:hover { background: var(--paper); color: var(--ink); }
/* sizes */
.btn-icon { width: 28px; height: 28px; padding: 0; border-radius: var(--radius-pill); }
/* a button that is also a header pill keeps the pill's shape and height */
.btn.pill { height: 32px; padding: 0 var(--space-3); font-size: var(--text-sm); border-radius: var(--radius-pill); border-color: var(--line); }
.btn.pill:hover { border-color: var(--glass-accent-line); background: var(--glass-accent); color: var(--accent-ink); }
/* ── Badge (components/ui/badge.tsx): h-5 · rounded-4xl · px-2 · text-xs/medium ── */
.badge {
  display: inline-flex;
  height: 20px;
  width: fit-content;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  overflow: hidden;
  padding: 0 var(--space-2);
  border: 1px solid transparent;
  border-radius: var(--radius-pill);
  font-family: var(--font-sans);
  font-size: var(--text-2xs);
  font-weight: 600;
  line-height: 1;
  letter-spacing: .08em;
  text-transform: uppercase;
  white-space: nowrap;
  backdrop-filter: blur(8px) saturate(1.6);
  -webkit-backdrop-filter: blur(8px) saturate(1.6);
  box-shadow: inset 0 1px 0 0 rgba(255, 255, 255, .55);
}
.badge .icon { width: 12px; height: 12px; }
.badge-muted { background: rgba(115, 115, 115, .10); border-color: rgba(115, 115, 115, .22); color: var(--muted); }
.badge-outline { background: rgba(255, 255, 255, .55); border-color: var(--line-strong); color: var(--ink-soft); }
.badge-accent { background: rgba(14, 107, 85, .12); border-color: rgba(14, 107, 85, .28); color: var(--accent); }
.badge-danger { background: rgba(239, 68, 68, .12); border-color: rgba(239, 68, 68, .28); color: var(--p0); }
.badge-success { background: rgba(5, 150, 105, .12); border-color: rgba(5, 150, 105, .28); color: var(--success); }
/* file role: sky = data shape · violet = logic · amber = call site · emerald = tests · gray = generated */
.file-role.schema_or_model { background: rgba(2, 132, 199, .12); border-color: rgba(2, 132, 199, .26); color: var(--lookup); }
.file-role.core_logic { background: rgba(124, 58, 237, .12); border-color: rgba(124, 58, 237, .26); color: #7c3aed; }
.file-role.consumer_or_call_site { background: rgba(71, 85, 105, .10); border-color: rgba(71, 85, 105, .22); color: var(--p2); }
.file-role.test { background: rgba(5, 150, 105, .12); border-color: rgba(5, 150, 105, .28); color: var(--success); }
.file-role.config_or_generated { background: rgba(115, 115, 115, .10); border-color: rgba(115, 115, 115, .22); color: var(--muted); }
.risk.read-closely { background: rgba(239, 68, 68, .12); border-color: rgba(239, 68, 68, .28); color: var(--p0); }
.risk.review { background: rgba(71, 85, 105, .10); border-color: rgba(71, 85, 105, .22); color: var(--p2); }
.risk.skim { background: rgba(115, 115, 115, .10); border-color: rgba(115, 115, 115, .22); color: var(--muted); }
.severity { min-width: 30px; font-variant-numeric: tabular-nums; letter-spacing: .06em; }
.file-hunks, .trail-count, .disproved-count, .unit-finding-count { letter-spacing: .04em; }
.severity.p0 { background: rgba(239, 68, 68, .12); border-color: rgba(239, 68, 68, .28); color: var(--p0); }
.severity.p1 { background: rgba(30, 41, 59, .10); border-color: rgba(30, 41, 59, .22); color: var(--p1); }
.severity.p2 { background: rgba(71, 85, 105, .10); border-color: rgba(71, 85, 105, .22); color: var(--p2); }
.severity.p3 { background: rgba(148, 163, 184, .14); border-color: rgba(148, 163, 184, .30); color: var(--p3); }
.trail-count, .disproved-count { margin-left: auto; }
.completion-copy { flex: 0 0 auto; }
.verdict { flex: 0 0 auto; }
.file-role, .file-hunks { display: none; }
@media (min-width: 900px) { .file-role, .file-hunks { display: inline-flex; } }
.modal { max-width: min(680px, calc(100vw - var(--space-8))); width: 100%; padding: var(--space-6); border: 1px solid var(--panel-line); border-radius: var(--radius-2xl); background: var(--surface); box-shadow: var(--shadow-float); color: var(--ink); }
.modal::backdrop { background: rgba(10, 10, 10, .40); backdrop-filter: blur(2px); }
.modal-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); }
.modal-head .btn { font-size: 20px; line-height: 1; }
.unit-announcer { position: fixed; }
/* ── Responsive ladder ──────────────────────────────────────────────
   1440+  three columns: TOC · content · trail
   1280   trail drops under the content, still two columns
   1024   TOC narrows
   900    TOC becomes an overlay; header collapses to two rows
   600    single column, edge-to-edge diffs, compact chrome           */
@media (max-width: 1440px) {
  .unit-grid { grid-template-columns: minmax(0, 1fr) 268px; }
}
@media (max-width: 1280px) {
  .unit-grid { grid-template-columns: minmax(0, 1fr); }
  .trail { position: static; grid-column: 1; grid-row: 1; max-height: none; overflow: visible;
           grid-auto-flow: column; grid-auto-columns: minmax(240px, 1fr); }
  .unit-main { grid-row: 2; }
}
@media (max-width: 1024px) {
  .body { grid-template-columns: 210px minmax(0, 1fr); gap: var(--space-4); }
  .trail { grid-auto-flow: row; grid-auto-columns: auto; }
  .summary { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 900px) {
  .nav-bar { grid-template-columns: auto minmax(0, 1fr); row-gap: var(--space-2); }
  .nav-actions { grid-column: 1 / -1; justify-content: space-between; }
  .nav .outline-toggle { display: inline-flex; }
  .meta h2 { display: none; }
  .body { grid-template-columns: minmax(0, 1fr); padding: 0 var(--space-4) var(--space-8); }
  .toc { position: fixed; top: calc(var(--header-h) + var(--space-6)); left: var(--space-4); right: var(--space-4); z-index: 40; display: none; max-height: calc(100vh - 96px); }
  .nav.open ~ .body .toc { display: block; }
  .nav.open ~ .body .toc-backdrop { display: block; position: fixed; inset: 0; z-index: 30; background: rgba(10, 10, 10, .28); }
  .workspace { padding: 0 0 104px; }
  .unit-head { grid-template-columns: 1fr; gap: var(--space-3); }
  .unit-facts { grid-template-columns: repeat(4, auto); justify-content: start; }
  .unit-facts strong { text-align: left; }
  .action-grid { grid-template-columns: repeat(auto-fit, minmax(min(200px, 100%), 1fr)); }
}
@media (max-width: 600px) {
  .stats { display: none; }
  .meta p { font-size: var(--text-sm); }
  .summary { padding: var(--space-4); }
  .summary h1 { font-size: 1.5rem; }
  .summary p, .context { font-size: var(--text-base); }
  .panel { padding: var(--space-4); }
  .next-actions { padding: var(--space-4); }
  .action-grid { grid-template-columns: 1fr; }
  .finding-jumps { grid-template-columns: 1fr; }
  .unit h2 { font-size: 1.5rem; }
  .unit-facts { grid-template-columns: repeat(2, auto); }
  .focus, .unit-findings, .quiz { padding: var(--space-3); }
  /* diffs go edge-to-edge so the code column keeps its width */
  .file { margin-left: calc(var(--space-4) * -1); margin-right: calc(var(--space-4) * -1); border-left: 0; border-right: 0; border-radius: 0; }
  .diff-line { grid-template-columns: 32px 32px 14px minmax(0, 1fr); }
  .diff-line code { padding: 0 var(--space-3) 0 var(--space-2); }
  .dock { left: var(--space-3); right: var(--space-3); transform: none; justify-content: space-between; }
  .dock .reviewed-action { min-width: 0; }
  .footer-state { min-width: 0; }
  .flow-grid { grid-template-columns: 1fr; }
  .next-actions-head { grid-template-columns: 1fr; }
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  .unit-findings li { margin-top: var(--space-2); transform: none; transition: none; }
  .unit-findings li:first-child { margin-top: 0; }
  *, *::before, *::after { transition-duration: .01ms !important; animation-duration: .01ms !important; }
}
@media print {
  .nav, .dock, .skip-link, .next-actions, .toc { display: none !important; }
  .shell { display: block; }.workspace { padding: 0; }.unit { display: block; page-break-before: always; }
  .summary, .file { box-shadow: none; }.reviewed-action { display: none; }
}
"""


SCRIPT = r"""
// panels = everything you can navigate to; pages = the units that count toward progress.
// The wrap-up panel is a destination, not a review unit.
const panels = [...document.querySelectorAll('.unit')];
const pages = panels.filter(panel => !panel.classList.contains('closing') && !panel.classList.contains('home'));
const links = [...document.querySelectorAll('.unit-link')];
const nav = document.querySelector('.nav');
const mark = document.getElementById('mark-reviewed');
const key = 'pr-walkthrough:' + document.body.dataset.storageKey;
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
let current = 0;
let saved = {};
try { saved = JSON.parse(localStorage.getItem(key) || '{}'); } catch {}

function persist() { localStorage.setItem(key, JSON.stringify(saved)); }

let reported = false;
function reportCompletion(reviewed, total) {
  const endpoint = document.body.dataset.progressEndpoint;
  if (reported || !endpoint || !navigator.sendBeacon) return;
  reported = true;
  const payload = JSON.stringify({
    token: document.body.dataset.progressToken || '',
    reviewed, total, completed_at: new Date().toISOString(),
  });
  // text/plain keeps this a CORS-simple request, so a file:// page needs no preflight.
  try { navigator.sendBeacon(endpoint, new Blob([payload], { type: 'text/plain' })); } catch {}
}

function updateProgress() {
  const count = pages.filter(page => saved[page.dataset.unitId]).length;
  document.getElementById('review-count').textContent = `${count} / ${pages.length}`;
  document.getElementById('progress-fill').style.width = `${(count / pages.length) * 100}%`;
  const done = count === pages.length;
  document.getElementById('completion').classList.toggle('done', done);
  document.getElementById('completion-count').textContent = `${count} of ${pages.length}`;
  if (done) reportCompletion(count, pages.length);
  pages.forEach((page, index) => links[panels.indexOf(page)].classList.toggle('reviewed', !!saved[page.dataset.unitId]));
  syncMark();
}

// One control in the toolbar, acting on whichever unit is on screen.
function pageIndex() { return pages.indexOf(panels[current]); }
function syncMark() {
  const i = pageIndex();
  if (i < 0) { mark.hidden = true; return; }
  mark.hidden = false;
  const done = !!saved[pages[i].dataset.unitId];
  mark.classList.toggle('done', done);
  mark.textContent = done ? 'Reviewed ✓' : i === pages.length - 1 ? 'Finish review' : 'Mark reviewed';
  mark.setAttribute('aria-pressed', String(done));
}
function show(index, options = {}) {
  const { focus = true, push = true } = options;
  current = Math.max(0, Math.min(panels.length - 1, index));
  panels.forEach((panel, i) => panel.classList.toggle('active', i === current));
  links.forEach((link, i) => {
    link.classList.toggle('active', i === current);
    link.setAttribute('aria-current', i === current ? 'step' : 'false');
  });
  document.getElementById('prev').disabled = current === 0;
  document.getElementById('next').disabled = current === panels.length - 1;
  const pi = pages.indexOf(panels[current]);
  document.getElementById('footer-state').textContent =
    pi < 0 ? (panels[current].classList.contains('home') ? 'Overview' : 'Wrap up')
           : `Module ${pi + 1} of ${pages.length}`;

  document.getElementById('unit-announcer').textContent = `Showing ${panels[current].querySelector('h2').textContent}`;
  if (push) history.pushState({ index: current }, '', '#unit-' + panels[current].dataset.unitId);
  links[current]?.scrollIntoView({ block: 'nearest' });
  syncMark();
  nav.classList.remove('open');
  if (focus) {
    window.scrollTo({ top: 0, behavior: reducedMotion ? 'auto' : 'smooth' });
    panels[current].querySelector('h2').focus({ preventScroll: true });
  }
}
function showFromHash(focus = false) {
  const index = panels.findIndex(panel => '#unit-' + panel.dataset.unitId === location.hash);
  show(index < 0 ? 0 : index, { focus, push: false });
}
links.forEach((link, index) => link.addEventListener('click', () => show(index)));
document.getElementById('prev').addEventListener('click', () => show(current - 1));
document.getElementById('next').addEventListener('click', () => show(current + 1));
document.getElementById('outline-toggle').addEventListener('click', () => nav.classList.toggle('open'));
document.querySelectorAll('.finding-jump').forEach(button => button.addEventListener('click', () => {
  const index = Number(button.dataset.unitIndex);
  show(index);
  requestAnimationFrame(() => revealFinding(button.dataset.findingId));
}));
mark.addEventListener('click', () => {
  const i = pageIndex();
  if (i < 0) return;
  const id = pages[i].dataset.unitId;
  const wasDone = !!saved[id];
  saved[id] = !wasDone;
  persist();
  updateProgress();
  if (!wasDone && current < panels.length - 1) show(current + 1);
});
const runModal = document.getElementById('run-modal');
document.getElementById('run-info').addEventListener('click', () => runModal.showModal());
runModal.addEventListener('click', event => { if (event.target === runModal) runModal.close(); });

document.addEventListener('keydown', event => {
  if (event.target.closest('input, textarea, button, a, summary, details, [contenteditable="true"]')) return;
  if (event.key === 'ArrowLeft') show(current - 1);
  if (event.key === 'ArrowRight') show(current + 1);
});
window.addEventListener('popstate', () => showFromHash(true));

function revealFinding(id) {
  const finding = document.getElementById(id);
  if (!finding) return;
  finding.open = true;
  finding.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'center' });
  finding.querySelector('summary')?.focus({ preventScroll: true });
}
document.querySelectorAll('.unit-finding-link').forEach(button =>
  button.addEventListener('click', () => revealFinding(button.dataset.findingId)));

const copyStatus = document.getElementById('copy-status');
document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', async () => {
  const value = button.dataset.copy;
  try {
    await navigator.clipboard.writeText(value);
    copyStatus.textContent = 'Copied: ' + value;
  } catch {
    // clipboard is unavailable over file:// in some browsers; select it so ctrl/cmd-c works.
    const field = document.createElement('textarea');
    field.value = value;
    field.setAttribute('readonly', '');
    field.style.cssText = 'position:fixed;top:0;left:0;opacity:0';
    document.body.appendChild(field);
    field.select();
    try { document.execCommand('copy'); copyStatus.textContent = 'Copied: ' + value; }
    catch { copyStatus.textContent = 'Copy manually: ' + value; }
    field.remove();
  }
}));

updateProgress();
showFromHash(false);
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


def positive_line(value: Any, path: str, *, nullable: bool = False) -> int | None:
    if nullable and value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise GuideError(f"{path} must be a positive integer" + (" or null" if nullable else ""))
    return value


def validate(data: Any) -> dict[str, Any]:
    data = expect(data, dict, "root")
    meta = expect(data.get("meta"), dict, "meta")
    for key in (
        "repository",
        "title",
        "base_ref",
        "head_ref",
        "head_sha",
        "generated_at",
        "summary",
        "verdict",
    ):
        text(meta.get(key), f"meta.{key}", allow_empty=key in {"base_ref", "head_ref", "verdict"})
    url = text(meta.get("url"), "meta.url")
    if urlparse(url).scheme != "https":
        raise GuideError("meta.url must use https")
    positive_line(meta.get("pr_number"), "meta.pr_number")

    stats = expect(data.get("stats"), dict, "stats")
    for key in ("files", "additions", "deletions"):
        value = stats.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise GuideError(f"stats.{key} must be a non-negative integer")

    process = expect(data.get("review_process"), dict, "review_process")
    if process.get("mode") not in REVIEW_MODES:
        raise GuideError(f"review_process.mode must be one of {sorted(REVIEW_MODES)}")
    if process.get("execution") not in EXECUTION_MODES:
        raise GuideError(f"review_process.execution must be one of {sorted(EXECUTION_MODES)}")
    text(process.get("merge_base_sha"), "review_process.merge_base_sha")
    passes = expect(process.get("passes"), list, "review_process.passes")
    if not passes:
        raise GuideError("review_process.passes must not be empty")
    lanes: set[str] = set()
    for i, raw_pass in enumerate(passes):
        review_pass = expect(raw_pass, dict, f"review_process.passes[{i}]")
        lanes.add(text(review_pass.get("lane"), f"review_process.passes[{i}].lane"))
        text(review_pass.get("summary"), f"review_process.passes[{i}].summary")
        if review_pass.get("status") not in PASS_STATUSES:
            raise GuideError(f"review_process.passes[{i}].status must be one of {sorted(PASS_STATUSES)}")
    for i, limitation in enumerate(expect(process.get("limitations", []), list, "review_process.limitations")):
        text(limitation, f"review_process.limitations[{i}]")

    inventory = expect(data.get("hunk_inventory"), list, "hunk_inventory")
    inventory_ids = [text(item, f"hunk_inventory[{i}]") for i, item in enumerate(inventory)]
    if len(inventory_ids) != len(set(inventory_ids)):
        raise GuideError("hunk_inventory contains duplicate ids")

    units = expect(data.get("units"), list, "units")
    if not units:
        raise GuideError("units must contain at least one review unit")

    unit_ids: set[str] = set()
    rendered_hunks: set[str] = set()
    anchors: set[tuple[str, str, int]] = set()

    for ui, raw_unit in enumerate(units):
        unit = expect(raw_unit, dict, f"units[{ui}]")
        unit_id = text(unit.get("id"), f"units[{ui}].id")
        if unit_id in unit_ids:
            raise GuideError(f"duplicate unit id: {unit_id}")
        unit_ids.add(unit_id)
        if unit.get("kind") not in KINDS:
            raise GuideError(f"units[{ui}].kind must be one of {sorted(KINDS)}")
        if unit.get("risk") not in RISKS:
            raise GuideError(f"units[{ui}].risk must be one of {sorted(RISKS)}")
        text(unit.get("title"), f"units[{ui}].title")
        text(unit.get("context"), f"units[{ui}].context")
        for fi, item in enumerate(expect(unit.get("review_focus"), list, f"units[{ui}].review_focus")):
            text(item, f"units[{ui}].review_focus[{fi}]")

        files = expect(unit.get("files"), list, f"units[{ui}].files")
        if not files:
            raise GuideError(f"units[{ui}].files must not be empty")
        for fi, raw_file in enumerate(files):
            file = expect(raw_file, dict, f"units[{ui}].files[{fi}]")
            path = text(file.get("path"), f"units[{ui}].files[{fi}].path")
            if file.get("role") not in ROLES:
                raise GuideError(f"units[{ui}].files[{fi}].role must be a known role")
            hunks = expect(file.get("hunks"), list, f"units[{ui}].files[{fi}].hunks")
            for hi, raw_hunk in enumerate(hunks):
                hunk = expect(raw_hunk, dict, f"units[{ui}].files[{fi}].hunks[{hi}]")
                hunk_id = text(hunk.get("id"), f"units[{ui}].files[{fi}].hunks[{hi}].id")
                if hunk_id in rendered_hunks:
                    raise GuideError(f"hunk appears more than once: {hunk_id}")
                rendered_hunks.add(hunk_id)
                text(hunk.get("header"), f"units[{ui}].files[{fi}].hunks[{hi}].header")
                lines = expect(hunk.get("lines"), list, f"units[{ui}].files[{fi}].hunks[{hi}].lines")
                for li, raw_line in enumerate(lines):
                    line = expect(raw_line, dict, f"units[{ui}].files[{fi}].hunks[{hi}].lines[{li}]")
                    line_type = line.get("type")
                    if line_type not in LINE_TYPES:
                        raise GuideError(f"line type must be one of {sorted(LINE_TYPES)}")
                    old_line = positive_line(line.get("old_line"), "old_line", nullable=True)
                    new_line = positive_line(line.get("new_line"), "new_line", nullable=True)
                    text(line.get("text"), "line.text", allow_empty=True)
                    if line_type == "add" and new_line is None:
                        raise GuideError(f"{hunk_id} added line is missing new_line")
                    if line_type == "del" and old_line is None:
                        raise GuideError(f"{hunk_id} deleted line is missing old_line")
                    if old_line is not None:
                        anchors.add((path, "LEFT", old_line))
                    if new_line is not None:
                        anchors.add((path, "RIGHT", new_line))

        quiz = expect(unit.get("quiz", []), list, f"units[{ui}].quiz")
        if len(quiz) > 3:
            raise GuideError(f"units[{ui}].quiz must contain at most three items")
        for qi, raw_quiz in enumerate(quiz):
            item = expect(raw_quiz, dict, f"units[{ui}].quiz[{qi}]")
            for key in ("question", "answer", "why"):
                text(item.get(key), f"units[{ui}].quiz[{qi}].{key}")

    missing = set(inventory_ids) - rendered_hunks
    extra = rendered_hunks - set(inventory_ids)
    if missing or extra:
        parts = []
        if missing:
            parts.append("missing " + ", ".join(sorted(missing)))
        if extra:
            parts.append("unexpected " + ", ".join(sorted(extra)))
        raise GuideError("hunk coverage mismatch: " + "; ".join(parts))

    findings = expect(data.get("findings", []), list, "findings")
    for i, raw_finding in enumerate(findings):
        finding = expect(raw_finding, dict, f"findings[{i}]")
        if finding.get("priority") not in PRIORITIES:
            raise GuideError(f"findings[{i}].priority must be P0, P1, P2, or P3")
        for key in ("title", "body", "path", "unit_id"):
            text(finding.get(key), f"findings[{i}].{key}")
        if finding["unit_id"] not in unit_ids:
            raise GuideError(f"findings[{i}] references unknown unit {finding['unit_id']}")
        side = finding.get("side")
        if side not in SIDES:
            raise GuideError(f"findings[{i}].side must be LEFT or RIGHT")
        line = positive_line(finding.get("line"), f"findings[{i}].line")
        if (finding["path"], side, line) not in anchors:
            raise GuideError(
                f"findings[{i}] does not match a rendered diff line: "
                f"{finding['path']} {side} {line}"
            )
        confidence = finding.get("confidence")
        if isinstance(confidence, bool) or not isinstance(confidence, int) or not 7 <= confidence <= 10:
            raise GuideError(f"findings[{i}].confidence must be an integer from 7 through 10")
        evidence = expect(finding.get("evidence"), list, f"findings[{i}].evidence")
        if not evidence:
            raise GuideError(f"findings[{i}].evidence must not be empty")
        for j, raw_evidence in enumerate(evidence):
            item = expect(raw_evidence, dict, f"findings[{i}].evidence[{j}]")
            text(item.get("path"), f"findings[{i}].evidence[{j}].path")
            positive_line(item.get("line"), f"findings[{i}].evidence[{j}].line")
            text(item.get("quote"), f"findings[{i}].evidence[{j}].quote")
        # Which lanes reached this independently. Convergence across lanes is a stronger
        # signal than a self-assigned score, so it must name real lanes, not invented ones.
        for j, lane in enumerate(expect(finding.get("found_by", []), list, f"findings[{i}].found_by")):
            if text(lane, f"findings[{i}].found_by[{j}]") not in lanes:
                raise GuideError(f"findings[{i}].found_by[{j}] is not a declared review lane: {lane}")

    # Candidates that were investigated and cleared. Recording why keeps the next reviewer
    # from re-litigating a question this review already settled.
    for i, raw_cleared in enumerate(expect(data.get("disproved", []), list, "disproved")):
        cleared = expect(raw_cleared, dict, f"disproved[{i}]")
        text(cleared.get("claim"), f"disproved[{i}].claim")
        text(cleared.get("why_not"), f"disproved[{i}].why_not")
        for j, raw_evidence in enumerate(expect(cleared.get("evidence", []), list, f"disproved[{i}].evidence")):
            item = expect(raw_evidence, dict, f"disproved[{i}].evidence[{j}]")
            text(item.get("path"), f"disproved[{i}].evidence[{j}].path")
            positive_line(item.get("line"), f"disproved[{i}].evidence[{j}].line")
            text(item.get("quote"), f"disproved[{i}].evidence[{j}].quote")

    learning = expect(data.get("learning", {}), dict, "learning")
    for key in ("architecture", "invariants", "gotchas"):
        for i, item in enumerate(expect(learning.get(key, []), list, f"learning.{key}")):
            text(item, f"learning.{key}[{i}]")
    for i, raw_flow in enumerate(expect(learning.get("data_flows", []), list, "learning.data_flows")):
        flow = expect(raw_flow, dict, f"learning.data_flows[{i}]")
        text(flow.get("title"), f"learning.data_flows[{i}].title")
        for key in ("steps", "files"):
            for j, item in enumerate(expect(flow.get(key), list, f"learning.data_flows[{i}].{key}")):
                text(item, f"learning.data_flows[{i}].{key}[{j}]")
    return data


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def render_list(items: list[str], css_class: str = "") -> str:
    if not items:
        return ""
    cls = f' class="{css_class}"' if css_class else ""
    return f"<ul{cls}>" + "".join(f"<li>{esc(item)}</li>" for item in items) + "</ul>"


def finding_card(finding: dict[str, Any]) -> str:
    """A finding pinned to its diff line, collapsed to a single row by default.

    Expanded it costs a screenful mid-diff; collapsed it is a marker you can scan
    past, so the diff keeps its reading rhythm.
    """
    evidence = "".join(
        f'<div class="evidence-row"><span>{esc(item["path"])}:{item["line"]}</span>'
        f'<code>{esc(item["quote"])}</code></div>'
        for item in finding["evidence"]
    )
    priority = esc(finding["priority"].lower())
    return (
        f'<details id="{esc(finding["_dom_id"])}" class="finding {priority}" '
        f'aria-label="{esc(finding["priority"])} finding: {esc(finding["title"])}">'
        f'<summary tabindex="0"><span class="badge severity {priority}">{esc(finding["priority"])}</span>'
        f'<span class="finding-peek">{esc(finding["title"])}</span>'
        f'<span class="anchor">{esc(finding["path"].rsplit("/", 1)[-1])}:{finding["line"]}</span>'
        f'{icon("right", "icon caret")}</summary>'
        f'<div class="finding-body"><p>{esc(finding["body"])}</p>'
        f'<details class="finding-evidence"><summary>Evidence &middot; confidence '
        f'{finding["confidence"]}/10{finding["_provenance"]}</summary>'
        f'{evidence}</details></div></details>'
    )


def render_disproved(cleared: list[dict[str, Any]]) -> str:
    """Candidates that were investigated and cleared, with the reason they did not hold."""
    if not cleared:
        return ""
    items = []
    for item in cleared:
        evidence = "".join(
            f'<div class="evidence-row"><span>{esc(source["path"])}:{source["line"]}</span>'
            f'<code>{esc(source["quote"])}</code></div>'
            for source in item.get("evidence", [])
        )
        items.append(
            f'<li class="disproved-item"><strong>{esc(item["claim"])}</strong>'
            f'<p>{esc(item["why_not"])}</p>'
            + (f'<div class="disproved-evidence">{evidence}</div>' if evidence else "")
            + "</li>"
        )
    return (
        '<details class="panel disproved" open aria-labelledby="disproved-title">'
        f'<summary><span class="panel-title" id="disproved-title">Checked and cleared</span>'
        f'<span class="badge badge-accent disproved-count">{len(cleared)}</span></summary>'
        '<p class="disproved-lede">Raised during the review, then ruled out. Recorded so nobody re-opens a settled question.</p>'
        f'<ol class="disproved-list">{"".join(items)}</ol></details>'
    )


def render_process(process: dict[str, Any]) -> str:
    passes = "".join(
        f'<article class="process-pass"><span class="badge process-status {esc(item["status"])}">'
        f'{esc(item["status"])}</span><strong>{esc(item["lane"])}</strong><p>{esc(item["summary"])}</p></article>'
        for item in process["passes"]
    )
    limitations = ""
    if process.get("limitations"):
        limitations = f'<div class="process-limitations"><strong>Limits:</strong>{render_list(process["limitations"])}</div>'
    # Provenance, not content: how the review ran matters less than what it found,
    # so it collapses and sits below the findings rather than ahead of them.
    return (
        '<dialog class="modal" id="run-modal" aria-labelledby="process-title">'
        '<form method="dialog" class="modal-head"><h2 class="panel-title" id="process-title">How this review ran</h2>'
        '<button class="btn btn-ghost btn-icon" aria-label="Close">&times;</button></form>'
        '<div class="process-head"><div class="process-tags">'
        f'<span class="badge badge-muted">{esc(process["mode"])} review</span>'
        f'<span class="badge badge-muted">{esc(process["execution"].replace("_", " "))}</span>'
        f'<span class="badge badge-muted">merge base {esc(process["merge_base_sha"][:12])}</span></div></div>'
        f'<div class="process-passes">{passes}</div>{limitations}</dialog>'
    )


def stat(count: int, noun: str) -> str:
    """One stat chip: value over label, pluralised."""
    label = noun if count == 1 else f"{noun}s"
    return f'<span class="stat"><strong>{count}</strong><span>{label}</span></span>'


def render_next_actions(meta: dict[str, Any], units: int, findings: int) -> str:
    """The post-review runway. Static: it names each action and the command that triggers it."""
    target = f'{meta["repository"]}#{meta["pr_number"]}'
    actions = [
        (
            "primary",
            "comment",
            "Comments on the PR",
            "Post the findings inline",
            "Every finding becomes a comment on the exact diff line it belongs to.",
            f"/pr-walkthrough submit {target}",
        ),
        (
            "",
            "book",
            "Adds a Wiki page",
            "Write up the codebase notes",
            "Architecture, flows, invariants and gotchas go to the repo Wiki. Existing pages stay untouched.",
            f"/pr-walkthrough publish wiki {target}",
        ),
        (
            "",
            "issue",
            "Opens issues",
            "Track the follow-ups",
            "One issue per follow-up, deduped against open and closed issues first.",
            f"/pr-walkthrough create issues {target}",
        ),
        (
            "",
            "tools",
            "Changes nothing",
            "Work out the fixes",
            "Proposes a concrete change for each finding. The pull request is left alone.",
            f"Plan fixes for the {findings} finding{'' if findings == 1 else 's'} in {target}",
        ),
    ]
    cards = "".join(
        f'<button type="button" class="action-card{" " + variant if variant else ""}" '
        f'data-copy="{esc(command)}">'
        f'<span class="badge badge-muted action-type">{icon(glyph, "icon action-icon")}{esc(kind)}</span>'
        f'<strong>{esc(title)}</strong>'
        f'<p>{esc(body)}</p>'
        f'<span class="action-copy">{icon("copy")} {esc(command)}</span></button>'
        for variant, glyph, kind, title, body, command in actions
    )
    token = (
        f'pr-walkthrough complete {target} head={meta["head_sha"][:12]} units={units}/{units}'
    )
    return (
        '<section class="next-actions" aria-labelledby="next-actions-title">'
        f'<div class="completion" id="completion"><span class="completion-mark" aria-hidden="true">&#10003;</span>'
        '<div class="completion-body"><strong>Walkthrough complete</strong>'
        f'<p><span id="completion-count">{units} of {units}</span> units reviewed. '
        'Paste this back to the agent to pick up where you left off.</p></div>'
        f'<button type="button" class="btn btn-accent completion-copy" data-copy="{esc(token)}">Copy completion token</button></div>'
        '<div class="next-actions-head"><div>'
        '<span class="next-actions-label">After the walkthrough</span>'
        '<h2 id="next-actions-title">Nothing has been <span class="accent-word">posted</span> yet</h2></div>'
        '<p>This page only reads. Run one of these in the agent.</p></div>'
        f'<div class="action-grid">{cards}</div>'
        '<p class="confirmation-note"><span class="confirmation-dot" aria-hidden="true"></span>'
        'You see every comment in full &mdash; path, line, side, body &mdash; and confirm it before anything reaches GitHub.</p>'
        '<span class="copy-status" role="status" aria-live="polite" id="copy-status"></span></section>'
    )


# ── Syntax highlighting ──────────────────────────────────────────────────────
# A regex tokenizer, not a parser. A diff reader needs strings, comments,
# keywords and numbers told apart; full grammar accuracy would cost a third-party
# dependency this package deliberately does not have.
_C_LIKE = ("//", r"/\*.*?\*/", [r'"(?:[^"\\\n]|\\.)*"', r"'(?:[^'\\\n]|\\.)*'", r"`(?:[^`\\]|\\.)*`"])
_HASH = ("#", None, [r'"""(?:.|\n)*?"""', r'"(?:[^"\\\n]|\\.)*"', r"'(?:[^'\\\n]|\\.)*'"])

LANG_SPECS: dict[str, tuple[Any, Any, list[str], set[str]]] = {
    "ts": (*_C_LIKE, {
        "abstract", "as", "async", "await", "break", "case", "catch", "class", "const", "continue",
        "declare", "default", "delete", "do", "else", "enum", "export", "extends", "finally", "for",
        "from", "function", "get", "if", "implements", "import", "in", "instanceof", "interface",
        "keyof", "let", "new", "of", "private", "protected", "public", "readonly", "return",
        "satisfies", "set", "static", "super", "switch", "this", "throw", "try", "type", "typeof",
        "var", "void", "while", "yield", "true", "false", "null", "undefined",
    }),
    "py": (*_HASH, {
        "and", "as", "assert", "async", "await", "break", "class", "continue", "def", "del", "elif",
        "else", "except", "finally", "for", "from", "global", "if", "import", "in", "is", "lambda",
        "None", "nonlocal", "not", "or", "pass", "raise", "return", "True", "False", "try", "while",
        "with", "yield", "match", "case", "self",
    }),
    "go": (*_C_LIKE, {
        "break", "case", "chan", "const", "continue", "default", "defer", "else", "fallthrough",
        "for", "func", "go", "goto", "if", "import", "interface", "map", "package", "range",
        "return", "select", "struct", "switch", "type", "var", "nil", "true", "false",
    }),
    "rs": (*_C_LIKE, {
        "as", "async", "await", "break", "const", "continue", "crate", "dyn", "else", "enum",
        "extern", "fn", "for", "if", "impl", "in", "let", "loop", "match", "mod", "move", "mut",
        "pub", "ref", "return", "self", "static", "struct", "super", "trait", "type", "unsafe",
        "use", "where", "while", "true", "false", "None", "Some", "Ok", "Err",
    }),
    "rb": (*_HASH, {
        "def", "end", "class", "module", "if", "elsif", "else", "unless", "case", "when", "while",
        "until", "for", "do", "begin", "rescue", "ensure", "yield", "return", "self", "nil",
        "true", "false", "require", "attr_accessor", "attr_reader", "puts",
    }),
    "sql": ("--", r"/\*.*?\*/", [r"'(?:[^'\\\n]|\\.)*'"], {
        "select", "from", "where", "join", "left", "right", "inner", "outer", "on", "group", "by",
        "order", "limit", "offset", "insert", "into", "values", "update", "set", "delete", "create",
        "table", "index", "alter", "drop", "and", "or", "not", "null", "as", "distinct", "having",
        "union", "with", "case", "when", "then", "else", "end", "returning", "primary", "key",
    }),
    "sh": ("#", None, [r'"(?:[^"\\\n]|\\.)*"', r"'[^'\n]*'"], {
        "if", "then", "else", "elif", "fi", "for", "in", "do", "done", "while", "case", "esac",
        "function", "return", "export", "local", "echo", "set", "source",
    }),
    "css": (None, r"/\*.*?\*/", [r'"(?:[^"\\\n]|\\.)*"', r"'(?:[^'\\\n]|\\.)*'"], set()),
    "json": (None, None, [r'"(?:[^"\\\n]|\\.)*"'], {"true", "false", "null"}),
    "yaml": ("#", None, [r'"(?:[^"\\\n]|\\.)*"', r"'[^'\n]*'"], {"true", "false", "null", "yes", "no"}),
}
LANG_BY_EXT = {
    "ts": "ts", "tsx": "ts", "mts": "ts", "cts": "ts", "js": "ts", "jsx": "ts", "mjs": "ts",
    "cjs": "ts", "java": "ts", "kt": "ts", "swift": "ts", "c": "ts", "h": "ts", "cc": "ts",
    "cpp": "ts", "hpp": "ts", "cs": "ts", "php": "ts", "scala": "ts",
    "py": "py", "pyi": "py", "go": "go", "rs": "rs", "rb": "rb", "sql": "sql",
    "sh": "sh", "bash": "sh", "zsh": "sh", "css": "css", "scss": "css", "less": "css",
    "json": "json", "yaml": "yaml", "yml": "yaml", "toml": "yaml",
}
_PATTERNS: dict[str, re.Pattern[str]] = {}


def _pattern(lang: str) -> re.Pattern[str]:
    if lang not in _PATTERNS:
        line_comment, block_comment, strings, _ = LANG_SPECS[lang]
        parts = []
        if block_comment:
            parts.append(f"(?P<cblock>{block_comment})")
        if line_comment:
            parts.append(f"(?P<comment>{re.escape(line_comment)}.*)")
        for i, rule in enumerate(strings):
            parts.append(f"(?P<s{i}>{rule})")
        parts.append(r"(?P<num>\b\d[\d_]*(?:\.\d+)?(?:[eE][+-]?\d+)?\b)")
        parts.append(r"(?P<name>[A-Za-z_$][\w$]*)")
        _PATTERNS[lang] = re.compile("|".join(parts))
    return _PATTERNS[lang]


def detect_language(path: str) -> str | None:
    return LANG_BY_EXT.get(path.rsplit(".", 1)[-1].lower()) if "." in path else None


# A diff hands us one line at a time, with no memory of the block it sits in — so a
# JSDoc continuation line reads as bare prose and words like `new`, `this`, `from`
# get highlighted as keywords mid-sentence. Detect continuation lines by their leading
# marker before tokenizing anything.
COMMENT_LEADS = {
    "ts": ("//", "/*", "*/", "*"), "go": ("//", "/*", "*/", "*"),
    "rs": ("//", "/*", "*/", "*"), "css": ("/*", "*/", "*"),
    "py": ("#",), "rb": ("#",), "sh": ("#",), "yaml": ("#",), "sql": ("--", "/*", "*/", "*"),
}
TYPE_RE = re.compile(r"^[A-Z][A-Za-z0-9_]*$")


def highlight(text: str, lang: str | None) -> str:
    """Escape and tokenize one source line. Escaping happens per token, never after."""
    if not lang or lang not in LANG_SPECS:
        return esc(text)
    stripped = text.lstrip()
    leads = COMMENT_LEADS.get(lang, ())
    if stripped and leads and stripped.startswith(leads):
        return f'<span class="t-cm">{esc(text)}</span>'
    keywords = LANG_SPECS[lang][3]
    out: list[str] = []
    cursor = 0
    for match in _pattern(lang).finditer(text):
        out.append(esc(text[cursor:match.start()]))
        kind, value = match.lastgroup or "", match.group()
        if kind in ("comment", "cblock"):
            token = "cm"
        elif kind.startswith("s"):
            token = "st"
        elif kind == "num":
            token = "nu"
        elif value in keywords:
            token = "kw"
        elif match.end() < len(text) and text[match.end()] == "(":
            token = "fn"
        elif TYPE_RE.match(value):
            token = "ty"
        elif text[match.end():match.end() + 1] == ":" and text[match.end() + 1:match.end() + 2] != ":":
            token = "pr"
        else:
            token = ""
        out.append(f'<span class="t-{token}">{esc(value)}</span>' if token else esc(value))
        cursor = match.end()
    out.append(esc(text[cursor:]))
    return "".join(out)


def render_diff_file(file: dict[str, Any], findings_by_anchor: dict[tuple[str, str, int], list[dict[str, Any]]]) -> str:
    """One file's diff.

    Findings are emitted as siblings of the scroll region, not inside it: a card
    nested in a horizontally-scrolling box has no width it can honestly use, which
    is what the old sticky/viewport-width hack was working around. Each finding
    closes the current scroll region and the next line opens a fresh one.
    """
    hunk_count = len(file["hunks"])
    lang = detect_language(file["path"])
    folder, _, name = file["path"].rpartition("/")
    path_label = (f'<span class="path-dir">{esc(folder)}/</span>' if folder else "") + f'<span class="path-name">{esc(name)}</span>'
    chunks = [
        '<details class="file" open>',
        f'<summary><span class="file-id">{icon("file")}'
        f'<code title="{esc(file["path"])}">{path_label}</code></span>'
        f'<span class="file-tools"><span class="badge file-role {esc(file["role"])}">{esc(file["role"].replace("_", " "))}</span>'
        f'<span class="badge badge-muted file-hunks">{hunk_count} change{"" if hunk_count == 1 else "s"}</span>'
        f'{icon("right", "icon caret")}</span></summary>',
        '<div class="file-body">',
    ]
    scrolling = False

    def open_scroll() -> None:
        nonlocal scrolling
        if not scrolling:
            chunks.append(
                f'<div class="diff-scroll" role="region" tabindex="0" '
                f'aria-label="Diff for {esc(file["path"])}">'
            )
            scrolling = True

    def close_scroll() -> None:
        nonlocal scrolling
        if scrolling:
            chunks.append("</div>")
            scrolling = False

    for hunk in file["hunks"]:
        open_scroll()
        chunks.append(f'<div class="hunk"><div class="hunk-head">{esc(hunk["header"])}</div>')
        for line in hunk["lines"]:
            old = "" if line["old_line"] is None else str(line["old_line"])
            new = "" if line["new_line"] is None else str(line["new_line"])
            marker = {"add": "+", "del": "−", "context": " "}[line["type"]]
            label = {"add": "Added", "del": "Deleted", "context": "Context"}[line["type"]]
            chunks.append(
                f'<div class="diff-line {esc(line["type"])}" role="row" aria-label="{label} line {esc(new or old)}">'
                f'<span class="ln" aria-hidden="true">{esc(old)}</span>'
                f'<span class="ln" aria-hidden="true">{esc(new)}</span>'
                f'<span class="marker" aria-hidden="true">{marker}</span>'
                f'<code><span class="sr-only">{label}: </span>{highlight(line["text"], lang)}</code></div>'
            )
            keys = []
            if line["old_line"] is not None:
                keys.append((file["path"], "LEFT", line["old_line"]))
            if line["new_line"] is not None:
                keys.append((file["path"], "RIGHT", line["new_line"]))
            cards = [card for key in keys for card in findings_by_anchor.get(key, [])]
            if cards:
                chunks.append("</div>")          # close .hunk
                close_scroll()
                chunks.extend(finding_card(card) for card in cards)
                open_scroll()
                chunks.append('<div class="hunk hunk-resumed">')
        chunks.append("</div>")                  # close .hunk
    close_scroll()
    chunks.append("</div></details>")
    return "".join(chunks)


def render_flow(learning: dict[str, Any]) -> str:
    """The change's data flows as a step diagram. Built from learning.data_flows."""
    flows = learning.get("data_flows", [])
    if not flows:
        return ""
    blocks = []
    for flow in flows:
        files = flow["files"]
        nodes = []
        for i, step in enumerate(flow["steps"], 1):
            if i > 1:
                nodes.append(f'<li class="flow-arrow" aria-hidden="true">{icon("right")}</li>')
            # pair each step with the file it runs in when the arrays line up
            where = (
                f'<code class="flow-where" title="{esc(files[i - 1])}">'
                f'{esc(files[i - 1].rsplit("/", 1)[-1])}</code>'
            ) if i <= len(files) else ""
            nodes.append(
                f'<li class="flow-node"><span class="flow-head"><span class="flow-num">{i}</span>{where}</span>'
                f'<span class="flow-text">{esc(step)}</span></li>'
            )
        extra = files[len(flow["steps"]):]
        tail = (
            '<div class="flow-files">' + "".join(f'<code>{esc(path)}</code>' for path in extra) + "</div>"
        ) if extra else ""
        blocks.append(
            f'<article class="flow"><h3 class="flow-title">{esc(flow["title"])}</h3>'
            f'<ol class="flow-steps">{"".join(nodes)}</ol>{tail}</article>'
        )
    return (
        '<section class="section" aria-labelledby="flow-title">'
        '<h2 class="panel-title" id="flow-title">How the change flows</h2>'
        f'<div class="flow-grid">{"".join(blocks)}</div></section>'
    )


CLAIM_RE = re.compile(r"^(Observed|Inference)\s*:\s*")
# a source reference inside prose: path.ext, optionally with :line or :line-line
REF_RE = re.compile(
    r"([A-Za-z0-9_./\[\]-]+\.(?:tsx?|jsx?|py|go|rb|rs|java|sql|md|ya?ml|json)(?::\d+(?:[-+]\d*)?)?)"
)


def render_claim(item: str) -> str:
    """One learning claim: its evidence class as a badge, its source refs as chips."""
    match = CLAIM_RE.match(item)
    kind = match.group(1) if match else ""
    body = item[match.end():] if match else item
    text_html = REF_RE.sub(r'<code class="ref">\1</code>', esc(body))
    badge = (
        f'<span class="badge claim-{kind.lower()}">{kind}</span>' if kind else ""
    )
    return f'<li class="claim">{badge}<span class="claim-body">{text_html}</span></li>'


def render_learning(learning: dict[str, Any]) -> str:
    groups = [
        ("Architecture", "architecture", "How the pieces fit together."),
        ("Invariants", "invariants", "What must stay true."),
        ("Gotchas", "gotchas", "What will bite the next person."),
    ]
    sections = []
    for title, key, lede in groups:
        items = learning.get(key, [])
        if not items:
            continue
        claims = "".join(render_claim(item) for item in items)
        sections.append(
            f'<section class="notes-group"><header class="notes-head">'
            f'<h3 class="panel-title">{title}</h3><p>{lede}</p></header>'
            f'<ol class="claims">{claims}</ol></section>'
        )
    return f'<div class="learning-grid">{"".join(sections)}</div>' if sections else ""


def render_html(data: dict[str, Any], writer: tuple[str, str] | None = None) -> str:
    """Render the guide. `writer` is an optional (endpoint, token) pair from --serve."""
    meta, stats, units = data["meta"], data["stats"], data["units"]
    findings_by_anchor: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    findings_by_unit: dict[str, list[dict[str, Any]]] = defaultdict(list)
    findings: list[dict[str, Any]] = []
    lane_count = len(data["review_process"]["passes"])
    for index, raw_finding in enumerate(data.get("findings", []), 1):
        found_by = raw_finding.get("found_by") or []
        finding = {
            **raw_finding,
            "_dom_id": f"finding-{index}",
            "_provenance": f" &middot; found by {len(found_by)} of {lane_count} lanes" if found_by else "",
        }
        findings.append(finding)
        findings_by_anchor[(finding["path"], finding["side"], finding["line"])].append(finding)
        findings_by_unit[finding["unit_id"]].append(finding)

    sidebar = [
        f'<li><button type="button" class="unit-link home-link" data-index="0" aria-current="false">'
        f'<span class="chapter-no">{icon("list")}</span><span class="unit-title">Overview</span></button></li>'
    ]
    pages = []
    for index, unit in enumerate(units):
        unit_findings = findings_by_unit[unit["id"]]
        file_count = len(unit["files"])
        hunk_count = sum(len(file["hunks"]) for file in unit["files"])
        sidebar.append(
            f'<li><button type="button" class="unit-link" data-index="{index + 1}" aria-current="false">'
            f'<span class="chapter-no"><span class="chapter-num">{index + 1:02}</span>'
            f'{icon("tick", "icon tick")}</span>'
            f'<span class="unit-title">{esc(unit["title"])}</span>'
            f'<span class="badge badge-danger unit-finding-count">{len(unit_findings) if unit_findings else ""}</span>'
            f'</button></li>'
        )
        quiz = ""
        if unit.get("quiz"):
            cards = []
            for item in unit["quiz"]:
                cards.append(
                    f'<details><summary><span>{esc(item["question"])}</span>'
                    f'{icon("right", "icon caret")}</summary>'
                    f'<p class="qa">{icon("check")}<span class="sr-only">Answer: </span>'
                    f'<span>{esc(item["answer"])}</span></p>'
                    f'<p class="qa qa-why">{icon("book")}<span class="sr-only">Why it matters: </span>'
                    f'<span>{esc(item["why"])}</span></p></details>'
                )
            quiz = (
                '<details class="quiz" open><summary><h3>'
                f'{icon("check")} Test your read'
                f'<span class="badge badge-accent trail-count">{len(unit["quiz"])}</span></h3>'
                f'{icon("right", "icon caret")}</summary>'
                '<div class="quiz-body">' + "".join(cards) + "</div></details>"
            )
        files = "".join(render_diff_file(file, findings_by_anchor) for file in unit["files"])
        triage = ""
        if unit_findings:
            worst = "has-p0" if any(f["priority"] == "P0" for f in unit_findings) else ""
            rows = "".join(
                f'<li style="--i:{depth}"><button type="button" class="unit-finding-link" '
                f'data-finding-id="{esc(f["_dom_id"])}">'
                f'<span class="badge severity {f["priority"].lower()}">{esc(f["priority"])}</span>'
                f'<span>{esc(f["title"])}</span>'
                f'<small>{esc(f["path"].rsplit("/", 1)[-1])}:{f["line"]}</small></button></li>'
                for depth, f in enumerate(unit_findings)
            )
            triage = (
                f'<section class="unit-findings {worst}">'
                f'<h3>{icon("alert")} Findings in this module'
                f'<span class="badge badge-accent trail-count">{len(unit_findings)}</span></h3>'
                f'<ol>{rows}</ol></section>'
            )
        pages.append(
            f'<article class="unit" data-index="{index}" data-unit-id="{esc(unit["id"])}">'
            f'<header class="unit-head"><div><div class="eyebrow"><span>Module {index + 1:02} / {len(units):02}</span>'
            f'<span class="badge risk {esc(unit["risk"])}">{esc(unit["risk"].replace("-", " "))}</span></div>'
            f'<h2 tabindex="-1">{esc(unit["title"])}</h2></div>'
            f'<div class="unit-facts">'
            f'{stat(file_count, "file")}{stat(hunk_count, "change")}'
            f'{stat(len(unit_findings), "finding")}{stat(len(unit.get("quiz", [])), "question")}'
            f'</div></header>'
            f'<div class="unit-grid">'
            f'<aside class="trail">{triage}'
            f'<section class="focus"><h3>{icon("search")} What to watch for</h3>'
            '<ol class="watch">'
            + "".join(
                f'<li class="watch-item"><span class="watch-dot" aria-hidden="true"></span>'
                f'<span>{esc(item)}</span></li>'
                for item in unit["review_focus"]
            )
            + '</ol></section>'
            f'{quiz}</aside>'
            f'<div class="unit-main"><p class="context">{esc(unit["context"])}</p>'
            f'{files}</div></div></article>'
        )

    sidebar.append(
        '<li><button type="button" class="unit-link closing-link" data-index="'
        f'{len(units) + 1}" aria-current="false"><span class="chapter-no">{icon("check")}</span>'
        '<span class="unit-title">Wrap up</span></button></li>'
    )
    sidebar.append(
        '<li><button type="button" class="unit-link closing-link" data-index="'
        f'{len(units) + 2}" aria-current="false"><span class="chapter-no">{icon("book")}</span>'
        '<span class="unit-title">Codebase notes</span></button></li>'
    )
    unit_index = {unit["id"]: index + 1 for index, unit in enumerate(units)}
    if findings:
        finding_jumps = "".join(
            f'<button type="button" class="finding-jump" data-unit-index="{unit_index[finding["unit_id"]]}" '
            f'data-finding-id="{esc(finding["_dom_id"])}"><span class="badge severity {finding["priority"].lower()}">'
            f'{esc(finding["priority"])}</span><span>{esc(finding["title"])}</span>'
            f'<small>{esc(finding["path"])}:{finding["line"]}</small></button>'
            for finding in findings
        )
        finding_index = (
            '<section class="section" aria-labelledby="finding-index-title">'
            f'<div class="finding-index-head"><h2 class="panel-title" id="finding-index-title">What needs fixing</h2>'
            f'<span>{len(findings)} root-cause finding{"s" if len(findings) != 1 else ""}</span></div>'
            f'<div class="finding-jumps">{finding_jumps}</div></section>'
        )
    else:
        finding_index = (
            '<section class="section" aria-labelledby="finding-index-title">'
            '<div class="finding-index-head"><h2 class="panel-title" id="finding-index-title">What needs fixing</h2>'
            '<span>0</span></div>'
            f'<p class="no-findings"><span class="badge badge-success">{icon("check")} Clean</span> Nothing to fix here. Every candidate raised during the review was checked and cleared.</p></section>'
        )

    storage_key = f"{meta['repository']}#{meta['pr_number']}@{meta['head_sha']}"
    writer_attrs = ""
    if writer:
        endpoint, token = writer
        writer_attrs = f' data-progress-endpoint="{esc(endpoint)}" data-progress-token="{esc(token)}"'
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700&family=Geist:wght@400;500&family=JetBrains+Mono:wght@400;500;700&family=Geist+Mono:wght@400;500&family=Playfair+Display:ital,wght@1,500&display=swap" rel="stylesheet">
<title>{esc(meta['repository'])}#{meta['pr_number']} · PR Walkthrough</title>
<style>{STYLES}</style></head>
<body data-storage-key="{esc(storage_key)}"{writer_attrs}>{ICON_SPRITE}
<a class="skip-link" href="#review-workspace">Skip to review</a>
<div class="shell"><header class="nav"><div class="nav-bar">
<div class="brand-row"><span class="pill brand">{icon('pr')} Review</span>
<button type="button" class="btn btn-accent outline-toggle" id="outline-toggle">Modules</button></div>
<div class="pill meta"><h2>{esc(meta['repository'])} #{meta['pr_number']}</h2><p>{esc(meta['title'])}</p></div>
<div class="nav-actions"><div class="pill stats">
<span class="plus">+{stats['additions']}</span><span class="minus">−{stats['deletions']}</span>
<span>{stats['files']} files</span><span>{len(findings)} findings</span></div>
<div class="pill progress-copy"><span class="progress-track" aria-hidden="true"><span class="progress-fill" id="progress-fill"></span></span>
<strong id="review-count">0 / {len(units)}</strong></div>
<button type="button" class="btn btn-ghost pill" id="run-info">{icon('tools')} How it ran</button>
<a class="btn btn-ghost pill pr-link" href="{esc(meta['url'])}">{icon('external')} Open on GitHub</a></div></div></header>
<div class="body"><div class="toc-backdrop" id="toc-backdrop"></div>
<nav class="toc" id="toc" aria-label="Review modules"><p class="toc-title">Modules</p>
<ol class="nav-list">{''.join(sidebar)}</ol></nav>
<main class="workspace" id="review-workspace"><div class="workspace-inner">
<article class="unit home" data-unit-id="__home">
<header class="unit-head home-head"><div><div class="summary-kicker">
<span class="branch">{esc(meta['head_ref'])} → {esc(meta['base_ref'])}</span>
<span class="badge badge-outline verdict">{esc(meta['verdict'] or 'Reviewed')}</span></div>
<h1 tabindex="-1">{esc(meta['title'])}</h1></div></header>
<section class="summary"><p>{esc(meta['summary'])}</p></section>
{finding_index}
{render_flow(data.get('learning', {}))}</article>
{''.join(pages)}
<article class="unit closing" data-unit-id="__closing">
<header class="unit-head"><div><div class="eyebrow"><span>Wrap up</span></div>
<h2 tabindex="-1">You&rsquo;ve been through every module</h2></div></header>
{render_next_actions(meta, len(units), len(findings))}
{render_disproved(data.get('disproved', []))}
</article>
<article class="unit notes" data-unit-id="__notes">
<header class="unit-head"><div><div class="eyebrow"><span>Reference</span></div>
<h2 tabindex="-1">Codebase notes</h2></div></header>
<p class="context">What this change revealed about how the codebase works &mdash; durable beyond this pull request.</p>
{render_learning(data.get('learning', {}))}</article></div></main></div>
{render_process(data['review_process'])}</div>
<div class="dock"><div class="footer-nav">
<button type="button" class="btn btn-ghost btn-icon" id="prev" aria-label="Previous module" title="Previous module (left arrow key)">{icon("left")}</button>
<span class="footer-state" id="footer-state">Module 1 of {len(units)}</span>
<button type="button" class="btn btn-ghost btn-icon" id="next" aria-label="Next module" title="Next module (right arrow key)">{icon("right")}</button></div>
<button type="button" class="btn btn-accent reviewed-action" id="mark-reviewed" aria-pressed="false">Mark reviewed</button></div>
<div class="sr-only unit-announcer" id="unit-announcer" aria-live="polite"></div>
<script>{SCRIPT}</script></body></html>'''


def md(value: Any) -> str:
    value = html.escape(str(value), quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!|>-])", r"\\\1", value)


def md_code(value: Any) -> str:
    return "`" + str(value).replace("`", "\\`").replace("\n", " ") + "`"


def md_bullets(items: list[str]) -> str:
    return "\n".join(f"- {md(item)}" for item in items)


def render_wiki(data: dict[str, Any]) -> str:
    meta, learning = data["meta"], data.get("learning", {})
    out = [
        f"# PR #{meta['pr_number']}: {md(meta['title'])}",
        "",
        f"Source: [{md(meta['repository'])}#{meta['pr_number']}]({meta['url']})  ",
        f"Reviewed head: {md_code(meta['head_sha'])}  ",
        f"Generated: {md(meta['generated_at'])}",
        "",
        md(meta["summary"]),
    ]
    for title, key in (("Architecture", "architecture"), ("Invariants", "invariants"), ("Gotchas", "gotchas")):
        items = learning.get(key, [])
        if items:
            out.extend(["", f"## {title}", "", md_bullets(items)])
    if learning.get("data_flows"):
        out.extend(["", "## Data flows"])
        for flow in learning["data_flows"]:
            out.extend(["", f"### {md(flow['title'])}", ""])
            out.extend(f"{i}. {md(step)}" for i, step in enumerate(flow["steps"], 1))
            out.extend(["", "Files: " + ", ".join(md_code(path) for path in flow["files"])])
    if data.get("disproved"):
        out.extend([
            "",
            "## Checked and cleared",
            "",
            "Investigated during this review and did not hold. Recorded so a later review does "
            "not re-open a settled question.",
        ])
        for item in data["disproved"]:
            out.extend(["", f"- **{md(item['claim'])}** {md(item['why_not'])}"])
            for source in item.get("evidence", []):
                out.append(f"  - {md_code(source['path'] + ':' + str(source['line']))} {md(source['quote'])}")
    out.extend(["", "## Review walkthrough"])
    covered: list[str] = []
    for index, unit in enumerate(data["units"], 1):
        out.extend([
            "",
            f"### {index:02}. {md(unit['title'])}",
            "",
            f"Risk: **{md(unit['risk'].replace('-', ' '))}** · Kind: **{md(unit['kind'])}**",
            "",
            md(unit["context"]),
        ])
        if unit["review_focus"]:
            out.extend(["", "Review focus:", "", md_bullets(unit["review_focus"])])
        paths = [file["path"] for file in unit["files"]]
        covered.extend(paths)
        out.extend(["", "Files: " + ", ".join(md_code(path) for path in paths)])
        for quiz in unit.get("quiz", []):
            out.extend([
                "",
                "<details>",
                f"<summary>{md(quiz['question'])}</summary>",
                "",
                f"**Answer:** {md(quiz['answer'])}",
                "",
                f"**Why it matters:** {md(quiz['why'])}",
                "",
                "</details>",
            ])
    out.extend(["", "## Files covered", "", md_bullets(sorted(set(covered))), ""])
    return "\n".join(out)


def library_root(override: Path | None = None) -> Path:
    if override is not None:
        return override.expanduser()
    configured = os.environ.get("PR_WALKTHROUGH_HOME") or os.environ.get("PR_REVIEW_QUIZ_HOME")
    if configured:
        return Path(configured).expanduser()
    data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(data_home).expanduser() if data_home else Path.home() / ".local" / "share"
    current = base / "pr-walkthrough"
    # Reviews archived before the rename stay discoverable; new ones go to the new root.
    legacy = base / "pr-review-quiz"
    if not current.exists() and legacy.exists():
        return legacy
    return current


def safe_segment(value: str) -> str:
    segment = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    if not segment:
        raise GuideError(f"unsafe empty path segment from {value!r}")
    return segment


def write_private(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)


def persist_snapshot(
    data: dict[str, Any],
    guide_json: str,
    html_page: str,
    wiki_page: str,
    root: Path,
) -> Path:
    meta = data["meta"]
    try:
        owner, repository = meta["repository"].split("/", 1)
    except ValueError as error:
        raise GuideError("meta.repository must be owner/repository") from error
    pr_dir = (
        root
        / "reviews"
        / safe_segment(owner)
        / safe_segment(repository)
        / f"pr-{meta['pr_number']}"
    )
    guide_sha256 = hashlib.sha256(guide_json.encode("utf-8")).hexdigest()
    renderer_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    snapshot = pr_dir / safe_segment(
        f'{meta["head_sha"][:12]}-{guide_sha256[:8]}-{renderer_sha256[:8]}'
    )
    snapshot.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    write_private(snapshot / "review.html", html_page)
    write_private(snapshot / "guide.json", guide_json)
    write_private(snapshot / "wiki.md", wiki_page)
    manifest = {
        "schema_version": 3,
        "repository": meta["repository"],
        "pr_number": meta["pr_number"],
        "url": meta["url"],
        "base_ref": meta["base_ref"],
        "head_ref": meta["head_ref"],
        "head_sha": meta["head_sha"],
        "generated_at": meta["generated_at"],
        "guide_sha256": guide_sha256,
        "renderer_sha256": renderer_sha256,
        "review_process": data["review_process"],
        "stats": {**data["stats"], "hunks": len(data["hunk_inventory"]), "findings": len(data.get("findings", []))},
        "artifacts": {"html": "review.html", "guide": "guide.json", "wiki": "wiki.md"},
    }
    write_private(snapshot / "manifest.json", json.dumps(manifest, indent=2) + "\n")
    latest = {"head_sha": meta["head_sha"], "snapshot": snapshot.name, "generated_at": meta["generated_at"]}
    latest_path = pr_dir / "latest.json"
    temporary = pr_dir / f".latest-{os.getpid()}.tmp"
    write_private(temporary, json.dumps(latest, indent=2) + "\n")
    os.replace(temporary, latest_path)
    return snapshot


def start_progress_server(token: str, target: dict[str, Any], done: Event) -> tuple[ThreadingHTTPServer, str]:
    """Localhost-only writer so the artifact can report reading progress back to disk.

    `target` is populated with the snapshot directory after the render lands, so the handler
    reads it lazily; a request only ever arrives once a human has worked through the guide.
    """

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler dispatch name
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(min(length, 8192))
            self.send_response(204)
            self.end_headers()
            snapshot = target.get("snapshot")
            if self.path != "/progress" or snapshot is None:
                return
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return
            if not isinstance(payload, dict):
                return
            if not hmac.compare_digest(str(payload.get("token", "")), token):
                return
            reviewed, total = payload.get("reviewed"), payload.get("total")
            if isinstance(reviewed, bool) or isinstance(total, bool):
                return
            if not isinstance(reviewed, int) or not isinstance(total, int) or total < 1:
                return
            write_private(
                snapshot / "progress.json",
                json.dumps(
                    {
                        "repository": target["repository"],
                        "pr": target["pr"],
                        "head_sha": target["head_sha"],
                        "reviewed": reviewed,
                        "total": total,
                        "completed_at": str(payload.get("completed_at", ""))[:40],
                    },
                    indent=2,
                )
                + "\n",
            )
            if reviewed >= total:
                done.set()

        def log_message(self, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/progress"


def iter_latest(root: Path) -> list[tuple[dict[str, Any], Path]]:
    rows: list[tuple[dict[str, Any], Path]] = []
    for latest_path in sorted((root / "reviews").glob("*/*/pr-*/latest.json")):
        try:
            latest = json.loads(latest_path.read_text(encoding="utf-8"))
            snapshot = latest_path.parent / safe_segment(text(latest.get("snapshot"), "latest.snapshot"))
            manifest_path = snapshot / "manifest.json"
            manifest = expect(json.loads(manifest_path.read_text(encoding="utf-8")), dict, "manifest")
            rows.append((manifest, snapshot / "review.html"))
        except (GuideError, OSError, json.JSONDecodeError):
            continue
    return rows


def latest_review(root: Path, target: str) -> Path:
    match = re.fullmatch(r"([^/]+)/([^#]+)#([1-9][0-9]*)", target)
    if not match:
        raise GuideError("--latest must be OWNER/REPOSITORY#NUMBER")
    owner, repository, number = match.groups()
    latest_path = root / "reviews" / safe_segment(owner) / safe_segment(repository) / f"pr-{number}" / "latest.json"
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    return latest_path.parent / safe_segment(text(latest.get("snapshot"), "latest.snapshot")) / "review.html"


def sample_guide() -> dict[str, Any]:
    return {
        "meta": {
            "repository": "owner/repo",
            "pr_number": 7,
            "url": "https://github.com/owner/repo/pull/7",
            "title": "Escape <script>alert(1)</script>",
            "base_ref": "main",
            "head_ref": "feature",
            "head_sha": "abc123",
            "generated_at": "2026-08-06T00:00:00Z",
            "summary": "A small safe change.",
            "verdict": "Correct",
        },
        "stats": {"files": 1, "additions": 1, "deletions": 0},
        "review_process": {
            "mode": "full",
            "execution": "native_parallel",
            "merge_base_sha": "def456",
            "passes": [
                {"lane": "intent and standards", "status": "completed", "summary": "Checked intent and rules."},
                {"lane": "correctness and reliability", "status": "completed", "summary": "Traced behavior."},
                {"lane": "tests and compatibility", "status": "completed", "summary": "Checked tests and contracts."},
            ],
            "limitations": ["No code graph index; navigation fell back to repository search."],
        },
        "hunk_inventory": ["src/a.py#0"],
        "units": [{
            "id": "safe-change",
            "kind": "change",
            "risk": "review",
            "title": "Safe change",
            "context": "Adds one value.",
            "review_focus": ["Boundary behavior"],
            "files": [{
                "path": "src/a.py",
                "role": "core_logic",
                "hunks": [{
                    "id": "src/a.py#0",
                    "header": "@@ -1,0 +1 @@",
                    "lines": [{"type": "add", "old_line": None, "new_line": 1,
                               "text": "    def load(self, tag: str = '<b>', n: int = 3) -> Boundary:  # keep it"}],
                }],
            }],
            "quiz": [{"question": "What crosses the boundary?", "answer": "A value.", "why": "It defines behavior."}],
        }],
        "findings": [{
            "priority": "P2",
            "title": "Handle the boundary",
            "body": "This value reaches the boundary without validation.",
            "path": "src/a.py",
            "line": 1,
            "side": "RIGHT",
            "unit_id": "safe-change",
            "confidence": 9,
            "found_by": ["correctness and reliability", "tests and compatibility"],
            "evidence": [{"path": "src/a.py", "line": 1, "quote": "value = '<tag>'"}],
        }],
        "disproved": [{
            "claim": "The boundary double-encodes the value.",
            "why_not": "The encoder runs once, at the call site, and the boundary passes it through.",
            "evidence": [{"path": "src/a.py", "line": 1, "quote": "value = '<tag>'"}],
        }],
        "learning": {
            "architecture": ["Observed: A owns the value (src/a.py:1)."],
            "data_flows": [{
                "title": "Value to boundary",
                "steps": ["A sets the value", "The boundary reads it"],
                "files": ["src/a.py", "src/boundary.py", "src/sink.py"],
            }],
            "invariants": ["Observed: the value is never empty at the boundary (src/a.py:1)."],
            "gotchas": ["Inference: older callers may omit the value (src/a.py:1)."],
        },
    }


# Classes the one-unit sample cannot exercise: toggled by script, or driven by an enum whose
# other members simply are not present in a single sample finding/unit/pass.
SCRIPT_STATE_CLASSES = {"active", "done", "open", "reviewed"}

# Priority-derived modifier: the one-finding sample is a P2, so it never renders.
DERIVED_CLASSES = {"has-p0"}


def check_css_coverage(*pages: str) -> None:
    """Fail if a class is styled but never rendered, or rendered but never styled.

    Both directions matter: dead CSS means a panel was designed and never emitted, and an
    unstyled class means markup shipped without its rule. Neither is visible in a self-check
    that only greps for strings.
    """
    # Strip comments and url(...) first: a filename in a comment or a hostname in a
    # data URI is not a selector. (Both have produced false positives here.)
    selectors = re.sub(r"/\*.*?\*/", "", STYLES, flags=re.S)
    selectors = re.sub(r"url\([^)]*\)", "", selectors)
    styled = set(re.findall(r"\.(-?[_a-zA-Z][\w-]*)", selectors))
    rendered: set[str] = set()
    for page in pages:
        for value in re.findall(r'class="([^"]*)"', page):
            rendered.update(value.split())
    allowed = (
        SCRIPT_STATE_CLASSES
        | DERIVED_CLASSES
        | {priority.lower() for priority in PRIORITIES}
        | RISKS
        | PASS_STATUSES
        | LINE_TYPES
        | ROLES
    )
    # Enum and state classes are exempt both ways: the sample cannot emit every member, and a
    # member with no rule of its own is legitimate when it falls through to a base rule.
    dead = styled - rendered - allowed
    unstyled = rendered - styled - allowed
    assert not dead, f"CSS classes are styled but never rendered: {sorted(dead)}"
    assert not unstyled, f"rendered classes have no CSS rule: {sorted(unstyled)}"

    # Same bug class for the icon sprite: every symbol shipped must be referenced,
    # and every reference must resolve to a symbol that exists.
    defined = set(re.findall(r'<symbol id="i-([a-z-]+)"', ICON_SPRITE))
    used = {name for page in pages for name in re.findall(r'href="#i-([a-z-]+)"', page)}
    assert not defined - used, f"icon symbols defined but never used: {sorted(defined - used)}"
    assert not used - defined, f"icons referenced with no symbol: {sorted(used - defined)}"


def self_check() -> None:
    data = validate(sample_guide())
    page = render_html(data)
    wiki = render_wiki(data)
    # A clean review renders a different page: the empty state and its icon only
    # exist on that branch, so cover both rather than allowlisting the difference.
    clean = {**sample_guide(), "findings": [], "disproved": []}
    clean_page = render_html(validate(clean))
    assert "Nothing to fix here" in clean_page
    check_css_coverage(page, clean_page)
    assert 'class="next-actions"' in page
    assert "/pr-walkthrough submit owner/repo#7" in page
    assert 'id="completion"' in page
    assert "Copy completion token" in page
    assert "data-progress-endpoint" not in page
    served = render_html(data, ("http://127.0.0.1:9/progress", "tok"))
    assert 'data-progress-endpoint="http://127.0.0.1:9/progress"' in served
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "P2 finding: Handle the boundary" in page
    assert "What needs fixing" in page
    assert "How this review ran" in page
    assert 'class="unit-findings' in page
    assert "white-space: pre-wrap" in page
    # the trail must precede the diff in source order, so triage is read first
    assert page.index('class="trail"') < page.index('class="diff-scroll"')
    assert page.index('class="unit-findings') < page.index('class="diff-scroll"')
    assert "confidence 9/10" in page
    assert "found by 2 of 3 lanes" in page
    assert "Checked and cleared" in page
    assert "Checked and cleared" in wiki
    assert "ruled out" in page
    assert 'id="mark-reviewed"' in page
    assert page.index('class="footer-nav"') < page.index('id="mark-reviewed"')
    assert "## Review walkthrough" in wiki
    with TemporaryDirectory(prefix="pr-walkthrough-") as directory:
        root = Path(directory) / "library"
        guide_json = json.dumps(data)
        snapshot = persist_snapshot(data, guide_json, page, wiki, root)
        assert (snapshot / "review.html").is_file()
        assert latest_review(root, "owner/repo#7") == snapshot / "review.html"
        assert len(iter_latest(root)) == 1
    print("render_review.py self-check passed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, help="guide JSON")
    parser.add_argument("html_output", nargs="?", type=Path, help="HTML output path")
    parser.add_argument("--wiki", type=Path, help="optional Markdown Wiki draft path")
    parser.add_argument("--library-root", type=Path, help="override the shared review library root")
    parser.add_argument("--no-persist", action="store_true", help="do not archive this render in the shared library")
    parser.add_argument(
        "--serve",
        action="store_true",
        help="run a localhost-only writer so the page can record reading progress, then wait for it",
    )
    parser.add_argument("--list-reviews", action="store_true", help="list the latest persisted review for every PR")
    parser.add_argument("--latest", metavar="OWNER/REPOSITORY#NUMBER", help="print the latest persisted HTML path")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    root = library_root(args.library_root)
    if args.self_check:
        self_check()
        return
    if args.list_reviews:
        for manifest, review_path in iter_latest(root):
            print(
                f"{manifest.get('generated_at', '')}\t{manifest.get('repository')}#{manifest.get('pr_number')}\t"
                f"{manifest.get('head_sha', '')}\t{review_path}"
            )
        return
    if args.latest:
        try:
            print(latest_review(root, args.latest))
        except (GuideError, OSError, json.JSONDecodeError) as error:
            parser.error(str(error))
        return
    if args.input is None or args.html_output is None:
        parser.error("input and html_output are required for rendering")
    guide_json = args.input.read_text(encoding="utf-8")
    data = validate(json.loads(guide_json))
    if args.serve and args.no_persist:
        parser.error("--serve needs a persisted snapshot to write progress into; drop --no-persist")
    writer = None
    server = None
    done = Event()
    target: dict[str, Any] = {
        "repository": data["meta"]["repository"],
        "pr": data["meta"]["pr_number"],
        "head_sha": data["meta"]["head_sha"],
        "snapshot": None,
    }
    if args.serve:
        # Token lives only in this process, so the copy inside an archived page grants nothing later.
        token = secrets.token_urlsafe(24)
        server, endpoint = start_progress_server(token, target, done)
        writer = (endpoint, token)
    html_page = render_html(data, writer)
    wiki_page = render_wiki(data)
    args.html_output.write_text(html_page, encoding="utf-8")
    if args.wiki:
        args.wiki.write_text(wiki_page, encoding="utf-8")
    print(f"wrote {args.html_output}")
    if args.wiki:
        print(f"wrote {args.wiki}")
    if not args.no_persist:
        snapshot = persist_snapshot(data, guide_json, html_page, wiki_page, root)
        target["snapshot"] = snapshot
        print(f"archived {snapshot}")
    if server is not None:
        # flush: this process then blocks, so a buffered pipe would hide the endpoint entirely.
        print(f"progress writer on {writer[0]} - open the page; ctrl-c to stop", flush=True)
        try:
            done.wait()
            print(f"review complete, wrote {target['snapshot'] / 'progress.json'}", flush=True)
        except KeyboardInterrupt:
            print("stopped", flush=True)
        finally:
            server.shutdown()


if __name__ == "__main__":
    main()
