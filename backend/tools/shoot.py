"""Screenshot the running UI for visual review."""

import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:3000/'


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1680, 'height': 1050},
                                device_scale_factor=2)
        errors = []
        page.on('console', lambda m: errors.append(f'{m.type}: {m.text}')
                if m.type in ('error', 'warning') else None)
        page.on('pageerror', lambda e: errors.append(f'pageerror: {e}'))

        page.goto(URL, wait_until='networkidle')
        page.wait_for_timeout(2500)
        page.screenshot(path='/tmp/ui_full.png')

        regions = page.locator('.chord-region')
        print('chord regions:', regions.count())
        print('note rings before hover:', page.locator('.note-ring').count())

        if regions.count() > 2:
            regions.nth(2).hover()
            page.wait_for_timeout(700)
            page.screenshot(path='/tmp/ui_hover.png')
            print('note rings after hover:', page.locator('.note-ring').count())

        score = page.locator('.score-scroll')
        box = score.bounding_box()
        if box:
            page.screenshot(path='/tmp/ui_score_top.png', clip={
                'x': box['x'], 'y': box['y'],
                'width': box['width'], 'height': min(520, box['height'])})

        ribbon = page.locator('.ribbon')
        rbox = ribbon.bounding_box()
        if rbox:
            page.screenshot(path='/tmp/ui_ribbon.png', clip=rbox)

        print('console issues:', errors[:12] or 'none')
        browser.close()


if __name__ == '__main__':
    main()
