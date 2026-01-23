import json
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode, urlunparse
import re

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

LIST_URL = "https://www.sccci.org.sg/event/index"
OUT = Path("data/events_current.json")

SGT = timezone(timedelta(hours=8))


def make_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]

def normalize_url(href: str) -> str:
    if not href:
        return ""
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return "https://www.sccci.org.sg" + href
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return urljoin("https://www.sccci.org.sg/", href)

# for extracting prices
def extract_prices(soup):
    member_price = ""
    non_member_price = ""

    price_box = soup.select_one("div.event-info-box2")
    if not price_box:
        return member_price, non_member_price

    txt = price_box.get_text(" ", strip=True)

    def pick_value(label_regex: str):
        """
        Returns either 'Free' or numeric amount (e.g. 350.00) or ''.
        label_regex should match ONLY the label (not the value).
        """
        # Free
        m_free = re.search(rf"{label_regex}\s*:?\s*(Free)\b", txt, re.I)
        if m_free:
            return "Free"

        # $ amount
        m_amt = re.search(
            rf"{label_regex}\s*:?\s*\$\s*([0-9,]+(?:\.[0-9]{{2}})?)",
            txt,
            re.I
        )
        return m_amt.group(1) if m_amt else ""

    # IMPORTANT:
    # - non-member is straightforward
    # - member must NOT match non-member price"
    non_member_price = pick_value(r"\bNon-?Member Price\b")
    member_price = pick_value(r"(?<!Non-)\bMember Price\b")  # key fix

    return member_price, non_member_price

