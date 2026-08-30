import io
import json
import random
import urllib.parse
from PIL import Image
import requests
import streamlit as st
import google.generativeai as genai

# مكتبات تصميم الـ PDF الاحترافي
from reportlab.lib.pagesizes import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
import arabic_reshaper
from bidi.algorithm import get_display

# =========================================================
# 1. إعدادات الواجهة والهوية البصرية
# =========================================================
st.set_page_config(
    page_title="Multi-Agent KDP Story Studio Pro",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main { background-color: #0B0E14; color: #E2E8F0; }
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3.2em;
        background: linear-gradient(90deg, #6366F1 0%, #A855F7 100%);
        color: white;
        font-weight: 700;
        border: none;
        transition: 0.3s;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(99, 102, 241, 0.4);
    }
    .agent-card {
        background-color: #131823;
        border: 1px solid #1E293B;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 15px;
    }
    .agent-log {
        background-color: #0F172A;
        border-left: 3px solid #38BDF8;
        padding: 10px;
        font-family: monospace;
        font-size: 12px;
        color: #38BDF8;
        border-radius: 0 6px 6px 0;
        margin-top: 8px;
    }
    .qc-success {
        color: #22C55E;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# =========================================================
# 2. حماية النظام
# =========================================================
PASSWORD_SECRET = "mourad1954#"

def check_auth():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        with st.sidebar:
            st.title("🔐 استوديو الوكلاء الذكي")
            pwd = st.text_input("كلمة المرور:", type="password")
            if st.button("دخول النظام"):
                if pwd == PASSWORD_SECRET:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("كلمة المرور غير صحيحة")
        return False
    return True

if not check_auth():
    st.stop()

# =========================================================
# 3. إعداد نموذج Gemini الأساسي
# =========================================================
def get_gemini_model(api_key):
    genai.configure(api_key=api_key)
    model_name = "models/gemini-1.5-flash"
    try:
        available = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
        for p in ["models/gemini-3.6-flash", "models/gemini-2.5-flash-latest", "models/gemini-1.5-flash", "gemini-1.5-flash"]:
            if p in available:
                model_name = p
                break
    except Exception:
        pass
    return genai.GenerativeModel(model_name)

# =========================================================
# 4. منظومة الوكلاء المتخصصين (Multi-Agent Pipeline)
# =========================================================

# الوكيل 1: كاتب السيناريو
def agent_writer(api_key, concept, lang, age, pages):
    model = get_gemini_model(api_key)
    prompt = f"""
    You are the Master Writer Agent for Children's Books. 
    Write an engaging, magical, and structured children's story based on:
    - Concept: {concept}
    - Language: {lang}
    - Age Group: {age}
    - Total Pages: {pages}
    
    Requirements:
    Write 2-4 captivating sentences per page with emotional depth and rhythm.
    Return strictly JSON format:
    {{
        "raw_pages": [
            {{"page_number": 1, "text": "..."}}
        ]
    }}
    """
    res = model.generate_content(prompt)
    raw = res.text.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(raw)

# الوكيل 2: المراجع والتدقيق
def agent_reviewer(api_key, story_data, lang):
    model = get_gemini_model(api_key)
    prompt = f"""
    You are the Chief Editor & KDP Quality Agent. Review the following draft story in {lang}.
    Polish the grammar, enhance vocabulary for children, create a catchy book title, subtitle, 2-paragraph HTML KDP description, and 7 powerful KDP search keywords.
    
    Draft: {json.dumps(story_data)}
    
    Return strictly JSON format matching this schema:
    {{
        "title": "Book Title",
        "subtitle": "Book Subtitle",
        "kdp_description": "Description text...",
        "keywords": ["kw1", "kw2", "kw3", "kw4", "kw5", "kw6", "kw7"],
        "pages": [
            {{"page_number": 1, "text": "Polished text..."}}
        ]
    }}
    """
    res = model.generate_content(prompt)
    raw = res.text.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(raw)

# الوكيل 3: هندسة الأوامر البصرية
def agent_prompt_engineer(api_key, story_data, char_desc, art_style):
    model = get_gemini_model(api_key)
    pages_text = json.dumps(story_data.get("pages", []))
    prompt = f"""
    You are the Master Prompt Engineer Agent for AI Image Generation (FLUX/Midjourney).
    For each page text provided below, create a highly detailed visual prompt.
    CRITICAL: You MUST include the exact character details ({char_desc}) and artistic style ({art_style}) in EVERY prompt to maintain strict character consistency.
    
    Pages: {pages_text}
    
    Return strictly JSON:
    {{
        "title": "{story_data.get('title', 'Children Storybook')}",
        "subtitle": "{story_data.get('subtitle', '')}",
        "kdp_description": "{story_data.get('kdp_description', '')}",
        "keywords": {json.dumps(story_data.get('keywords', []))},
        "pages_with_prompts": [
            {{"page_number": 1, "text": "...", "image_prompt": "Detailed prompt including {char_desc} and {art_style}"}}
        ]
    }}
    """
    res = model.generate_content(prompt)
    raw = res.text.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(raw)

# محرك توليد الصور مفتوح المصدر (FLUX.1)
def generate_image_flux(prompt_text, seed):
    try:
        clean_prompt = f"{prompt_text}, 8k, masterpiece, children's book illustration, vibrant colors"
        encoded = urllib.parse.quote(clean_prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&seed={seed}&model=flux&nologo=true"
        resp = requests.get(url, timeout=35)
        if resp.status_code == 200:
            return Image.open(io.BytesIO(resp.content))
    except Exception:
        pass
    return Image.new("RGB", (1024, 1024), color=(240, 240, 240))

# الوكيل 4: مراقبة الجودة والتدقيق البصري (Vision QC)
def agent_vision_qc(api_key, image_pil, expected_prompt):
    try:
        model = get_gemini_model(api_key)
        img_byte_arr = io.BytesIO()
        image_pil.save(img_byte_arr, format='PNG')
        img_bytes = img_byte_arr.getvalue()
        
        image_part = {"mime_type": "image/png", "data": img_bytes}
        
        qc_prompt = f"""
        You are the Visual Quality Control (QC) Agent. Evaluate if this generated image accurately matches the required scene description and character specifications.
        Required Description: {expected_prompt}
        
        Analyze the image composition, character presence, and art style.
        Reply strictly in JSON:
        {{
            "match": true,
            "score": 95,
            "feedback": "Passed QC evaluation"
        }}
        """
        response = model.generate_content([image_part, qc_prompt])
        raw = response.text.strip().replace("```json", "").replace("
