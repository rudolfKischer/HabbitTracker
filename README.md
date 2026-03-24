# HabbitTracker

Personal habit tracking app. Live at https://dailytally.duckdns.org

## Google OAuth
- https://console.cloud.google.com/auth/clients?project=habbittracker-490406

---

## Deployment

Runs on a Raspberry Pi via systemd + nginx + Let's Encrypt.

### App status & logs
```bash
# Status
sudo systemctl status habittracker

# Live logs
sudo journalctl -u habittracker -f
```

### Nginx status & logs
```bash
# Status
sudo systemctl status nginx

# Access logs
sudo tail -f /var/log/nginx/access.log

# Error logs
sudo tail -f /var/log/nginx/error.log
```

### Restart services
```bash
# Restart app after code changes
sudo systemctl restart habittracker

# Restart nginx after config changes only
sudo systemctl restart nginx
```

### Auto-deploy (push from anywhere)
The Pi checks GitHub every minute and auto-deploys any new commits on `main`.

**Workflow:**
1. Make changes on any machine
2. `git push origin main`
3. Within ~1 minute the live site updates automatically

**How it works:**
`deploy.sh` runs via cron every minute. It fetches `origin/main` and compares
with the local HEAD. If there are new commits it pulls and restarts the service.

```bash
# Watch deploy logs
tail -f ~/deploy.log

# Run manually
~/deploy.sh
```

### DuckDNS
- Subdomain: dailytally
- Domain: dailytally.duckdns.org
- Dashboard: https://www.duckdns.org
- Token: stored in ~/duckdns-update.sh (keep secret)
- IP update script: ~/duckdns-update.sh (runs every 5 min via cron)
- Update log: ~/duckdns.log

### SSL cert
Managed by certbot, auto-renews every 90 days.
```bash
sudo certbot renew --dry-run  # test renewal
```
