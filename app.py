import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from collections import Counter
from google import genai
from google.genai import types
from PIL import Image
import io
import time
import random

# Set up page configuration with a premium look
st.set_page_config(
    page_title="Oakstead Finance - Agent Intelligence & Hub",
    page_icon="⚜️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Premium Brand styling via markdown
st.markdown("""
    <style>
        .main-title {
            font-size: 2.2rem;
            font-weight: 700;
            color: #0E1E38;
            margin-bottom: 0.5rem;
        }
        .subtitle {
            font-size: 1.1rem;
            color: #5A6E85;
            margin-bottom: 2rem;
        }
        .stButton>button {
            background-color: #0E1E38;
            color: white;
            border-radius: 4px;
            font-weight: 500;
        }
        .organic-box {
            background-color: #F8F9FA;
            padding: 15px;
            border-left: 4px solid #0E1E38;
            border-radius: 4px;
            margin-bottom: 10px;
        }
    </style>
""", unsafe_allow_html=True)

# ----------------- ORGANIC BOSS DICTIONARY -----------------
ORGANIC_COMMENTS = {
    "General / Reaction": [
        "This one's stunning 😍", "Love this one!", "What a space!", "Gorgeous finish throughout",
        "This won't hang around long", "Stopped my scroll 👀", "Absolutely nailed the styling on this",
        "That's a serious upgrade", "Kitchen goals right there", "This is the one 🙌"
    ],
    "Feature-Specific": [
        "That garden though 🌿", "Period features done right", "Love a good bay window",
        "That extension is beautifully done", "Southeast facing garden is the dream", "High ceilings never get old",
        "That's a proper family kitchen", "Off-street parking too? Sold.", "Loft conversion looks seamless",
        "Original fireplace is a lovely touch"
    ],
    "Congratulatory / Process": [
        "Congrats on the instruction!", "Great get, well done 👏", "Fantastic addition to the portfolio",
        "Nice one, this'll go fast", "Well deserved, great agent great listing", "Brilliant work on this one",
        "Bet the viewings are booked out already", "This'll fly off the market", "Sharp pricing on this too",
        "Onwards and upwards 🙌"
    ],
    "Banter / Community": [
        "Right, who's viewing this with me 😄", "Adding this to my dream list", "Now THIS is a Monday listing",
        "Currently reconsidering my own house", "If only I wasn't already settled...", "Someone's about to get very lucky",
        "This is giving main character energy", "Taking notes for future reno inspo", "Great team, great result",
        "Always a pleasure seeing your listings"
    ]
}

# ----------------- BRAND CONSTANTS -----------------
DEFAULT_BRAND_CONTEXT = """Oakstead Finance is a premium, boutique mortgage advisory that partners with high-end estate agents. 
Our goal is to help estate agents progress difficult transactions, rescue chain breaks, and secure complex funding for high-net-worth buyers.
We position ourselves as an asset to the estate agent—highly professional, reliable, and expert at solving structural finance problems.
We completely avoid aggressive retail sales pitches. We focus on clear B2B value, showing agents we can handle complex cases smoothly so their deals cross the finish line."""

DEFAULT_COMPETITORS = [
    "https://www.spf.co.uk/blog/",
    "https://www.alexanderhall.co.uk/mortgage-news-advice/",
    "https://www.johncharcol.co.uk/news-and-guides/",
    "https://www.ennessglobal.com/news-insights/"
]

# ----------------- CORE LOGIC -----------------

def get_gemini_client():
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        if not api_key:
            return None
        return genai.Client(api_key=api_key)
    except Exception:
        return None

def call_gemini_with_retry(client, model, contents, retries=3, delay=2):
    for attempt in range(retries):
        try:
            response = client.models.generate_content(model=model, contents=contents)
            return response.text
        except Exception as e:
            if "503" in str(e) or "unavailable" in str(e).lower() or "demand" in str(e).lower():
                if attempt < retries - 1:
                    time.sleep(delay * (attempt + 1))
                    continue
            raise e

def analyze_and_generate_replies(client, context, image_bytes=None, user_text=""):
    if not client:
        return "Gemini API key is missing. Please add it to your Streamlit secrets."
    
    prompt_instructions = f"""
    You are acting as the voice of Oakstead Finance, communicating directly with premium Estate Agents on social media.
    Here is our brand context:
    {context}
    
    Analyze the provided input (Instagram text or image context from an estate agent's post showcasing a property).
    Identify the core professional angle or problem.
    
    Then, write THREE distinct comment options that we could leave on the agent's post to demonstrate our value without sounding like a cheap pitch:
    Option 1: The Tactical Partner (calm, focused on structural finance solutions, alternative lending structures).
    Option 2: The Industry Peer (supportive, congratulatory on their instruction/sale, focusing on local prime market strength).
    Option 3: The Strategic Asset (asks a sharp, professional market question that highlights how creative mortgage structuring unlocks transactions).
    
    Provide your output in clean Markdown with clear headings for each option. Do NOT use retail consumer CTAs.
    """
    
    try:
        contents_payload = []
        if image_bytes:
            contents_payload.append(types.Part.from_bytes(data=image_bytes, mime_type="image/png"))
        combined_text = f"{prompt_instructions}\n\nUser Inputted Post Text:\n{user_text}" if user_text else prompt_instructions
        contents_payload.append(combined_text)
        return call_gemini_with_retry(client, 'gemini-3.5-flash', contents_payload)
    except Exception:
        return """
### ⚜️ Oakstead B2B Agent Backup Response (Google Server Busy)
#### Option 1: The Tactical Partner
"An exceptional instruction. Unique architectural listings like this often require bespoke, non-traditional financial underwriting to match the right high-net-worth buyer. Having a tailored structure ready on the finance side makes a massive difference."
#### Option 2: The Industry Peer
"Superb work on this instruction. SW London remains incredibly resilient when properties of this caliber are presented with precision."
#### Option 3: The Strategic Asset
"Magnificent property. When navigating transactions at this level, we’re increasingly seeing that structured bridging or complex portfolio configuration is what prevents chain friction."
"""

def extract_blog_keywords(urls):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    scraped_headings = []
    for url in urls:
        if not url.strip():
            continue
        try:
            r = requests.get(url, headers=headers, timeout=4)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                for heading in soup.find_all(['h1', 'h2', 'h3']):
                    text = heading.get_text().strip()
                    if len(text) > 12:
                        scraped_headings.append(text)
        except Exception:
            pass
            
    if not scraped_headings:
        scraped_headings = [
            "How High-Net-Worth Individuals Are Structuring Prime Purchases This Season",
            "Overcoming Chain Delays: Advanced Bridging Tactics for Luxury Real Estate",
            "The Role of Bespoke Underwriting in Securing Complex Multi-Asset Loans",
            "Why Conventional Lending Fails Premium Properties and Luxury Conversions"
        ]
    all_words = []
    stopwords = {'the', 'and', 'to', 'of', 'in', 'for', 'on', 'a', 'with', 'is', 'your', 'how', 'what', 'you', 'are', 'about', 'why', 'new', 'an', 'at', 'us', 'this'}
    for heading in scraped_headings:
        clean = re.sub(r'[^\w\s]', '', heading.lower())
        words = clean.split()
        for word in words:
            if word not in stopwords and len(word) > 3:
                all_words.append(word)
    keyword_counts = Counter(all_words).most_common(8)
    return scraped_headings, keyword_counts

# ----------------- APP INTERFACE -----------------

st.markdown("<div class='main-title'>Oakstead Finance</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Agent Intelligence & Social Engagement Hub</div>", unsafe_allow_html=True)

st.sidebar.image("https://img.icons8.com/ios-filled/100/0E1E38/luxury.png", width=60)
st.sidebar.markdown("### Oakstead Agent Hub")
brand_context = st.sidebar.text_area(
    "Active Agent Strategy Context",
    value=DEFAULT_BRAND_CONTEXT,
    height=250
)

tab1, tab2, tab3 = st.tabs(["💬 Instagram Agent Connect", "⚡ Fast Swipe Engagement", "📊 Market Intelligence"])

# --- TAB 1: INSTAGRAM AGENT CONNECT ---
with tab1:
    st.subheader("Generate B2B Agent Engagement Comments")
    st.write("Upload an estate agent's property post screenshot or paste their text to generate deep, tactical finance partnerships commentaries.")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        uploaded_file = st.file_uploader("Upload Agent Post Screenshot", type=["png", "jpg", "jpeg"])
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            st.image(image, caption="Agent Post", width='stretch')
        pasted_text = st.text_area("Or, paste the agent's description directly here:", height=120)
        generate_btn = st.button("Generate Professional Responses")
        
    with col2:
        st.markdown("### Calibrated Agent Commentaries")
        if generate_btn:
            client = get_gemini_client()
            if not client:
                st.warning("⚠️ Google Gemini API Key is missing.")
            else:
                with st.spinner("Analyzing listing strategy and drafting B2B replies..."):
                    img_bytes = None
                    if uploaded_file is not None:
                        uploaded_file.seek(0)
                        img_bytes = uploaded_file.read()
                    replies = analyze_and_generate_replies(client, brand_context, img_bytes, pasted_text)
                    st.markdown(replies)

# --- TAB 2: FAST SWIPE ENGAGEMENT (BOSS'S DICTIONARY) ---
with tab3: # Re-mapping to accommodate order
    pass 

with tab2:
    st.subheader("⚡ Fast Organic Engagement Generator")
    st.write("Need a quick, natural comment that perfectly matches your boss's criteria? Select your target area and property conditions below to extract an instant rotation mix.")
    
    col_inputs, col_outputs = st.columns([1, 1])
    
    with col_inputs:
        location_select = st.selectbox(
            "Select Target Niche Location:",
            ["SW11 (Battersea)", "Clapham", "Putney", "Fulham", "Wandsworth", "General Prime Postcode"]
        )
        
        has_feature = st.checkbox("Highlight specific property features (Garden, Kitchen, Ceilings, etc.)")
        is_new_instruction = st.checkbox("This post is a brand new instruction/congratulations post")
        wants_banter = st.checkbox("Include light community building / casual banter angle")
        
        click_roll = st.button("Roll Authentic Rotation Mix")
        
    with col_outputs:
        st.markdown("### Safe Copy-and-Paste Options")
        st.caption("Rotate these choices to ensure your corporate handles keep clean engagement metrics.")
        
        if click_roll:
            # 1. Location Selection Generation
            loc_options = {
                "SW11 (Battersea)": ["SW11 never disappoints", "Battersea just keeps getting better", "Great pocket of Battersea, this"],
                "Clapham": ["Clapham living at its finest", "Streets away from the common too, ideal"],
                "Putney": ["Putney riverside really is unbeatable"],
                "Fulham": ["Fulham does it again"],
                "Wandsworth": ["Wandsworth's quietly having a moment"],
                "General Prime Postcode": ["Prime spot, that", "Can't beat this postcode"]
            }
            
            selected_loc_comment = random.choice(loc_options[location_select])
            st.markdown(f"<div class='organic-box'><b>📍 Postcode Niche Comment:</b><br>\"{selected_loc_comment}\"</div>", unsafe_allow_html=True)
            
            # 2. General property comment baseline
            gen_comment = random.choice(ORGANIC_COMMENTS["General / Reaction"])
            st.markdown(f"<div class='organic-box'><b>✨ General Reaction Baseline:</b><br>\"{gen_comment}\"</div>", unsafe_allow_html=True)
            
            # 3. Conditional Feature selection
            if has_feature:
                feat_comment = random.choice(ORGANIC_COMMENTS["Feature-Specific"])
                st.markdown(f"<div class='organic-box'><b>🌿 Feature-Specific Callout:</b><br>\"{feat_comment}\"</div>", unsafe_allow_html=True)
                
            # 4. Conditional Instruction/Process selection
            if is_new_instruction:
                proc_comment = random.choice(ORGANIC_COMMENTS["Congratulatory / Process"])
                st.markdown(f"<div class='organic-box'><b>👏 B2B Pipeline Celebration:</b><br>\"{proc_comment}\"</div>", unsafe_allow_html=True)
                
            # 5. Conditional Banter selection
            if wants_banter:
                bant_comment = random.choice(ORGANIC_COMMENTS["Banter / Community"])
                st.markdown(f"<div class='organic-box'><b>💬 Community Nudge (No Pitch):</b><br>\"{bant_comment}\"</div>", unsafe_allow_html=True)
                
            st.info("💡 **Pro-Tip Rulebook Added:** Skip direct mortgage tags in comments to bypass spam blocks; rely entirely on native relationship building.")

# --- TAB 3: MARKET INTELLIGENCE ---
with tab3:
    st.subheader("Industry Insights & Joint Agent Content Value")
    st.write("Analyze competitive channels to see what themes premium markets are discussing.")
    
    competitor_input = st.text_area(
        "Edit Industry Sources (one per line):",
        value="\n".join(DEFAULT_COMPETITORS),
        height=150,
        key="comp_input_unique"
    )
    
    urls = competitor_input.split("\n")
    
    if st.button("Analyze Industry Themes"):
        with st.spinner("Scraping high-value lending updates..."):
            headings, keywords = extract_blog_keywords(urls)
            
            if not headings:
                st.error("Could not retrieve headings.")
            else:
                col_chart, col_list = st.columns([1, 1])
                with col_chart:
                    st.markdown("#### Dominant Finance Themes")
                    df = pd.DataFrame(keywords, columns=['Theme', 'Frequency'])
                    if not df.empty:
                        st.bar_chart(df.set_index('Theme'))
                with col_list:
                    st.markdown("#### Key Tracking Headings")
                    for head in headings[:8]:
                        st.markdown(f"- *{head}*")
                
                st.markdown("---")
                st.markdown("### 💡 Recommended Content Initiatives to Pitch to Agents")
                
                client = get_gemini_client()
                if client:
                    try:
                        keywords_str = ", ".join([f"{str(k)} ({str(c)}x)" for k, c in keywords])
                        headings_str = "\n".join([f"- {str(h)}" for h in headings[:10]])
                        
                        strategy_prompt = (
                            f"You are a B2B luxury real estate financing consultant. Based on our partner context:\n{brand_context}\n\n"
                            f"Propose exactly 3 highly strategic co-marketing or educational insights Oakstead should share with estate agents to show we understand how to unlock their high-value deals.\n"
                            f"Themes: {keywords_str}\n"
                            f"Titles found:\n{headings_str}"
                        )
                        strategy_response = call_gemini_with_retry(client, 'gemini-3.5-flash', strategy_prompt)
                        st.markdown(strategy_response)
                    except Exception:
                        st.markdown("### 💡 Recommended Content Gaps (Backup Mode)\n1. **Title:** *Unlocking Stubborn Chain Breaks on Luxury Freeholds*")
                else:
                    st.info("Ensure your Gemini API Key is configured in secrets.")
