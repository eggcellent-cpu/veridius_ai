import json
import time
from pathlib import Path
import win32com.client as win32
import pythoncom  
# import schedule  # ← uncomment when using scheduler

# Files
DRAFTS_FILE = "out/drafts.json"
SENT_FILE = "out/sent_emails.json"

# Recipients for testing / production
TEST_RECIPIENTS = [
    "234342t@mymail.nyp.edu.sg",
    # "someone_else@example.com",
    # "another_person@example.com",
]



def send_emails():
    pythoncom.CoInitialize()
    try:
        drafts_path = Path(DRAFTS_FILE)
        if not drafts_path.exists():
            print(f"No drafts found at {DRAFTS_FILE}")
            return

        drafts_json = json.loads(drafts_path.read_text(encoding="utf-8"))
        items = drafts_json.get("items", [])

        if not items:
            print("No email items found in drafts.")
            return

        sent_path = Path(SENT_FILE)
        sent_ids = json.loads(sent_path.read_text()) if sent_path.exists() else []

        outlook = win32.Dispatch("Outlook.Application")

        sent_count = 0

        for item in items:
            event_id = item.get("event_id")
            if event_id in sent_ids:
                continue

            html_path = Path(item.get("email_preview_path", ""))
            if not html_path.exists():
                print(f"HTML file not found: {html_path}")
                continue

            html_content = html_path.read_text(encoding="utf-8")

            mail = outlook.CreateItem(0)  # olMailItem
            mail.Subject = item["draft"].get("subject", "No Subject")
            mail.HTMLBody = html_content
            mail.To = "; ".join(TEST_RECIPIENTS)

            # Store values BEFORE sending
            subject = mail.Subject
            recipient = ", ".join(TEST_RECIPIENTS)

            try:
                mail.Send()
                print(f"✅ Sent: {subject} → {recipient}")
                sent_ids.append(event_id)
                sent_count += 1
            except Exception as e:
                print(f"⚠ Send error (likely false): {subject} | {e}")


            mail = None
            time.sleep(10)  

        sent_path.write_text(json.dumps(sent_ids, indent=2))
        print(f"\n📨 Done. {sent_count} email(s) sent.")

    finally:
        pythoncom.CoUninitialize()



# EXECUTION OPTIONS


# 🔹 TESTING (manual run)
send_emails()


# 🔹 PRODUCTION (biweekly scheduler)
# Uncomment everything below when deploying
#
# import schedule
#
# schedule.every(2).weeks.do(send_emails)
# print("📅 Scheduler started (every 2 weeks). Press Ctrl+C to stop.")
#
# while True:
#     schedule.run_pending()
#     time.sleep(60)
