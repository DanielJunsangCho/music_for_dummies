"""Measure layout boxes in the running UI to track down overflow."""

import json
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1]

SCRIPT = """
() => {
  const info = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return {left: Math.round(r.left), right: Math.round(r.right),
            width: Math.round(r.width), scrollWidth: el.scrollWidth,
            clientWidth: el.clientWidth};
  };
  const wide = [];
  document.querySelectorAll('*').forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.right > window.innerWidth + 2) {
      wide.push({tag: el.tagName, cls: el.className?.toString?.().slice(0, 40),
                 right: Math.round(r.right), width: Math.round(r.width)});
    }
  });
  return {
    viewport: window.innerWidth,
    docScroll: document.documentElement.scrollWidth,
    app: info('.app'),
    workspace: info('.workspace'),
    scoreScroll: info('.score-scroll'),
    scoreStack: info('.score-stack'),
    inspector: info('.inspector'),
    ribbon: info('.ribbon'),
    ribbonTrack: info('.ribbon-track'),
    overflowing: wide.slice(0, 10),
  };
}
"""

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1680, 'height': 1050})
    page.goto(URL, wait_until='networkidle')
    page.wait_for_timeout(2000)
    print(json.dumps(page.evaluate(SCRIPT), indent=2))
    browser.close()
