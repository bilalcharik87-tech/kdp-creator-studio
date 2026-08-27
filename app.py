import io
import json
import random
import streamlit as st
import google.generativeai as genai
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib.pagesizes import inch
from reportlab.pdfgen import canvas

==========================================

1. إعدادات الواجهة وهوية التطبيق

==========================================

st.set_page_config(
page_title="AI StoryCraft Studio | KDP Agent",
page_icon="✨",
layout="wide",
initial_sidebar_state="expanded"
)

تخصيص التصميم عبر CSS

st.markdown("""

""", unsafe_allow_html=True)

==========================================

2. الحماية ومفتاح الذكاء الاصطناعي

==========================================

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

إعداد مفتاح Gemini API في الشريط الجانبي

with st.sidebar:
st.markdown("### ⚙️ إعدادات الذكاء الاصطناعي")
api_key = st.text_input(
"Google Gemini API Key:",
type="password",
help="احصل عليه مجاناً من Google AI Studio (aistudio.google.com)"
)
if not api_key:
st.warning("⚠️ أدخل مفتاح API لتفعيل الوكيل الذكي.")

==========================================

3. محرك الفحص الآلي والوكيل الذكي

==========================================

def get_working_model(key):
"""دالة لاكتشاف الموديل الشغال تلقائياً في حساب المستخدم لتفادي خطأ 404"""
genai.configure(api_key=key)
try:
all_models = genai.list_models()
supported = [m.name for m in all_models if 'generateContent' in m.supported_generation_methods]

    # ترتيب الأفضلية للموديلات
    for name in supported:
        if 'flash' in name:
            return name
    for name in supported:
        if 'pro' in name:
            return name
    if supported:
        return supported[0]
except Exception:
    pass
return "gemini-1.5-flash"


def generate_story_agent(prompt_idea, target_lang, age_group, pages_count, style_theme, key):
genai.configure(api_key=key)

# اختيار الموديل الفعال تلقائياً
active_model_name = get_working_model(key)
model = genai.GenerativeModel(active_model_name)

system_instruction = f"""


You are an expert Children's Book Author and Amazon KDP Publishing Specialist.
Generate a complete children's storybook structured strictly as a JSON object.

Parameters:

Target Language: {target_lang}

Age Group: {age_group}

Total Story Pages: {pages_count}

Illustration Style: {style_theme}

Respond ONLY with a valid JSON using this exact structure without markdown or extra explanation:
{{
"title": "Story title in {target_lang}",
"kdp_description": "2-paragraph description in {target_lang}",
"keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5", "keyword6", "keyword7"],
"character_design": "Detailed description of character consistency for AI image generation",
"pages": [
{{
"page_number": 1,
"text": "Story text for page 1 in {target_lang}",
"image_prompt": "Prompt in {style_theme} style"
}}
]
}}
"""

response = model.generate_content(f"{system_instruction}\n\nStory Idea: {prompt_idea}")

raw_text = response.text.strip()
if "```json" in raw_text:
    clean_text = raw_text.split("```json")[1].split("```")[0].strip()
elif "```" in raw_text:
    clean_text = raw_text.split("```")[1].split("```")[0].strip()
else:
    clean_text = raw_text
    
return json.loads(clean_text), active_model_name


دالة معالجة النص العربي

def format_arabic(text):
try:
return get_display(arabic_reshaper.reshape(text))
except Exception:
return text

==========================================

4. محرك تصدير PDF

==========================================

def create_kdp_storybook_pdf(story_json, target_lang):
buffer = io.BytesIO()
size = 8.5 * inch
c = canvas.Canvas(buffer, pagesize=(size, size))

# صفحة الغلاف
c.setFont("Helvetica-Bold", 24)
title = format_arabic(story_json['title']) if "العربية" in target_lang else story_json['title']
c.drawCentredString(size / 2, size - 120, title)

c.rect(1 * inch, 2.5 * inch, 6.5 * inch, 4.5 * inch)
c.setFont("Helvetica", 12)
c.drawCentredString(size / 2, 4.5 * inch, "[ Cover Illustration ]")
c.showPage()

