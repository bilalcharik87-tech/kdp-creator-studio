import io
import json
import random
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

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

# ==========================================
# الأمان: كلمة المرور يجب ألا تكون مكتوبة في الكود أبداً
# خصوصاً أن هذا الملف مرفوع على GitHub. ضع القيمة في:
# .streamlit/secrets.toml -> APP_PASSWORD = "..."
# أو في إعدادات الـ Secrets الخاصة بمنصة النشر (Streamlit Cloud مثلاً).
# ==========================================
APP_PASSWORD = st.secrets.get("APP_PASSWORD", None)

def check_auth():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        with st.sidebar:
            st.title("🔐 تسجيل الدخول")
            if APP_PASSWORD is None:
                st.error("⚠️ لم يتم ضبط APP_PASSWORD في secrets. أضفه قبل النشر ولا تكتب كلمة السر داخل الكود.")
                return False
            pwd = st.text_input("كلمة المرور:", type="password")
            if st.button("دخول"):
                if pwd == APP_PASSWORD:
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
    st.markdown("---")
    st.caption("إذا فشلت بعض الصور، جرّب زر «إعادة محاولة الصور الفاشلة» بالأسفل.")

# ==========================================
# توليد الصور — مع إعادة محاولة، تسجيل الأخطاء، وseed ثابت لكل كتاب لتحسين الاتساق البصري
# ==========================================
def generate_real_image(prompt, book_seed=None, retries=3, timeout=45):
    last_error = None
    for attempt in range(retries):
        try:
            clean_prompt = f"{prompt}, high quality 3d digital illustration, vibrant colors, pixar style, children's storybook art, 8k, highly detailed"
            encoded = urllib.parse.quote(clean_prompt)
            # نفس الـ seed الأساسي لكل الكتاب + إزاحة بسيطة لكل صفحة => تنويع خفيف مع الحفاظ على أسلوب متقارب
            seed = (book_seed + attempt) if book_seed is not None else random.randint(1000, 999999)
            url = f"https://image.pollinations.ai/prompt/{encoded}?width=800&height=800&seed={seed}&nologo=true"
            resp = requests.get(url, timeout=timeout)
            if resp.status_code == 200 and resp.content:
                img = Image.open(io.BytesIO(resp.content))
                img.load()  # يتأكد من أن الصورة فعلاً صالحة وليست ملف فارغ/تالف
                return img, None
            last_error = f"HTTP {resp.status_code}"
        except Exception as e:
            last_error = str(e)
        time.sleep(1.5 * (attempt + 1))  # تأخير متزايد قبل إعادة المحاولة
    # فشلت كل المحاولات: أعد صورة افتراضية + رسالة الخطأ الحقيقية بدل الابتلاع الصامت
    return Image.new("RGB", (800, 800), color=(255, 235, 204)), last_error


def generate_all_images(pages, book_seed, max_workers=4):
    """يولّد كل الصور بالتوازي مع شريط تقدم، ويرجع dict لكل صفحة + قاموس بالأخطاء."""
    results = {}
    errors = {}
    progress = st.progress(0, text="بدء توليد الرسوم...")
    total = len(pages)
    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_page = {
            executor.submit(generate_real_image, p["image_prompt"], book_seed + p["page_number"]): p["page_number"]
            for p in pages
        }
        for future in as_completed(future_to_page):
            num = future_to_page[future]
            img, err = future.result()
            results[num] = img
            if err:
                errors[num] = err
            done += 1
            progress.progress(done / total, text=f"تم توليد {done}/{total} صورة...")
    progress.empty()
    return results, errors


def get_text_model(key):
    genai.configure(api_key=key)
    # ترتيب أولوية يفضّل أحدث نماذج Flash المتاحة فعلياً، مع تراجع آمن لنماذج أقدم مضمونة التوفر
    priority = [
        "models/gemini-3.7-flash",
        "models/gemini-3.6-flash",
        "models/gemini-3.5-flash",
        "models/gemini-2.5-flash",
        "gemini-2.5-flash",
        "models/gemini-2.5-flash-lite",
    ]
    try:
        available = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
        for p in priority:
            if p in available:
                return genai.GenerativeModel(p)
        if available:
            return genai.GenerativeModel(available[0])
    except Exception:
        pass
    return genai.GenerativeModel("models/gemini-2.5-flash")


