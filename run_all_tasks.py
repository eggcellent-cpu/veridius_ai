import subprocess
import sys

TASKS = [
    ("Task 1: Scrape SCCCI events", "source/task1_scrape_data.py"),
    ("Task 2: Detect delta changes", "source/task2_detect_new_data.py"),
    # Add later:
    ("Task 3: Draft emails", "source/task3_draft_emails.py"),
    ("Task 4: Send/Export drafts", "source/task4_send_or_export.py"),
]

def render_bar(done: int, total: int, width: int = 30) -> str:
    ratio = done / total
    filled = int(ratio * width)
    bar = "█" * filled + "░" * (width - filled)
    pct = ratio * 100
    return f"[{bar}] {pct:5.1f}% ({done}/{total})"

def run_task(name: str, script_path: str):
    print(f"\n▶ {name}")
    subprocess.check_call([sys.executable, script_path])

def main():
    total = len(TASKS)
    done = 0

    print("Progress:", render_bar(done, total))

    for name, script in TASKS:
        run_task(name, script)
        done += 1
        print("Progress:", render_bar(done, total))

    print("\n✅ All tasks completed.")

if __name__ == "__main__":
    main()
