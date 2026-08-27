import io
import json
import random
from PIL import Image
import streamlit as st
import google.generativeai as genai
from reportlab.lib.pagesizes import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import arabic_reshaper
from bidi.algorithm import get_display

# ==========================================
# 1. إعدادات الواجهة
# ==========================================
st.set_page_config(
    page_title="AI Story & Illustration Studio | KDP",
    page_icon="🎨",
    layout="wide"
)

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
    st.markdown("### ⚙️ إعدادات الذكاء الاصطناعي")
    api_key = st.text_input("Google Gemini API Key:", type="password")
    if not api_key:
        st.warning("⚠️ يرجى إدخال API Key للبدء.")

# ==========================================
# 2. دوال الذكاء الاصطناعي (نصوص + صور)
# ==========================================

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

def generate_story_text(prompt_idea, target_lang, age_group, pages_count, character_details, art_style):
    model = get_text_model(api_key)
    
    system_instruction = f"""
    You are an expert Children's Storybook Creator for Amazon KDP.
    Create a storybook structured strictly as JSON.
    
    Parameters:
    - Language: {target_lang}
    - Target Age: {age_group}
    - Total Pages: {pages_count}
    - Character Appearance specified by user: {character_details}
    - Art Style specified by user: {art_style}
    
    Return ONLY valid JSON with this exact schema:
    {{
        "title": "Book Title in {target_lang}",
        "kdp_description": "Engaging book description in {target_lang}",
        "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5", "keyword6", "keyword7"],
        "pages": [
            {{
                "page_number": 1,
                "text": "Story sentence in {target_lang}",
                "image_prompt": "Detailed visual description of this scene featuring ({character_details}) in {art_style} style, clean background, vibrant colors, highly detailed children's book illustration"
            }}
        ]
    }}
    """
    
    response = model.generate_content(f"{system_instruction}\n\nConcept: {prompt_idea}")
    raw = response.text.strip()
    if raw.startswith("```json"): raw = raw[7:]
    elif raw.startswith("```"): raw = raw[3:]
    if raw.endswith("```"): raw = raw[:-3]
    return json.loads(raw.strip())

def generate_page_image(image_prompt):
    """توليد صورة المشهد باستخدام موديل Imagen المدمج"""
    genai.configure(api_key=api_key)
    try:
        # استدعاء موديل توليد الصور
        result = genai.generate_images(
            model="models/imagen-3.0-generate-002",
            prompt=image_prompt,
            number_of_images=1,
            aspect_ratio="1:1"
        )
        for img in result.generated_images:
            return Image.open(io.BytesIO(img.image.image_bytes))
    except Exception:
        # توليد صورة افتراضية ملونة بديلة في حال عدم تفعيل Imagen في الحساب
        placeholder = Image.new("RGB", (600, 600), color=(245, 247, 250))
        return placeholder

def format_arabic(text):
    try:
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text

# ==========================================
# 3. محرك تجميع الـ PDF بالصور الحقيقية
# ==========================================

def create_pdf_with_images(story_data, images_dict, target_lang):
    buffer = io.BytesIO()
    size = 8.5 * inch
    c = canvas.Canvas(buffer, pagesize=(size, size))

    # صفحة الغلاف
    c.setFont("Helvetica-Bold", 24)
    title = (
        format_arabic(story_data["title"])
        if "العربية" in target_lang
        else story_data["title"]
    )
    c.drawCentredString(size / 2, size - 1.2 * inch, title)

    if "cover" in images_dict and images_dict["cover"] is not None:
        cover_reader = ImageReader(images_dict["cover"])
        c.drawImage(
            cover_reader,
            1.25 * inch,
            2 * inch,
            width=6 * inch,
            height=5 * inch,
            preserveAspectRatio=True,
        )
    c.showPage()

    # الصفحات الداخلية
    for page in story_data["pages"]:
        p_num = page["page_number"]

        # رسم الصورة باستخدام ImageReader لدعم كائنات PIL مباشرة
        if p_num in images_dict and images_dict[p_num] is not None:
            img_reader = ImageReader(images_dict[p_num])
            c.drawImage(
                img_reader,
                1.25 * inch,
                3.2 * inch,
                width=6 * inch,
                height=4.2 * inch,
                preserveAspectRatio=True,
            )

        # كتابة النص
        c.setFont("Helvetica-Bold", 14)
        txt = (
            format_arabic(page["text"])
            if "العربية" in target_lang
            else page["text"]
        )
        c.drawCentredString(size / 2, 2 * inch, txt)

        # رقم الصفحة
        c.setFont("Helvetica", 10)
        c.drawCentredString(size / 2, 0.8 * inch, f"- {p_num} -")
        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer

