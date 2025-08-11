import os

import asyncio
import logging
from utils.postgres import POSTGRES
from utils.crawler import crawler_fun  

CRAWL_TIMEOUT_MINUTES = int(os.getenv("CRAWLER_TIMEOUT_MINUTES", 5))

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )


async def fetch_crawl_ready_job():
    query = """
      SELECT * FROM crawl_events 
      WHERE (
          is_processing = FALSE 
          OR (is_processing = TRUE AND progress_updated_at < now() - INTERVAL '1 minute' * $1)
      )
      ORDER BY created_at ASC
      LIMIT 1
    """
    return await POSTGRES.fetch_one(query, (CRAWL_TIMEOUT_MINUTES, ))

async def mark_event_in_progress(event_id):
    query = """
    UPDATE crawl_events 
    SET is_processing = TRUE, progress_updated_at = now()
    WHERE id = $1
    """
    await POSTGRES.execute(query, [event_id])

async def delete_event(event_id):
    query = "DELETE FROM crawl_events WHERE id = $1"
    await POSTGRES.execute(query, [event_id])

async def start_crawl_worker():
    while True:
        try:
            logging.info("[CRAWLER] Checking for crawl-ready jobs...")
            job_event = await fetch_crawl_ready_job()
            if job_event:
                logging.info(f"[CRAWLER] Found job_event: {job_event['id']} for job_id={job_event['job_id']}")
                event_id = job_event["id"]
                job_id = job_event["job_id"]

                await mark_event_in_progress(event_id)

                logging.info(f"[CRAWLER] Processing job_id={job_id}")
                await crawler_fun(job_id, event_id)
                logging.info(f"[CRAWLER] Completed job_id={job_id}")
                await delete_event(event_id)
                logging.info(f"[CRAWLER] Deleted job_event with id={event_id}")
            else:
                await asyncio.sleep(30)  # Sleep before next check
        except Exception as e:
            logging.exception(f"[CRAWLER] Unexpected error: {e}")
            query = """
            UPDATE crawl_events 
            SET is_processing = FALSE, progress_updated_at = now()
            WHERE id = $1
            """
            await POSTGRES.execute(query, [event_id])

async def main():
    await POSTGRES.init()

    try:
        await start_crawl_worker()
    except asyncio.CancelledError:
        logging.info("[CRAWLER] Cancellation received, shutting down gracefully...")
    except Exception as e:
        logging.exception(f"[CRAWLER] Unexpected error: {e}")
    finally:
        logging.info("[CRAWLER] Closing PostgreSQL pool...")
        try:
            await POSTGRES.close()
        except Exception as e:
            logging.exception("[CRAWLER] Error during closing DB pool")

if __name__ == "__main__":
    setup_logging()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("[CRAWLER] KeyboardInterrupt received. Exiting.")