# الصفحات الداخلية
for page in story_json['pages']:
    c.setStrokeColorRGB(0.8, 0.8, 0.8)
    c.rect(1 * inch, 3.2 * inch, 6.5 * inch, 4.2 * inch)
    c.setFont("Helvetica", 11)
    c.drawCentredString(size / 2, 5.2 * inch, f"[ Illustration Page {page['page_number']} ]")
    
    c.setFont("Helvetica-Bold", 14)
    txt = format_arabic(page['text']) if "العربية" in target_lang else page['text']
    c.drawCentredString(size / 2, 2 * inch, txt)
    
    c.setFont("Helvetica", 10)
    c.drawCentredString(size / 2, 0.8 * inch, f"- {page['page_number']} -")
    c.showPage()
    
c.save()
buffer.seek(0)
return buffer


==========================================

5. الواجهة التفاعلية

==========================================

st.title("✨ AI Children's Book Creator Studio")
st.caption("وكيل ذكاء اصطناعي لتأليف القصص، صياغة برومبتات الصور، وتصميم كتب KDP المربعة.")

col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
st.markdown("### 📝 إعداد فكرة القصة")
story_idea = st.text_area(
"صف فكرة القصة أو السيناريو باختصار:",
value="A curious little astronaut boy and his robot dog exploring the glowing moon caves.",
height=110
)

c1, c2 = st.columns(2)
with c1:
    language = st.selectbox(
        "لغة الكتاب:",
        ["العربية (Arabic)", "English", "Deutsch (German)", "Français (French)"]
    )
    pages_qty = st.slider("عدد الصفحات الداخلية:", 4, 24, 6)
with c2:
    age_target = st.selectbox(
        "الفئة العمرية:",
        ["Toddlers (2-4 years)", "Early Readers (4-6 years)", "Kids (6-8 years)", "Middle Grade (8-12 years)"]
    )
    art_style = st.selectbox(
        "أسلوب الرسم (Art Style):",
        ["Cute 3D Pixar Animation", "Soft Pastel Watercolor", "Vibrant Vector Flat Art", "Classic Storybook Vintage"]
    )
    
generate_btn = st.button("🚀 تشغيل الوكيل وتوليد القصة بالكامل")


if generate_btn:
if not api_key:
st.error("❌ يرجى إدخال Gemini API Key في الشريط الجانبي أولاً.")
else:
with st.spinner("🤖 جاري فحص الحساب واختيار أفضل موديل متاح لتوليد القصة..."):
try:
story_res, used_model = generate_story_agent(
story_idea, language, age_target, pages_qty, art_style, api_key
)
st.session_state["generated_story"] = story_res
st.session_state["target_lang"] = language
st.session_state["used_model"] = used_model
st.success(f"🎉 تم توليد القصة بنجاح باستعمال الموديل ({used_model})!")
except Exception as e:
st.error(f"حدث خطأ أثناء التوليد: {str(e)}")

with col_right:
st.markdown("### 📖 المعاينة الحية وبيانات KDP")

if "generated_story" in st.session_state:
    data = st.session_state["generated_story"]
    lang = st.session_state["target_lang"]
    
    st.markdown(f"""
    <div class="metric-card">
        <h2 style="color: #FF8533; margin-top:0;">{data['title']}</h2>
        <p><b>👤 وصف الشخصية الأساسي (Consistency Prompt):</b><br><small>{data['character_design']}</small></p>
        <p><b>🏷️ الكلمات المفتاحية المقترحة لـ KDP:</b><br>
        <code>{' , '.join(data['keywords'])}</code></p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("#### 📄 توزيع الصفحات والمشاهد:")
    for p in data['pages']:
        with st.expander(f"الصفحة {p['page_number']}: {p['text'][:40]}..."):
            st.write(f"**نص الصفحة:** {p['text']}")
            st.markdown(
                f'<div class="prompt-box"><b>🎨 Image Prompt:</b><br>{p["image_prompt"]}</div>',
                unsafe_allow_html=True
            )
            
    pdf_bytes = create_kdp_storybook_pdf(data, lang)
    st.download_button(
        "⬇️ تحميل ملف الكتاب الداخلي (PDF جاهز للطباعة 8.5x8.5)",
        data=pdf_bytes,
        file_name=f"{data['title'].replace(' ', '_')}_Interior.pdf",
        mime="application/pdf"
    )
else:
    st.info("👈 املأ التفاصيل واضغط على زر التشغيل لرؤية المحتوى والبرومبتات وملف الـ PDF هنا.")
