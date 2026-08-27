import io
import json
import random
import urllib.parse
from PIL import Image
import requests
import streamlit as st
import google.generativeai as genai
from reportlab.lib.pagesizes import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
import arabic_reshaper
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_CENTER
from bidi.algorithm import get_display

st.set_page_config(page_title="AI StoryCraft Studio Pro", page_icon="✨", layout="wide")

PASSWORD_SECRET = "mourad1954#"

def check_auth():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        with st.sidebar:
            st.title("🔐 تسجيل الدخول")
            pwd = st.text_input("كلمة المرور:", type="password")
            if st.button("دخول"):
                if pwd == PASSWORD_SECRET:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("كلمة المرور غير صحيحة")
        return False
    return True

if not check_auth():
    st.stop()

with st.sidebar:
    st.markdown("### ⚙️ الإعدادات")
    api_key = st.text_input("Google Gemini API Key:", type="password")

# توليد الصور باستخدام محرك Flux / Pollinations عالي الجودة ومجاني بدون أخطاء صلاحيات
def generate_real_image(prompt):
    try:
        clean_prompt = f"{prompt}, high quality 3d digital illustration, vibrant colors, pixar style, children's storybook art, 8k, highly detailed"
        encoded = urllib.parse.quote(clean_prompt)
        # توليد بذرة عشوائية لتنويع الرسوم
        seed = random.randint(1000, 999999)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=800&height=800&seed={seed}&nologo=true"
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            return Image.open(io.BytesIO(resp.content))
    except Exception as e:
        pass
    # صورة افتراضية ملونة في حال انقطاع الاتصال
    return Image.new("RGB", (800, 800), color=(255, 235, 204))

def get_text_model(key):
    genai.configure(api_key=key)
    priority = ["models/gemini-3.6-flash", "gemini-3.6-flash", "models/gemini-2.5-flash-latest", "models/gemini-1.5-flash"]
    try:
        available = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
        for p in priority:
            if p in available:
                return genai.GenerativeModel(p)
        if available:
            return genai.GenerativeModel(available[0])
    except Exception:
        pass
    return genai.GenerativeModel("models/gemini-3.6-flash")

def generate_pro_story(concept, target_lang, age_group, pages_count, char_desc, art_style):
    model = get_text_model(api_key)
    
    prompt = f"""
    You are an award-winning children's book author writing a bestseller for Amazon KDP.
    Write a rich, captivating, emotionally engaging children's story.
    
    Guidelines:
    - Target Language: {target_lang}
    - Target Age: {age_group}
    - Total Pages: {pages_count}
    - Main Character Visuals: {char_desc}
    - Art Style: {art_style}
    
    Writing Requirements:
    - Do NOT write boring single-line sentences. Write 2 to 4 engaging, colorful sentences per page with sensory details, playful dialogue, and rhythm.
    - Each image prompt must include the exact character details ({char_desc}) and artistic style ({art_style}) to ensure visual consistency.
    
    Return ONLY valid JSON matching this schema:
    {{
        "title": "Enchanting Book Title in {target_lang}",
        "kdp_description": "Rich Amazon listing description",
        "keywords": ["kw1", "kw2", "kw3", "kw4", "kw5", "kw6", "kw7"],
        "pages": [
            {{
                "page_number": 1,
                "text": "Engaging narrative paragraph in {target_lang}",
                "image_prompt": "Specific visual scene prompt focusing on {char_desc}, environment, cute expressions, {art_style}"
            }}
        ]
    }}
    """
    
    res = model.generate_content(f"{prompt}\n\nConcept Idea: {concept}")
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

# محرك تصميم PDF احترافي
def render_pro_pdf(story_data, images_dict, target_lang):
    buffer = io.BytesIO()
    size = 8.5 * inch
    c = canvas.Canvas(buffer, pagesize=(size, size))
    
    styles = getSampleStyleSheet()
    
    # نمط نص مخصص للأطفال مع التفاف تلقائي وهوامش آمنة
    story_text_style = ParagraphStyle(
        'StoryText',
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=19,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#2C3E50")
    )
    
    # --- 1. صفحة الغلاف ---
    c.setFillColor(colors.HexColor("#FFFDF9"))
    c.rect(0, 0, size, size, fill=1, stroke=0)
    
    # عنوان الغلاف
    c.setFillColor(colors.HexColor("#D9534F"))
    c.setFont("Helvetica-Bold", 24)
    title_text = format_arabic(story_data['title']) if "العربية" in target_lang else story_data['title']
    c.drawCentredString(size / 2, size - 1.2 * inch, title_text)
    
    # صورة الغلاف (استخدام صورة الصفحة 1 كغلاف)
    if 1 in images_dict and images_dict[1] is not None:
        reader = ImageReader(images_dict[1])
        c.drawImage(reader, 1.25 * inch, 2.2 * inch, width=6 * inch, height=4.8 * inch, preserveAspectRatio=True)
        
    c.setFillColor(colors.HexColor("#7F8C8D"))
    c.setFont("Helvetica", 11)
    c.drawCentredString(size / 2, 1.2 * inch, "A Beautiful Story for Kids • KDP Edition")
    c.showPage()
    
    # --- 2. الصفحات الداخلية ---
    for page in story_data["pages"]:
        num = page["page_number"]
        
        # خلفية الصفحة
        c.setFillColor(colors.HexColor("#FAFAFA"))
        c.rect(0, 0, size, size, fill=1, stroke=0)
        
        # رسم صورة الصفحة (سواء 1 أو 2 أو 3 ...)
        if num in images_dict and images_dict[num] is not None:
            reader = ImageReader(images_dict[num])
            c.drawImage(reader, 1.25 * inch, 3.2 * inch, width=6 * inch, height=4.5 * inch, preserveAspectRatio=True)
        else:
            # إطار بديل في حال لم تولد الصورة بعد
            c.setStrokeColor(colors.HexColor("#E2E8F0"))
            c.rect(1.25 * inch, 3.2 * inch, 6 * inch, 4.5 * inch)
            c.setFillColor(colors.HexColor("#A0AEC0"))
            c.setFont("Helvetica", 12)
            c.drawCentredString(size / 2, 5.4 * inch, f"[ Illustration {num} ]")
        
        # كتابة النص مع التفاف تلقائي وهامش آمن يمنع خروج النص عن الصفحة
        txt = format_arabic(page["text"]) if "العربية" in target_lang else page["text"]
        p = Paragraph(txt, story_text_style)
        
        # عرض الصندوق النصي الملتف في الأسفل
        p_width = 6.2 * inch
        p_height = 1.8 * inch
        p.wrapOn(c, p_width, p_height)
        p.drawOn(c, (size - p_width) / 2, 1.3 * inch)
        
        # رقم الصفحة
        c.setFillColor(colors.HexColor("#BDC3C7"))
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(size / 2, 0.6 * inch, f"- {num} -")
        c.showPage()
        
    c.save()
    buffer.seek(0)
    return buffer

