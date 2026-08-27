import io
import json
import arabic_reshaper
from bidi.algorithm import get_display
import google.generativeai as genai
from reportlab.lib.pagesizes import inch
from reportlab.pdfgen import canvas
import streamlit as st

# ==========================================
# 1. إعدادات الواجهة وهوية التطبيق (Modern SaaS)
# ==========================================
st.set_page_config(
    page_title="AI StoryCraft Studio | KDP Agent",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# تخصيص التصميم عبر CSS
st.markdown(
    """
<style>
    .main { background-color: #0E1117; color: #FAFAFA; }
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        background: linear-gradient(90deg, #FF4B4B 0%, #FF8533 100%);
        color: white;
        font-weight: bold;
        border: none;
    }
    .metric-card {
        background-color: #1E232F;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #2E3648;
        margin-bottom: 15px;
    }
    .prompt-box {
        background-color: #161B22;
        border-left: 4px solid #FF8533;
        padding: 12px;
        font-family: monospace;
        font-size: 13px;
        border-radius: 0 8px 8px 0;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ==========================================
# 2. الحماية ومفتاح الذكاء الاصطناعي
# ==========================================
PASSWORD_SECRET = "mourad1954#"


def check_auth():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        with st.sidebar:
            st.title("🔐 بوابة الدخول")
            pwd = st.text_input("كلمة المرور الخاصة:", type="password")
            if st.button("تسجيل الدخول"):
                if pwd == PASSWORD_SECRET:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("كلمة المرور غير صحيحة")
        return False
    return True


if not check_auth():
    st.info("👋 مرحباً بك في استوديو الذكاء الاصطناعي لتأليف كتب KDP. يرجى تسجيل الدخول للمتابعة.")
    st.stop()

# إعداد مفتاح Gemini API في الشريط الجانبي
with st.sidebar:
    st.markdown("### ⚙️ إعدادات الذكاء الاصطناعي")
    api_key = st.text_input(
        "Google Gemini API Key:",
        type="password",
        help="احصل عليه مجاناً من Google AI Studio (aistudio.google.com)",
    )
    if not api_key:
        st.warning("⚠️ أدخل مفتاح API لتفعيل الوكيل الذكي.")

# ==========================================
# 3. محرك الوكيل الذكي (AI Agent Engine)
# ==========================================


def generate_story_agent(
    prompt_idea, target_lang, age_group, pages_count, style_theme
):
    genai.configure(api_key=api_key)

    # استخدام التسمية القياسية المحدثة لتفادي خطأ 404
    try:
        model = genai.GenerativeModel("models/gemini-1.5-flash-latest")
    except Exception:
        model = genai.GenerativeModel("gemini-pro")

    system_instruction = f"""
    You are an expert Children's Book Author and Amazon KDP Publishing Specialist.
    Generate a complete children's storybook structured strictly as a JSON object.
    
    Parameters:
    - Target Language: {target_lang}
    - Age Group: {age_group}
    - Total Story Pages: {pages_count}
    - Illustration Style: {style_theme}
    
    Respond ONLY with valid JSON using this exact schema:
    {{
        "title": "Book title in {target_lang}",
        "kdp_description": "2-paragraph description in {target_lang}",
        "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5", "keyword6", "keyword7"],
        "character_design": "Detailed prompt describing main character consistency",
        "pages": [
            {{
                "page_number": 1,
                "text": "Page 1 story text in {target_lang}",
                "image_prompt": "Midjourney/DALL-E prompt in {style_theme} style"
            }}
        ]
    }}
    """

    response = model.generate_content(
        f"{system_instruction}\n\nStory Concept: {prompt_idea}"
    )

    clean_text = (
        response.text.strip()
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )
    return json.loads(clean_text)


# دالة معالجة النص العربي
def format_arabic(text):
    try:
        return get_display(arabic_reshaper.reshape(text))
    except:
        return text


# ==========================================
# 4. محرك توليد وتنسيق PDF
# ==========================================


def create_kdp_storybook_pdf(story_json, target_lang):
    buffer = io.BytesIO()
    # مقاس مربع 8.5 x 8.5 إنش
    size = 8.5 * inch
    c = canvas.Canvas(buffer, pagesize=(size, size))

    # صفحة الغلاف
    c.setFont("Helvetica-Bold", 24)
    title = (
        format_arabic(story_json["title"])
        if target_lang == "العربية (Arabic)"
        else story_json["title"]
    )
    c.drawCentredString(size / 2, size - 120, title)

    c.rect(1 * inch, 2.5 * inch, 6.5 * inch, 4.5 * inch)
    c.setFont("Helvetica", 12)
    c.drawCentredString(size / 2, 4.5 * inch, "[ Cover Illustration Area ]")
    c.showPage()

    # الصفحات الداخلية
    for page in story_json["pages"]:
        # مكان الرسمة
        c.setStrokeColorRGB(0.8, 0.8, 0.8)
        c.rect(1 * inch, 3.2 * inch, 6.5 * inch, 4.2 * inch)
        c.setFont("Helvetica", 11)
        c.drawCentredString(
            size / 2, 5.2 * inch, f"[ Illustration Page {page['page_number']} ]"
        )

        # النص
        c.setFont("Helvetica-Bold", 14)
        txt = (
            format_arabic(page["text"])
            if target_lang == "العربية (Arabic)"
            else page["text"]
        )
        c.drawCentredString(size / 2, 2 * inch, txt)

        # رقم الصفحة
        c.setFont("Helvetica", 10)
        c.drawCentredString(size / 2, 0.8 * inch, f"- {page['page_number']} -")
        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer


# ==========================================
# 5. واجهة الاستوديو التفاعلية
# ==========================================
st.title("✨ AI Children's Book Creator Studio")
st.caption(
    "وكيل ذكاء اصطناعي متكامل لتأليف القصص، توليد برومبتات الصور، وتجهيز ملفات الطباعة لـ Amazon KDP."
)

col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.markdown("### 📝 إعداد فكرة القصة")
    story_idea = st.text_area(
        "صف فكرة القصة أو السيناريو باختصار:",
        value="A curious little astronaut boy and his robot dog exploring the glowing moon caves.",
        height=110,
    )

    c1, c2 = st.columns(2)
    with c1:
        language = st.selectbox(
            "لغة الكتاب:",
            [
                "العربية (Arabic)",
                "English",
                "Deutsch (German)",
                "Français (French)",
            ],
        )
        pages_qty = st.slider("عدد الصفحات الداخلية:", 4, 24, 8)
    with c2:
        age_target = st.selectbox(
            "الفئة العمرية:",
            [
                "Toddlers (2-4 years)",
                "Early Readers (4-6 years)",
                "Kids (6-8 years)",
                "Middle Grade (8-12 years)",
            ],
        )
        art_style = st.selectbox(
            "أسلوب الرسم (Art Style):",
            [
                "Cute 3D Pixar Animation",
                "Soft Pastel Watercolor",
                "Vibrant Vector Flat Art",
                "Classic Storybook Vintage",
            ],
        )

    generate_btn = st.button("🚀 تشغيل الوكيل وتوليد القصة بالكامل")

if generate_btn:
    if not api_key:
        st.error("❌ يرجى إدخال Gemini API Key في الشريط الجانبي أولاً.")
    else:
        with st.spinner("🤖 الوكيل يقوم الآن بتأليف القصة، صياغة البرومبتات، وتجهيز خطة النشر..."):
            try:
                story_res = generate_story_agent(
                    story_idea, language, age_target, pages_qty, art_style
                )
                st.session_state["generated_story"] = story_res
                st.session_state["target_lang"] = language
                st.success("🎉 تم تأليف القصة وتجهيز الكتاب بنجاح!")
            except Exception as e:
                st.error(f"حدث خطأ أثناء التوليد: {str(e)}")

with col_right:
    st.markdown("### 📖 المعاينة الحية وبيانات KDP")

    if "generated_story" in st.session_state:
        data = st.session_state["generated_story"]
        lang = st.session_state["target_lang"]

        # بطاقة العنوان والبيانات الوصفية
        st.markdown(
            f"""
        <div class="metric-card">
            <h2 style="color: #FF8533; margin-top:0;">{data['title']}</h2>
            <p><b>👤 وصف الشخصية الأساسي (Consistency Prompt):</b><br><small>{data['character_design']}</small></p>
            <p><b>🏷️ الكلمات المفتاحية المقترحة لـ KDP:</b><br>
            <code>{' , '.join(data['keywords'])}</code></p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # استعراض الصفحات والبرومبتات
        st.markdown("#### 📄 توزيع الصفحات والمشاهد:")
        for p in data["pages"]:
            with st.expander(
                f"الصفحة {p['page_number']}: {p['text'][:40]}..."
            ):
                st.write(f"**نص الصفحة:** {p['text']}")
                st.markdown(
                    f'<div class="prompt-box"><b>🎨 Image Prompt:</b><br>{p["image_prompt"]}</div>',
                    unsafe_allow_html=True,
                )

        # زر تنزيل الـ PDF
        pdf_bytes = create_kdp_storybook_pdf(data, lang)
        st.download_button(
            "⬇️ تحميل ملف الكتاب الداخلي (PDF جاهز للطباعة 8.5x8.5)",
            data=pdf_bytes,
            file_name=f"{data['title'].replace(' ', '_')}_Interior.pdf",
            mime="application/pdf",
        )
    else:
        st.info("👈 املأ التفاصيل واضغط على زر التشغيل لرؤية المحتوى والبرومبتات وملف الـ PDF هنا.")
