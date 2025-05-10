import os
import logging
import time
import requests
from dotenv import load_dotenv
from utils.logging_config import setup_logging

setup_logging()
logger = logging.getLogger()
load_dotenv()

BASE_URL = "https://api.cloudflare.com/client/v4/zones/"
CLOUDFLARE_ZONEID = os.getenv("CLOUDFLARE_ZONEID")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_DOMAIN_LIST = [d.strip() for d in os.getenv("CLOUDFLARE_DOMAIN_LIST", "").split(',') if d.strip()]

if not CLOUDFLARE_ZONEID or not CLOUDFLARE_API_TOKEN or not CLOUDFLARE_DOMAIN_LIST:
    logger.critical("Missing required environment variables. Check .env file.")
    exit(1)



def get_public_ip():
    try:
        logger.debug('Fetching public IP')
        result = requests.get("https://api.ipify.org?format=json")
        result.raise_for_status()
        return result.json()['ip']
    except Exception as e:
        logger.error(f'Failed to fetch public IP: {e}')


def save_ip(ip):
    with open("saved_ip.txt", "w") as f:
        f.write(ip)


def get_saved_ip():
    if os.path.exists("saved_ip.txt"):
        with open("saved_ip.txt", "r") as f:
            return f.read().strip()
    return None


def get_cloudflare_record_id(domain_name):
    url = f"{BASE_URL}{CLOUDFLARE_ZONEID}/dns_records"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        records = response.json().get("result", [])
        for record in records:
            if record["name"] == domain_name:
                return record["id"]
        raise ValueError(f"DNS record with name '{domain_name}' not found.")
    except requests.RequestException as e:
        logger.error(f"Failed to fetch DNS records: {e}")


def update_cloudflare_domain(new_ip, record_id, domain_name):
    url = f"{BASE_URL}{CLOUDFLARE_ZONEID}/dns_records/{record_id}"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "type": "A",
        "name": domain_name,
        "content": new_ip,
        "ttl": 1,
        "proxied": False,
    }
    try:
        response = requests.put(url, json=data, headers=headers)
        response.raise_for_status()
        logger.info(f"Updated '{domain_name}' to {new_ip}.")
    except requests.RequestException as e:
        logger.error(f"Error updating DNS record for {domain_name}: {e}")


if __name__ == "__main__":
    while True:
        try:
            current_ip = get_public_ip()
            if current_ip != get_saved_ip():
                logger.info(f"New IP detected: {current_ip}")
                for domain_name in CLOUDFLARE_DOMAIN_LIST:
                    record_id = get_cloudflare_record_id(domain_name)
                    update_cloudflare_domain(current_ip, record_id, domain_name)
                save_ip(current_ip)
            else:
                logger.debug("IP has not changed. No update needed.")
        except Exception as e:
            logger.error(f"Unhandled error: {e}")
        time.sleep(60 * 10)