def extract_json(raw_text):
    """استخراج JSON بشكل مرن حتى لو أضاف النموذج نصاً زائداً حول الكائن."""
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```(json)?", "", raw_text).strip()
        raw_text = re.sub(r"```$", "", raw_text).strip()
    # كحل أخير: خذ من أول { إلى آخر }
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        raw_text = match.group(0)
    return json.loads(raw_text)


def generate_pro_story(concept, target_lang, age_group, pages_count, char_desc, art_style, retries=2):
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
    - Keep each page's "text" field under 320 characters so it fits nicely on a printed page.
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

    last_error = None
    for attempt in range(retries + 1):
        try:
            res = model.generate_content(
                f"{prompt}\n\nConcept Idea: {concept}",
                generation_config={"response_mime_type": "application/json"},
            )
            return extract_json(res.text)
        except Exception as e:
            last_error = e
            time.sleep(1.5)
    raise last_error


def format_arabic(text):
    try:
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


# ==========================================
# محرك تصميم PDF احترافي — مع منع تقصّ/تراكب النص تلقائياً
# ==========================================
def build_story_style(font_size):
    return ParagraphStyle(
        'StoryText',
        fontName='Helvetica-Bold',
        fontSize=font_size,
        leading=font_size * 1.45,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#2C3E50"),
    )


def fit_paragraph(canvas_obj, text, max_width, max_height, start_font_size=13, min_font_size=8):
    """يقلّص حجم الخط تدريجياً حتى تتسع الفقرة في الصندوق المخصص، فلا يحدث تقصّ أو تراكب أبداً."""
    font_size = start_font_size
    while font_size >= min_font_size:
        style = build_story_style(font_size)
        p = Paragraph(text, style)
        w, h = p.wrapOn(canvas_obj, max_width, max_height)
        if h <= max_height:
            return p, h
        font_size -= 1
    # حتى بأصغر خط لم تتسع: أرجعها بأصغر خط ممكن (نادراً ما يحدث مع حد 320 حرف)
    style = build_story_style(min_font_size)
    p = Paragraph(text, style)
    p.wrapOn(canvas_obj, max_width, max_height)
    return p, max_height


def render_pro_pdf(story_data, images_dict, target_lang):
    buffer = io.BytesIO()
    size = 8.5 * inch
    c = canvas.Canvas(buffer, pagesize=(size, size))

    # --- 1. صفحة الغلاف ---
    c.setFillColor(colors.HexColor("#FFFDF9"))
    c.rect(0, 0, size, size, fill=1, stroke=0)

    c.setFillColor(colors.HexColor("#D9534F"))
    c.setFont("Helvetica-Bold", 24)
    title_text = format_arabic(story_data['title']) if "العربية" in target_lang else story_data['title']
    c.drawCentredString(size / 2, size - 1.2 * inch, title_text)

    if 1 in images_dict and images_dict[1] is not None:
        reader = ImageReader(images_dict[1])
        c.drawImage(reader, 1.25 * inch, 2.2 * inch, width=6 * inch, height=4.8 * inch, preserveAspectRatio=True)

    c.setFillColor(colors.HexColor("#7F8C8D"))
    c.setFont("Helvetica", 11)
    c.drawCentredString(size / 2, 1.2 * inch, "A Beautiful Story for Kids • KDP Edition")
    c.showPage()

    # --- 2. الصفحات الداخلية ---
    text_zone_top = 3.1 * inch      # الحد الأعلى لمنطقة النص (أسفل الصورة)
    text_zone_bottom = 0.9 * inch   # الحد الأدنى لمنطقة النص (فوق رقم الصفحة)
    max_text_height = text_zone_top - text_zone_bottom
    p_width = 6.4 * inch

    for page in story_data["pages"]:
        num = page["page_number"]

        c.setFillColor(colors.HexColor("#FAFAFA"))
        c.rect(0, 0, size, size, fill=1, stroke=0)

        if num in images_dict and images_dict[num] is not None:
            reader = ImageReader(images_dict[num])
            c.drawImage(reader, 1.25 * inch, 3.4 * inch, width=6 * inch, height=4.3 * inch, preserveAspectRatio=True)
        else:
            c.setStrokeColor(colors.HexColor("#E2E8F0"))
            c.rect(1.25 * inch, 3.4 * inch, 6 * inch, 4.3 * inch)
            c.setFillColor(colors.HexColor("#A0AEC0"))
            c.setFont("Helvetica", 12)
            c.drawCentredString(size / 2, 5.5 * inch, f"[ Illustration {num} ]")

        txt = format_arabic(page["text"]) if "العربية" in target_lang else page["text"]
        p, actual_h = fit_paragraph(c, txt, p_width, max_text_height)
        # نتوسّط عمودياً داخل منطقة النص المخصصة بدل موضع ثابت كي لا يتراكب مع الصورة أو رقم الصفحة
        y_pos = text_zone_bottom + (max_text_height - actual_h) / 2
        p.drawOn(c, (size - p_width) / 2, y_pos)

        c.setFillColor(colors.HexColor("#BDC3C7"))
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(size / 2, 0.5 * inch, f"- {num} -")
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
                    st.session_state["img_errors"] = {}
                    st.session_state["book_seed"] = random.randint(1000, 999999)
                    st.success("✨ تم تأليف القصة بنجاح!")
                except Exception as e:
                    st.error(f"خطأ في توليد القصة: {e}")

