# Cloudflare Dynamic DNS Updater

This script automates updating a Cloudflare DNS record with your current public IP address. Ideal for dynamic IP environments (e.g., home servers).

**Key Features:**
- Fetches your public IP.
- Compares it to the last-saved IP.
- Updates Cloudflare DNS via API if the IP changes.
- Logs all actions/errors for debugging.

**Setup:**
 **Cloudflare Configuration:**
   - Create an API token with **Edit** permissions for DNS in your zone (*Profile → API Tokens*).
   - **Environment Variables (.env):**
     - `CLOUDFLARE_ZONEID` – Cloudflare Zone ID.  
     - `CLOUDFLARE_API_TOKEN` – API token with DNS edit permissions.  
     - `CLOUDFLARE_DOMAIN_LIST` – Comma-separated list of domains to update. 

**Usage:**
- Run manually: `python main.py`

- **Docker Run:**
  ```bash
  docker build -t cloudflare-ddns .
  ```
  ```bash
  docker run -d \
  --name cloudflare-ddns \
  --env-file .env \
  -v $(pwd)/saved_ip.txt:/app/saved_ip.txt \
  cloudflare-ddns

  ```
