import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from collections import Counter
from google import genai
from google.genai import types
import random
import feedparser
from datetime import datetime

# ----------------- PAGE CONFIG -----------------
st.set_page_config(
    page_title="Oakstead Finance - Agent Engagement Hub",
    page_icon="⚜️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------- STYLING -----------------
st.markdown("""
    <style>
        .main-title { font-size: 2.1rem; font-weight: 700; color: #0E1E38; margin-bottom: 0.2rem; }
        .subtitle { font-size: 1.05rem; color: #5A6E85; margin-bottom: 1.6rem; }
        .stButton>button { background-color: #0E1E38; color: white; border-radius: 6px; font-weight: 500; width: 100%; border: none; padding: 0.5rem 0; }
        .stButton>button:hover { background-color: #1B3A63; }
        .fca-badge { background-color: #F0F4F8; border-left: 4px solid #0E1E38; padding: 12px 16px; border-radius: 4px; font-size: 0.88rem; color: #2B3A4F; margin-bottom: 20px; }
        .news-card { background-color: #FAFBFC; padding: 16px; border-radius: 8px; border: 1px solid #E4E8ED; margin-bottom: 14px; }
        .news-title { font-size: 1.0rem; font-weight: 600; color: #0E1E38; margin: 4px 0; }
        .news-title a { color: #0E1E38; text-decoration: none; }
        .news-title a:hover { text-decoration: underline; }
        .news-meta { font-size: 0.78rem; color: #8B98A8; text-transform: uppercase; letter-spacing: 0.02em; }
        .comment-card { background-color: #FAFBFC; border: 1px solid #E4E8ED; border-radius: 8px; padding: 14px 16px; margin-bottom: 10px; }
        .comment-label { font-size: 0.75rem; color: #8B98A8; text-transform: uppercase; letter-spacing: 0.03em; margin-bottom: 4px; }
        .section-divider { border-top: 1px solid #E4E8ED; margin: 1.8rem 0; }
    </style>
""", unsafe_allow_html=True)

# ----------------- COMMENT LIBRARY (warm, human, design/atmosphere-led) -----------------
# These are genuine reaction-style comments for engaging with estate agents' listing
# photos on Instagram. Deliberately no mention of mortgages, rates, or finance —
# this is relationship-building, not financial promotion.
ENGAGEMENT_LIBRARY = {
    "Design & Execution": [
        "Excellent execution on this one",
        "Truly beautiful design throughout",
        "The finish on this is spot on",
        "Every detail here feels considered",
        "Beautifully put together, this",
        "Lovely attention to detail",
        "The styling is exactly right",
        "Really well executed space",
        "Such a considered layout",
        "The proportions work so well here",
    ],
    "Atmosphere & Feel": [
        "The atmosphere in these photos is lovely",
        "Such a warm feel to this one",
        "Really inviting space",
        "You can feel the light in these",
        "Such a calm, considered home",
        "This looks like a lovely place to live",
        "Real warmth to this",
        "Feels like a proper family home",
        "Such a welcoming feel throughout",
        "The light in these rooms is gorgeous",
    ],
    "Local / Postcode": [
        "SW11 never disappoints",
        "Battersea just keeps getting better",
        "Clapham living at its finest",
        "Putney riverside really is unbeatable",
        "Fulham does it again",
        "Wandsworth's quietly having a moment",
        "Great pocket of Battersea, this",
        "Prime spot, that",
        "Streets from the common too, ideal",
        "Can't beat this part of SW London",
    ],
    "Feature-Specific": [
        "That garden is lovely",
        "Period features done really well",
        "Love a good bay window",
        "That extension has been done beautifully",
        "South-facing garden is a real find",
        "High ceilings never get old",
        "That's a proper family kitchen",
        "Off-street parking too, that's rare round here",
        "Loft conversion looks seamless",
        "Original fireplace is a lovely touch",
    ],
    "Congratulations / Process": [
        "Congratulations on the instruction",
        "Great get, well done",
        "Lovely addition to the portfolio",
        "This one won't hang around",
        "Well deserved, lovely listing",
        "Brilliant work on this one",
        "Imagine the viewings will book up fast",
        "Nicely presented, this'll go quickly",
        "Well priced too, from what I can see",
        "Onwards and upwards",
    ],
    "Community / Banter": [
        "Right, who's viewing this with me",
        "Adding this to the dream list",
        "Now this is a Monday listing",
        "Reconsidering my own house right now",
        "Someone's about to get very lucky",
        "Taking notes for future inspiration",
        "Great team, great result",
        "Always a pleasure seeing your listings",
        "This is a proper find",
        "Good to see this on the market",
    ],
}

DEFAULT_COMPETITORS = [
    "https://www.spf.co.uk/blog/",
    "https://www.alexanderhall.co.uk/mortgage-news-advice/",
    "https://www.johncharcol.co.uk/news-and-guides/",
    "https://www.ennessglobal.com/news-insights/"
]

# Live RSS/Atom feeds for UK mortgage & property market news
NEWS_FEEDS = {
    "Mortgage Strategy": "https://www.mortgagestrategy.co.uk/feed/",
    "Financial Reporter": "https://www.financialreporter.co.uk/rss/news",
    "Mortgage Solutions": "https://www.mortgagesolutions.co.uk/feed/",
    "Property Industry Eye": "https://propertyindustryeye.com/feed/",
}

# ----------------- HELPERS -----------------

@st.cache_data(ttl=900, show_spinner=False)  # cache for 15 minutes
def fetch_rss_news():
    """Fetches live articles from real UK mortgage/property RSS feeds using feedparser,
    which is far more tolerant of real-world feed quirks than manual XML parsing."""
    news_items = []
    errors = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; OaksteadNewsBot/1.0)"}

    for source, url in NEWS_FEEDS.items():
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
            if parsed.bozo and not parsed.entries:
                errors.append(source)
                continue
            for entry in parsed.entries[:4]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "#")
                published = entry.get("published", entry.get("updated", ""))
                pub_display = ""
                if published:
                    try:
                        pub_display = pd.to_datetime(published).strftime("%d %b %Y")
                    except Exception:
                        pub_display = published[:16]
                if title:
                    news_items.append({
                        "source": source,
                        "title": title,
                        "link": link,
                        "published": pub_display,
                    })
        except Exception:
            errors.append(source)
            continue

    # Sort newest first where we have a parseable date
    def sort_key(item):
        try:
            return pd.to_datetime(item["published"])
        except Exception:
            return pd.Timestamp.min

    news_items.sort(key=sort_key, reverse=True)
    return news_items, errors


