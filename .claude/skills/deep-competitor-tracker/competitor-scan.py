#!/usr/bin/env python3
"""
Playwright-based competitor data scanner for /competitor-audit.

Visits Play Store, App Store, AppBrain, review sites, and hiring pages.
Outputs structured JSON to stdout for the skill to consume.

All targets (competitors, app IDs, URLs) are read from scan-urls.json — nothing about
any specific company or vertical is hardcoded here. Populate scan-urls.json from
business.json via /operator-onboarding before running.

Usage:
  python3 .claude/skills/deep-competitor-tracker/competitor-scan.py                       # full scan
  python3 .claude/skills/deep-competitor-tracker/competitor-scan.py --section app_store    # single section
  python3 .claude/skills/deep-competitor-tracker/competitor-scan.py --competitor example   # single competitor (matches a "competitor" key in scan-urls.json)
"""

import json, sys, time, re, argparse
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

SCAN_URLS_PATH = Path(__file__).parent.parent.parent / "knowledge/competitor-audit/scan-urls.json"

def load_scan_urls():
    with open(SCAN_URLS_PATH) as f:
        return json.load(f)

def safe_text(el):
    return el.inner_text().strip() if el else None

def scrape_play_store(page, url, competitor):
    result = {"competitor": competitor, "platform": "android", "source_url": url}
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2000)

        # Rating
        rating_el = page.query_selector('[itemprop="starRating"] [aria-label*="rating"]')
        if not rating_el:
            rating_el = page.query_selector('div[aria-label*="stars"]')
        if rating_el:
            label = rating_el.get_attribute("aria-label") or ""
            m = re.search(r'([\d.]+)', label)
            if m:
                result["rating"] = float(m.group(1))

        # Rating count
        rating_count_els = page.query_selector_all('div[class*="Rating"] span')
        for el in rating_count_els:
            txt = el.inner_text().strip()
            if 'review' in txt.lower() or re.match(r'[\d.,]+[KMB]?\s*(reviews?|ratings?)', txt, re.I):
                result["rating_count"] = txt
                break

        # Install count — look for "X+" pattern near "Downloads" or in the stats area
        all_text = page.inner_text("body")
        install_patterns = [
            r'([\d,]+[KMB+]+)\s*(?:downloads|installs)',
            r'(\d+[LMK]+\+?)\s*(?:downloads|installs)',
            r'(\d+,\d+,\d+\+?)\s*(?:downloads|installs)',
        ]
        for pat in install_patterns:
            m = re.search(pat, all_text, re.I)
            if m:
                result["installs"] = m.group(1)
                break

        # Installs from the info section (the badges like "10L+", "10M+")
        if "installs" not in result:
            info_els = page.query_selector_all('[class*="Info"] span, [class*="header"] span')
            for el in info_els:
                txt = el.inner_text().strip()
                if re.match(r'\d+[LMKB]\+', txt):
                    result["installs"] = txt
                    break

        # Version
        version_els = page.query_selector_all('div:has-text("Version") + div, [class*="version"]')
        for el in version_els:
            txt = el.inner_text().strip()
            if re.match(r'\d+\.\d+', txt):
                result["version"] = txt
                break

        # Updated date
        updated_match = re.search(r'Updated\s+on\s+(\w+\s+\d+,?\s+\d{4})', all_text)
        if updated_match:
            result["updated"] = updated_match.group(1)

        # What's New
        whats_new_header = page.query_selector('h2:has-text("What\'s new")')
        if whats_new_header:
            sibling = whats_new_header.evaluate_handle("el => el.nextElementSibling")
            if sibling:
                try:
                    result["whats_new"] = sibling.as_element().inner_text().strip()[:500]
                except:
                    pass

        # Screenshot the page for verification
        screenshot_path = f"/tmp/competitor-scan-{competitor}-android.png"
        page.screenshot(path=screenshot_path, full_page=False)
        result["screenshot"] = screenshot_path

    except PlaywrightTimeout:
        result["error"] = "Page load timeout"
    except Exception as e:
        result["error"] = str(e)

    return result

def scrape_app_store(page, url, competitor):
    result = {"competitor": competitor, "platform": "ios", "source_url": url}
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2000)

        all_text = page.inner_text("body")

        # Rating — App Store shows "4.7" prominently in the info bar
        rating_matches = re.findall(r'\b(\d\.\d)\b', all_text[:500])
        for rm in rating_matches:
            val = float(rm)
            if 1.0 <= val <= 5.0:
                result["rating"] = val
                break

        # Rating count — "42K Ratings"
        m = re.search(r'([\d.,]+[KM]?)\s*Ratings?', all_text, re.I)
        if m:
            result["rating_count"] = m.group(1)

        # Version
        m = re.search(r'Version\s+([\d.]+)', all_text)
        if m:
            result["version"] = m.group(1)

        # Updated date
        m = re.search(r'(\w+\s+\d+,?\s+\d{4})', all_text[:1000])
        if m:
            result["updated"] = m.group(1)

        # What's New — try multiple selectors
        for selector in [
            'section:has(h2:has-text("What\'s New")) div[class*="content"]',
            '[class*="version-history"] p',
            'section:has(h2:has-text("What\'s New")) p',
        ]:
            whats_new_el = page.query_selector(selector)
            if whats_new_el:
                result["whats_new"] = whats_new_el.inner_text().strip()[:500]
                break

        screenshot_path = f"/tmp/competitor-scan-{competitor}-ios.png"
        page.screenshot(path=screenshot_path, full_page=False)
        result["screenshot"] = screenshot_path

    except PlaywrightTimeout:
        result["error"] = "Page load timeout"
    except Exception as e:
        result["error"] = str(e)

    return result

