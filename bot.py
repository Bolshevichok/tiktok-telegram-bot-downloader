#!/usr/bin/env python3
import asyncio
import logging
import os
import io
from typing import List

from telegram import Update, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TikTokBot:
    def __init__(self, token: str):
        self.token = token
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            'Hi! 👋 Send me a TikTok URL and I\'ll download it for you!\n\n'
            'Supported:\n'
            '• 🎥 TikTok videos\n'
            '• 📸 TikTok photo carousels\n'
            '• 🎵 TikTok audio\n\n'
            'Just paste any TikTok link!'
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            'Help 📖\n\n'
            '1. Send me any TikTok URL\n'
            '2. I will download it for you\n'
            '3. You will receive the content\n\n'
            'Examples:\n'
            '• https://www.tiktok.com/@user/video/123456789\n'
            '• https://vt.tiktok.com/ZSxxxxx/\n'
            '• https://www.tiktok.com/@user/photo/123456789'
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message_text = update.message.text
        
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
            services = ['snaptik', 'tikmate', 'mdown', 'ttdownloader']
            
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
                        await self.send_downloads(update, downloads, service_name)
                        await processing_msg.delete()
                        return
                    else:
                        logger.warning(f"{service_name} returned no downloads")
                        
                except Exception as e:
                    logger.warning(f"{service_name} failed: {e}")
                    continue
            
            await processing_msg.edit_text('❌ Failed to download this content')
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await processing_msg.edit_text('❌ Error occurred')

    async def send_downloads(self, update: Update, downloads: List, service_name: str):
        try:
            videos = []
            photos = []
            audios = []
            
            for d in downloads:
                try:
                    content = d.download()
                    if isinstance(content, io.BytesIO):
                        content_bytes = content.getvalue()
                        
                        if len(content_bytes) < 50 * 1024 * 1024:
                            if content_bytes.startswith(b'\x00\x00\x00'):
                                logger.info(f"Detected MP4 video: size={len(content_bytes)} bytes, watermark={d.watermark}")
                                videos.append({
                                    'content': content_bytes,
                                    'watermark': d.watermark,
                                    'download_obj': d
                                })
                            elif content_bytes.startswith((b'\xFF\xD8\xFF', b'\x89PNG', b'GIF')):
                                logger.info(f"Detected image: size={len(content_bytes)} bytes")
                                photos.append({
                                    'content': content_bytes,
                                    'download_obj': d
                                })
                            elif str(d.type) == 'music' or content_bytes.startswith((b'ID3', b'\xFF\xFB')):
                                logger.info(f"Detected audio: size={len(content_bytes)} bytes")
                                audios.append({
                                    'content': content_bytes,
                                    'download_obj': d
                                })
                            else:
                                if str(d.type) == 'video':
                                    logger.info(f"Fallback video detection: size={len(content_bytes)} bytes, watermark={d.watermark}")
                                    videos.append({
                                        'content': content_bytes,
                                        'watermark': d.watermark,
                                        'download_obj': d
                                    })
                                else:
                                    logger.info(f"Fallback photo detection: size={len(content_bytes)} bytes")
                                    photos.append({
                                        'content': content_bytes,
                                        'download_obj': d
                                    })
                except Exception as e:
                    logger.warning(f"Failed to download item: {e}")
                    continue
            
            sent_count = 0
            
            if photos:
                if len(photos) == 1:
                    await update.message.reply_photo(photo=io.BytesIO(photos[0]['content']))
                    sent_count += 1
                else:
                    media = []
                    for photo in photos[:10]:
                        media.append(InputMediaPhoto(media=io.BytesIO(photo['content'])))
                    await update.message.reply_media_group(media=media)
                    sent_count += len(photos)
            
            if videos:
                valid_videos = [v for v in videos if len(v['content']) > 100 * 1024]
                
                if valid_videos:
                    valid_videos.sort(key=lambda x: (x['watermark'], -len(x['content'])))
                    
                    best_video = valid_videos[0]
                    await update.message.reply_video(video=io.BytesIO(best_video['content']))
                    sent_count += 1
                    
                    logger.info(f"Sent video: size={len(best_video['content'])} bytes, watermark={best_video['watermark']}")
                else:
                    logger.warning("All videos were too small (likely thumbnails), skipping video sending")
            
            if sent_count == 0 and audios:
                for audio in audios[:1]:
                    await update.message.reply_audio(audio=io.BytesIO(audio['content']))
                    sent_count += 1
            
            if sent_count == 0:
                await update.message.reply_text('❌ Could not download any content from this URL.')
                
        except Exception as e:
            logger.error(f"Error in send_downloads: {e}")
            await update.message.reply_text('❌ Error processing downloads')

    def run(self):
        application = Application.builder().token(self.token).build()

        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("help", self.help_command))
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