def get_gemini_client():
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        return genai.Client(api_key=api_key) if api_key else None
    except Exception:
        return None


def call_gemini(client, model, contents):
    response = client.models.generate_content(model=model, contents=contents)
    return response.text


def generate_engagement_comment(client, listing_context, image_bytes=None):
    """Generates a short, genuine-sounding Instagram comment praising a listing's
    design, execution or atmosphere. Deliberately has nothing to do with finance,
    mortgages, or Oakstead — this is warm relationship-building with agents,
    not a financial promotion, so it stays well clear of FCA content rules."""
    prompt = f"""
You're writing a short, genuine Instagram comment from James at Oakstead Finance, a mortgage
broker in SW London, on a local estate agent's property listing photo. The goal is simply to
be warm, human, and supportive of the agent's work — building a good relationship, nothing more.

Tone: calm, warm, plain English. Sounds like someone who actually looked at the photos and has
something specific and real to say — about the design, the execution, the atmosphere, the light,
or the setting. Never salesy, never hype, no exclamation marks, no emojis, no finance jargon.
Do NOT mention mortgages, rates, products, advice, or Oakstead in any way — this is purely a
compliment on the property or the agent's work.

Listing details: {listing_context if listing_context.strip() else "No extra detail given — keep it general but genuine."}

Write ONE comment, max 18 words. Output only the comment text, nothing else.
"""
    try:
        payload = []
        if image_bytes:
            payload.append(types.Part.from_bytes(data=image_bytes, mime_type="image/png"))
        payload.append(prompt)
        return call_gemini(client, "gemini-3.5-flash", payload).strip().strip('"')
    except Exception:
        return "Really beautiful execution on this one — the light in these photos is lovely."


