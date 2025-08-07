import os
import re
import json
import requests
import logging
import subprocess
from pathlib import Path
from urllib.parse import urlparse
import re
import requests
import whois
from validate_email_address import validate_email
from typing import List
from postgres import POSTGRES
import uuid
import datetime
import logging
from playwright.async_api import async_playwright
from fuzzywuzzy import fuzz
from urllib.parse import urlparse
from send_mail import send_email


from postgres import POSTGRES

SERPER_API_KEY = os.getenv("SERPER_API_KEY")
SERPER_API_URL = os.getenv("SERPER_API_URL")

SHARED_DIR = os.getenv("SHARED_DIR", "/app/shared")

def search_google(query, page=1, max_results=100):
    headers = {"X-API-KEY": SERPER_API_KEY}
    payload = {"q": query, "page": page}
    response = requests.post(SERPER_API_URL, json=payload, headers=headers)
    # logging.info(response.text)
    results = response.json().get("organic", [])[:max_results]
    return [r["link"] for r in results if "link" in r]

def extract_domain(url):
    return urlparse(url).netloc.lower()

def include_filter(url, include, exclude):
    url_domain = extract_domain(url)
    if include and not any(extract_domain(term) == url_domain for term in include):
        return False
    if any(extract_domain(term) == url_domain for term in exclude):
        return False
    return True

def normalize(text):
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)
    return text.strip()

STANDARD_EMAIL_PREFIXES = [
    "contact", "info", "admin", "support", "legal",
    "webmaster", "help", "hello", "team"
]

def guess_standard_emails(domain: str):
    if domain.startswith("www."):
        domain = domain[4:]
    elif domain.startswith("m."):
        domain = domain[2:]
    elif domain.startswith("blog."):
        domain = domain[5:]
    return [f"{prefix}@{domain}" for prefix in STANDARD_EMAIL_PREFIXES]

def extract_emails_from_html(html: str):
    email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    mailto_pattern = r"mailto:([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)"
    
    emails = set(re.findall(email_pattern, html))
    emails.update(re.findall(mailto_pattern, html))
    
    return list(emails)


def is_smtp_valid(email: str) -> bool:
    try:
        return validate_email(email, verify=True)
    except Exception:
        return False

async def save_outreach_contacts(job_id: str, crawl_result_id: str, emails: List[str]):
    now = datetime.datetime.now(datetime.timezone.utc)

    query = """
        INSERT INTO outreach_contacts (
            id, job_id, crawl_result_id, email, status, created_at, updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
    """

    # Prepare batch inserts
    queries = [
        (
            query,
            [str(uuid.uuid4()), job_id, crawl_result_id, email, 'NOT_CONTACTED', now, now],
            False  # No return value expected
        )
        for email in emails
    ]

    await POSTGRES.execute_transaction_with_results(queries)

async def extract_possible_emails(page, url:str, content: str, job_id:str, crawl_result_id: str, test_email:str):
    parsed = urlparse(url)
    domain = parsed.netloc
    possible_emails = set()
    possible_emails.update(extract_emails_from_html(content))

    for suffix in ["/contact", "/about", "/privacy-policy", "/terms", "/legal",
    "/contact-us", "/support", "/help", "/team", "/reach-us", "/connect"]:
        sub_url = f"https://{domain}{suffix}"
        try:
            await page.goto(sub_url, timeout=10000)
            await page.wait_for_timeout(2000)
            sub_html = await page.content()
            possible_emails.update(extract_emails_from_html(sub_html))
        except Exception as e:
            logging.warning(f"Failed to fetch subpage {sub_url}: {e}")
            continue

    # 3. WHOIS fallback
    try:
        whois_info = whois.whois(domain)
        if isinstance(whois_info.emails, list):
            possible_emails.update(whois_info.emails)
        elif whois_info.emails:
            possible_emails.add(whois_info.emails)
    except Exception:
        pass

    # 4. Standard guesses
    possible_emails.update(guess_standard_emails(domain))

    # working_emails = [email for email in possible_emails if is_smtp_valid(email)]
    # if working_emails and len(working_emails) > 0:
    #     logging.info(f"Found {len(working_emails)} valid emails")
    # else:
    #     logging.info(f"No valid emails found")
    await save_outreach_contacts(
        job_id=job_id,
        crawl_result_id=crawl_result_id,
        # emails=working_emails
        emails=[test_email]
    )

