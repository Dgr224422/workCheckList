# Raspberry Pi 4 deployment

## Target
- Raspberry Pi 4
- Raspberry Pi OS 64-bit (Bookworm recommended)
- Internet access for `apt` and `pip`

## 1) Clone project

```bash
git clone <YOUR_REPO_URL> workCheckList
cd workCheckList
```

## 2) Base setup

```bash
bash deploy/raspberrypi/setup_pi.sh
```

This script does:
- installs system libs (`libzbar0`, `libgl1`, `libglib2.0-0`)
- sets timezone to `Europe/Moscow`
- creates `.venv`
- installs `requirements.txt`
- creates `data/`, `logs/`, `media/`

## 3) Configure environment

```bash
nano .env
```

Required values:
- `BOT_TOKEN`
- `SYSTEM_ADMIN_ID`
- optional: `ADMIN_IDS`, `CLEANUP_DAYS`

## 4) Install autostart service

```bash
bash deploy/raspberrypi/install_service.sh
```

## 5) Check service

```bash
sudo systemctl status workchecklist-bot.service
sudo journalctl -u workchecklist-bot.service -f
```

## Manual run (without systemd)

```bash
bash scripts/run_bot.sh
```

## Update bot on Pi

```bash
cd ~/workCheckList
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart workchecklist-bot.service
```

## Troubleshooting

- `ImportError: libzbar.so...`
  - run: `sudo apt-get install -y libzbar0`
- service does not start:
  - check `.env`
  - check logs: `sudo journalctl -u workchecklist-bot.service -n 200 --no-pager`
