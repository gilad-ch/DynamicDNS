import os
import logging
import time
import requests
from utils.logging_config import setup_logging
from utils.config import cloudflare_config

setup_logging()
logger = logging.getLogger()

BASE_URL = "https://api.cloudflare.com/client/v4/zones/"


def get_public_ip():
    try:
        logger.debug(f'Fetching public ip')
        result = requests.request(
            method="GET", url="https://api.ipify.org?format=json")
        result.raise_for_status()
        return result.json()['ip']
    except Exception as e:
        logger.error(f'Failed to fetch public ip from api.ipify.org: {e}')
        raise


def save_ip(ip):
    with open("saved_ip.txt", "w") as f:
        f.write(ip)


def get_saved_ip():
    if os.path.exists("saved_ip.txt"):
        with open("saved_ip.txt", "r") as f:
            return f.read()
    else:
        return None


def get_cloudflare_record_id():
    """Retrieve the DNS record ID dynamically based on the record name."""
    url = f"{BASE_URL}{
        cloudflare_config.ZONE_ID}/dns_records"
    headers = {
        "Authorization": f"Bearer {cloudflare_config.CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        records = response.json().get("result", [])
        for record in records:
            if record["name"] == cloudflare_config.DNS_RECORD_NAME:
                return record["id"]

        logger.error(f"DNS record with name '{
            cloudflare_config.DNS_RECORD_NAME}' not found.")
        raise
    except requests.RequestException as e:
        logger.error(f"Failed to fetch DNS records: {e}")
        raise


def update_cloudflare_domain(new_ip, record_id):
    url = f"{BASE_URL}{
        cloudflare_config.ZONE_ID}/dns_records/{record_id}"
    headers = {
        "Authorization": f"Bearer {cloudflare_config.CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "type": "A",  # Use "AAAA" for IPv6
        "name": cloudflare_config.DNS_RECORD_NAME,
        "content": new_ip,
        "ttl": 1,  # 1 for Auto TTL
        "proxied": False,  # Set to False if you don't want Cloudflare's proxy
    }

    try:
        response = requests.put(url, json=data, headers=headers)
        response.raise_for_status()
        logger.info(f"DNS record updated successfully to {new_ip}.")
    except requests.RequestException as e:
        logger.error(f"Error updating DNS record: {e}")
        raise


if __name__ == "__main__":
    while True:
        current_ip = get_public_ip()
        if current_ip != get_saved_ip():
            logger.info(
                f"New IP detected... Updating domain to IP: {current_ip}")

            update_cloudflare_domain(
                new_ip=current_ip, record_id=get_cloudflare_record_id())
            save_ip(current_ip)
        time.sleep(60 * 30)
