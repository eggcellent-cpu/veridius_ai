import os
import json
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

DATA_DIR = Path("data")
OUT_DIR = Path("out")
EMAIL_DIR = OUT_DIR / "emails"

DELTA = DATA_DIR / "events_delta.json"
DRAFTS_JSON = OUT_DIR / "drafts.json"

SGT = timezone(timedelta(hours=8))

# Optional preference list (we'll auto-pick the first available that supports generateContent)
PREFERRED_MODELS = ("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro")


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def clean_money(v: str) -> str:
    if not v:
        return ""
    if isinstance(v, str) and v.lower() == "free":
        return "Free"
    return v


def safe_text(s: str, limit: int = 800) -> str:
    if not s:
        return ""
    s = re.sub(r"\s+", " ", str(s)).strip()
    return s[:limit]


def build_prompt(event: dict) -> str:
    e = event.get("event", {})
    dt = e.get("datetime", {})
    pricing = e.get("pricing", {})
    reg = event.get("registration", {})

    title = e.get("title", "")
    date_range = dt.get("date_range", "")
    time_range = dt.get("time_range", "")
    location = e.get("location", "")
    member_price = clean_money(pricing.get("member", ""))
    non_member_price = clean_money(pricing.get("non_member", ""))
    signup_link = reg.get("signup_link", "")
    desc = safe_text(event.get("description_preview", ""), 500)

    return f"""
You are drafting a targeted marketing email + WhatsApp invite for SCCCI events.
Audience: trade association secretariats (busy, professional tone).
Write concise and clear. No emojis.

EVENT INFO
Title: {title}
Date: {date_range}
Time: {time_range}
Venue: {location}
Member Price: {member_price}
Non-member Price: {non_member_price}
Registration Link: {signup_link}
Extra context (may be noisy): {desc}

Return STRICT JSON only (no markdown, no backticks), with keys:
- subject: string (<= 80 chars)
- email_blurb: string (2-3 sentences, include CTA)
- whatsapp_text: string (<= 250 chars, include link)
""".strip()


def parse_json_response(text: str) -> dict:
    """
    Gemini sometimes returns extra text. We'll extract the first JSON object.
    """
    text = (text or "").strip()

    # Try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # Extract first {...} block
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"Gemini response did not contain JSON. Raw: {text[:200]}...")
    return json.loads(m.group(0))


def render_email_html(draft: dict, event: dict) -> str:
    e = event.get("event", {})
    dt = e.get("datetime", {})
    pricing = e.get("pricing", {})
    reg = event.get("registration", {})

    title = e.get("title", "")
    date_range = dt.get("date_range", "")
    time_range = dt.get("time_range", "")
    location = e.get("location", "")
    member_price = pricing.get("member", "")
    non_member_price = pricing.get("non_member", "")
    signup_link = reg.get("signup_link", "")

    media = event.get("media", {})
    images = (media.get("images") or {}).get("items", [])
    hero_img = images[0].get("url") if images else ""

    subject = (draft.get("subject") or "").strip()
    blurb = (draft.get("email_blurb") or "").strip()

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>{subject}</title>
</head>
<body style="margin:0;padding:0;background:#f6f7fb;font-family:Arial,sans-serif;">
  <div style="max-width:680px;margin:0 auto;padding:24px;">
    <div style="background:#ffffff;border-radius:14px;padding:22px;box-shadow:0 2px 10px rgba(0,0,0,.06);">
      <div style="font-size:13px;color:#666;margin-bottom:10px;">
        SCCCI Event Notice (Auto-drafted for approval)
      </div>

    {f'<img src="{hero_img}" alt="" style="width:100%;border-radius:12px;margin:12px 0;object-fit:cover;" />' if hero_img else ''}

      <h1 style="margin:0 0 10px 0;font-size:22px;line-height:1.25;color:#111;">
        {title}
      </h1>

      <div style="font-size:14px;color:#333;line-height:1.55;margin-bottom:14px;">
        {blurb}
      </div>

      <div style="border:1px solid #eee;border-radius:12px;padding:14px;margin:16px 0;">
        <div style="display:flex;gap:14px;flex-wrap:wrap;font-size:14px;color:#222;line-height:1.5;">
          <div><b>Date:</b> {date_range}</div>
          <div><b>Time:</b> {time_range}</div>
          <div><b>Venue:</b> {location or "TBC"}</div>
          <div><b>Member:</b> {member_price or "TBC"}</div>
          <div><b>Non-member:</b> {non_member_price or "TBC"}</div>
        </div>
      </div>

      <div style="margin:18px 0;">
        <a href="{signup_link}" style="display:inline-block;background:#111;color:#fff;text-decoration:none;padding:12px 16px;border-radius:10px;font-size:14px;">
          Register / Find out more
        </a>
      </div>

      <div style="font-size:12px;color:#777;line-height:1.45;margin-top:18px;">
        If this is not relevant to your association, please disregard. This message is generated automatically based on the SCCCI events page.
      </div>
    </div>

    <div style="text-align:center;font-size:12px;color:#999;margin-top:14px;">
      Generated on {datetime.now(SGT).strftime("%Y-%m-%d %H:%M")} (SGT)
    </div>
  </div>
