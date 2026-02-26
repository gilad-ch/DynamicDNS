import os
import logging
import signal
import time
import requests
from dotenv import load_dotenv
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    retry_if_exception_type,
)
from utils.logging_config import setup_logging

setup_logging()
logger = logging.getLogger()
load_dotenv()

BASE_URL = "https://api.cloudflare.com/client/v4/zones/"
REQUEST_TIMEOUT = 15
IP_SOURCES = [
    "https://api.ipify.org?format=json",
    "https://api64.ipify.org?format=json",
    "https://ifconfig.me/ip",
]

CLOUDFLARE_ZONEID = os.getenv("CLOUDFLARE_ZONEID")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_DOMAIN_LIST = [
    d.strip() for d in os.getenv("CLOUDFLARE_DOMAIN_LIST", "").split(",") if d.strip()
]
UPDATE_INTERVAL_MINUTES = int(os.getenv("UPDATE_INTERVAL_MINUTES", "10"))
FAILURE_BACKOFF_MAX_MINUTES = int(os.getenv("FAILURE_BACKOFF_MAX_MINUTES", "30"))
FAILURE_COUNT_BEFORE_BACKOFF = int(os.getenv("FAILURE_COUNT_BEFORE_BACKOFF", "5"))

if not CLOUDFLARE_ZONEID or not CLOUDFLARE_API_TOKEN or not CLOUDFLARE_DOMAIN_LIST:
    logger.critical("Missing required environment variables. Check .env file.")
    exit(1)

_shutdown_requested = False


def _shutdown_handler(signum=None, frame=None):
    global _shutdown_requested
    _shutdown_requested = True


signal.signal(signal.SIGTERM, _shutdown_handler)


def _parse_ip_from_response(response, url):
    if "ifconfig.me" in url:
        ip = response.text.strip()
    else:
        data = response.json()
        ip = data.get("ip") if isinstance(data, dict) else None
    if not ip or not ip.replace(".", "").isdigit():
        raise ValueError(f"Invalid IP from {url}: {ip}")
    return ip


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=8),
    retry=retry_if_exception_type((requests.RequestException, ValueError)),
    reraise=True,
)
def get_public_ip() -> str:
    last_error = None
    for url in IP_SOURCES:
        try:
            logger.debug("Fetching public IP from %s", url)
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            ip = _parse_ip_from_response(response, url)
            return ip
        except (requests.RequestException, ValueError) as e:
            last_error = e
            logger.warning("IP source %s failed: %s", url, e)
            continue
    raise last_error


def save_ip(ip: str) -> None:
    tmp_path = "saved_ip.txt.tmp"
    target_path = "saved_ip.txt"
    with open(tmp_path, "w") as f:
        f.write(ip)
    os.replace(tmp_path, target_path)


def get_saved_ip() -> str | None:
    if os.path.exists("saved_ip.txt"):
        with open("saved_ip.txt", "r") as f:
            return f.read().strip()
    return None


def _api_headers():
    return {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json",
    }


def _retry_on_5xx_or_timeout(exc):
    if isinstance(exc, requests.HTTPError):
        resp = getattr(exc, "response", None)
        if resp is not None and 400 <= resp.status_code < 500:
            return False
    return isinstance(exc, requests.RequestException)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=8),
    retry=retry_if_exception(_retry_on_5xx_or_timeout),
    reraise=True,
)
def get_cloudflare_record_id(domain_name: str) -> str:
    url = f"{BASE_URL}{CLOUDFLARE_ZONEID}/dns_records"
    response = requests.get(url, headers=_api_headers(), timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    records = response.json().get("result", [])
    for record in records:
        if record["name"] == domain_name:
            return record["id"]
    raise ValueError(f"DNS record with name '{domain_name}' not found.")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=8),
    retry=retry_if_exception(_retry_on_5xx_or_timeout),
    reraise=True,
)
def update_cloudflare_domain(new_ip: str, record_id: str, domain_name: str) -> None:
    url = f"{BASE_URL}{CLOUDFLARE_ZONEID}/dns_records/{record_id}"
    data = {
        "type": "A",
        "name": domain_name,
        "content": new_ip,
        "ttl": 1,
        "proxied": False,
    }
    response = requests.put(
        url, json=data, headers=_api_headers(), timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()
    logger.info("Updated '%s' to %s.", domain_name, new_ip)


def validate_startup() -> None:
    url = f"{BASE_URL}{CLOUDFLARE_ZONEID}"
    response = requests.get(url, headers=_api_headers(), timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    if not response.json().get("success"):
        raise RuntimeError("Cloudflare API returned success=false")
    for domain in CLOUDFLARE_DOMAIN_LIST:
        get_cloudflare_record_id(domain)
    logger.info("Startup validation passed.")


if __name__ == "__main__":
    try:
        validate_startup()
    except Exception as e:
        logger.critical("Startup validation failed: %s", e)
        exit(1)

    failure_count = 0

    while not _shutdown_requested:
        try:
            current_ip = get_public_ip()
            if current_ip != get_saved_ip():
                logger.info("New IP detected: %s", current_ip)
                record_ids = {}
                for domain_name in CLOUDFLARE_DOMAIN_LIST:
                    record_ids[domain_name] = get_cloudflare_record_id(domain_name)
                for domain_name in CLOUDFLARE_DOMAIN_LIST:
                    update_cloudflare_domain(
                        current_ip, record_ids[domain_name], domain_name
                    )
                save_ip(current_ip)
                failure_count = 0
            else:
                logger.debug("IP has not changed. No update needed.")
                failure_count = 0
        except KeyboardInterrupt:
            logger.info("Shutdown requested.")
            break
        except Exception as e:
            failure_count += 1
            logger.error("Unhandled error: %s", e)
            sleep_minutes = (
                UPDATE_INTERVAL_MINUTES
                if failure_count < FAILURE_COUNT_BEFORE_BACKOFF
                else min(
                    UPDATE_INTERVAL_MINUTES
                    * (
                        2
                        ** min(
                            max(0, failure_count - FAILURE_COUNT_BEFORE_BACKOFF), 3
                        )
                    ),
                    FAILURE_BACKOFF_MAX_MINUTES,
                )
            )
            if failure_count >= FAILURE_COUNT_BEFORE_BACKOFF:
                logger.warning(
                    "Failure %d; backing off to %d min sleep.",
                    failure_count,
                    sleep_minutes,
                )
            time.sleep(60 * sleep_minutes)
            continue

        for _ in range(60 * UPDATE_INTERVAL_MINUTES):
            if _shutdown_requested:
                break
            time.sleep(1)
