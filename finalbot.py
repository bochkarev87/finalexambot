import logging
import sqlite3
import requests
import re
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# ========== SETTINGS ==========
TELEGRAM_TOKEN = "8619808739:AAEgp_l8pHVkFCRPaCfdoh2UcoIPAMYpy6s"  # INSERT YOUR TOKEN

# NewsAPI key (get free at https://newsapi.org)
NEWS_API_KEY = "147974fd0fd048eda08a000d95269667"  # INSERT YOUR NEWSAPI KEY

# Local Ollama API
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2:3b"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== DATABASE ==========
def init_db():
    conn = sqlite3.connect('content_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            post_text TEXT NOT NULL,
            post_url TEXT,
            created_at TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            posts_text TEXT NOT NULL,
            theme TEXT,
            keywords TEXT,
            style TEXT,
            topics TEXT,
            tone TEXT,
            ideas TEXT,
            created_at TEXT NOT NULL
        )
    ''')
    
    cursor.execute("PRAGMA table_info(analyses)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'theme' not in columns:
        cursor.execute("ALTER TABLE analyses ADD COLUMN theme TEXT")
    if 'keywords' not in columns:
        cursor.execute("ALTER TABLE analyses ADD COLUMN keywords TEXT")
    if 'style' not in columns:
        cursor.execute("ALTER TABLE analyses ADD COLUMN style TEXT")
    if 'topics' not in columns:
        cursor.execute("ALTER TABLE analyses ADD COLUMN topics TEXT")
    if 'tone' not in columns:
        cursor.execute("ALTER TABLE analyses ADD COLUMN tone TEXT")
    if 'ideas' not in columns:
        cursor.execute("ALTER TABLE analyses ADD COLUMN ideas TEXT")
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")

def add_post(user_id, post_text, post_url=""):
    conn = sqlite3.connect('content_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO user_posts (user_id, post_text, post_url, created_at)
        VALUES (?, ?, ?, ?)
    ''', (user_id, post_text, post_url, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    count = cursor.execute("SELECT COUNT(*) FROM user_posts WHERE user_id = ?", (user_id,)).fetchone()[0]
    conn.close()
    return count

def get_user_posts(user_id, limit=10):
    conn = sqlite3.connect('content_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT post_text FROM user_posts WHERE user_id = ? ORDER BY id DESC LIMIT ?
    ''', (user_id, limit))
    posts = [row[0] for row in cursor.fetchall()]
    conn.close()
    return posts

def clear_user_posts(user_id):
    conn = sqlite3.connect('content_bot.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_posts WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def save_analysis(user_id, posts_text, theme, keywords, style, topics, tone, ideas):
    conn = sqlite3.connect('content_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO analyses (user_id, posts_text, theme, keywords, style, topics, tone, ideas, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, posts_text, theme, keywords, style, topics, tone, ideas, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_last_analysis(user_id):
    conn = sqlite3.connect('content_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT theme, keywords, style, topics, tone, ideas FROM analyses WHERE user_id = ? ORDER BY id DESC LIMIT 1
    ''', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result

# ========== TELEGRAM POST PARSING ==========
def parse_telegram_post(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return None, f"Failed to load post (status {response.status_code})"
        
        html = response.text
        
        match = re.search(r'<meta property="og:description" content="([^"]+)"', html)
        if match:
            text = match.group(1)
            text = text.replace('&#39;', "'").replace('&quot;', '"').replace('&amp;', '&')
            return text, None
        
        match = re.search(r'<div class="tgme_widget_message_text"[^>]*>([^<]+(?:<[^>]+>[^<]*</[^>]+>[^<]*)*)</div>', html, re.DOTALL)
        if match:
            text = re.sub(r'<[^>]+>', '', match.group(1))
            text = text.replace('\n', ' ').strip()
            return text, None
        
        return None, "Could not find post text. Make sure the post is public."
        
    except Exception as e:
        return None, f"Parsing error: {str(e)}"

# ========== NEWS API ==========
def search_news(keywords, limit=8):
    """Search real news using NewsAPI"""
    try:
        from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": keywords,
            "from": from_date,
            "sortBy": "relevancy",
            "language": "en",
            "pageSize": limit,
            "apiKey": NEWS_API_KEY
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            articles = data.get("articles", [])
            
            news_list = []
            for article in articles:
                news_list.append({
                    "title": article.get("title", ""),
                    "description": article.get("description", ""),
                    "source": article.get("source", {}).get("name", "")
                })
            return news_list
        else:
            logger.error(f"NewsAPI error: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"News search error: {e}")
        return []

# ========== OLLAMA AI ==========
def ask_llama(prompt):
    try:
        payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 2048
            }
        }
        
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            return result.get("response", "Error: empty response")
        else:
            return f"API Error: {response.status_code}"
            
    except requests.exceptions.ConnectionError:
        return "❌ Cannot connect to Ollama. Make sure Ollama is running (ollama serve)"
    except Exception as e:
        return f"❌ Error: {str(e)}"

def analyze_channel(posts_text):
    """Extract channel theme, style, topics, and tone"""
    prompt = f"""
Analyze these posts from a Telegram channel:

POSTS:
{posts_text}

Answer in this exact format (use short, clear answers):

THEME: (one sentence describing the main topic, generalized, no specific brands)

STYLE: (one word: expert / entertaining / personal / news)

TOPICS: (3-5 general topics separated by commas, without specific names)

TONE: (one word or short phrase: friendly / professional / humorous / neutral)
"""
    return ask_llama(prompt)

def generate_post_ideas(theme, style, topics, tone, news_articles):
    """Generate creative post ideas based on real news and channel style"""
    
    # Format news for context
    news_text = ""
    for i, article in enumerate(news_articles[:8], 1):
        news_text += f"- {article['title']}\n"
    
    if not news_text:
        news_text = "No recent news found. Generate ideas based on the channel theme."
    
    prompt = f"""
You are a creative content strategist.

CHANNEL INFO:
- Theme: {theme}
- Style: {style}
- Main Topics: {topics}
- Tone: {tone}

REAL NEWS FROM THE PAST WEEK (use for inspiration, but don't copy):
{news_text}

Your task:
Generate 5 ORIGINAL post ideas that:
1. Match the channel's theme and style
2. Are inspired by the real news above
3. Use DIFFERENT FORMATS for each idea (mix it up!)

AVAILABLE FORMATS (use a variety, don't repeat the same format more than twice):
- How-to guide / tutorial
- Opinion piece / hot take
- Predictions / future trends
- Analysis / deep dive
- Myth busting / misconceptions
- Personal experience / story
- Curated list (only use this format once at most)
- Comparison (only use this format once at most)
- Q&A / answering audience questions
- Behind the scenes
- Case study
- News commentary (add your unique perspective)
- Controversial opinion
- Beginner's guide
- Expert tips

Output ONLY the headlines, numbered 1 to 5.
Do NOT use "Top 5" or "Best" formats unless it's genuinely the best fit.

Example of good variety:
1. How I Finally Fixed My Laptop Overheating Issues
2. Is Cloud Gaming Actually Worth It in 2026?
3. What Nobody Tells You About Buying a Used Smartphone
4. The Future of Foldable Phones: Predictions for Next Year
5. Why I Switched from Windows to Mac (and Back Again)

Example of BAD variety (too repetitive):
1. Top 5 Smartphones
2. Top 5 Laptops
3. Best Headphones
4. Best Cameras
5. Top 10 Gadgets

Now generate 5 ideas with different formats:
"""
    
    return ask_llama(prompt)

def generate_more_ideas(theme, style, topics, tone, previous_ideas):
    """Generate additional creative ideas with variety"""
    
    prompt = f"""
You are a creative content strategist.

CHANNEL INFO:
- Theme: {theme}
- Style: {style}
- Main Topics: {topics}
- Tone: {tone}

Previous ideas:
{previous_ideas}

Generate 5 NEW, DIFFERENT post ideas for this channel.
- Do NOT repeat formats from previous ideas
- Use a variety of formats (opinion, guide, analysis, predictions, personal story, etc.)
- Avoid "Top 5" or "Best" formats unless absolutely necessary

Output ONLY the headlines, numbered 1 to 5.
"""
    
    return ask_llama(prompt)

# ========== BOT COMMANDS ==========
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "🤖 *Content Idea Generator*\n\n"
        "I analyze your channel and generate creative post ideas inspired by REAL news.\n\n"
        "📌 *How it works:*\n"
        "1. Send me 5 links to your Telegram channel posts\n"
        "2. I analyze your channel's theme, style, and tone\n"
        "3. I search for REAL news in your niche\n"
        "4. I generate 5 creative post ideas\n\n"
        "📋 *Commands:*\n"
        "/start — welcome\n"
        "/clear — start over\n"
        "/more — generate 5 more ideas",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "📖 *Instructions*\n\n"
        "1. Find 5 public posts from your Telegram channel\n"
        "2. Copy each link (Share → Copy Link)\n"
        "3. Send each link to me\n"
        "4. After 5 posts, I analyze your channel\n"
        "5. I search for REAL news in your niche\n"
        "6. I generate 5 creative post ideas\n\n"
        "To get more ideas: /more\n"
        "To start over: /clear",
        parse_mode='Markdown'
    )

async def handle_url(update: Update, context: CallbackContext):
    url = update.message.text.strip()
    user_id = update.effective_user.id
    
    if not url.startswith('https://t.me/'):
        await update.message.reply_text(
            "❌ Send a Telegram post link\n"
            "Example: https://t.me/durov/123"
        )
        return
    
    status_msg = await update.message.reply_text("🔍 Parsing post...")
    
    post_text, error = parse_telegram_post(url)
    
    if error:
        await status_msg.edit_text(f"❌ {error}")
        return
    
    if not post_text or len(post_text) < 10:
        await status_msg.edit_text("❌ Post is too short or text could not be extracted")
        return
    
    count = add_post(user_id, post_text, url)
    
    await status_msg.edit_text(
        f"✅ Post saved!\n\n"
        f"📊 Posts saved: {count} / 5\n\n"
        f"{'🎉 Limit reached! Analyzing your channel...' if count >= 5 else '📎 Send more links (need 5)'}"
    )
    
    if count >= 5:
        await generate_ideas(update, context, user_id)

async def generate_ideas(update: Update, context: CallbackContext, user_id=None):
    if user_id is None:
        user_id = update.effective_user.id
    
    posts = get_user_posts(user_id, limit=10)
    
    if len(posts) < 3:
        await update.message.reply_text(
            f"❌ Not enough posts. Currently: {len(posts)}. Need at least 3."
        )
        return
    
    posts_text = "\n\n---\n\n".join([f"Post {i+1}: {post}" for i, post in enumerate(posts)])
    
    status_msg = await update.message.reply_text(
        f"🔍 Analyzing your channel...\n"
        f"⏳ This may take 20-30 seconds"
    )
    
    try:
        # Step 1: Analyze channel
        analysis = analyze_channel(posts_text)
        
        # Parse results
        theme_match = re.search(r'THEME:\s*(.+)', analysis, re.IGNORECASE)
        style_match = re.search(r'STYLE:\s*(.+)', analysis, re.IGNORECASE)
        topics_match = re.search(r'TOPICS:\s*(.+)', analysis, re.IGNORECASE)
        tone_match = re.search(r'TONE:\s*(.+)', analysis, re.IGNORECASE)
        
        theme = theme_match.group(1).strip() if theme_match else "General topics"
        style = style_match.group(1).strip() if style_match else "informative"
        topics = topics_match.group(1).strip() if topics_match else "various topics"
        tone = tone_match.group(1).strip() if tone_match else "neutral"
        
        # Extract keywords from topics for news search
        keywords = topics.split(",")[0].strip() if topics else theme
        
        await status_msg.edit_text(
            f"📊 *Channel Analysis*\n\n"
            f"**Theme:** {theme}\n"
            f"**Style:** {style}\n"
            f"**Topics:** {topics}\n"
            f"**Tone:** {tone}\n\n"
            f"📰 Searching for real news to inspire ideas...",
            parse_mode='Markdown'
        )
        
        # Step 2: Search for real news
        news_articles = search_news(keywords, limit=8)
        
        # Step 3: Generate creative ideas
        await status_msg.edit_text(
            f"📊 *Channel Analysis*\n\n"
            f"**Theme:** {theme}\n"
            f"**Style:** {style}\n"
            f"**Topics:** {topics}\n"
            f"**Tone:** {tone}\n\n"
            f"💡 Generating creative post ideas...",
            parse_mode='Markdown'
        )
        
        ideas = generate_post_ideas(theme, style, topics, tone, news_articles)
        
        # Save to database
        save_analysis(user_id, posts_text, theme, keywords, style, topics, tone, ideas)
        context.user_data['last_theme'] = theme
        context.user_data['last_style'] = style
        context.user_data['last_topics'] = topics
        context.user_data['last_tone'] = tone
        context.user_data['last_ideas'] = ideas
        
        # Final response with analysis and ideas
        final_response = (
            f"📊 *Channel Analysis*\n\n"
            f"**Theme:** {theme}\n"
            f"**Style:** {style}\n"
            f"**Topics:** {topics}\n"
            f"**Tone:** {tone}\n\n"
            f"✨ *5 Creative Post Ideas:*\n\n"
            f"{ideas}"
        )
        
        await status_msg.edit_text(final_response, parse_mode='Markdown')
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")

async def more_ideas(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    last_data = get_last_analysis(user_id)
    
    if not last_data:
        await update.message.reply_text(
            "❌ You have no saved analysis.\n"
            "First send 5 post links to generate ideas."
        )
        return
    
    theme, keywords, style, topics, tone, previous_ideas = last_data
    
    status_msg = await update.message.reply_text(
        "🔄 Generating 5 more ideas...\n"
        "⏳ This may take 20-30 seconds"
    )
    
    try:
        new_ideas = generate_more_ideas(theme, style, topics, tone, previous_ideas)
        await status_msg.edit_text(
            f"✨ *5 More Creative Ideas*\n\n{new_ideas}",
            parse_mode='Markdown'
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")

async def clear_posts(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    clear_user_posts(user_id)
    await update.message.reply_text("✅ All saved posts cleared. You can start fresh!")

# ========== RUN ==========
def main():
    init_db()
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("clear", clear_posts))
    application.add_handler(CommandHandler("more", more_ideas))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    
    logger.info("Content Idea Bot started...")
    logger.info(f"Model: {MODEL_NAME}")
    logger.info(f"Ollama: {OLLAMA_URL}")
    
    if NEWS_API_KEY == "ВАШ_API_КЛЮЧ":
        logger.warning("⚠️ Please add your NewsAPI key!")
    
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            logger.info("✅ Ollama is running")
        else:
            logger.warning("⚠️ Ollama is not responding")
    except:
        logger.warning("⚠️ Ollama is not running! Start with: ollama serve")
    
    application.run_polling()

if __name__ == '__main__':
    main()