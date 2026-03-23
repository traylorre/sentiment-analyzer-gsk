#!/usr/bin/env python3
"""Take Playwright screenshots of the dashboard for trace inspection report.

Usage:
    python scripts/screenshot_dashboard.py [--ticker GME] [--output reports/dashboard-gme.png]
"""

import argparse
import asyncio
from pathlib import Path


async def capture_dashboard(ticker: str, output_path: str) -> None:
    """Navigate to dashboard, search for ticker, screenshot the chart."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
        )
        page = await context.new_page()

        api_calls = []
        page.on("request", lambda req: api_calls.append(req.url) if "api" in req.url else None)

        frontend_url = "https://main.d29tlmksqcx494.amplifyapp.com"
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        print(f"Navigating to {frontend_url}...")
        await page.goto(frontend_url, timeout=30000)
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await asyncio.sleep(2)

        # Find ticker search input
        search_input = await page.query_selector('input[placeholder*="ticker" i]') or \
                       await page.query_selector('input[placeholder*="search" i]')

        if not search_input:
            print("No search input found — screenshot landing page only")
            await page.screenshot(path=str(output), full_page=False)
            await browser.close()
            return

        # Type ticker
        print(f"Searching for {ticker}...")
        await search_input.click()
        await search_input.fill(ticker)
        await asyncio.sleep(2)

        # Screenshot search results
        search_path = output.with_name(f"dashboard-search-{ticker.lower()}.png")
        await page.screenshot(path=str(search_path), full_page=False)
        print(f"Search screenshot: {search_path}")

        # Click result
        clicked = False
        for sel in [f'text={ticker}', '[role="option"]', f'li:has-text("{ticker}")']:
            try:
                result = await page.query_selector(sel)
                if result and await result.is_visible():
                    await result.click()
                    clicked = True
                    print(f"  Selected: {sel}")
                    break
            except Exception:
                pass

        if clicked:
            # Wait for chart data to load
            await asyncio.sleep(5)

            # Screenshot chart
            chart_path = output.with_name(f"dashboard-chart-{ticker.lower()}.png")
            await page.screenshot(path=str(chart_path), full_page=False)
            size_kb = chart_path.stat().st_size / 1024
            print(f"Chart screenshot: {chart_path} ({size_kb:.0f}KB)")

            # Check if chart rendered (file > 150KB suggests actual chart data)
            if size_kb > 150:
                print(f"  Chart rendered with data (>{150}KB)")
            else:
                print(f"  WARNING: Chart may be empty ({size_kb:.0f}KB)")
        else:
            print(f"  Could not select {ticker} from results")

        # Log API calls
        data_calls = [c for c in api_calls if "ohlc" in c or "sentiment" in c]
        print(f"\nData API calls ({len(data_calls)}):")
        for call in data_calls:
            print(f"  {call[:120]}")

        await browser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="GME")
    parser.add_argument("--output", default="reports/dashboard-gme.png")
    args = parser.parse_args()
    asyncio.run(capture_dashboard(args.ticker, args.output))


if __name__ == "__main__":
    main()