# for extracting images
def normalize_image_url(src: str, base_url: str) -> str:
    """
    - Converts relative -> absolute
    - Removes common tracking params (optional)
    - Keeps essential params like ?c=... if the site uses it
    """
    if not src:
        return ""
    abs_url = urljoin(base_url, src)

    # Optional cleanup: drop utm_ params only
    parsed = urlparse(abs_url)
    q = parse_qsl(parsed.query, keep_blank_values=True)
    q = [(k, v) for (k, v) in q if not k.lower().startswith("utm_")]
    new_query = urlencode(q, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

# for extracting signup link
def extract_signup_link(soup) -> str:
    # common registration providers / shortlinks
    patterns = [
        r"forms\.office\.com",
        r"form\.gov\.sg",
        r"formsg",
        r"forms\.gle",
        r"docs\.google\.com/forms",
        r"go\.gov\.sg",
        r"bit\.ly",
    ]

    # 1) try to find any <a> that links to these
    for a in soup.select("a[href]"):
        href = a.get("href", "").strip()
        if not href:
            continue
        for p in patterns:
            if re.search(p, href, re.I):
                return href

    # 2) fallback: button area like "Join this event"
    btn = soup.select_one("div.link-btn a[href], a.btn[href]")
    if btn:
        return btn.get("href", "").strip()

    return ""

# for extracting location
def extract_location(soup) -> str:
    # Try: label style "Location : ..."
    txt = soup.get_text("\n", strip=True)
    m = re.search(r"Location\s*:\s*(.+)", txt, re.I)
    if not m:
        return ""
    # take only the line after Location:
    location = m.group(1).strip()
    # stop at next line break if it accidentally captured too much
    location = location.split("\n")[0].strip()
    return location

# for extracting status
def extract_status(soup) -> str:
    main = soup.select_one(".main-container") or soup
    txt = main.get_text(" ", strip=True).lower()

    if "closed" in txt:
        return "Closed"
    if "open for registration" in txt or "join this event" in txt or "click here to register" in txt:
        return "Open"
    return "Unknown"

# for inferring provider from signup link
def infer_provider(signup_link: str) -> str:
    if not signup_link:
        return ""
    s = signup_link.lower()
    if "forms.office.com" in s:
        return "Microsoft Forms"
    if "forms.gle" in s or "docs.google.com/forms" in s:
        return "Google Forms"
    if "form.gov.sg" in s:
        return "FormSG"
    if "sccci.org.sg/user/event/registerevent" in s:
        return "SCCCI Registration"
    return "Other"

# scrape images function
def extract_images(soup: BeautifulSoup, event_url: str) -> dict:
    """
    Returns nested dict:
    {
      "count": int,
      "items": [{"url": "...", "alt": "...", "source": "main|content|any"}]
    }
    """
    images = []
    seen = set()

    # Focus areas first (more likely relevant)
    areas = [
        ("main", soup.select_one(".main-container") or soup),
        ("content", soup.select_one(".event-detail, .event-content, .event-description") or soup),
    ]

    def add_img(src: str, alt: str, source: str):
        u = normalize_image_url(src, event_url)
        if not u:
            return
        if u in seen:
            return
        seen.add(u)
        images.append({
            "url": u,
            "alt": (alt or "").strip(),
            "source": source,
        })

    # 1) normal <img src="...">
    for source, area in areas:
        for img in area.select("img"):
            src = (img.get("src") or "").strip()
            alt = (img.get("alt") or "").strip()
            if not src:
                continue
            add_img(src, alt, source)

    # 2) sometimes background-image in style=""
    bg_imgs = soup.select('[style*="background-image"]')
    for node in bg_imgs:
        style = node.get("style", "")
        m = re.search(r'background-image\s*:\s*url\(["\']?(.*?)["\']?\)', style, re.I)
        if m:
            add_img(m.group(1).strip(), "", "bg-style")

    return {"count": len(images), "items": images}

# scrape event detail page function
def scrape_event_detail(page, event_url: str) -> dict:
    page.goto(event_url, timeout=60000)
    page.wait_for_load_state("networkidle")

    soup = BeautifulSoup(page.content(), "lxml")

    # Title
    title = ""
    h1 = soup.select_one("div.pageTitle h1, h1")
    if h1:
        title = h1.get_text(strip=True)

    # date + time
    date_range = ""
    time_range = ""
    for row in soup.select("div.event-info-box div.event-info-row"):
        icon = row.select_one("i")
        txt = row.get_text(" ", strip=True)
        if not icon:
            continue
        classes = " ".join(icon.get("class", []))
        if "fa-calendar-alt" in classes:
            date_range = txt.replace("(add to calendar)", "").strip()
        elif "fa-clock" in classes:
            time_range = txt.strip()

    # prices
    member_price, non_member_price = extract_prices(soup)

    # description preview
    desc = ""
    body = soup.select_one(".event-detail, .event-content, .event-description, .main-container")
    if body:
        desc = body.get_text(" ", strip=True)
        desc = re.sub(r"\s+", " ", desc).strip()
        desc = desc[:800]

    # signup link + cleanup
    signup_link = extract_signup_link(soup)
    if signup_link == "#":
        signup_link = ""

    # location + status
    location = extract_location(soup)
    status = extract_status(soup)

    # images
    images = extract_images(soup, event_url)

    return {
        "event_id": make_id(event_url),
        "source": {
            "list_url": LIST_URL,
            "event_url": event_url,
            "scraped_at": datetime.now(SGT).isoformat(),
        },
        "event": {
            "title": title,
            "datetime": {
                "date_range": date_range,
                "time_range": time_range,
            },
            "location": location,
            "pricing": {
                "member": member_price,
                "non_member": non_member_price,
            },
            "status": status,
        },
        "registration": {
            "signup_link": signup_link,
            "provider": infer_provider(signup_link),
        },
        "media": {
            "images": images
        },
        "description_preview": desc,  # keep if you still want it for AI drafting
    }
    

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1) Load listing page
        page.goto(LIST_URL, timeout=60000)
        page.wait_for_load_state("networkidle")

        html = page.content()
        soup = BeautifulSoup(html, "lxml")

        # 2) Extract ONLY event detail links
        event_urls = []
        seen = set()

        for a in soup.select('a[href*="/event/detail?slug="]'):
            href = a.get("href", "").strip()
            if not href:
                continue
            url = normalize_url(href)
            if url in seen:
                continue
            seen.add(url)
            event_urls.append(url)

        # 3) Visit each detail page and scrape info
        events = []
        for url in event_urls:
            try:
                events.append(scrape_event_detail(page, url))
            except Exception as e:
                events.append({
                    "event_id": make_id(url),
                    "event_url": url,
                    "error": str(e),
                    "scraped_at": datetime.now(SGT).isoformat(),
                })

        browser.close()

    # Save
    OUT.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Task 1] Events scraped: {len(events)}")
    print(f"Saved: {OUT.resolve()}")


if __name__ == "__main__":
    main()