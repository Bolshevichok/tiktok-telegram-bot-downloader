import os
import logging
import tempfile
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import yt_dlp
import requests

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')

class TikTokDownloader:
    def __init__(self):
        self.ydl_opts = {
            'format': 'best[height<=720]',
            'outtmpl': '%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
        }
    
    async def download_tiktok(self, url: str) -> dict:
        """Downloads video/photo from TikTok and returns file information"""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                self.ydl_opts['outtmpl'] = os.path.join(temp_dir, '%(id)s.%(ext)s')
                
                with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    
                    ydl.download([url])
                    
                    filename = f"{info['id']}.{info['ext']}"
                    filepath = os.path.join(temp_dir, filename)
                    
                    if os.path.exists(filepath):
                        with open(filepath, 'rb') as f:
                            file_data = f.read()
                        
                        return {
                            'success': True,
                            'data': file_data,
                            'filename': filename,
                            'title': info.get('title', 'TikTok Video'),
                            'ext': info['ext']
                        }
                    else:
                        return {'success': False, 'error': 'File not found after download'}
                        
        except Exception as e:
            logger.error(f"Download error: {e}")
            return {'success': False, 'error': str(e)}

downloader = TikTokDownloader()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /start command"""
    welcome_message = """
🎬 Hello! I'm a bot for downloading videos from TikTok.

📱 Just send me a TikTok video link, and I'll download it for you!

🔗 Supported link formats:
• https://vm.tiktok.com/...
• https://www.tiktok.com/@username/video/...
• https://tiktok.com/...

⚡ Just send a link, and I'll do the rest!
    """
    await update.message.reply_text(welcome_message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text messages"""
    message_text = update.message.text
    
    if not any(domain in message_text.lower() for domain in ['tiktok.com', 'vm.tiktok.com']):
        await update.message.reply_text(
            "❌ Please send a valid TikTok video link."
        )
        return
    
    loading_message = await update.message.reply_text("⏳ Downloading video...")
    
    try:
        result = await downloader.download_tiktok(message_text)
        
        if result['success']:
            if result['ext'] in ['mp4', 'mov', 'avi']:
                await update.message.reply_video(
                    video=result['data'],
                    filename=result['filename'],
                    caption=f"🎬 {result['title']}"
                )
            elif result['ext'] in ['jpg', 'jpeg', 'png', 'webp']:
                await update.message.reply_photo(
                    photo=result['data'],
                    caption=f"📸 {result['title']}"
                )
            else:
                await update.message.reply_document(
                    document=result['data'],
                    filename=result['filename'],
                    caption=f"📁 {result['title']}"
                )
            
            await loading_message.delete()
            
        else:
            await loading_message.edit_text(f"❌ Error: {result['error']}")
            
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await loading_message.edit_text(f"❌ An error occurred: {str(e)}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Error handler"""
    logger.error(f"Update {update} caused error {context.error}")

def main():
    """Main function to start the bot"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found! Check your .env file")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    logger.info("Bot started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