def extract_blog_keywords(urls):
    headers = {"User-Agent": "Mozilla/5.0"}
    scraped_headings = []
    for url in urls:
        if not url.strip():
            continue
        try:
            r = requests.get(url, headers=headers, timeout=6)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for heading in soup.find_all(["h1", "h2", "h3"]):
                    text = heading.get_text().strip()
                    if len(text) > 15:
                        scraped_headings.append(text)
        except Exception:
            pass

    if not scraped_headings:
        return [], []

    all_words = []
    stopwords = {"the", "and", "to", "of", "in", "for", "on", "a", "with", "is", "your", "how", "what", "you", "are"}
    for heading in scraped_headings:
        clean = re.sub(r"[^\w\s]", "", heading.lower())
        for word in clean.split():
            if word not in stopwords and len(word) > 4:
                all_words.append(word)
    return scraped_headings, Counter(all_words).most_common(6)


# ----------------- HEADER -----------------
st.markdown("<div class='main-title'>⚜️ Oakstead Agent Engagement Hub</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Warm, genuine engagement with local agents — plus a live view of the market</div>", unsafe_allow_html=True)

st.markdown("""
    <div class='fca-badge'>
        <b>Note:</b> Everything here is relationship-building content (comments, drafts, market news) —
        no rates, products, or advice are generated. Always review before posting, and check anything
        you're unsure about with James before it goes live.
    </div>
""", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["💬 Instagram Engagement", "📰 Live Market News", "📊 Competitor Content Ideas"])

# --- TAB 1: INSTAGRAM ENGAGEMENT ---
with tab1:
    st.subheader("Quick comment library")
    st.caption("Pick a category and location, then grab a few options to copy across.")

    col_filters, col_refresh = st.columns([4, 1])
    with col_filters:
        f1, f2 = st.columns(2)
        with f1:
            category_select = st.selectbox("Category", list(ENGAGEMENT_LIBRARY.keys()))
        with f2:
            loc_options = ["General", "SW11 (Battersea)", "Clapham", "Putney", "Fulham", "Wandsworth"]
            loc_select = st.selectbox("Location flavour", loc_options)
    with col_refresh:
        st.markdown("<div style='height: 1.85rem'></div>", unsafe_allow_html=True)
        roll_matrix = st.button("Shuffle options")

    loc_map = {
        "SW11 (Battersea)": "Great pocket of Battersea, this",
        "Clapham": "Clapham living at its finest",
        "Putney": "Putney riverside really is unbeatable",
        "Fulham": "Fulham does it again",
        "Wandsworth": "Wandsworth's quietly having a moment",
        "General": "Prime spot, that",
    }

    pool = ENGAGEMENT_LIBRARY[category_select]
    if "shuffle_seed" not in st.session_state:
        st.session_state.shuffle_seed = 0
    if roll_matrix:
        st.session_state.shuffle_seed += 1

    rnd = random.Random(st.session_state.shuffle_seed)
    selected_samples = rnd.sample(pool, min(len(pool), 3))

    cc1, cc2 = st.columns(2)
    with cc1:
        st.markdown("<div class='comment-card'><div class='comment-label'>Local highlight</div>" + loc_map[loc_select] + "</div>", unsafe_allow_html=True)
        st.code(loc_map[loc_select], language="text")
    with cc2:
        st.markdown(f"<div class='comment-card'><div class='comment-label'>{category_select}</div>" + selected_samples[0] + "</div>", unsafe_allow_html=True)
        st.code(selected_samples[0], language="text")

    cc3, cc4 = st.columns(2)
    with cc3:
        st.markdown(f"<div class='comment-card'><div class='comment-label'>{category_select}</div>" + selected_samples[1] + "</div>", unsafe_allow_html=True)
        st.code(selected_samples[1], language="text")
    with cc4:
        st.markdown(f"<div class='comment-card'><div class='comment-label'>{category_select}</div>" + selected_samples[2] + "</div>", unsafe_allow_html=True)
        st.code(selected_samples[2], language="text")

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

    st.subheader("Custom comment for a specific listing")
    st.caption("Drop in a screenshot or a few details about the listing, and get a one-off genuine comment tailored to it.")

    col_input, col_output = st.columns([1, 1])
    with col_input:
        uploaded_file = st.file_uploader("Listing screenshot (optional)", type=["png", "jpg", "jpeg"])
        pasted_text = st.text_area(
            "Listing details (optional)",
            height=100,
            placeholder="e.g. 4 bed Victorian conversion in Northcote Road, big south-facing garden, exposed brick kitchen"
        )
        run_ai = st.button("Generate custom comment")

    with col_output:
        if run_ai:
            client = get_gemini_client()
            if not client:
                st.warning("No GEMINI_API_KEY found in secrets — add one to enable custom comment generation.")
            else:
                with st.spinner("Writing a comment..."):
                    img_bytes = uploaded_file.read() if uploaded_file else None
                    ai_comment = generate_engagement_comment(client, pasted_text, img_bytes)
                st.markdown("<div class='comment-card'><div class='comment-label'>Custom comment</div>" + ai_comment + "</div>", unsafe_allow_html=True)
                st.code(ai_comment, language="text")
        else:
            st.info("Add a screenshot or a few details on the left, then generate a one-off comment here.")

