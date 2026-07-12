"""Background worker. Run alongside the API: python -m app.worker
Polls the Postgres job queue every 30s and paces cold outreach in small
batches through the day instead of a morning blast (deliverability-friendly)."""
import time
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo
from . import config, db, orchestrator

OUTREACH_EVERY_MIN = 20      # a small batch at most every 20 minutes
BATCH_SIZE = 3


def loop():
    last_batch = 0.0
    print("worker up")
    while True:
        try:
            db.set_setting("worker_heartbeat", datetime.now(ZoneInfo(config.TZ)).isoformat())
            if not db.is_paused():
                for job in db.due_jobs():
                    try:
                        orchestrator.run_job(job)
                        db.mark_job(job["id"], "done")
                    except Exception:
                        db.mark_job(job["id"], "failed")
                        traceback.print_exc()

                now = datetime.now(ZoneInfo(config.TZ))
                in_window = config.QUIET_HOURS[1] <= now.hour < config.QUIET_HOURS[0]
                if in_window and time.time() - last_batch > OUTREACH_EVERY_MIN * 60:
                    n = orchestrator.start_outreach_batch(BATCH_SIZE)
                    if n:
                        print(f"outreach batch: {n} dispatched")
                    last_batch = time.time()
        except Exception:
            traceback.print_exc()
        time.sleep(30)


if __name__ == "__main__":
    loop()
