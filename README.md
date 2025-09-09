# Cloudflare Dynamic DNS Updater

This script automates updating a Cloudflare DNS record with your current public IP address. Ideal for dynamic IP environments (e.g., home servers).

**Key Features:**
- Fetches your public IP.
- Compares it to the last-saved IP.
- Updates Cloudflare DNS via API if the IP changes.
- Logs all actions/errors for debugging.

**Setup:**
1. **Requirements:**
   - Install: `pip install requests`

2. **Cloudflare Configuration:**
   - Create an API token with **Edit** permissions for DNS in your zone (*Profile → API Tokens*).
   - In `utils/config.py`, add:
     ```python
     cloudflare_config = {
         "CLOUDFLARE_API_TOKEN": "your-api-token-here",
         "ZONE_ID": "your-zone-id",
         "DNS_RECORD_NAME": "subdomain.example.com"  # Record to update
     }
     ```

**Usage:**
- Run manually: `python script.py`
- **Automate:** Add a cron job (e.g., every 15 minutes):
  ```bash
  */15 * * * * /usr/bin/python3 /path/to/script.py
  ```

**Notes:**
- Logs are stored in `logs/cloudflare_ddns.log` (auto-generated).
- For IPv6, change `type: "A"` to `"AAAA"` in `update_cloudflare_domain()`.