</body>
</html>
"""


def pick_model_name(prefer=PREFERRED_MODELS) -> str:
    """
    Auto-select a model that supports generateContent for your API key.
    Fixes 'model not found' errors when a model name changes.
    """
    models = list(genai.list_models())

    supported = []
    for m in models:
        methods = getattr(m, "supported_generation_methods", []) or []
        if "generateContent" in methods:
            supported.append(m.name.replace("models/", ""))

    for name in prefer:
        if name in supported:
            return name

    if supported:
        return supported[0]

    raise RuntimeError("No Gemini models available that support generateContent for this API key.")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    EMAIL_DIR.mkdir(parents=True, exist_ok=True)

    delta = load_json(DELTA, {})
    items = delta.get("items", [])

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("[Task 3] GEMINI_API_KEY not set. Skipping GenAI drafting.")
        # still write an empty drafts.json so frontend works
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        EMAIL_DIR.mkdir(parents=True, exist_ok=True)
        DRAFTS_JSON.write_text(json.dumps({
            "summary": {"run_at": datetime.now(SGT).isoformat(), "input_items": 0, "drafted": 0, "errors": 0},
            "items": []
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return

    genai.configure(api_key=api_key)

    # ✅ auto-pick a valid model (prevents 404 model errors)
    model_name = pick_model_name()
    print("[Task 3] Using model:", model_name)
    model = genai.GenerativeModel(model_name)

    drafts_out = []
    run_at = datetime.now(SGT).isoformat()

    for item in items:
        change_type = item.get("change_type", "")
        event_id = item.get("event_id", "")
        event = item.get("event", {})

        status = (((event.get("event") or {}).get("status")) or "").strip()
        signup_link = (((event.get("registration") or {}).get("signup_link")) or "").strip()

        # rules: only NEW/UPDATED + Open + has signup link
        if change_type not in ("NEW", "UPDATED"):
            continue
        if status != "Open":
            continue
        if not signup_link:
            continue

        prompt = build_prompt(event)

        try:
            resp = model.generate_content(prompt)
            draft = parse_json_response(getattr(resp, "text", ""))

            draft = {
                "subject": (draft.get("subject") or "").strip(),
                "email_blurb": (draft.get("email_blurb") or "").strip(),
                "whatsapp_text": (draft.get("whatsapp_text") or "").strip(),
            }

            # Save email HTML preview
            html = render_email_html(draft, event)
            preview_path = EMAIL_DIR / f"{event_id}.html"
            preview_path.write_text(html, encoding="utf-8")

            drafts_out.append({
                "event_id": event_id,
                "change_type": change_type,
                "generated_at": run_at,
                "draft": draft,
                "event": event,
                "email_preview_path": str(preview_path),
            })

            print(f"[Task 3] Drafted: {event_id} ({draft['subject'][:45]}...)")

        except Exception as e:
            drafts_out.append({
                "event_id": event_id,
                "change_type": change_type,
                "generated_at": run_at,
                "error": str(e),
                "event": event,
            })
            print(f"[Task 3] ERROR {event_id}: {e}")

    output = {
        "summary": {
            "run_at": run_at,
            "input_items": len(items),
            "drafted": sum(1 for d in drafts_out if "draft" in d),
            "errors": sum(1 for d in drafts_out if "error" in d),
        },
        "items": drafts_out,
    }

    DRAFTS_JSON.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[Task 3] Saved:", DRAFTS_JSON.resolve())
    print("[Task 3] Email previews:", EMAIL_DIR.resolve())


if __name__ == "__main__":
    main()