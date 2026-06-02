# HabbitTracker

Personal habit tracking app. Live at https://dailytally.link

## Google OAuth
- https://console.cloud.google.com/auth/clients?project=habbittracker-490406

---

## Deployment

Runs on [Fly.io](https://fly.io) as app `habbittracker` (region `yyz`). The
SQLite DB lives on the `habbittracker_data` persistent volume mounted at
`/data` — see `fly.toml` and `Dockerfile`.

### Deploy

Deploys run automatically when a pull request is **merged into `main`** via
`.github/workflows/deploy.yml` (uses the `FLY_API_TOKEN` repo secret). The
workflow can also be triggered manually from the Actions tab.

To deploy from your machine without going through GitHub:

```bash
fly deploy
```

### App status & logs

```bash
fly status -a habbittracker
fly logs -a habbittracker
```

### SSH into the machine

```bash
fly ssh console -a habbittracker
```

### Database backup

Weekly backup runs via `.github/workflows/backup-db.yml` — it pulls
`/data/habits.db` from the Fly machine via `fly ssh sftp` and commits it to
`backups/habits.db`. Can also be triggered manually from the Actions tab.

### SSL / Domain

TLS is terminated by Fly. The custom domain `dailytally.link` points at the
Fly app via a CNAME / A+AAAA cert managed through `fly certs`.
