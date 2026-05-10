# CW Spotter

A real-time Reverse Beacon Network (RBN) spot viewer optimized for mobile use, with KiwiSDR integration and SKCC member lookup.

## Features

- **Live spots** streamed over WebSocket from the RBN Telnet feed
- **Deduplication** — one row per DX station per band, updated in place
- **Filtering** — WPM range, SNR floor, band, mode, DX/spotter continent, beacon toggle
- **KiwiSDR integration** — tap a spot to tune a KiwiSDR; static (your saved station) or dynamic (nearest to the spotter) mode
- **SKCC lookup** — optionally overlay SKCC member numbers on spot rows
- **Band summary** — live per-band spot count badges
- **Dark/light mode** — persisted across sessions
- **PWA** — installable on iOS and Android via Safari/Chrome

## Architecture

```
RBN Telnet feed
      │
  rbn_client.py
      │
  server.py  ──── aiohttp HTTP :8080 (static files)
      │       └── websockets  :8081 (spot stream)
      │
  nginx  ──── :8090  HTTP
         └─── :4443  HTTPS (Tailscale TLS)   ← /ws proxied to :8081
```

Data files refreshed by systemd timers:
- `cty.dat` — BigCTY DXCC data (monthly)
- `web/kiwi_stations.json` — KiwiSDR station list (weekly)
- `web/skcc_members.json` — SKCC member roster (weekly, Friday)

## Prerequisites

- Rocky Linux 9 / RHEL 9
- Python 3.12+
- nginx
- An amateur radio callsign registered with the [Reverse Beacon Network](https://www.reversebeacon.net/)
- (Optional) [Tailscale](https://tailscale.com/) for remote HTTPS access

## Quick Install

```bash
sudo bash install.sh
```

The script will prompt for your callsign and (optionally) your Tailscale hostname, then handle the rest.

## Manual Install

### 1. Create system user and directory

```bash
sudo useradd -r -s /sbin/nologin -d /opt/cwspots cwspots
sudo mkdir -p /opt/cwspots/web
sudo chown -R cwspots:cwspots /opt/cwspots
```

### 2. Copy files

```bash
sudo cp -r *.py requirements.txt cty.dat web/ /opt/cwspots/
sudo cp -r systemd/ /opt/cwspots/
sudo chown -R cwspots:cwspots /opt/cwspots
```

### 3. Download DXCC data

```bash
sudo -u cwspots curl -fsSL -o /opt/cwspots/cty.dat \
    https://www.country-files.com/cty/cty.dat
```

### 4. Create Python virtual environment

```bash
sudo -u cwspots python3 -m venv /opt/cwspots/venv
sudo -u cwspots /opt/cwspots/venv/bin/pip install -r /opt/cwspots/requirements.txt
```

### 5. Fetch initial data

```bash
sudo -u cwspots /opt/cwspots/venv/bin/python /opt/cwspots/fetch_kiwis.py
sudo -u cwspots /opt/cwspots/venv/bin/python /opt/cwspots/fetch_skcc.py
```

### 6. Install systemd units

Edit `systemd/cwspots.service` and replace `YOUR_CALLSIGN` with your callsign.

```bash
sudo cp systemd/*.service systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload

sudo systemctl enable --now cwspots
sudo systemctl enable --now cwspots-kiwis.timer
sudo systemctl enable --now cwspots-skcc.timer
sudo systemctl enable --now cwspots-ctydat.timer
```

### 7. Configure nginx

```bash
sudo cp nginx/cwspots.conf /etc/nginx/conf.d/cwspots.conf
sudo nginx -t && sudo systemctl reload nginx
```

### 8. Open firewall ports

```bash
sudo firewall-cmd --permanent --add-port=8090/tcp
sudo firewall-cmd --reload
```

## Tailscale HTTPS (optional)

For secure remote access via Tailscale:

```bash
sudo mkdir -p /etc/nginx/ssl
sudo tailscale cert \
    --cert-file /etc/nginx/ssl/ts.crt \
    --key-file  /etc/nginx/ssl/ts.key \
    YOUR_TAILSCALE_HOSTNAME

sudo cp systemd/cwspots-tlscert.service systemd/cwspots-tlscert.timer \
    /etc/systemd/system/
```

Edit `/etc/systemd/system/cwspots-tlscert.service` and replace `YOUR_TAILSCALE_HOSTNAME`.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now cwspots-tlscert.timer
sudo firewall-cmd --permanent --add-port=4443/tcp
sudo firewall-cmd --reload
```

Then uncomment the HTTPS server block in `nginx/cwspots.conf` and reload nginx.

## Configuration

All configuration is via environment variables in `cwspots.service`:

| Variable | Default | Description |
|---|---|---|
| `RBN_CALLSIGN` | *(required)* | Your callsign, used to log in to the RBN feed |
| `PORT` | `8080` | aiohttp HTTP port |
| `WS_PORT` | `8081` | WebSocket port |

## Updating

```bash
sudo cp *.py /opt/cwspots/
sudo cp web/app.js web/index.html web/style.css /opt/cwspots/web/
sudo systemctl restart cwspots
```

## License

MIT