with col2:
    st.subheader("2. الرسوم الحية وتصدير الـ PDF")
    if "story_res" in st.session_state:
        data = st.session_state["story_res"]

        st.markdown(f"### 📖 {data['title']}")

        cgen1, cgen2 = st.columns(2)
        with cgen1:
            if st.button("🎨 توليد جميع الرسوم الملونة الآن (HD AI Images)"):
                imgs, errs = generate_all_images(data["pages"], st.session_state["book_seed"])
                st.session_state["page_imgs"] = imgs
                st.session_state["img_errors"] = errs
                if errs:
                    st.warning(f"⚠️ فشلت {len(errs)} صورة وتم استبدالها بلون افتراضي. اضغط الزر بجانبه لإعادة المحاولة.")
                else:
                    st.success("✅ اكتمل توليد كافة الرسوم بنجاح!")
        with cgen2:
            failed_pages = [p for p in data["pages"] if st.session_state.get("img_errors", {}).get(p["page_number"])]
            if failed_pages and st.button("🔁 إعادة محاولة الصور الفاشلة فقط"):
                imgs, errs = generate_all_images(failed_pages, st.session_state["book_seed"])
                st.session_state["page_imgs"].update(imgs)
                new_errors = dict(st.session_state.get("img_errors", {}))
                for num in imgs:
                    new_errors.pop(num, None)
                new_errors.update(errs)
                st.session_state["img_errors"] = new_errors

        for p in data["pages"]:
            num = p["page_number"]
            with st.expander(f"الصفحة {num}"):
                st.write(p["text"])
                err = st.session_state.get("img_errors", {}).get(num)
                if err:
                    st.error(f"فشل توليد الصورة: {err}")
                if num in st.session_state.get("page_imgs", {}):
                    st.image(st.session_state["page_imgs"][num], width=320)
                else:
                    st.caption("لم يتم توليد صورة لهذه الصفحة بعد.")
                if st.button(f"رسم/إعادة رسم الصفحة {num}", key=f"btn_{num}"):
                    img, err = generate_real_image(p["image_prompt"], st.session_state["book_seed"] + num)
                    st.session_state.setdefault("page_imgs", {})[num] = img
                    errs = st.session_state.setdefault("img_errors", {})
                    if err:
                        errs[num] = err
                    else:
                        errs.pop(num, None)
                    st.rerun()

        st.markdown("---")
        pdf_out = render_pro_pdf(data, st.session_state.get("page_imgs", {}), st.session_state["target_l"])
        st.download_button("⬇️ تحميل القصة المصورة كاملة (PDF عالي الجودة)", data=pdf_out, file_name=f"{data['title'].replace(' ', '_')}.pdf", mime="application/pdf")
    else:
        st.info("👈 اضبط خيارات القصة واضغط تأليف لتظهر المشاهد والرسومات هنا.")