def scrape_appbrain(page, url, competitor):
    result = {"competitor": competitor, "source": "appbrain", "source_url": url}
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2000)

        all_text = page.inner_text("body")

        # Downloads — AppBrain layout: "1,000,000+\nDownloads" or "NUMBER Downloads"
        download_patterns = [
            r'([\d,]+\+?)\s*\n?\s*Downloads',
            r'Downloads[:\s]*([\d,]+\+?)',
            r'Installs[:\s]*([\d,]+\+?)',
        ]
        for pat in download_patterns:
            m = re.search(pat, all_text, re.I)
            if m:
                val = m.group(1).strip()
                if len(val) > 2:
                    result["downloads_exact"] = val
                    break

        # Reviews count — "81,520 reviews"
        m = re.search(r'([\d,]+)\s*reviews', all_text, re.I)
        if m:
            result["review_count"] = m.group(1)

        # Rating — "★ 3.74" or "3.74" near rating context
        m = re.search(r'[★☆]?\s*([\d]\.\d+)\s*\n?\s*[\d,]+\s*reviews', all_text)
        if m:
            result["rating"] = float(m.group(1))

        # Version
        m = re.search(r'(\d+\.\d+\.\d+)', all_text)
        if m:
            result["version"] = m.group(1)

        screenshot_path = f"/tmp/competitor-scan-{competitor}-appbrain.png"
        page.screenshot(path=screenshot_path, full_page=False)
        result["screenshot"] = screenshot_path

    except PlaywrightTimeout:
        result["error"] = "Page load timeout"
    except Exception as e:
        result["error"] = str(e)

    return result

def scrape_review_site(page, url, competitor, source):
    result = {"competitor": competitor, "source": source, "source_url": url}
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2000)

        all_text = page.inner_text("body")

        # Overall rating
        m = re.search(r'([\d.]+)\s*/?\s*5', all_text)
        if m:
            result["overall_rating"] = m.group(1)

        # Grab first few review snippets
        review_els = page.query_selector_all('[class*="review"] p, [class*="Review"] p, .review-text')
        reviews = []
        for el in review_els[:5]:
            txt = el.inner_text().strip()
            if len(txt) > 20:
                reviews.append(txt[:200])
        if reviews:
            result["recent_reviews"] = reviews

        screenshot_path = f"/tmp/competitor-scan-{competitor}-{source}.png"
        page.screenshot(path=screenshot_path, full_page=False)
        result["screenshot"] = screenshot_path

    except PlaywrightTimeout:
        result["error"] = "Page load timeout"
    except Exception as e:
        result["error"] = str(e)

    return result

def scrape_hiring(page, url, competitor, source):
    result = {"competitor": competitor, "source": source, "source_url": url}
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(3000)

        all_text = page.inner_text("body")

        # Extract job titles — look for common patterns
        job_els = page.query_selector_all('[class*="job"] a, [class*="Job"] a, [class*="position"] a, li a[href*="job"]')
        jobs = []
        for el in job_els[:15]:
            title = el.inner_text().strip()
            href = el.get_attribute("href") or ""
            if title and len(title) > 3:
                jobs.append({"title": title, "url": href})
        if jobs:
            result["open_positions"] = jobs

        screenshot_path = f"/tmp/competitor-scan-{competitor}-{source}.png"
        page.screenshot(path=screenshot_path, full_page=False)
        result["screenshot"] = screenshot_path

    except PlaywrightTimeout:
        result["error"] = "Page load timeout"
    except Exception as e:
        result["error"] = str(e)

    return result

def scrape_social(page, url, competitor, platform):
    result = {"competitor": competitor, "platform": platform, "source_url": url}
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(3000)

        # Just screenshot — X.com DOM is dynamic and changes frequently
        screenshot_path = f"/tmp/competitor-scan-{competitor}-{platform}.png"
        page.screenshot(path=screenshot_path, full_page=False)
        result["screenshot"] = screenshot_path
        result["note"] = "Screenshot captured for manual review. DOM extraction unreliable on X.com."

    except PlaywrightTimeout:
        result["error"] = "Page load timeout (X.com may require login)"
    except Exception as e:
        result["error"] = str(e)

    return result

