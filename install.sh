#!/usr/bin/env bash
# CW Spotter installer for Rocky Linux 9 / RHEL 9
set -euo pipefail

# ── Checks ────────────────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    echo "Run as root: sudo bash install.sh" >&2
    exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

# ── Prompts ───────────────────────────────────────────────────────────────────
read -rp "Your amateur radio callsign (e.g. W1AW): " CALLSIGN
CALLSIGN=${CALLSIGN^^}   # uppercase
if [[ -z "$CALLSIGN" ]]; then
    echo "Callsign required." >&2; exit 1
fi

read -rp "Tailscale hostname for HTTPS (leave blank to skip): " TS_HOST

# ── Dependencies ──────────────────────────────────────────────────────────────
echo "Installing dependencies..."
dnf install -y python3.12 python3.12-pip nginx curl

# ── User and directory ────────────────────────────────────────────────────────
if ! id cwspots &>/dev/null; then
    useradd -r -s /sbin/nologin -d /opt/cwspots cwspots
fi
mkdir -p /opt/cwspots/web
chown -R cwspots:cwspots /opt/cwspots

# ── Copy application files ────────────────────────────────────────────────────
echo "Copying application files..."
cp "$SCRIPT_DIR"/*.py "$SCRIPT_DIR/requirements.txt" /opt/cwspots/
cp -r "$SCRIPT_DIR"/web/* /opt/cwspots/web/
chown -R cwspots:cwspots /opt/cwspots

# ── DXCC data ─────────────────────────────────────────────────────────────────
echo "Downloading cty.dat..."
curl -fsSL -o /opt/cwspots/cty.dat https://www.country-files.com/cty/cty.dat
chown cwspots:cwspots /opt/cwspots/cty.dat

# ── Python venv ───────────────────────────────────────────────────────────────
echo "Setting up Python virtual environment..."
sudo -u cwspots python3.12 -m venv /opt/cwspots/venv
sudo -u cwspots /opt/cwspots/venv/bin/pip install -q -r /opt/cwspots/requirements.txt

# ── Initial data fetch ────────────────────────────────────────────────────────
echo "Fetching KiwiSDR station list..."
sudo -u cwspots /opt/cwspots/venv/bin/python /opt/cwspots/fetch_kiwis.py

echo "Fetching SKCC member roster..."
sudo -u cwspots /opt/cwspots/venv/bin/python /opt/cwspots/fetch_skcc.py

# ── systemd units ─────────────────────────────────────────────────────────────
echo "Installing systemd units..."

# Main service with user's callsign
sed "s/YOUR_CALLSIGN/$CALLSIGN/" "$SCRIPT_DIR/systemd/cwspots.service" \
    > /etc/systemd/system/cwspots.service

for f in cwspots-kiwis.service cwspots-kiwis.timer \
          cwspots-skcc.service  cwspots-skcc.timer \
          cwspots-ctydat.service cwspots-ctydat.timer; do
    cp "$SCRIPT_DIR/systemd/$f" /etc/systemd/system/
done

systemctl daemon-reload
systemctl enable --now cwspots
systemctl enable --now cwspots-kiwis.timer
systemctl enable --now cwspots-skcc.timer
systemctl enable --now cwspots-ctydat.timer

# ── nginx ─────────────────────────────────────────────────────────────────────
echo "Configuring nginx..."
cp "$SCRIPT_DIR/nginx/cwspots.conf" /etc/nginx/conf.d/cwspots.conf
systemctl enable --now nginx
nginx -t && systemctl reload nginx

# ── Firewall ──────────────────────────────────────────────────────────────────
echo "Opening firewall port 8090..."
firewall-cmd --permanent --add-port=8090/tcp
firewall-cmd --reload

# ── Tailscale HTTPS (optional) ────────────────────────────────────────────────
if [[ -n "$TS_HOST" ]]; then
    echo "Setting up Tailscale TLS for $TS_HOST..."
    mkdir -p /etc/nginx/ssl

    tailscale cert \
        --cert-file /etc/nginx/ssl/ts.crt \
        --key-file  /etc/nginx/ssl/ts.key \
        "$TS_HOST"

    sed "s/YOUR_TAILSCALE_HOSTNAME/$TS_HOST/" \
        "$SCRIPT_DIR/systemd/cwspots-tlscert.service" \
        > /etc/systemd/system/cwspots-tlscert.service
    cp "$SCRIPT_DIR/systemd/cwspots-tlscert.timer" /etc/systemd/system/

    # Enable HTTPS block in nginx config
    sed -i 's/# HTTPS_BLOCK_START//' /etc/nginx/conf.d/cwspots.conf
    sed -i 's/# HTTPS_BLOCK_END//'   /etc/nginx/conf.d/cwspots.conf
    sed -i "s/YOUR_TAILSCALE_HOSTNAME/$TS_HOST/g" /etc/nginx/conf.d/cwspots.conf

    systemctl daemon-reload
    systemctl enable --now cwspots-tlscert.timer

    firewall-cmd --permanent --add-port=4443/tcp
    firewall-cmd --reload

    nginx -t && systemctl reload nginx
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo
echo "CW Spotter installed successfully."
echo "  HTTP:  http://$(hostname -I | awk '{print $1}'):8090"
[[ -n "$TS_HOST" ]] && echo "  HTTPS: https://$TS_HOST:4443"
echo
echo "Check status:  systemctl status cwspots"
echo "View logs:     journalctl -u cwspots -f"
