import io
import json
import random
import urllib.parse
from PIL import Image
import requests
import streamlit as st
import google.generativeai as genai

# مكتبات التنسيق المتقدم للـ PDF
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
# 1. تهيئة الصفحة والواجهة الاحترافية (Modern Dark Studio)
# =========================================================
st.set_page_config(
    page_title="KDP AI StoryCraft Studio Pro",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main { background-color: #0E1117; }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
        background: linear-gradient(90deg, #FF4B4B 0%, #FF7433 100%);
        color: white;
        font-weight: 700;
        border: none;
        transition: 0.3s;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(255, 75, 75, 0.4);
    }
    .kdp-card {
        background-color: #1A1F2C;
        border: 1px solid #2E384D;
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 15px;
    }
    .prompt-box {
        background-color: #11151F;
        border-left: 3px solid #00D26A;
        padding: 10px;
        font-family: monospace;
        font-size: 12px;
        border-radius: 0 6px 6px 0;
        color: #E2E8F0;
    }
</style>
""", unsafe_allow_html=True)

# =========================================================
# 2. الحماية والأمان
# =========================================================
PASSWORD_SECRET = "mourad1954#"

def check_auth():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        with st.sidebar:
            st.title("🔐 استوديو التأليف والنشر")
            pwd = st.text_input("أدخل كلمة المرور:", type="password")
            if st.button("تسجيل الدخول"):
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
# 3. محركات الذكاء الاصطناعي (Open-Source AI Pipelines)
# =========================================================

# توليد الصور باستخدام نماذج FLUX.1 و SDXL المفتوحة المصدر
def generate_flux_image(prompt, seed=None):
    if seed is None:
        seed = random.randint(100000, 999999)
    try:
        clean_prompt = f"{prompt}, 8k resolution, masterpieces, crisp details, children storybook illustration, vibrant lighting, centered composition"
        encoded = urllib.parse.quote(clean_prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&seed={seed}&model=flux&nologo=true"
        resp = requests.get(url, timeout=40)
        if resp.status_code == 200:
            return Image.open(io.BytesIO(resp.content)), seed
    except Exception:
        pass
    # صورة افتراضية عند تعذر الشبكة
    return Image.new("RGB", (1024, 1024), color=(245, 240, 230)), seed

# محرك صياغة القصة (Gemini / LLM Engine)
def generate_story_content(api_key, concept, char_desc, art_style, target_lang, age_group, pages_count):
    genai.configure(api_key=api_key)
    
    # اختيار الموديل الفعال تلقائياً
    model_name = "models/gemini-1.5-flash"
    try:
        available = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
        for p in ["models/gemini-3.6-flash", "models/gemini-2.5-flash-latest", "models/gemini-1.5-flash"]:
            if p in available:
                model_name = p
                break
    except Exception:
        pass

    model = genai.GenerativeModel(model_name)
    
    system_prompt = f"""
    You are a bestselling Children's Book Author and Amazon KDP strategist.
    Create a complete children's storybook based on the given parameters.
    
    Parameters:
    - Target Language: {target_lang}
    - Age Range: {age_group}
    - Total Pages: {pages_count}
    - Character Identity (MUST be preserved across all pages): {char_desc}
    - Illustration Style: {art_style}
    
    Writing Requirements:
    1. Write an immersive, emotionally resonant narrative (2 to 4 sentences per page). Use rhythm, sensory words, and delightful dialogue.
    2. Image Prompts must be strictly formatted for FLUX.1 / SDXL engines, including character visual details: "{char_desc}" in every single prompt to ensure visual consistency.
    
    Return strictly JSON with this schema:
    {{
        "title": "Main Book Title in {target_lang}",
        "subtitle": "Engaging Subtitle in {target_lang}",
        "kdp_description": "200-word HTML description with bullet points and bold tags",
        "keywords": ["7 high volume low competition keywords"],
        "pages": [
            {{
                "page_number": 1,
                "text": "Story text for page 1 in {target_lang}",
                "image_prompt": "Scene action prompt including {char_desc}, setting, lighting, {art_style}"
            }}
        ]
    }}
    """
    
    res = model.generate_content(f"{system_prompt}\n\nConcept: {concept}")
    raw = res.text.strip()
    if raw.startswith("```json"): raw = raw[7:]
    elif raw.startswith("```"): raw = raw[3:]
    if raw.endswith("```"): raw = raw[:-3]
    return json.loads(raw.strip())

def format_arabic(text):
    try:
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text

# =========================================================
# 4. محرك إنشاء الـ PDF الاحترافي لـ Amazon KDP (8.5 x 8.5)
# =========================================================
def build_kdp_pdf(story_data, images_dict, target_lang):
    buffer = io.BytesIO()
    size = 8.5 * inch
    c = canvas.Canvas(buffer, pagesize=(size, size))
    
    # أنماط النصوص المتقدمة
    styles = getSampleStyleSheet()
    story_style = ParagraphStyle(
        'StoryTextStyle',
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=18,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#2C3E50")
    )
    
    # --- 1. صفحة الغلاف (Cover Page) ---
    c.setFillColor(colors.HexColor("#FFFDF9"))
    c.rect(0, 0, size, size, fill=1, stroke=0)
    
    # العنوان
    c.setFillColor(colors.HexColor("#D9534F"))
    c.setFont("Helvetica-Bold", 24)
    main_title = format_arabic(story_data['title']) if "العربية" in target_lang else story_data['title']
    c.drawCentredString(size / 2, size - 1.1 * inch, main_title)
    
    # رسم صورة الغلاف
    if 1 in images_dict and images_dict[1] is not None:
        reader = ImageReader(images_dict[1])
        c.drawImage(reader, 1.25 * inch, 2.2 * inch, width=6 * inch, height=4.9 * inch, preserveAspectRatio=True)
        
    c.setFillColor(colors.HexColor("#7F8C8D"))
    c.setFont("Helvetica", 10)
    c.drawCentredString(size / 2, 1.1 * inch, "Premium Amazon KDP Edition")
    c.showPage()
    
    # --- 2. الصفحات الداخلية (Interior Story Pages) ---
    for page in story_data["pages"]:
        num = page["page_number"]
        
        # خلفية الصفحة
        c.setFillColor(colors.HexColor("#FFFFFF"))
        c.rect(0, 0, size, size, fill=1, stroke=0)
        
        # إدراج الصورة
        if num in images_dict and images_dict[num] is not None:
            reader = ImageReader(images_dict[num])
            c.drawImage(reader, 1.25 * inch, 3.1 * inch, width=6 * inch, height=4.6 * inch, preserveAspectRatio=True)
        else:
            c.setStrokeColor(colors.HexColor("#CBD5E0"))
            c.rect(1.25 * inch, 3.1 * inch, 6 * inch, 4.6 * inch)
            c.setFillColor(colors.HexColor("#A0AEC0"))
            c.setFont("Helvetica", 11)
            c.drawCentredString(size / 2, 5.3 * inch, f"[ Illustration Page {num} ]")
            
        # إدراج النص مع التفاف تلقائي وهوامش آمنة
        txt = format_arabic(page["text"]) if "العربية" in target_lang else page["text"]
        p = Paragraph(txt, story_style)
        
        # عرض كتلة النص
        box_w = 6.2 * inch
        box_h = 1.6 * inch
        p.wrapOn(c, box_w, box_h)
        p.drawOn(c, (size - box_w) / 2, 1.2 * inch)
        
        # رقم الصفحة
        c.setFillColor(colors.HexColor("#BDC3C7"))
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
    st.markdown("### ⚙️ المفاتيح والمحركات")
    api_key = st.text_input("Google Gemini API Key:", type="password")
    image_engine = st.selectbox("محرك توليد الرسوم:", ["FLUX.1-schnell (Open-Source)", "SDXL Turbo (Open-Source)"])

st.title("📚 AI StoryCraft Studio Pro | KDP Author Suite")
st.caption("أداة متكاملة لتأليف قصص الأطفال، توليد رسوم الذكاء الاصطناعي مفتوحة المصدر، وتصدير كتب KDP جاهزة للطباعة.")

col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.subheader("1. إعداد القصة وهوية البطل")
    concept_input = st.text_area(
        "فكرة القصة وسيناريو المغامرة:",
        "A curious little astronaut boy and his playful robot puppy discover glowing crystal caves on Mars.",
        height=85
    )
    
    char_input = st.text_input(
        "مظهر البطل بدقة (Character Consistency Prompt):",
        "A 6-year-old boy in a sleek white spacesuit with orange badges, friendly blue eyes, accompanied by a small metallic robot dog"
    )
    
    c1, c2 = st.columns(2)
    with c1:
        lang_choice = st.selectbox("لغة الكتاب:", ["English", "Deutsch (German)", "Français (French)", "العربية (Arabic)"])
        pages_val = st.slider("عدد الصفحات:", 4, 16, 6)
    with c2:
        age_choice = st.selectbox("الفئة العمرية:", ["Ages 3-5 (Preschool)", "Ages 6-8 (Early Readers)", "Ages 8-12 (Middle Grade)"])
        style_choice = st.selectbox(
            "النمط الفني (Art Style):",
            [
                "Cute 3D Pixar Animation style, cinematic volumetric lighting, raytracing",
                "Whimsical Pastel Watercolor & Ink Children's Book Art",
                "Vibrant 2D Vector Flat Storybook Art, Disney aesthetic"
            ]
        )
        
    if st.button("🚀 1. تأليف القصة وصياغة السيناريو"):
        if not api_key:
            st.error("❌ يرجى إدخال Gemini API Key في القائمة الجانبية أولاً.")
        else:
            with st.spinner("✍️ يقوم الوكيل الذكي بكتابة القصة وهندسة برومبتات الرسوم..."):
                try:
                    res = generate_story_content(api_key, concept_input, char_input, style_choice, lang_choice, age_choice, pages_val)
                    st.session_state["story_data"] = res
                    st.session_state["target_lang"] = lang_choice
                    st.session_state["images_dict"] = {}
                    # تثبيت بذرة الرسوم للشخصية
                    st.session_state["master_seed"] = random.randint(100000, 999999)
                    st.success("✨ تم تأليف القصة بنجاح!")
                except Exception as e:
                    st.error(f"خطأ أثناء التأليف: {e}")

with col_right:
    st.subheader("2. المعاينة الحية وتصدير الـ PDF")
    
    if "story_data" in st.session_state:
        data = st.session_state["story_data"]
        
        # بطاقة بيانات النشر KDP
        st.markdown(f"""
        <div class="kdp-card">
            <h3 style="color:#FF7433; margin:0 0 5px 0;">{data['title']}</h3>
            <p style="margin:0 0 10px 0; color:#A0AEC0;"><small>{data.get('subtitle', '')}</small></p>
            <p><b>🏷️ كلمات KDP المفتاحية (7 Keywords):</b><br>
            <code>{' , '.join(data.get('keywords', []))}</code></p>
        </div>
        """, unsafe_allow_html=True)
        
        # زر التوليد التلقائي لجميع الصور
        if st.button("🎨 2. توليد جميع رسومات القصة عبر FLUX.1 (Batch Generation)"):
            with st.spinner("🎨 جاري رسم المشاهد الفنية بدقة عالية وتناسق بصري..."):
                master_seed = st.session_state.get("master_seed", 42)
                for p in data["pages"]:
                    p_num = p["page_number"]
                    img, _ = generate_flux_image(p["image_prompt"], seed=master_seed + p_num)
                    st.session_state["images_dict"][p_num] = img
                st.success("✅ اكتمل توليد كافة الرسوم بنجاح!")

        # استعراض الصفحات والصور
        for p in data["pages"]:
            p_num = p["page_number"]
            with st.expander(f"الصفحة {p_num}"):
                st.write(f"**نص الصفحة:** {p['text']}")
                if p_num in st.session_state["images_dict"]:
                    st.image(st.session_state["images_dict"][p_num], caption=f"المشهد {p_num}", width=340)
                else:
                    if st.button(f"رسم مشهد الصفحة {p_num}", key=f"btn_p_{p_num}"):
                        img, _ = generate_flux_image(p["image_prompt"])
                        st.session_state["images_dict"][p_num] = img
                        st.rerun()
                st.markdown(f'<div class="prompt-box"><b>FLUX Prompt:</b><br>{p["image_prompt"]}</div>', unsafe_allow_html=True)
                
        st.markdown("---")
        # تنزيل الـ PDF النهائي
        pdf_out = build_kdp_pdf(data, st.session_state.get("images_dict", {}), st.session_state["target_lang"])
        st.download_button(
            "⬇️ تحميل كتاب القصة المصورة بالكامل (PDF جاهز للطباعة 8.5x8.5)",
            data=pdf_out,
            file_name=f"{data['title'].replace(' ', '_')}_KDP_Interior.pdf",
            mime="application/pdf"
        )
    else:
        st.info("👈 املأ تفاصيل القصة والشخصية واضغط على زر التأليف للبدء.")