def scrape_ads_library(page, url, tag):
    """LinkedIn / Meta / Google Ads Transparency. JS-heavy — give it 8s to render,
       then screenshot + grab body text excerpt. Scanner does not parse counts;
       the calling skill should read the screenshot or excerpt to extract them."""
    result = {"tag": tag, "source_url": url}
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(8000)
        try:
            body = page.locator("body").inner_text(timeout=5000)
            result["text_excerpt"] = body[:1500]
        except Exception:
            result["text_excerpt"] = ""
        screenshot_path = f"/tmp/competitor-scan-ads-{tag}.png"
        page.screenshot(path=screenshot_path, full_page=False)
        result["screenshot"] = screenshot_path
    except PlaywrightTimeout:
        result["error"] = "Page load timeout"
    except Exception as e:
        result["error"] = str(e)[:300]
    return result

def main():
    parser = argparse.ArgumentParser(description="Playwright competitor scanner")
    parser.add_argument("--section", choices=["app_store", "cross_verification", "review_sites", "social_media", "hiring", "ads_library", "all"], default="all")
    parser.add_argument("--competitor", help="Filter to a single competitor")
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--no-headless", dest="headless", action="store_false")
    args = parser.parse_args()

    scan_urls = load_scan_urls()
    results = {"scan_timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "data": {}}

    sections_to_run = [args.section] if args.section != "all" else ["app_store", "cross_verification", "review_sites", "social_media", "hiring", "ads_library"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        page = context.new_page()

        # App Store data (Play Store + Apple App Store)
        if "app_store" in sections_to_run:
            results["data"]["app_store"] = []
            for entry in scan_urls.get("app_store_data", []):
                if args.competitor and entry["competitor"] != args.competitor:
                    continue
                print(f"  Scanning {entry['competitor']} {entry['platform']}...", file=sys.stderr)
                if entry["platform"] == "android":
                    data = scrape_play_store(page, entry["url"], entry["competitor"])
                else:
                    data = scrape_app_store(page, entry["url"], entry["competitor"])
                if "note" in entry:
                    data["note"] = entry["note"]
                results["data"]["app_store"].append(data)
                time.sleep(1)

        # Cross-verification (AppBrain) — best-effort, Cloudflare may block after 1st request
        if "cross_verification" in sections_to_run:
            results["data"]["cross_verification"] = []
            for entry in scan_urls.get("cross_verification", []):
                if args.competitor and entry["competitor"] != args.competitor:
                    continue
                print(f"  Cross-verifying {entry['competitor']} via {entry['source']}...", file=sys.stderr)
                data = scrape_appbrain(page, entry["url"], entry["competitor"])
                if "note" in entry:
                    data["note"] = entry["note"]
                results["data"]["cross_verification"].append(data)
                time.sleep(5)  # longer delay to avoid Cloudflare rate limiting

        # Review sites
        if "review_sites" in sections_to_run:
            results["data"]["review_sites"] = []
            for entry in scan_urls.get("review_sites", []):
                if args.competitor and entry["competitor"] != args.competitor:
                    continue
                print(f"  Scanning {entry['competitor']} reviews on {entry['source']}...", file=sys.stderr)
                data = scrape_review_site(page, entry["url"], entry["competitor"], entry["source"])
                results["data"]["review_sites"].append(data)
                time.sleep(1)

        # Social media
        if "social_media" in sections_to_run:
            results["data"]["social_media"] = []
            for entry in scan_urls.get("social_media", []):
                if args.competitor and entry["competitor"] != args.competitor:
                    continue
                print(f"  Scanning {entry['competitor']} {entry['platform']}...", file=sys.stderr)
                data = scrape_social(page, entry["url"], entry["competitor"], entry["platform"])
                results["data"]["social_media"].append(data)
                time.sleep(1)

        # Hiring
        if "hiring" in sections_to_run:
            results["data"]["hiring"] = []
            for entry in scan_urls.get("hiring", []):
                if args.competitor and entry["competitor"] != args.competitor:
                    continue
                print(f"  Scanning {entry['competitor']} jobs on {entry['source']}...", file=sys.stderr)
                data = scrape_hiring(page, entry["url"], entry["competitor"], entry["source"])
                results["data"]["hiring"].append(data)
                time.sleep(1)

        # Ads library — LinkedIn / Meta / Google Ads Transparency
        if "ads_library" in sections_to_run:
            results["data"]["ads_library"] = []
            for entry in scan_urls.get("ads_library", []):
                if not entry.get("url"):
                    continue  # skip _todo / _description placeholders
                if args.competitor and entry.get("competitor") and entry["competitor"] != args.competitor:
                    continue
                print(f"  Scanning ads library: {entry['tag']}...", file=sys.stderr)
                data = scrape_ads_library(page, entry["url"], entry["tag"])
                if entry.get("competitor"):
                    data["competitor"] = entry["competitor"]
                if entry.get("platform"):
                    data["platform"] = entry["platform"]
                results["data"]["ads_library"].append(data)
                time.sleep(2)

        browser.close()

    # Output JSON to stdout
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