# ==========================================
# واجهة التطبيق
# ==========================================
st.title("🌟 AI StoryCraft Studio Pro | KDP Author Suite")
st.write("وكيل ذكاء اصطناعي متكامل لتأليف قصص أطفال احترافية وتوليد رسومها الملونة وتصديرها بصيغة PDF فوراً.")

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("1. حبكة القصة وهوية البطل")
    concept = st.text_area("فكرة القصة وسيناريو المغامرة:", "A curious little baby fox discovers a glowing enchanted garden filled with laughing flowers and musical berries.", height=90)
    char_design = st.text_input("مظهر البطل بدقة (Consistency):", "A cute baby red fox with fluffy white-tipped tail, big curious green eyes, wearing a little teal explorer vest")
    
    ca, cb = st.columns(2)
    with ca:
        lang = st.selectbox("اللغة:", ["English", "العربية (Arabic)", "Deutsch (German)", "Français (French)"])
        pages = st.slider("عدد الصفحات:", 4, 12, 6)
    with cb:
        age_grp = st.selectbox("الفئة المستهدفة:", ["Ages 3-5 (Early Readers)", "Ages 6-8 (Storybook)", "Ages 8-12"])
        art = st.selectbox("الأسلوب الفني:", ["Cute 3D Pixar Animation style, warm cinematic lighting", "Whimsical Watercolor and Ink Storybook", "Vibrant Digital Disney-Style Illustration"])
        
    if st.button("🚀 1. تأليف القصة وصياغة المشاهد"):
        if not api_key:
            st.error("أدخل Gemini API Key أولاً.")
        else:
            with st.spinner("✍️ جاري كتابة السيناريو الاحترافي..."):
                try:
                    res = generate_pro_story(concept, lang, age_grp, pages, char_design, art)
                    st.session_state["story_res"] = res
                    st.session_state["target_l"] = lang
                    st.session_state["page_imgs"] = {}
                    st.success("✨ تم تأليف القصة بنجاح!")
                except Exception as e:
                    st.error(f"خطأ: {e}")

with col2:
    st.subheader("2. الرسوم الحية وتصدير الـ PDF")
    if "story_res" in st.session_state:
        data = st.session_state["story_res"]
        
        st.markdown(f"### 📖 {data['title']}")
        
        if st.button("🎨 توليد جميع الرسوم الملونة الآن (HD AI Images)"):
            with st.spinner("🎨 جاري رسم المشاهد الفنية الملونة..."):
                for p in data["pages"]:
                    img = generate_real_image(p["image_prompt"])
                    st.session_state["page_imgs"][p["page_number"]] = img
                st.success("✅ اكتمل توليد كافة الرسوم بنجاح!")
                
        for p in data["pages"]:
            num = p["page_number"]
            with st.expander(f"الصفحة {num}"):
                st.write(p["text"])
                if num in st.session_state["page_imgs"]:
                    st.image(st.session_state["page_imgs"][num], width=320)
                else:
                    if st.button(f"رسم الصفحة {num}", key=f"btn_{num}"):
                        st.session_state["page_imgs"][num] = generate_real_image(p["image_prompt"])
                        st.rerun()
                        
        st.markdown("---")
        pdf_out = render_pro_pdf(data, st.session_state.get("page_imgs", {}), st.session_state["target_l"])
        st.download_button("⬇️ تحميل القصة المصورة كاملة (PDF عالي الجودة)", data=pdf_out, file_name=f"{data['title'].replace(' ', '_')}.pdf", mime="application/pdf")
    else:
        st.info("👈 اضبط خيارات القصة واضغط تأليف لتظهر المشاهد والرسومات هنا.")
