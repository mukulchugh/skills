#!/usr/bin/env python3
"""Validate and render a PR Review Quiz guide as self-contained HTML and Markdown."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
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


STYLES = r"""
:root {
  --canvas: #eef3f8;
  --paper: #fbfcfe;
  --surface: #ffffff;
  --nav: #142033;
  --nav-surface: #1b2a41;
  --ink: #172033;
  --muted: #627086;
  --line: #d7dfeb;
  --line-strong: #b8c4d5;
  --accent: #285bb8;
  --accent-soft: #e7eefc;
  --active: #8bd8c8;
  --add: #e7f5eb;
  --add-strong: #c8ead2;
  --del: #fcebec;
  --del-strong: #f4cdd0;
  --code: #111927;
  --code-muted: #53637a;
  --p0: #b42318;
  --p1: #d14900;
  --p2: #a15c00;
  --p3: #52657d;
  --shadow: 0 18px 50px rgba(30, 55, 90, .09);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  background: var(--canvas);
  color: var(--ink);
  font: 15px/1.58 ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  text-rendering: optimizeLegibility;
}
button, input { font: inherit; }
button { -webkit-tap-highlight-color: transparent; }
a { color: var(--accent); text-underline-offset: 3px; }
code, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.skip-link { position: fixed; left: 12px; top: -60px; z-index: 100; background: white; color: var(--ink); padding: 10px 14px; border-radius: 6px; }
.skip-link:focus { top: 12px; }
:focus-visible { outline: 3px solid #5a8ceb; outline-offset: 3px; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
.shell { display: grid; grid-template-columns: 328px minmax(0, 1fr); min-height: 100vh; }
.nav {
  position: sticky;
  top: 0;
  z-index: 20;
  height: 100vh;
  overflow: auto;
  padding: 24px 18px 32px;
  color: #eef4fc;
  background: var(--nav);
  border-right: 1px solid #263750;
}
.brand-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.brand { font: 700 12px/1 ui-monospace, monospace; letter-spacing: .13em; text-transform: uppercase; color: var(--active); }
.outline-toggle { display: none; min-height: 44px; border: 1px solid #40516a; border-radius: 7px; background: var(--nav-surface); color: white; padding: 0 12px; }
.meta { margin: 22px 6px 16px; }
.meta h2 { margin: 0 0 6px; font-size: 16px; line-height: 1.25; letter-spacing: -.01em; }
.meta p { margin: 0; color: #aebbd0; font-size: 13px; line-height: 1.45; }
.stats { display: flex; flex-wrap: wrap; gap: 8px 13px; margin-top: 14px; color: #d9e3f1; font: 12px ui-monospace, monospace; }
.stats .plus { color: #83d3a0; }
.stats .minus { color: #f09b9f; }
.progress-copy { display: flex; justify-content: space-between; margin: 16px 0 7px; color: #aebbd0; font-size: 12px; }
.progress-track { height: 4px; overflow: hidden; background: #2b3b54; border-radius: 9px; }
.progress-fill { display: block; width: 0; height: 100%; background: var(--active); transition: width .18s ease; }
.nav-list { list-style: none; padding: 10px 0 0; margin: 16px 0 0; border-top: 1px solid #2d3d56; }
.nav-list li { position: relative; }
.nav-list li:not(:last-child)::after { content: ""; position: absolute; left: 19px; top: 41px; bottom: -5px; width: 1px; background: #31425c; }
.unit-link {
  position: relative;
  width: 100%;
  min-height: 58px;
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr) auto;
  grid-template-rows: auto auto;
  gap: 3px 10px;
  align-items: start;
  padding: 9px 8px;
  border: 0;
  border-radius: 8px;
  text-align: left;
  background: transparent;
  color: #f4f7fb;
  cursor: pointer;
}
.unit-link:hover { background: #1a2a42; }
.unit-link.active { background: #21324c; box-shadow: inset 3px 0 0 var(--active); }
.chapter-no {
  grid-row: 1 / 3;
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  margin-top: 2px;
  border: 1px solid #4d5e76;
  border-radius: 50%;
  color: #afbdd1;
  font: 11px ui-monospace, monospace;
  background: var(--nav);
  z-index: 1;
}
.unit-link.active .chapter-no { border-color: var(--active); color: var(--nav); background: var(--active); }
.unit-link.reviewed .chapter-no { color: transparent; border-color: #6bc18a; background: #234635; }
.unit-link.reviewed .chapter-no::after { content: "✓"; color: #9ae0b3; font-weight: 800; }
.unit-title { min-width: 0; font-size: 13px; line-height: 1.24; font-weight: 680; }
.unit-meta { grid-column: 2; color: #93a3ba; font: 10px ui-monospace, monospace; text-transform: uppercase; letter-spacing: .09em; }
.unit-finding-count { align-self: center; min-width: 23px; padding: 2px 6px; border-radius: 99px; background: #5a281f; color: #ffc2b8; font: 700 10px ui-monospace, monospace; text-align: center; }
.unit-finding-count:empty { display: none; }
.workspace { width: 100%; min-width: 0; padding: 34px clamp(22px, 4vw, 64px) 112px; }
.workspace-inner { width: 100%; max-width: 1380px; margin: 0 auto; }
.summary {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 24px;
  align-items: start;
  padding: 24px 26px;
  margin-bottom: 26px;
  border: 1px solid var(--line);
  border-top: 4px solid var(--accent);
  background: var(--surface);
  box-shadow: var(--shadow);
}
.summary .branch { color: var(--muted); font: 12px ui-monospace, monospace; }
.summary h1 { max-width: 980px; margin: 7px 0 8px; font-size: clamp(24px, 3vw, 38px); line-height: 1.08; letter-spacing: -.035em; }
.summary p { max-width: 900px; margin: 0; color: #44526a; font-size: 16px; }
.summary-actions { display: flex; flex-direction: column; align-items: flex-end; gap: 10px; white-space: nowrap; }
.verdict { padding: 6px 10px; border: 1px solid #ddb56d; border-radius: 5px; color: #7b4a00; background: #fff6df; font-weight: 700; font-size: 12px; }
.finding-index { margin: 0 0 28px; padding: 18px 20px; border: 1px solid var(--line); background: #f8fafd; }
.finding-index-head { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; margin-bottom: 10px; }
.finding-index h2 { margin: 0; font-size: 14px; letter-spacing: .04em; text-transform: uppercase; }
.finding-index-head span { color: var(--muted); font-size: 12px; }
.finding-jumps { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(390px, 100%), 1fr)); gap: 8px; }
.finding-jump { min-height: 58px; display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 3px 9px; align-items: start; border: 1px solid var(--line); border-radius: 6px; background: white; color: var(--ink); padding: 9px 10px; text-align: left; cursor: pointer; }
.finding-jump:hover { border-color: var(--line-strong); background: var(--paper); }
.finding-jump > span:nth-child(2) { min-width: 0; line-height: 1.35; font-weight: 650; }
.severity { display: inline-flex; align-items: center; justify-content: center; min-width: 30px; height: 22px; border: 1px solid currentColor; border-radius: 4px; font: 800 11px ui-monospace, monospace; }
.severity.p0 { color: var(--p0); }.severity.p1 { color: var(--p1); }.severity.p2 { color: var(--p2); }.severity.p3 { color: var(--p3); }
.finding-jump small { grid-column: 2; min-width: 0; overflow: hidden; color: var(--muted); font: 11px ui-monospace, monospace; text-overflow: ellipsis; white-space: nowrap; }
.no-findings { margin: 0; color: #326b49; }
.process { margin: 0 0 28px; padding: 18px 20px; border: 1px solid var(--line); background: var(--surface); }
.process-head { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.process h2 { margin: 0; font-size: 14px; letter-spacing: .04em; text-transform: uppercase; }
.process-tags { display: flex; flex-wrap: wrap; gap: 6px; color: var(--muted); font: 11px ui-monospace, monospace; }
.process-tags span { padding: 3px 7px; border: 1px solid var(--line); background: var(--paper); }
.process-passes { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 8px; }
.process-pass { padding: 12px 13px; border: 1px solid var(--line); background: var(--paper); }
.process-pass strong { display: block; margin-bottom: 4px; font-size: 13px; }
.process-pass p { margin: 0; color: var(--muted); font-size: 12px; }
.process-status { float: right; color: #326b49; font: 10px ui-monospace, monospace; text-transform: uppercase; }
.process-status.failed { color: var(--p0); }.process-status.fallback { color: var(--p2); }
.process-limitations { margin: 12px 0 0; color: #6f4c12; font-size: 12px; }
.unit { display: none; scroll-margin-top: 20px; }
.unit.active { display: block; }
.unit-head { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 20px; align-items: start; margin: 0 0 18px; }
.eyebrow { display: flex; flex-wrap: wrap; gap: 9px; align-items: center; color: var(--muted); font: 11px ui-monospace, monospace; text-transform: uppercase; letter-spacing: .09em; }
.risk { padding: 3px 7px; border-left: 3px solid var(--p3); background: #e9eef4; color: #4d5d73; }
.risk.read-closely { border-color: var(--p0); color: #8f231b; background: #fceceb; }
.risk.review { border-color: var(--p2); color: #795000; background: #fff3d8; }
.unit h2 { margin: 7px 0 0; max-width: 1020px; font-size: clamp(27px, 3.5vw, 44px); line-height: 1.06; letter-spacing: -.04em; }
.unit-facts { display: grid; grid-template-columns: repeat(2, auto); gap: 8px 18px; padding: 8px 0; color: var(--muted); font: 11px ui-monospace, monospace; text-transform: uppercase; }
.unit-facts strong { display: block; color: var(--ink); font-size: 15px; text-align: right; }
.brief { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(280px, .65fr); gap: 18px; margin: 0 0 24px; }
.context, .focus { margin: 0; padding: 18px 20px; border: 1px solid var(--line); background: var(--surface); }
.context { color: #35445b; font-size: 17px; }
.focus h3, .quiz h3 { margin: 0 0 9px; color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .1em; }
.focus ul { margin: 0; padding-left: 18px; }
.focus li + li { margin-top: 5px; }
.file { overflow: hidden; margin: 18px 0 28px; border: 1px solid var(--line-strong); border-radius: 7px; background: var(--surface); box-shadow: 0 7px 25px rgba(33, 55, 87, .06); }
.file > header { position: sticky; top: 0; z-index: 4; display: flex; align-items: center; justify-content: space-between; gap: 16px; min-height: 46px; padding: 10px 14px; border-bottom: 1px solid var(--line); background: rgba(251, 252, 254, .96); backdrop-filter: blur(8px); }
.file > header code { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; font-weight: 700; }
.file-role { color: var(--muted); font: 10px ui-monospace, monospace; text-transform: uppercase; letter-spacing: .08em; white-space: nowrap; }
.diff-scroll { overflow-x: auto; overscroll-behavior-x: contain; background: #fbfcfe; scrollbar-color: #aab8ca transparent; }
.hunk { min-width: 100%; }
.hunk + .hunk { border-top: 1px solid var(--line-strong); }
.hunk-head { position: sticky; left: 0; width: 100%; min-width: max-content; padding: 8px 14px; color: #365676; background: #eaf1f8; font: 12px ui-monospace, monospace; border-bottom: 1px solid #d5e2ef; }
.diff-line { display: grid; grid-template-columns: 48px 48px 24px max-content; width: max-content; min-width: 100%; min-height: 25px; font: 13px/1.75 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.diff-line .ln { color: var(--code-muted); text-align: right; padding: 1px 10px 1px 4px; user-select: none; border-right: 1px solid rgba(108, 126, 151, .16); }
.diff-line .marker { color: var(--code-muted); text-align: center; user-select: none; }
.diff-line code { display: block; min-width: 100%; padding: 1px 18px 1px 8px; white-space: pre; color: var(--code); }
.diff-line.add { background: var(--add); }.diff-line.add .marker { color: #217342; }.diff-line.add code { background: linear-gradient(90deg, var(--add-strong) 0 3px, transparent 3px); }
.diff-line.del { background: var(--del); }.diff-line.del .marker { color: #a9323a; }.diff-line.del code { background: linear-gradient(90deg, var(--del-strong) 0 3px, transparent 3px); }
.finding { position: sticky; left: 0; width: min(860px, calc(100vw - 390px)); margin: 12px 16px; padding: 14px 16px; border: 1px solid #e3b875; border-left: 5px solid var(--p2); border-radius: 6px; background: #fff8e8; box-shadow: 0 9px 22px rgba(102, 69, 16, .08); white-space: normal; }
.finding.p0 { border-color: #e5a29d; border-left-color: var(--p0); background: #fff0ef; }.finding.p1 { border-left-color: var(--p1); }.finding.p3 { border-left-color: var(--p3); }
.finding-head { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.finding strong { font-size: 14px; }
.finding .anchor { color: var(--muted); font: 11px ui-monospace, monospace; }
.finding p { margin: 7px 0 0; color: #3d4655; }
.finding-evidence { margin-top: 10px; border-top: 1px solid rgba(127, 96, 39, .22); }
.finding-evidence summary { min-height: 38px; display: flex; align-items: center; cursor: pointer; color: var(--muted); font: 11px ui-monospace, monospace; }
.evidence-row { margin: 0 0 8px; }
.evidence-row span { display: block; color: var(--muted); font: 10px ui-monospace, monospace; }
.evidence-row code { display: block; overflow-x: auto; padding: 6px 8px; background: rgba(255,255,255,.65); color: var(--code); white-space: pre; }
.quiz { margin: 28px 0 12px; padding: 18px 20px; border: 1px solid var(--line); background: #f6f9fd; }
.quiz details { margin: 8px 0; border-top: 1px solid var(--line); }
.quiz summary { min-height: 44px; display: flex; align-items: center; cursor: pointer; font-weight: 700; }
.quiz details p { margin: 4px 0 10px; color: #43516a; }
.unit-finish { display: flex; justify-content: flex-end; margin: 24px 0 10px; }
.reviewed-action { min-height: 46px; padding: 10px 16px; border: 1px solid var(--accent); border-radius: 6px; background: var(--accent); color: white; font-weight: 750; cursor: pointer; }
.reviewed-action.done { color: #25613c; border-color: #83c79a; background: #e8f6ed; }
.learning { margin: 34px 0 0; border: 1px solid var(--line); background: var(--surface); }
.learning > summary { min-height: 48px; display: flex; align-items: center; padding: 0 18px; cursor: pointer; font-weight: 750; }
.learning-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; padding: 0 18px 18px; }
.learning article { padding: 14px 16px; border: 1px solid var(--line); background: var(--paper); }
.learning h3 { margin: 0 0 8px; font-size: 14px; }.learning ul, .learning ol { margin: 0; padding-left: 19px; }
.paths { color: var(--muted); font: 11px ui-monospace, monospace; }
.footer-nav { position: fixed; right: max(18px, env(safe-area-inset-right)); bottom: max(18px, env(safe-area-inset-bottom)); z-index: 30; display: grid; grid-template-columns: auto minmax(96px, auto) auto; align-items: center; gap: 6px; padding: 5px; border: 1px solid var(--line-strong); border-radius: 8px; background: rgba(255,255,255,.94); box-shadow: 0 12px 35px rgba(28, 48, 78, .18); backdrop-filter: blur(10px); }
.footer-nav button { min-height: 42px; border: 0; border-radius: 5px; padding: 8px 12px; background: #eaf0f8; color: var(--ink); cursor: pointer; }
.footer-nav button:hover { background: #dce6f3; }.footer-nav button:disabled { opacity: .38; cursor: default; }
.footer-state { color: var(--muted); font: 11px ui-monospace, monospace; text-align: center; }
.unit-announcer { position: fixed; }
@media (max-width: 1080px) {
  .shell { grid-template-columns: 285px minmax(0, 1fr); }
  .brief { grid-template-columns: 1fr; }
  .finding { width: min(760px, calc(100vw - 340px)); }
}
@media (max-width: 900px) {
  .shell { display: block; }
  .nav { height: auto; min-height: 68px; padding: 12px 16px; border-right: 0; border-bottom: 1px solid #2b3d59; overflow: visible; }
  .brand-row { min-height: 44px; }
  .outline-toggle { display: inline-flex; align-items: center; }
  .meta { display: none; }
  .nav-list { display: none; position: fixed; inset: 69px 0 0; z-index: 40; overflow-y: auto; margin: 0; padding: 14px 12px max(30px, env(safe-area-inset-bottom)); border: 0; background: var(--nav); }
  .nav.open .nav-list { display: block; }
  .unit-link { min-height: 62px; }
  .workspace { padding: 20px 14px 104px; }
  .summary { grid-template-columns: 1fr; padding: 20px; }
  .summary-actions { flex-direction: row; align-items: center; }
  .unit-head { grid-template-columns: 1fr; }
  .unit-facts { grid-template-columns: repeat(4, auto); justify-content: start; }
  .unit-facts strong { text-align: left; }
  .finding { width: calc(100vw - 62px); }
  .footer-nav { left: 10px; right: 10px; bottom: max(8px, env(safe-area-inset-bottom)); }
}
@media (max-width: 560px) {
  .summary h1 { font-size: 25px; }
  .summary p, .context { font-size: 15px; }
  .finding-index { padding: 14px; }
  .finding-jumps { grid-template-columns: 1fr; }
  .unit h2 { font-size: 30px; }
  .unit-facts { grid-template-columns: repeat(2, auto); }
  .context, .focus { padding: 15px; }
  .file { margin-left: -14px; margin-right: -14px; border-left: 0; border-right: 0; border-radius: 0; }
  .diff-line { grid-template-columns: 42px 42px 22px max-content; font-size: 12px; }
  .finding { width: calc(100vw - 28px); margin-left: 14px; margin-right: 14px; }
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after { transition-duration: .01ms !important; animation-duration: .01ms !important; }
}
@media print {
  .nav, .footer-nav, .skip-link { display: none !important; }
  .shell { display: block; }.workspace { padding: 0; }.unit { display: block; page-break-before: always; }
  .summary, .file { box-shadow: none; }.reviewed-action { display: none; }
}
"""


SCRIPT = r"""
const pages = [...document.querySelectorAll('.unit')];
const links = [...document.querySelectorAll('.unit-link')];
const nav = document.querySelector('.nav');
const key = 'pr-review-quiz:' + document.body.dataset.storageKey;
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
let current = 0;
let saved = {};
try { saved = JSON.parse(localStorage.getItem(key) || '{}'); } catch {}

function persist() { localStorage.setItem(key, JSON.stringify(saved)); }
function updateProgress() {
  const count = pages.filter(page => saved[page.dataset.unitId]).length;
  document.getElementById('review-count').textContent = `${count} / ${pages.length}`;
  document.getElementById('progress-fill').style.width = `${(count / pages.length) * 100}%`;
  pages.forEach((page, index) => {
    const done = !!saved[page.dataset.unitId];
    links[index].classList.toggle('reviewed', done);
    const action = page.querySelector('.reviewed-action');
    action.classList.toggle('done', done);
    action.textContent = done ? 'Reviewed · undo' : index === pages.length - 1 ? 'Mark review complete' : 'Mark reviewed & continue';
    action.setAttribute('aria-pressed', String(done));
  });
}
function show(index, options = {}) {
  const { focus = true, push = true } = options;
  current = Math.max(0, Math.min(pages.length - 1, index));
  pages.forEach((page, i) => page.classList.toggle('active', i === current));
  links.forEach((link, i) => {
    link.classList.toggle('active', i === current);
    link.setAttribute('aria-current', i === current ? 'step' : 'false');
  });
  document.getElementById('prev').disabled = current === 0;
  document.getElementById('next').disabled = current === pages.length - 1;
  document.getElementById('footer-state').textContent = `Unit ${current + 1} of ${pages.length}`;
  document.getElementById('outline-toggle').textContent = `Unit ${current + 1} of ${pages.length} · Outline`;
  document.getElementById('unit-announcer').textContent = `Showing unit ${current + 1}: ${pages[current].querySelector('h2').textContent}`;
  if (push) history.pushState({ index: current }, '', '#unit-' + pages[current].dataset.unitId);
  links[current]?.scrollIntoView({ block: 'nearest' });
  nav.classList.remove('open');
  if (focus) {
    pages[current].scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'start' });
    pages[current].querySelector('h2').focus({ preventScroll: true });
  }
}
function showFromHash(focus = false) {
  const index = pages.findIndex(page => '#unit-' + page.dataset.unitId === location.hash);
  show(index < 0 ? 0 : index, { focus, push: false });
}
links.forEach((link, index) => link.addEventListener('click', () => show(index)));
document.getElementById('prev').addEventListener('click', () => show(current - 1));
document.getElementById('next').addEventListener('click', () => show(current + 1));
document.getElementById('outline-toggle').addEventListener('click', () => nav.classList.toggle('open'));
document.querySelectorAll('.finding-jump').forEach(button => button.addEventListener('click', () => {
  const index = Number(button.dataset.unitIndex);
  show(index);
  requestAnimationFrame(() => {
    const finding = document.getElementById(button.dataset.findingId);
    finding?.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'center' });
    finding?.focus({ preventScroll: true });
  });
}));
pages.forEach((page, index) => page.querySelector('.reviewed-action').addEventListener('click', () => {
  const id = page.dataset.unitId;
  const wasDone = !!saved[id];
  saved[id] = !wasDone;
  persist();
  updateProgress();
  if (!wasDone && index < pages.length - 1) show(index + 1);
}));
document.addEventListener('keydown', event => {
  if (event.target.closest('input, textarea, button, a, summary, details, [contenteditable="true"]')) return;
  if (event.key === 'ArrowLeft') show(current - 1);
  if (event.key === 'ArrowRight') show(current + 1);
});
window.addEventListener('popstate', () => showFromHash(true));
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
    for i, raw_pass in enumerate(passes):
        review_pass = expect(raw_pass, dict, f"review_process.passes[{i}]")
        text(review_pass.get("lane"), f"review_process.passes[{i}].lane")
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
    evidence = "".join(
        f'<div class="evidence-row"><span>{esc(item["path"])}:{item["line"]}</span>'
        f'<code>{esc(item["quote"])}</code></div>'
        for item in finding["evidence"]
    )
    return (
        f'<aside id="{esc(finding["_dom_id"])}" tabindex="-1" '
        f'class="finding {esc(finding["priority"].lower())}" '
        f'aria-label="{esc(finding["priority"])} finding: {esc(finding["title"])}">'
        f'<div class="finding-head"><span class="severity {esc(finding["priority"].lower())}">'
        f'{esc(finding["priority"])}</span><strong>{esc(finding["title"])}</strong>'
        f'<span class="anchor">{esc(finding["path"])}:{finding["line"]}</span></div>'
        f'<p>{esc(finding["body"])}</p>'
        f'<details class="finding-evidence"><summary>Evidence · confidence {finding["confidence"]}/10</summary>'
        f'{evidence}</details></aside>'
    )


def render_process(process: dict[str, Any]) -> str:
    passes = "".join(
        f'<article class="process-pass"><span class="process-status {esc(item["status"])}">'
        f'{esc(item["status"])}</span><strong>{esc(item["lane"])}</strong><p>{esc(item["summary"])}</p></article>'
        for item in process["passes"]
    )
    limitations = ""
    if process.get("limitations"):
        limitations = f'<div class="process-limitations"><strong>Limits:</strong>{render_list(process["limitations"])}</div>'
    return (
        '<section class="process" aria-labelledby="process-title"><div class="process-head">'
        '<h2 id="process-title">Review execution</h2><div class="process-tags">'
        f'<span>{esc(process["mode"])} review</span><span>{esc(process["execution"].replace("_", " "))}</span>'
        f'<span>merge base {esc(process["merge_base_sha"][:12])}</span></div></div>'
        f'<div class="process-passes">{passes}</div>{limitations}</section>'
    )


def render_diff_file(file: dict[str, Any], findings_by_anchor: dict[tuple[str, str, int], list[dict[str, Any]]]) -> str:
    chunks = [
        '<section class="file">',
        f'<header><code title="{esc(file["path"])}">{esc(file["path"])}</code>'
        f'<span class="file-role">{esc(file["role"].replace("_", " "))}</span></header>',
        f'<div class="diff-scroll" role="region" tabindex="0" aria-label="Diff for {esc(file["path"])}">',
    ]
    for hunk in file["hunks"]:
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
                f'<code><span class="sr-only">{label}: </span>{esc(line["text"])}</code></div>'
            )
            keys = []
            if line["old_line"] is not None:
                keys.append((file["path"], "LEFT", line["old_line"]))
            if line["new_line"] is not None:
                keys.append((file["path"], "RIGHT", line["new_line"]))
            for key in keys:
                chunks.extend(finding_card(f) for f in findings_by_anchor.get(key, []))
        chunks.append("</div>")
    chunks.append("</div></section>")
    return "".join(chunks)


def render_learning(learning: dict[str, Any]) -> str:
    if not any(learning.get(key) for key in ("architecture", "invariants", "gotchas", "data_flows")):
        return ""
    parts = ['<details class="learning"><summary>Codebase learning appendix</summary><div class="learning-grid">']
    for title, key in (
        ("Architecture", "architecture"),
        ("Invariants", "invariants"),
        ("Gotchas", "gotchas"),
    ):
        items = learning.get(key, [])
        if items:
            parts.append(f'<article><h3>{title}</h3>{render_list(items)}</article>')
    for flow in learning.get("data_flows", []):
        parts.append(
            f'<article><h3>{esc(flow["title"])}</h3>'
            f'<ol>{"".join(f"<li>{esc(step)}</li>" for step in flow["steps"])}</ol>'
            f'<p class="paths">{esc(" → ".join(flow["files"]))}</p></article>'
        )
    parts.append("</div></details>")
    return "".join(parts)


def render_html(data: dict[str, Any]) -> str:
    meta, stats, units = data["meta"], data["stats"], data["units"]
    findings_by_anchor: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    findings_by_unit: dict[str, list[dict[str, Any]]] = defaultdict(list)
    findings: list[dict[str, Any]] = []
    for index, raw_finding in enumerate(data.get("findings", []), 1):
        finding = {**raw_finding, "_dom_id": f"finding-{index}"}
        findings.append(finding)
        findings_by_anchor[(finding["path"], finding["side"], finding["line"])].append(finding)
        findings_by_unit[finding["unit_id"]].append(finding)

    sidebar = []
    pages = []
    for index, unit in enumerate(units):
        unit_findings = findings_by_unit[unit["id"]]
        file_count = len(unit["files"])
        hunk_count = sum(len(file["hunks"]) for file in unit["files"])
        sidebar.append(
            f'<li><button type="button" class="unit-link" data-index="{index}" aria-current="false">'
            f'<span class="chapter-no">{index + 1:02}</span>'
            f'<span class="unit-title">{esc(unit["title"])}</span>'
            f'<span class="unit-finding-count">{len(unit_findings) if unit_findings else ""}</span>'
            f'<span class="unit-meta">{esc(unit["kind"])} · {esc(unit["risk"].replace("-", " "))}</span>'
            f'</button></li>'
        )
        quiz = ""
        if unit.get("quiz"):
            cards = []
            for item in unit["quiz"]:
                cards.append(
                    f'<details><summary>{esc(item["question"])}</summary>'
                    f'<p><strong>Answer:</strong> {esc(item["answer"])}</p>'
                    f'<p><strong>Why it matters:</strong> {esc(item["why"])}</p></details>'
                )
            quiz = '<section class="quiz"><h3>Check your mental model</h3>' + "".join(cards) + "</section>"
        files = "".join(render_diff_file(file, findings_by_anchor) for file in unit["files"])
        pages.append(
            f'<article class="unit" data-index="{index}" data-unit-id="{esc(unit["id"])}">'
            f'<header class="unit-head"><div><div class="eyebrow"><span>Unit {index + 1:02} / {len(units):02}</span>'
            f'<span class="risk {esc(unit["risk"])}">{esc(unit["risk"].replace("-", " "))}</span></div>'
            f'<h2 tabindex="-1">{esc(unit["title"])}</h2></div>'
            f'<div class="unit-facts"><span><strong>{file_count}</strong> files</span>'
            f'<span><strong>{hunk_count}</strong> hunks</span><span><strong>{len(unit_findings)}</strong> findings</span>'
            f'<span><strong>{len(unit.get("quiz", []))}</strong> questions</span></div></header>'
            f'<div class="brief"><p class="context">{esc(unit["context"])}</p>'
            f'<section class="focus"><h3>Review focus</h3>{render_list(unit["review_focus"])}</section></div>'
            f'{files}{quiz}<div class="unit-finish"><button type="button" class="reviewed-action" '
            f'aria-pressed="false">Mark reviewed &amp; continue</button></div></article>'
        )

    unit_index = {unit["id"]: index for index, unit in enumerate(units)}
    if findings:
        finding_jumps = "".join(
            f'<button type="button" class="finding-jump" data-unit-index="{unit_index[finding["unit_id"]]}" '
            f'data-finding-id="{esc(finding["_dom_id"])}"><span class="severity {finding["priority"].lower()}">'
            f'{esc(finding["priority"])}</span><span>{esc(finding["title"])}</span>'
            f'<small>{esc(finding["path"])}:{finding["line"]}</small></button>'
            for finding in findings
        )
        finding_index = (
            '<section class="finding-index" aria-labelledby="finding-index-title">'
            f'<div class="finding-index-head"><h2 id="finding-index-title">Findings to resolve</h2>'
            f'<span>{len(findings)} root-cause finding{"s" if len(findings) != 1 else ""}</span></div>'
            f'<div class="finding-jumps">{finding_jumps}</div></section>'
        )
    else:
        finding_index = (
            '<section class="finding-index" aria-labelledby="finding-index-title">'
            '<div class="finding-index-head"><h2 id="finding-index-title">Findings</h2><span>0</span></div>'
            '<p class="no-findings">No actionable defects survived validation.</p></section>'
        )

    storage_key = f"{meta['repository']}#{meta['pr_number']}@{meta['head_sha']}"
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(meta['repository'])}#{meta['pr_number']} · PR Review Quiz</title>
<style>{STYLES}</style></head>
<body data-storage-key="{esc(storage_key)}"><a class="skip-link" href="#review-workspace">Skip to review</a>
<div class="shell"><aside class="nav"><div class="brand-row"><div class="brand">PR Review Quiz</div>
<button type="button" class="outline-toggle" id="outline-toggle">Review outline</button></div>
<div class="meta"><h2>{esc(meta['repository'])} #{meta['pr_number']}</h2><p>{esc(meta['title'])}</p>
<div class="stats"><span class="plus">+{stats['additions']}</span><span class="minus">−{stats['deletions']}</span>
<span>{stats['files']} files</span><span>{len(data['hunk_inventory'])} hunks</span><span>{len(findings)} findings</span></div>
<div class="progress-copy"><span>Review progress</span><strong id="review-count">0 / {len(units)}</strong></div>
<div class="progress-track" aria-hidden="true"><span class="progress-fill" id="progress-fill"></span></div></div>
<nav aria-label="Review units"><ol class="nav-list">{''.join(sidebar)}</ol></nav></aside>
<main class="workspace" id="review-workspace"><div class="workspace-inner">
<section class="summary"><div><span class="branch">{esc(meta['head_ref'])} → {esc(meta['base_ref'])}</span>
<h1>{esc(meta['title'])}</h1><p>{esc(meta['summary'])}</p></div>
<div class="summary-actions"><span class="verdict">{esc(meta['verdict'] or 'Reviewed')}</span>
<a href="{esc(meta['url'])}">Open pull request ↗</a></div></section>
{render_process(data['review_process'])}{finding_index}{''.join(pages)}{render_learning(data.get('learning', {}))}</div></main></div>
<div class="footer-nav"><button type="button" id="prev">← Previous</button>
<span class="footer-state" id="footer-state">Unit 1 of {len(units)}</span>
<button type="button" id="next">Next →</button></div>
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
    configured = os.environ.get("PR_REVIEW_QUIZ_HOME")
    if configured:
        return Path(configured).expanduser()
    data_home = os.environ.get("XDG_DATA_HOME")
    return (Path(data_home).expanduser() if data_home else Path.home() / ".local" / "share") / "pr-review-quiz"


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
            "limitations": [],
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
                    "lines": [{"type": "add", "old_line": None, "new_line": 1, "text": "value = '<tag>'"}],
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
            "evidence": [{"path": "src/a.py", "line": 1, "quote": "value = '<tag>'"}],
        }],
        "learning": {"architecture": ["Observed: A owns the value (src/a.py:1)."], "data_flows": [], "invariants": [], "gotchas": []},
    }


def self_check() -> None:
    data = validate(sample_guide())
    page = render_html(data)
    wiki = render_wiki(data)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "P2 finding: Handle the boundary" in page
    assert "Findings to resolve" in page
    assert "Review execution" in page
    assert "confidence 9/10" in page
    assert "Mark reviewed &amp; continue" in page
    assert "## Review walkthrough" in wiki
    with TemporaryDirectory(prefix="pr-review-quiz-") as directory:
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
    html_page = render_html(data)
    wiki_page = render_wiki(data)
    args.html_output.write_text(html_page, encoding="utf-8")
    if args.wiki:
        args.wiki.write_text(wiki_page, encoding="utf-8")
    print(f"wrote {args.html_output}")
    if args.wiki:
        print(f"wrote {args.wiki}")
    if not args.no_persist:
        snapshot = persist_snapshot(data, guide_json, html_page, wiki_page, root)
        print(f"archived {snapshot}")


if __name__ == "__main__":
    main()