async def scan_url_for_text(job_id, ip_text, url, test_email, threshold=85):
    normalized_ip = normalize(ip_text)
    match_data = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=15000)
            await page.wait_for_timeout(3000)
            content = await page.content()  # Full HTML content
            visible_text = await page.text_content("body") or ""
            normalized_content = normalize(visible_text)
            score = fuzz.partial_ratio(normalized_ip, normalized_content)

            if score >= threshold:
                logging.info(f"✅ Match found! URL: {url}, Score: {score}")
                timestamp = datetime.datetime.now(datetime.timezone.utc)
                base_name = f"screenshot_{timestamp.strftime("%Y%m%d_%H%M%S")}"

                image_path = os.path.join(SHARED_DIR, "images" f"{base_name}.png")
                ots_path = os.path.join(SHARED_DIR, "ots", f"{base_name}.ots")

                await page.screenshot(path=image_path, full_page=True)
                
                subprocess.run(["ots", "stamp", image_path])
                default_ots = image_path + ".ots"
                os.replace(default_ots, ots_path)
                
                snippet_start = normalized_content.find(normalized_ip[:10])
                snippet = normalized_content[snippet_start:snippet_start + 200]

                match_data = {
                    "url": url,
                    "match_score": score,
                    "matched_snippet": snippet,
                    "timestamp": timestamp,
                    "screenshot": image_path,
                    "ots_path": ots_path,
                    "status": "MATCHED"
                }

                crawl_result_id = await save_crawl_result(
                    job_id=job_id,
                    result=match_data
                )

                await extract_possible_emails(page, url, content, job_id, crawl_result_id, test_email)
                return True

        except Exception as e:
            logging.error(f"[CRAWL ERROR] {url} => {e}")
            error_data = {
                "url": url,
                "timestamp": datetime.datetime.now(datetime.timezone.utc),
                "status": "ERROR",
                "match_score": None,
                "matched_snippet": None,
                "screenshot": None,
                "ots_path": None
            }
            await save_crawl_result(job_id, error_data)
        return False

async def save_crawl_result(job_id, result):
    query = """
        INSERT INTO crawl_results (
            job_id, url, matched_snippet, match_score,
            screenshot_path, ots_path, timestamp, status
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
    """
    args = [
        job_id,
        result["url"],
        result.get("matched_snippet"),
        result.get("match_score"),
        result.get("screenshot"),
        result.get("ots_path"),
        result["timestamp"],
        result["status"]
    ]

    # Wrap the single insert query in a list
    results = await POSTGRES.execute_transaction_with_results([
        (query, args, True)
    ])
    
    return results[0]['id'] 

async def crawler(job_id, event_id):
    logger = logging.getLogger("crawler")
    logger.info(f"[CRAWLER] Starting crawl for job_id={job_id}")

    # 1. Mark job as 'CRAWLING'
    await POSTGRES.execute("""
            UPDATE jobs SET status = 'CRAWLING', updated_at = now() WHERE id = $1
        """, [job_id])
    
    # fetch test email from test email map table
    test_email_record = await POSTGRES.fetch_one("""
        SELECT test_email FROM test_email_map WHERE job_id = $1
    """, [job_id])
    test_email = test_email_record["test_email"] if test_email_record else None
    # 2. Get job details
    job = await POSTGRES.fetch_one("SELECT input_text, filters FROM jobs WHERE id = $1", [job_id])
    input_text = job["input_text"]
    filters = json.loads(job["filters"]) if job["filters"] else {}
    include = filters.get("include_domains", [])
    exclude = filters.get("exclude_domains", [])

    # 3. Crawl loop
    page_num = 1
    found_match = False
    batch_match_found = False
    while True:
        if page_num > 1:
            await POSTGRES.execute(
                    """
                    UPDATE crawl_events SET progress_updated_at = now() 
                    WHERE id = $1
                    """, [event_id]
            )
            
        logging.info(f"[CRAWLER] Crawling page {page_num} for job_id={job_id}")
        urls = search_google(input_text, page=page_num)  # 100 URLs max
        if not urls:
            break
        # Break into 10-url batches
        batches = [urls[i:i + 10] for i in range(0, len(urls), 10)]
        for i, batch in enumerate(batches):
            filtered_urls_in_batch = [url for url in batch if include_filter(url, include, exclude)]
            for url in filtered_urls_in_batch:
                match_found = await scan_url_for_text(job_id, input_text, url, test_email)
                if match_found:
                    found_match = True
                    batch_match_found = True
            if not batch_match_found:
                logger.info(f"[CRAWLER] No matches found in batch {i + 1} for job_id={job_id}")
                logger.info("Stopping further crawling")
                break
        if batch_match_found:
            page_num += 1
            batch_match_found = False  # Reset for next batch
        else:
            logger.info(f"[CRAWLER] No matches found in page {page_num} for job_id={job_id}")
            break
    if not found_match:
        logger.info(f"[CRAWLER] No matches found for job_id={job_id} after crawling {page_num} pages.")
        if test_email:
            logger.info(f"[CRAWLER] Sending 'no match found' email to {test_email}")
            
            subject = "No IP Infringements Found"
            body = f"""
            Hello,

            We completed the crawl for the search input:

            "{input_text}"

            After scanning multiple sources, we did not find any suspected cases of IP infringement.

            Thank you,
            Third Chair
            """
            try:
                await send_email(to_email=test_email, subject=subject, body=body.strip())
                logger.info(f"[CRAWLER] ✅ Sent 'no infringement' email to {test_email}")
            except Exception as e:
                logger.exception(f"[CRAWLER] ❌ Failed to send email to {test_email}: {e}")
        return 
    return