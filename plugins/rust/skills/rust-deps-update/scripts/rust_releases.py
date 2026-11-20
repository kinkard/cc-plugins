#!/usr/bin/env python3
"""Rust release notes after <from> up to <to> (default: latest stable), only the sections that change how code is written.

Usage: rust_releases.py <from> [<to>] [--compat]    e.g. rust_releases.py 1.85 1.99
  --compat  also print "Compatibility Notes" (breaking changes to watch for)
Source: RELEASES.md from rust-lang/rust (one plain-markdown file, unlike the releases.rs HTML pages).
"""
import re, sys, urllib.request

args = [a for a in sys.argv[1:] if not a.startswith("--")]
if not args:
    sys.exit(__doc__)
keep = {"Language", "Libraries", "Stabilized APIs", "Const Stabilized APIs", "Cargo"}
if "--compat" in sys.argv:
    keep.add("Compatibility Notes")

ver = lambda s: tuple(int(x) for x in s.split("."))
lo = ver(args[0]) + (999,)  # "1.85" and "1.85.1" both exclude every 1.85.x release
hi = ver(args[1]) + (999,) if len(args) > 1 else (999,)

text = urllib.request.urlopen("https://raw.githubusercontent.com/rust-lang/rust/master/RELEASES.md", timeout=30).read().decode()
# A release header is "Version 1.99.0 (2026-10-01)" followed by a ===== line; sections are "Name" + ----- lines.
releases = re.split(r"^(?=Version \d+\.\d+\.\d+ \()", text, flags=re.M)
out = []
for rel in reversed(releases):
    m = re.match(r"Version (\d+\.\d+\.\d+) \((\S+)\)", rel)
    if not m or not (lo < ver(m[1]) <= hi):
        continue
    sections = []
    for name, body in re.findall(r"^(\S[^\n]*)\n-{3,}\n(.*?)(?=^\S[^\n]*\n-{3,}\n|\Z)", rel, flags=re.M | re.S):
        if name.strip() not in keep:
            continue
        body = re.sub(r"^\[[^\]]+\]: \S+\n?", "", body, flags=re.M)      # link reference definitions
        body = re.sub(r"\[(`[^`]+`)\]\([^)]+\)", r"\1", body)             # [`api`](url) -> `api`
        body = re.sub(r"\[(`[^`]+`)\]", r"\1", body)                      # [`api`] -> `api`
        body = re.sub(r"\[((?:[^\[\]]|\[[^\[\]]*\])+)\]\([^)]+\)", r"\1", body)  # [text](url) -> text
        body = re.sub(r"</?a\b[^>]*>", "", body).strip()                  # <a id=...> anchors
        if body:
            sections.append(f"## {name.strip()}\n{body}")
    if sections:
        out.append(f"\n# {m[1]} ({m[2]})\n" + "\n".join(sections))
print("\n".join(out).strip() or f"no releases in ({args[0]}, {args[1] if len(args) > 1 else 'latest'}]")
