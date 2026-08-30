import io
import json
import random
import re
import urllib.parse
from PIL import Image
import requests
import streamlit as st
import google.generativeai as genai

# مكتبات إخراج الـ PDF
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
# 1. إعدادات الواجهة (Modern UI & Theme)
# =========================================================
st.set_page_config(
    page_title="AI StoryCraft Studio Pro | KDP Suite",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main { background-color: #0E1117; color: #FAFAFA; }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
        background: linear-gradient(90deg, #4F46E5 0%, #7C3AED 100%);
        color: white;
        font-weight: bold;
        border: none;
        transition: 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(124, 58, 237, 0.4);
    }
    .kdp-box {
        background-color: #1E232F;
        border: 1px solid #2E3648;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 12px;
    }
    .prompt-preview {
        background-color: #131720;
        border-left: 3px solid #10B981;
        padding: 8px 12px;
        font-family: monospace;
        font-size: 11px;
        color: #94A3B8;
        border-radius: 0 6px 6px 0;
        margin-top: 5px;
    }
</style>
""", unsafe_allow_html=True)

# =========================================================
# 2. نظام الدخول والحماية
# =========================================================
PASSWORD_SECRET = "mourad1954#"

def check_authentication():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        with st.sidebar:
            st.title("🔐 استوديو KDP الاحترافي")
            pwd = st.text_input("أدخل كلمة المرور الخاصة:", type="password")
            if st.button("تسجيل الدخول"):
                if pwd == PASSWORD_SECRET:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("كلمة المرور غير صحيحة")
        return False
    return True

if not check_authentication():
    st.stop()

# =========================================================
# 3. محركات الذكاء الاصطناعي ومعالجة البيانات
# =========================================================

def parse_json_safely(raw_text):
    """استخراج كائن JSON بشكل نظيف مهما كانت مخرجات الموديل"""
    try:
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception:
        pass
    clean = raw_text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean)

def get_active_model(api_key):
    genai.configure(api_key=api_key)
    priority_list = [
        "models/gemini-3.6-flash",
        "gemini-3.6-flash",
        "models/gemini-2.5-flash-latest",
        "models/gemini-1.5-flash",
        "gemini-1.5-flash"
    ]
    try:
        available = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
        for p in priority_list:
            if p in available:
                return genai.GenerativeModel(p)
        if available:
            return genai.GenerativeModel(available[0])
    except Exception:
        pass
    return genai.GenerativeModel("models/gemini-1.5-flash")

def generate_complete_storybook(api_key, concept, char_desc, style_choice, lang, age, pages_num):
    """وكيل ذكي مدمج ينفذ السرد، التدقيق، وهندسة الأوامر في خطوة موحدة وموثوقة"""
    model = get_active_model(api_key)
    
    prompt = f"""
    You are an elite Children's Book Author, Editor, and Art Director for Amazon KDP Bestsellers.
    Generate a complete, high-quality storybook based strictly on the parameters below.

    Parameters:
    - Language: {lang}
    - Age Group: {age}
    - Total Pages: {pages_num}
    - Main Character Visual Description: {char_desc}
    - Artistic Style: {style_choice}
    - Concept: {concept}

    Guidelines:
    1. Write an engaging, emotionally warm story with 2-4 rhyming or lyrical sentences per page in {lang}.
    2. Ensure the main character's exact traits ({char_desc}) are explicitly repeated in EVERY image prompt for visual consistency.
    3. Art prompts MUST specify character actions, background environment, lighting, and style ({style_choice}).

    Output strictly in valid JSON format:
    {{
        "title": "Main Book Title in {lang}",
        "subtitle": "Subtitle in {lang}",
        "kdp_description": "Compelling 2-paragraph HTML listing description",
        "keywords": ["7 high-traffic KDP search keywords"],
        "pages": [
            {{
                "page_number": 1,
                "text": "Narrative paragraph in {lang}",
                "image_prompt": "Prompt for page 1 including {char_desc}, setting, {style_choice}"
            }}
        ]
    }}
    """
    response = model.generate_content(prompt)
    return parse_json_safely(response.text)

def generate_page_image(prompt_text, seed_val):
    """محرك توليد الرسوم مفتوح المصدر (FLUX.1) مع حماية ضد انقطاع الشبكة"""
    try:
        enhanced = f"{prompt_text}, 8k, masterpiece, children's storybook illustration, vibrant studio lighting, crisp edges"
        encoded_prompt = urllib.parse.quote(enhanced)
        url = f"[https://image.pollinations.ai/prompt/](https://image.pollinations.ai/prompt/){encoded_prompt}?width=1024&height=1024&seed={seed_val}&model=flux&nologo=true"
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            return Image.open(io.BytesIO(resp.content))
    except Exception:
        pass
    # صورة بديلة متدرجة الألوان في حال بطء الشبكة
    return Image.new("RGB", (1024, 1024), color=(250, 245, 235))

def format_text_arabic(text):
    try:
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text

# =========================================================
# 4. محرك الـ PDF الاحترافي لـ Amazon KDP (8.5 × 8.5 إنش)
# =========================================================
def build_production_pdf(story_data, images_map, target_lang):
    buffer = io.BytesIO()
    size = 8.5 * inch
    c = canvas.Canvas(buffer, pagesize=(size, size))
    
    styles = getSampleStyleSheet()
    story_style = ParagraphStyle(
        'StoryTextStyle',
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=19,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1E293B")
    )
    
    # 1. الغلاف (Cover)
    c.setFillColor(colors.HexColor("#FFFDF9"))
    c.rect(0, 0, size, size, fill=1, stroke=0)
    
    c.setFillColor(colors.HexColor("#4F46E5"))
    c.setFont("Helvetica-Bold", 24)
    raw_title = story_data.get('title', 'Children Storybook')
    cover_title = format_text_arabic(raw_title) if "العربية" in target_lang else raw_title
    c.drawCentredString(size / 2, size - 1.1 * inch, cover_title)
    
    # استخدام صورة الصفحة الأولى كغلاف
    if 1 in images_map and images_map[1] is not None:
        reader = ImageReader(images_map[1])
        c.drawImage(reader, 1.25 * inch, 2.2 * inch, width=6 * inch, height=4.8 * inch, preserveAspectRatio=True)
        
    c.setFillColor(colors.HexColor("#64748B"))
    c.setFont("Helvetica", 10)
    c.drawCentredString(size / 2, 1.1 * inch, "Created with AI StoryCraft Studio • KDP Edition")
    c.showPage()
    
    # 2. الصفحات الداخلية (Interior)
    for p in story_data.get("pages", []):
        num = p.get("page_number", 1)
        c.setFillColor(colors.HexColor("#FFFFFF"))
        c.rect(0, 0, size, size, fill=1, stroke=0)
        
        # رسم الصورة
        if num in images_map and images_map[num] is not None:
            reader = ImageReader(images_map[num])
            c.drawImage(reader, 1.25 * inch, 3.1 * inch, width=6 * inch, height=4.6 * inch, preserveAspectRatio=True)
        else:
            c.setStrokeColor(colors.HexColor("#E2E8F0"))
            c.rect(1.25 * inch, 3.1 * inch, 6 * inch, 4.6 * inch)
            c.setFillColor(colors.HexColor("#94A3B8"))
            c.setFont("Helvetica", 11)
            c.drawCentredString(size / 2, 5.4 * inch, f"[ Illustration {num} ]")
            
        # إدراج النص بتنسيق Flowable ملتف ومضبوط الهوامش
        raw_text = p.get("text", "")
        formatted_txt = format_text_arabic(raw_text) if "العربية" in target_lang else raw_text
        paragraph = Paragraph(formatted_txt, story_style)
        
        box_w = 6.2 * inch
        box_h = 1.6 * inch
        paragraph.wrapOn(c, box_w, box_h)
        paragraph.drawOn(c, (size - box_w) / 2, 1.2 * inch)
        
        # ترقيم الصفحة
        c.setFillColor(colors.HexColor("#94A3B8"))
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(size / 2, 0.5 * inch, f"- {num} -")
        c.showPage()
        
    c.save()
    buffer.seek(0)
    return buffer

# =========================================================
# 5. واجهة الاستوديو التفاعلية
# =========================================================
with st.sidebar:
    st.markdown("### ⚙️ إعدادات المحرك")
    api_key = st.text_input("Google Gemini API Key:", type="password")
    st.caption("✨ محرك التوليد الفني: FLUX.1 + Unified LLM Agent")

st.title("📚 AI StoryCraft Studio Pro")
st.write("استوديو ذكي لتأليف وتصميم قصص الأطفال، توليد الرسوم المتناسقة، وتصدير ملفات PDF جاهزة لـ Amazon KDP.")

col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.subheader("1. مواصفات القصة والشخصية")
    concept_input = st.text_area(
        "فكرة القصة وسيناريو الأحداث:",
        "A brave little fox and his robot friend exploring a glowing crystal cave on a magical planet.",
        height=85
    )
    char_input = st.text_input(
        "مظهر البطل وثبات الملامح (Consistency Prompt):",
        "A cute baby red fox wearing a tiny teal vest and a small yellow explorer backpack, big curious green eyes"
    )
    
    c1, c2 = st.columns(2)
    with c1:
        lang_choice = st.selectbox("لغة الكتاب:", ["English", "العربية (Arabic)", "Deutsch (German)", "Français (French)"])
        pages_count = st.slider("عدد الصفحات:", 4, 12, 6)
    with c2:
        age_choice = st.selectbox("الفئة العمرية:", ["Ages 3-5", "Ages 6-8", "Ages 8-12"])
        style_choice = st.selectbox(
            "النمط الفني:",
            [
                "Cute 3D Pixar Animation style, soft cinematic volumetric lighting, 8k",
                "Whimsical Pastel Watercolor & Ink Children's Book Art",
                "Vibrant Digital Disney-Style Illustration"
            ]
        )
        
    if st.button("🚀 1. تأليف القصة وهندسة المشاهد"):
        if not api_key:
            st.error("الرجاء إدخال API Key في القائمة الجانبية.")
        else:
            with st.spinner("🤖 جاري تأليف القصة وضبط معايير KDP..."):
                try:
                    result = generate_complete_storybook(
                        api_key, concept_input, char_input, style_choice, lang_choice, age_choice, pages_count
                    )
                    st.session_state["storybook_data"] = result
                    st.session_state["target_lang"] = lang_choice
                    st.session_state["images_cache"] = {}
                    st.session_state["base_seed"] = random.randint(100000, 999999)
                    st.success("🎉 تم تأليف القصة وصياغة الأوامر بنجاح!")
                except Exception as err:
                    st.error(f"خطأ أثناء التأليف: {err}")

with col_right:
    st.subheader("2. المعاينة الحية وتصدير الـ PDF")
    
    if "storybook_data" in st.session_state:
        data = st.session_state["storybook_data"]
        
        # بطاقة بيانات KDP
        st.markdown(f"""
        <div class="kdp-box">
            <h3 style="color:#7C3AED; margin:0 0 5px 0;">{data.get('title', 'My Storybook')}</h3>
            <p style="margin:0 0 8px 0; color:#94A3B8;"><small>{data.get('subtitle', '')}</small></p>
            <p><b>🏷️ كلمات KDP المفتاحية:</b><br>
            <code>{' , '.join(data.get('keywords', []))}</code></p>
        </div>
        """, unsafe_allow_html=True)
        
        # زر توليد كافة الرسوم دفعة واحدة
        if st.button("🎨 2. توليد كافة الرسوم الآن (FLUX.1 Engine)"):
            base_seed = st.session_state.get("base_seed", 42)
            with st.spinner("🎨 جاري رسم المشاهد وتثبيت ملامح الشخصية..."):
                for page in data.get("pages", []):
                    p_num = page.get("page_number", 1)
                    prompt_str = page.get("image_prompt", "")
                    img = generate_page_image(prompt_str, seed_val=base_seed + p_num)
                    st.session_state["images_cache"][p_num] = img
                st.success("✨ اكتمل توليد كافة الرسوم بنجاح!")
                
        # عرض الصفحات
        for page in data.get("pages", []):
            p_num = page.get("page_number", 1)
            with st.expander(f"الصفحة {p_num}"):
                st.write(f"**النص:** {page.get('text', '')}")
                if p_num in st.session_state.get("images_cache", {}):
                    st.image(st.session_state["images_cache"][p_num], width=320)
                else:
                    if st.button(f"رسم الصفحة {p_num}", key=f"btn_draw_{p_num}"):
                        img = generate_page_image(page.get("image_prompt", ""), seed_val=st.session_state.get("base_seed", 42) + p_num)
                        st.session_state["images_cache"][p_num] = img
                        st.rerun()
                st.markdown(f'<div class="prompt-preview"><b>Prompt:</b> {page.get("image_prompt", "")}</div>', unsafe_allow_html=True)
                
        st.markdown("---")
        pdf_bytes = build_production_pdf(data, st.session_state.get("images_cache", {}), st.session_state.get("target_lang", "English"))
        st.download_button(
            "⬇️ تحميل كتاب القصة كامل (PDF قياسي لـ KDP)",
            data=pdf_bytes,
            file_name=f"{data.get('title', 'Storybook').replace(' ', '_')}.pdf",
            mime="application/pdf"
        )
    else:
        st.info("👈 املأ الفكرة ومواصفات البطل واضغط على زر التأليف للبدء.")
