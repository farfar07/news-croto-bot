import os
import time
import feedparser
import requests
from huggingface_hub import login
from langchain_huggingface import HuggingFaceEndpoint
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

# === ENV ===
HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID", "-4891438477")
RSS_URL = os.getenv("RSS_URL", "https://news.google.com/rss/search?q=crypto+OR+bitcoin+OR+ethereum+war+OR+SEC+OR+ETF+OR+inflation+OR+hack&hl=en-US&gl=US&ceid=US:en")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 300))

# === HF AUTH ===
login(HUGGINGFACE_TOKEN)

llm = HuggingFaceEndpoint(
    repo_id="google/flan-t5-small",
    temperature=0.3,
    max_new_tokens=128
)

prompt_template = PromptTemplate(
    input_variables=["title", "summary"],
    template="""
Summarize this news for crypto impact.

Title: {title}
Summary: {summary}

Respond:
Summary: <short summary>
Tone: [bullish/bearish/neutral]
"""
)

seen_links = set()

CRITICAL_KEYWORDS = [
    "crash", "ban", "collapse", "fall", "shutdown",
    "lawsuit", "probe", "jail", "fraud", "freeze",
    "regulation", "regulatory action", "sell-off", "delist"
]

def fetch_articles():
    return feedparser.parse(RSS_URL).entries

def analyze_article(title, summary):
    prompt = prompt_template.format(title=title, summary=summary)
    return llm.invoke(prompt)

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {'chat_id': CHAT_ID, 'text': msg}
    requests.post(url, data=data)

def is_critical_bearish(summary_text, tone):
    summary_lower = summary_text.lower()
    return (
        tone.lower() == "bearish" and
        any(keyword in summary_lower for keyword in CRITICAL_KEYWORDS)
    )

print("🐻 Crypto Bearish Alert Bot running...")

while True:
    try:
        for article in fetch_articles():
            if article.link in seen_links:
                continue
            seen_links.add(article.link)

            title = article.title
            summary = article.get("summary", "")
            print(f"\n📰 {title}")
            result = analyze_article(title, summary)

            # Parse model output
            lines = result.strip().splitlines()
            parsed_summary = ""
            tone = ""
            for line in lines:
                if line.lower().startswith("summary:"):
                    parsed_summary = line.split(":", 1)[1].strip()
                elif line.lower().startswith("tone:"):
                    tone = line.split(":", 1)[1].strip()

            if is_critical_bearish(parsed_summary, tone):
                message = f"🚨 *CRITICAL BEARISH NEWS*\n📰 *{title}*\n🔗 {article.link}\n\n📉 {parsed_summary}"
                send_telegram(message)
                print("✅ Bearish alert sent!")
            else:
                print("ℹ️ Skipped (not critical bearish)")
    except Exception as e:
        print(f"⚠️ Error: {e}")
    time.sleep(CHECK_INTERVAL)
