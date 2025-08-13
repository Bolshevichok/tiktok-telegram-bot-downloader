#!/usr/bin/env python3
import asyncio
import logging
import os
import io
import time
from typing import List

from telegram import Update, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from database import get_db_manager

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TikTokBot:
    def __init__(self, token: str):
        self.token = token
        self.db = get_db_manager()
        # Concurrency control
        try:
            max_concurrent = int(os.getenv("MAX_CONCURRENT", "5"))
        except ValueError:
            max_concurrent = 5
        self.semaphore = asyncio.Semaphore(max_concurrent)
        # File size limit (in MB) -> bytes
        try:
            max_file_mb = int(os.getenv("MAX_FILE_SIZE_MB", "60"))  # default 60MB
        except ValueError:
            max_file_mb = 60
        self.max_file_size = max_file_mb * 1024 * 1024
        logger.info("TikTok bot initialized with database connection")
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Register user in database
        user = update.effective_user
        self.db.get_or_create_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        await update.message.reply_text(
            'Hi! 👋 Send me a TikTok URL and I\'ll download it for you!\n\n'
            'Supported:\n'
            '• 🎥 TikTok videos\n'
            '• 📸 TikTok photo carousels\n'
            '• 🎵 TikTok audio\n\n'
            'Commands:\n'
            '/start - Show this message\n'
            '/stats - Show your usage statistics\n\n'
            'Just paste any TikTok link!'
        )

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user statistics."""
        user = update.effective_user
        stats = self.db.get_user_stats(user.id)
        
        if not stats:
            await update.message.reply_text("No statistics available.")
            return
        
        stats_text = f"""📊 Your Statistics:

