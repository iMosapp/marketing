# Inventory Feed Playbook (owner + dealer onboarding)

## What exists
- Tools > Manage > Inventory Feed (`/admin/inventory-feed`) and the "Feed" button on the Inventory screen (managers/admins).
- Two transports, one pipeline (`services/inventory_feed.py`): `url` (public CSV/TSV/XML link, checked hourly at :20, re-imports only when content hash changes) and `sftp` (dealer's tool drops a CSV on an SFTP folder we own; newest file matching the pattern, re-imports only when name/mtime/size changed).
- Upsert by VIN (>= 11 chars) else stock number, scoped to the store. Units that drop off the file are marked `sold` (`sold_reason: dropped_off_feed`) when "Mark missing vehicles as sold" is on.
- Every pull is a row in `inventory_feed_runs`; two failures in a row or 3 days without a successful pull raises an `inventory_feed_issue` alert ("Fix the HomeNet inventory feed", action Fix -> /admin/inventory-feed) for store managers/org admins.
- Passwords are Fernet-encrypted with a key derived from JWT_SECRET.

## Onboarding a dealer (fastest path first)
1. Ask: "Do you run Facebook Marketplace / Automotive Inventory Ads or Google Vehicle Listing Ads?" If yes they already have a catalog feed URL (HomeNet IOL > Exports, or their website provider's support desk). Paste it in the app, Test, Connect and import. Done.
2. Small independents: Google Sheet with VIN, Stock, Year, Make, Model, Trim, Price, Mileage, Color, Body, Photo URLs -> File > Share > Publish to web > CSV. Paste the link (edit links are auto-converted).
3. Provider insists on SFTP (HomeNet vfsr form, vAuto rep, Dealer.com 3rd-party request form): create a login + folder for that dealer on our SFTP box, give the dealer host / port 22 / username / password / folder, then enter the same details in the app with pattern `*.csv`.
4. Fallback: manual CSV upload in Inventory (already existed).

## Owner: SFTP box for ~$4/mo (SFTPGo on Hetzner/DigitalOcean, Ubuntu 24.04)
```
curl -sS https://download.sftpgo.com/apt/gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/sftpgo-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/sftpgo-archive-keyring.gpg] https://download.sftpgo.com/apt $(lsb_release -c -s) main" | sudo tee /etc/apt/sources.list.d/sftpgo.list
sudo apt update && sudo apt install -y sftpgo
# SFTPGo defaults: SFTP 2022, web admin 8080. Vendor forms assume port 22:
sudo sed -i 's/^#\?Port 22/Port 2222/' /etc/ssh/sshd_config && sudo systemctl restart ssh
sudo sed -i 's/"port": 2022/"port": 22/' /etc/sftpgo/sftpgo.json && sudo systemctl restart sftpgo
sudo ufw allow 22 && sudo ufw allow 2222 && sudo ufw allow 8080
```
Then http://HOST:8080/web/admin -> setup wizard -> Users > Add per dealer (username = dealer slug, strong password, home /srv/sftpgo/data/<slug>, permissions list/upload/download/overwrite/delete).
Later swap to SFTP To Go ($18/mo) or Files.com: nothing changes in the app, only host/user/password.

## Certification (talking points)
- Inventory: none needed. Dealer-authorized exports from HomeNet / vAuto / website provider.
- DMS (CDK Fortellis, Reynolds RCI, Dealertrack Opentrack): only for deals/RO/service data. Months + per-rooftop fees. Not needed.
- CRM: leads in/out via ADF/XML email, accepted by every CRM without certification.
