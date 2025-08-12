# TikTok Downloader Bot

Telegram bot for downloading TikTok videos, photo carousels and audio. Includes PostgreSQL logging of users/requests.

## Quick Start

1. Get bot token from [@BotFather](https://t.me/botfather)
2. Copy environment file and edit:
   ```bash
   cp .env.example .env
   ```
3. Fill `TELEGRAM_BOT_TOKEN` and secure DB credentials in `.env`.
4. Start services:
   ```bash
   docker-compose up -d --build
   ```
5. Send a TikTok link to your bot.

## Environment Variables
| Variable | Description | Default |
|----------|-------------|---------|
| TELEGRAM_BOT_TOKEN | Bot API token from BotFather | (required) |
| DB_HOST | PostgreSQL host (service name in compose) | postgres |
| DB_PORT | PostgreSQL port | 5432 |
| DB_NAME | Database name | tiktok_bot |
| DB_USER | Database user | postgres |
| DB_PASSWORD | Database password | CHANGE_ME |
| MAX_CONCURRENT | Max simultaneous download handlers | 5 |
| MAX_FILE_SIZE_MB | Per-file size cap in MB | 60 |

Optional (not yet wired fully): `LOG_LEVEL`, `REQUEST_TIMEOUT_SECONDS`.

## Resource Limits
The bot limits memory spikes by:
* Streaming media into memory once (no duplicate copy)
* Skipping files larger than `MAX_FILE_SIZE_MB`
* Capping parallel processing with a semaphore (`MAX_CONCURRENT`)

Tune for low-resource hosts:
* Reduce `MAX_CONCURRENT` to 2–3
* Lower `MAX_FILE_SIZE_MB` (e.g. 40) to skip large videos

## Security Notes
* Use a dedicated DB user with least privileges (avoid the default `postgres`).
* Rotate `TELEGRAM_BOT_TOKEN` and `DB_PASSWORD` if leaked.
* Do **not** commit your real `.env`.

## Commands
| Command | Description |
|---------|-------------|
| /start  | Welcome + instructions |
| /help   | Help message |
| /stats  | Your usage statistics |

## Development
Install dependencies locally:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python bot.py
```

## License
MIT (add LICENSE file if distributing publicly).