👤 User: {stats.get('first_name', 'Unknown')}
📅 Member since: {stats.get('member_since', 'Unknown').strftime('%B %d, %Y') if stats.get('member_since') else 'Unknown'}
📥 Total requests: {stats.get('total_requests', 0)}
✅ Successful: {stats.get('successful_requests', 0)}
📈 Success rate: {stats.get('success_rate', 0):.1f}%"""
        
        await update.message.reply_text(stats_text)
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            'Help 📖\n\n'
            '1. Send me any TikTok URL\n'
            '2. I will download it for you\n'
            '3. You will receive the content\n\n'
            'Commands:\n'
            '/start - Show welcome message\n'
            '/help - Show this help\n'
            '/stats - Show your usage statistics\n\n'
            'Examples:\n'
            '• https://www.tiktok.com/@user/video/123456789\n'
            '• https://vt.tiktok.com/ZSxxxxx/\n'
            '• https://www.tiktok.com/@user/photo/123456789'
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message_text = update.message.text
        start_time = time.time()
        
        # Get user info and register/update in database
        user = update.effective_user
        self.db.get_or_create_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        import re
        tiktok_patterns = [
            r'https?://(?:www\.)?tiktok\.com/[@\w/.-]+',
            r'https?://vt\.tiktok\.com/[\w]+/?',
            r'https?://vm\.tiktok\.com/[\w]+/?',
            r'https?://m\.tiktok\.com/[@\w/.-]+'
        ]
        
        tiktok_url = None
        for pattern in tiktok_patterns:
            match = re.search(pattern, message_text)
            if match:
                tiktok_url = match.group(0)
                break
        
        if not tiktok_url:
            await update.message.reply_text(
                'Please send a valid TikTok URL! 🔗\n\n'
                'Examples:\n'
                '• https://www.tiktok.com/@user/video/123456789\n'
                '• https://vt.tiktok.com/ZSxxxxx/'
            )
            return
        
        processing_msg = await update.message.reply_text('⏳ Processing...')
        
        try:
            async with self.semaphore:
                services = ['snaptik', 'tikmate', 'mdown', 'ttdownloader']
                success = False
                service_used = None
                request_type = None
                files_count = 0
                total_size = 0
                error_message = None

                for service_name in services:
                    try:
                        if service_name == 'snaptik':
                            from tiktok_downloader import snaptik
                            downloads = snaptik(tiktok_url)
                        elif service_name == 'tikmate':
                            from tiktok_downloader import tikmate
                            downloads = tikmate(tiktok_url)
                        elif service_name == 'mdown':
                            from tiktok_downloader import mdown
                            downloads = mdown(tiktok_url)
                        elif service_name == 'ttdownloader':
                            from tiktok_downloader import ttdownloader
                            downloads = ttdownloader(tiktok_url)

                        if downloads:
                            logger.info(f"Successfully got {len(downloads)} downloads from {service_name}")
                            result = await self.send_downloads(update, downloads, service_name)

                            if result['success']:
                                success = True
                                service_used = service_name
                                request_type = result.get('type', 'unknown')
                                files_count = result.get('files_count', 1)
                                total_size = result.get('total_size', 0)
                                await processing_msg.delete()
                                break
                            else:
                                error_message = result.get('error', 'Failed to send content')
                        else:
                            logger.warning(f"{service_name} returned no downloads")
                            error_message = f"{service_name} returned no downloads"

                    except Exception as e:
                        logger.warning(f"{service_name} failed: {e}")
                        error_message = str(e)
                        continue

                if not success:
                    await processing_msg.edit_text('❌ Failed to download this content')

                # Log request to database
                processing_time = time.time() - start_time
                self.db.log_request(
                    telegram_id=user.id,
                    tiktok_url=tiktok_url,
                    request_type=request_type,
                    service_used=service_used,
                    success=success,
                    file_size=total_size,
                    files_count=files_count,
                    error_message=error_message if not success else None,
                    processing_time=processing_time
                )

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await processing_msg.edit_text('❌ Error occurred')

            # Log error to database
            processing_time = time.time() - start_time
            self.db.log_request(
                telegram_id=user.id,
                tiktok_url=tiktok_url,
                request_type='unknown',
                service_used=None,
                success=False,
                error_message=str(e),
                processing_time=processing_time
            )

    async def send_downloads(self, update: Update, downloads: List, service_name: str):
        def is_mp4(h: bytes) -> bool:
            # MP4: box size (4 bytes) + 'ftyp'
            return len(h) >= 12 and h[4:8] == b'ftyp'
        
        def is_jpeg(h: bytes) -> bool:
            return h.startswith(b'\xFF\xD8\xFF')
        
        def is_png(h: bytes) -> bool:
            return h.startswith(b'\x89PNG\r\n\x1a\n')
        
        def is_gif(h: bytes) -> bool:
            return h.startswith(b'GIF87a') or h.startswith(b'GIF89a')
        
        def is_webp(buf: bytes) -> bool:
            # RIFF....WEBP
            return len(buf) >= 12 and buf[0:4] == b'RIFF' and buf[8:12] == b'WEBP'
        
        def looks_like_image(header: bytes, first_64: bytes, url: str, declared_type: str) -> bool:
            if is_jpeg(header) or is_png(header) or is_gif(header) or is_webp(header):
                return True
            ext_match = any(url.lower().split('?')[0].endswith(x) for x in ('.jpg', '.jpeg', '.png', '.gif', '.webp'))
            if ext_match:
                return True
            if declared_type in ('image','photo','photos','picture'):
                return True
            return False
        
        try:
            videos = []
            photos = []
            audios = []
            total_size = 0
            skipped_oversize = 0
            
            for d in downloads:
                try:
                    content = d.download()  # returns BytesIO
                    if not isinstance(content, io.BytesIO):
                        continue
                    size = content.getbuffer().nbytes
                    if size > self.max_file_size:
                        skipped_oversize += 1
                        logger.warning(f"Skipping oversize file {size} bytes > limit {self.max_file_size}")
                        continue
                    total_size += size
                    
                    # Read header / sample
                    raw = content.getbuffer()
                    header = bytes(raw[:16])
                    first_64 = bytes(raw[:64])
                    
                    declared_type = str(getattr(d, 'type', '')).lower()
                    url = str(getattr(d, 'url', ''))
                    
                    # Audio detection
                    if declared_type == 'music' or first_64.startswith(b'ID3') or first_64.startswith(b'\xFF\xFB'):
                        audios.append({'content': content, 'download_obj': d, 'size': size})
                        continue
                    
                    # Image detection
                    if looks_like_image(header, first_64, url, declared_type):
                        photos.append({'content': content, 'download_obj': d, 'size': size})
                        continue
                    
                    # Video detection (MP4 or declared video). Some services give slideshow MP4 for photo posts.
                    if is_mp4(header) or declared_type == 'video':
                        # Heuristic: if this is a suspected slideshow for a photo post and we ALSO have other images later,
                        # we'll still collect it as video but prefer images when sending.
                        videos.append({'content': content, 'watermark': getattr(d, 'watermark', None), 'download_obj': d, 'size': size})
                        continue
                    
                    # Fallback: if nothing matched, treat as photo if small; else video
                    if size < 800_000:  # likely an image (small)
                        photos.append({'content': content, 'download_obj': d, 'size': size})
                    else:
                        videos.append({'content': content, 'watermark': getattr(d, 'watermark', None), 'download_obj': d, 'size': size})
                
                except Exception as e:
                    logger.warning(f"Failed to download item: {e}")
                    continue
            
            sent_count = 0
            request_type = 'unknown'
            
            # Preference logic: if we have any photos AND no "real" large videos (>1MB) we treat as photo post
            large_videos = [v for v in videos if v['size'] > 1_000_000]
            if photos and not large_videos:
                request_type = 'photos'
                if len(photos) == 1:
                    photos[0]['content'].seek(0)
                    await update.message.reply_photo(photo=photos[0]['content'])
                    sent_count += 1
                else:
                    media = []
                    for photo in photos[:10]:
                        photo['content'].seek(0)
                        media.append(InputMediaPhoto(media=photo['content']))
                    await update.message.reply_media_group(media=media)
                    sent_count += len(photos)
            
            # Send video only if nothing already sent
            if sent_count == 0 and videos:
                request_type = 'video'
                # Filter out tiny "thumbnail" or slideshow artifacts (<120KB) unless no other choice
                filtered_videos = [v for v in videos if v['size'] > 120 * 1024] or videos
                # Prefer non-watermark, then bigger size
                filtered_videos.sort(key=lambda x: (x.get('watermark') is True, -x['size']))
                best_video = filtered_videos[0]
                best_video['content'].seek(0)
                await update.message.reply_video(video=best_video['content'])
                sent_count += 1
                logger.info(f"Sent video: size={best_video['size']} bytes, watermark={best_video.get('watermark')}")
            
            # Fallback to audio
            if sent_count == 0 and audios:
                request_type = 'audio'
                audio = audios[0]
                audio['content'].seek(0)
                await update.message.reply_audio(audio=audio['content'])
                sent_count += 1
            
            if sent_count == 0:
                if skipped_oversize and not (videos or photos or audios):
                    await update.message.reply_text('❌ Все файлы превышают лимит размера.')
                else:
                    await update.message.reply_text('❌ Не удалось скачать контент по ссылке.')
                return {
                    'success': False,
                    'error': 'No content could be sent (oversize skipped)' if skipped_oversize else 'No content could be sent',
                    'type': request_type,
                    'files_count': 0,
                    'total_size': total_size
                }
            
            return {
                'success': True,
                'type': request_type,
                'files_count': sent_count,
                'total_size': total_size
            }
                
        except Exception as e:
            logger.error(f"Error in send_downloads: {e}")
            await update.message.reply_text('❌ Ошибка при обработке загрузок')
            return {
                'success': False,
                'error': str(e),
                'type': 'unknown',
                'files_count': 0,
                'total_size': 0
            }

    def run(self):
        application = Application.builder().token(self.token).build()

        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("stats", self.stats))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        logger.info("Starting TikTok bot...")
        application.run_polling()

def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set!")
        return
    
    bot = TikTokBot(token)
    bot.run()

if __name__ == '__main__':
    main()
