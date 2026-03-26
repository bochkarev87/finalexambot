# finalexambot

Content Idea Generator Bot

A Telegram bot that analyzes posts from your channel and generates content ideas using a local AI model.

Features:

Send a link to any public Telegram post — the bot saves the text

After 5 posts, it automatically analyzes the channel's theme and style

Generates 5 new post ideas

/more command — generates 5 more ideas

Completely free, runs locally

Requirements:

OS: Windows / macOS / Linux

Python 3.9 or higher

RAM: 8 GB (16 GB recommended)

Disk space: 10 GB free

Installation:

Install Python. Download from python.org and install. During installation, make sure to check "Add Python to PATH". Verify installation with: python --version

Install Ollama. Download from ollama.com and install. After installation, Ollama will run in the background.

Download the AI model. Open terminal and run: ollama pull llama3.2:3b. Wait for the download to complete (about 2-3 GB).

Create a Telegram bot. Open Telegram, find @BotFather, send /newbot, choose a name and username for your bot, copy the token. The token looks like 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz. I forgot to say that you also need NEWS_API TOKEN. So create him and put it in code.

Download the bot code. Create a folder, download the bot.py file or copy the code from the repository.

Install dependencies. In terminal run: pip install python-telegram-bot requests

Configure the token. Open bot.py in a text editor and replace TELEGRAM_TOKEN = "YOUR_BOT_TOKEN" with your actual token.

Running:

Start Ollama. In terminal run: ollama serve. Keep this window open.

Start the bot. Open a new terminal, navigate to the bot folder with cd path-to-folder, then run: python bot.py. You should see "Content Idea Bot started..."

Test the bot. Open Telegram, find your bot, send /start, send a link to any public post (e.g., https://t.me/durov/123), repeat 5 times. After the 5th post, the bot will generate ideas.

Bot Commands:
/start — welcome and instructions
/help — detailed instructions
/posts — show saved posts
/more — generate 5 more ideas
/clear — clear all saved posts

Usage Example: User sends 5 links to posts from a gaming channel. The bot analyzes the theme, style, key topics, and tone of voice, then outputs 5 new post ideas, such as: "Top 5 games of 2026 you might have missed", "How streamers make millions: a breakdown", "Flagship GPU comparison: is the upgrade worth it", and so on.

Troubleshooting:

ModuleNotFoundError: No module named 'telegram' — run pip install python-telegram-bot

Cannot connect to Ollama — make sure Ollama is running with ollama serve

Model not found — download the model with ollama pull llama3.2:3b

Bot does not respond — check that the correct token is inserted in the code

Cannot parse post — make sure the post is public. Private channels are not supported

Generation is too slow — the first run loads the model into memory; subsequent requests will be faster

Project Structure:
content-idea-bot/
├── bot.py # Main bot code
├── content_bot.db # Database (created automatically)
└── README.md # This instruction

Dependencies for requirements.txt:
python-telegram-bot
requests

Install dependencies via requirements.txt: pip install -r requirements.txt

License: MIT