# --- TAB 2: LIVE MARKET NEWS ---
with tab2:
    st.subheader("Live UK mortgage & property market news")
    st.caption("Pulled directly from live industry RSS feeds — refreshes every 15 minutes.")

    news_items, errors = fetch_rss_news()

    if not news_items:
        st.error(
            "Couldn't reach any of the news feeds right now — this usually means the site is "
            "temporarily down or blocking automated requests, not that anything is wrong with the app. "
            "Try refreshing in a few minutes."
        )
    else:
        if errors:
            st.caption(f"Note: couldn't reach {', '.join(errors)} this time — showing the rest.")

        col_left_news, col_right_news = st.columns(2)
        for index, article in enumerate(news_items):
            target_col = col_left_news if index % 2 == 0 else col_right_news
            with target_col:
                meta = article["source"] + (f" · {article['published']}" if article["published"] else "")
                st.markdown(f"""
                    <div class='news-card'>
                        <span class='news-meta'>{meta}</span>
                        <div class='news-title'><a href="{article['link']}" target="_blank">{article['title']}</a></div>
                    </div>
                """, unsafe_allow_html=True)

    if st.button("Refresh news now"):
        fetch_rss_news.clear()
        st.rerun()

# --- TAB 3: COMPETITOR CONTENT IDEAS ---
with tab3:
    st.subheader("Competitor content gaps & post ideas")
    st.write("See what themes other SW London-relevant brokers are writing about, and get compliant post ideas for Oakstead.")

    comp_urls = st.text_area("Tracked sources", value="\n".join(DEFAULT_COMPETITORS), height=100)
    run_tracker = st.button("Analyse trends & generate ideas")

    if run_tracker:
        with st.spinner("Scraping competitor journals..."):
            headings, keywords = extract_blog_keywords(comp_urls.split("\n"))

        if not headings:
            st.warning("Couldn't extract headings from those sources right now — they may be blocking automated requests. Try again shortly or swap in different URLs.")
        else:
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.markdown("#### Tracked market keywords")
                df_keys = pd.DataFrame(keywords, columns=["Theme", "Density"])
                st.bar_chart(df_keys.set_index("Theme"))
            with col_g2:
                st.markdown("#### Tracked headlines")
                for h in headings[:4]:
                    st.markdown(f"- *{h}*")

            st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
            st.markdown("### 💡 Post ideas for Oakstead Finance")

            client = get_gemini_client()
            if client:
                strategy_prompt = f"""
You write plain-English, warm, non-salesy content ideas for Oakstead Finance, an independent
mortgage broker in SW London (Battersea, Clapham, Wandsworth, Fulham, Putney). The brand voice
is calm, considered, honest — never hype, no exclamation marks, no guaranteed outcomes or
specific rates.

Based on these competitor content themes: {keywords}, suggest 3 Instagram post ideas for
Oakstead. Keep them grounded in real client situations (first-time buyers, self-employed income,
complex cases) rather than luxury/HNW jargon unless the theme specifically points that way.
Do not include any interest rates, approval odds, or lending criteria.
"""
                with st.spinner("Drafting ideas..."):
                    try:
                        ideas = call_gemini(client, "gemini-3.5-flash", strategy_prompt)
                        st.markdown(ideas)
                    except Exception:
                        st.warning("Gemini API call failed — check your GEMINI_API_KEY and try again.")
            else:
                st.info("Add a GEMINI_API_KEY in your Streamlit secrets to unlock post idea generation.")
