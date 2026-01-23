import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

DATA_DIR = Path("data")
CURRENT = DATA_DIR / "events_current.json"
PREVIOUS = DATA_DIR / "events_previous.json"
DELTA = DATA_DIR / "events_delta.json"

SGT = timezone(timedelta(hours=8))


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def index_by_event_id(events: list[dict]) -> dict[str, dict]:
    out = {}
    for e in events:
        eid = e.get("event_id")
        if eid:
            out[eid] = e
    return out


def fingerprint(e: dict) -> dict:
    """
    Keep only fields that matter for emailing.
    If any of these change, we treat it as an update.
    """
    event = e.get("event", {})
    dt = event.get("datetime", {})
    pricing = event.get("pricing", {})
    reg = e.get("registration", {})
    media = e.get("media", {})
    images = (media.get("images") or {}).get("items", [])
    image_urls = [img.get("url", "") for img in images if img.get("url")]

    return {
        "title": event.get("title", ""),
        "date_range": dt.get("date_range", ""),
        "time_range": dt.get("time_range", ""),
        "location": event.get("location", ""),
        "member_price": pricing.get("member", ""),
        "non_member_price": pricing.get("non_member", ""),
        "status": event.get("status", ""),
        "signup_link": reg.get("signup_link", ""),
        "provider": reg.get("provider", ""),
        "image_urls": sorted(set(image_urls)),
    }


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    current_list = load_json(CURRENT, [])
    prev_list = load_json(PREVIOUS, [])

    current = index_by_event_id(current_list)
    prev = index_by_event_id(prev_list)

    delta = []
    summary = {
        "run_at": datetime.now(SGT).isoformat(),
        "current_count": len(current),
        "previous_count": len(prev),
        "new": 0,
        "updated": 0,
        "skipped_closed": 0,
    }

    for eid, cur_event in current.items():
        cur_fp = fingerprint(cur_event)

        # Skip Closed/Unknown
        if cur_fp.get("status") != "Open":
            summary["skipped_closed"] += 1
            continue

        if eid not in prev:
            delta.append({
                "change_type": "NEW",
                "event_id": eid,
                "event": cur_event,
            })
            summary["new"] += 1
            continue

        prev_fp = fingerprint(prev[eid])

        if cur_fp != prev_fp:
            delta.append({
                "change_type": "UPDATED",
                "event_id": eid,
                "before": prev_fp,
                "after": cur_fp,
                "event": cur_event,
            })
            summary["updated"] += 1

    output = {
        "summary": summary,
        "items": delta
    }

    DELTA.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    # After detecting delta, update previous snapshot for next run
    PREVIOUS.write_text(json.dumps(current_list, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[Task 2] Delta written:", DELTA.resolve())
    print("[Task 2] Previous snapshot updated:", PREVIOUS.resolve())
    print("Summary:", summary)


if __name__ == "__main__":
    main()