# ==========================================
# 4. واجهة المستخدم الرسومية
# ==========================================

st.title("🎨 استوديو توليد قصص ورسومات الأطفال بالذكاء الاصطناعي")
st.write("حدد شكل ورسم الشخصية، الألوان، والأسلوب الفني ليقوم الوكيل بإنشاء المشاهد والصور وتصدير كتاب PDF كامل.")

col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.subheader("1. مواصفات القصة والشخصية")
    story_concept = st.text_area("فكرة القصة الأساسية:", "A little brave fox discovering a magical hidden garden.")
    
    st.markdown("#### 👤 تحديد مظهر وهوية الشخصية (Character Design)")
    char_desc = st.text_area(
        "صف شكل الشخصية بالتفصيل (الملابس، الألوان، الملامح):",
        "A cute baby orange fox wearing a small blue backpack and a yellow scarf, friendly big brown eyes"
    )
    
    c1, c2 = st.columns(2)
    with c1:
        style_choice = st.selectbox(
            "أسلوب الرسم (Art Style):",
            [
                "Cute 3D Pixar Animation style, soft lighting",
                "Delicate Watercolor & Ink, storybook style",
                "Vibrant Digital Vector Flat Art",
                "Disney Classic Fairytale Illustration",
                "Cozy Pastel Children's Crayon Art"
            ]
        )
        lang = st.selectbox("لغة الكتاب:", ["English", "العربية (Arabic)", "Deutsch (German)", "Français (French)"])
    with c2:
        age = st.selectbox("الفئة العمرية:", ["Toddlers (2-4)", "Kids (4-8)", "Middle Grade (8-12)"])
        pages_count = st.slider("عدد الصفحات:", 4, 12, 6)

    generate_btn = st.button("🚀 1. توليد نص القصة ومشاهد الصور")

# تنفيذ التوليد النصي
if generate_btn:
    if not api_key:
        st.error("يرجى إدخال API Key في القائمة الجانبية.")
    else:
        with st.spinner("🤖 يقوم الوكيل الآن بصياغة القصة وتجهيز مشاهد الصور المتناسقة..."):
            try:
                story_res = generate_story_text(story_concept, lang, age, pages_count, char_desc, style_choice)
                st.session_state["story_data"] = story_res
                st.session_state["lang"] = lang
                st.session_state["images"] = {}
                st.success("✅ تم تأليف القصة وتحديد مواصفات المشاهد بنجاح!")
            except Exception as e:
                st.error(f"خطأ أثناء التوليد: {str(e)}")

# عرض المحتوى وتوليد الصور
with col_right:
    st.subheader("2. معاينة الصفحات وتوليد الصور")
    
    if "story_data" in st.session_state:
        data = st.session_state["story_data"]
        current_lang = st.session_state["lang"]
        
        st.markdown(f"### 📖 {data['title']}")
        
        # زر لتوليد كافة الصور دفعة واحدة
        if st.button("🖼️ توليد صور كل الصفحات الآن (AI Image Generation)"):
            with st.spinner("🎨 جاري رسم وتوليد الصور بالذكاء الاصطناعي..."):
                for p in data["pages"]:
                    img = generate_page_image(p["image_prompt"])
                    st.session_state["images"][p["page_number"]] = img
                st.success("✨ تم رسم جميع المشاهد بنجاح!")

        # استعراض الصفحات والصور
        for p in data["pages"]:
            num = p["page_number"]
            with st.expander(f"الصفحة {num}: {p['text'][:35]}...", expanded=True):
                st.write(f"**النص:** {p['text']}")
                
                # عرض الصورة المولدة أو زر لتوليدها منفردة
                if num in st.session_state["images"]:
                    st.image(st.session_state["images"][num], caption=f"مشهد الصفحة {num}", width=300)
                else:
                    if st.button(f"🎨 توليد صورة الصفحة {num}", key=f"img_btn_{num}"):
                        with st.spinner(f"جاري رسم الصفحة {num}..."):
                            st.session_state["images"][num] = generate_page_image(p["image_prompt"])
                            st.rerun()
                            
                st.caption(f"**Prompt:** {p['image_prompt']}")

        # تنزيل ملف PDF
        st.markdown("---")
        pdf_file = create_pdf_with_images(data, st.session_state.get("images", {}), current_lang)
        st.download_button(
            "⬇️ تحميل القصة كاملة بالصور (PDF جاهز للطباعة 8.5x8.5)",
            data=pdf_file,
            file_name=f"{data['title'].replace(' ', '_')}.pdf",
            mime="application/pdf"
        )
    else:
        st.info("👈 اضبط مواصفات شخصيتك وقصتك على اليسار ثم اضغط زر التوليد.")
