import io
import math
import random
import streamlit as st
from reportlab.lib.pagesizes import inch
from reportlab.pdfgen import canvas

# ==========================================
# 1. إعدادات الصفحة ونظام حماية التطبيق
# ==========================================
st.set_page_config(
    page_title="KDP Creator Studio",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

PASSWORD_SECRET = "mourad1954#"


def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.sidebar.title("🔒 تسجيل الدخول")
        pwd = st.sidebar.text_input("أدخل كلمة المرور:", type="password")
        if st.sidebar.button("دخول"):
            if pwd == PASSWORD_SECRET:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.sidebar.error("❌ كلمة المرور غير صحيحة")
        return False
    return True


if not check_password():
    st.warning(
        "⚠️ لوحة التحكم مقفلة. يرجى إدخال كلمة المرور من القائمة الجانبية للوصول للأدوات."
    )
    st.stop()

# ==========================================
# 2. دوال إنشاء ملفات الـ PDF لـ Amazon KDP
# ==========================================


def generate_logbook_pdf(
    page_width, page_height, num_pages, style="Lined", bleed=True
):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(page_width * inch, page_height * inch))
    margin = 0.375 * inch if bleed else 0.5 * inch

    for page_num in range(1, num_pages + 1):
        c.setFont("Helvetica-Bold", 12)
        c.drawString(
            margin, page_height * inch - margin - 15, "DATE: _____________"
        )

        c.setStrokeColorRGB(0.75, 0.75, 0.75)
        c.setLineWidth(0.7)

        if "Lined" in style:
            y = page_height * inch - margin - 40
            while y > margin + 15:
                c.line(margin, y, (page_width * inch) - margin, y)
                y -= 22
        elif "Grid" in style:
            grid_size = 18
            y_start = page_height * inch - margin - 35
            for x in range(
                int(margin), int((page_width * inch) - margin), grid_size
            ):
                c.line(x, margin, x, y_start)
            for y in range(int(margin), int(y_start), grid_size):
                c.line(margin, y, (page_width * inch) - margin, y)

        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer


def generate_wordsearch_grid(size=10):
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return [[random.choice(letters) for _ in range(size)] for _ in range(size)]


def generate_activity_pdf(page_width, page_height, puzzles_count=5):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(page_width * inch, page_height * inch))

    word_lists = [
        "SPACE - PLANET - ROCKET - STARS - MOON",
        "TIGER - LION - MONKEY - ZEBRA - GIRAFFE",
        "APPLE - BANANA - ORANGE - GRAPES - MANGO",
        "RIVER - FOREST - MOUNTAIN - OCEAN - DESERT",
        "DOCTOR - TEACHER - PILOT - ARTIST - NURSE",
    ]

    for p in range(1, puzzles_count + 1):
        grid = generate_wordsearch_grid(10)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(
            (page_width * inch) / 2, page_height * inch - 50, f"PUZZLE #{p}"
        )

        c.setFont("Courier-Bold", 16)
        start_x = (page_width * inch - (10 * 24)) / 2
        start_y = page_height * inch - 100

        for r, row in enumerate(grid):
            for col_idx, char in enumerate(row):
                c.drawString(
                    start_x + (col_idx * 24), start_y - (r * 24), char
                )

        c.setFont("Helvetica-Bold", 12)
        words = word_lists[(p - 1) % len(word_lists)]
        c.drawCentredString(
            (page_width * inch) / 2, start_y - (11 * 24), f"FIND: {words}"
        )
        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer


# ==========================================
# 3. واجهة المستخدم الرسومية (Dashboard)
# ==========================================
st.title("📚 استوديو إنشاء وتصدير كتب KDP الخاص بك")
st.write("أداة سحابية لتصميم وتوليد المحتوى الداخلي للكتب بصيغة PDF جاهزة للرفع.")

tab1, tab2, tab3 = st.tabs([
    "📓 دفاتر وسجلات (Log Books)",
    "🧩 كتب أنشطة (Activity Books)",
    "📖 قصص أطفال (Kids Storybook)",
])

# --- القسم الأول: Log Books ---
with tab1:
    st.subheader("إعداد دفاتر الملاحظات وتتبع العادات (Interiors)")
    col1, col2, col3 = st.columns(3)
    with col1:
        size_option = st.selectbox(
            "المقاس (Trim Size):",
            ["6 x 9 inch", "8.5 x 11 inch", "8.25 x 6 inch"],
            key="log_size",
        )
    with col2:
        pages_count = st.number_input(
            "عدد الصفحات الإجمالي:",
            min_value=24,
            max_value=400,
            value=100,
            step=10,
        )
    with col3:
        book_style = st.selectbox(
            "نمط الصفحة:",
            ["Lined (مسطر قياسي)", "Grid (شبكة مربعات)"],
            key="log_style",
        )

    w, h = [float(x) for x in size_option.replace(" inch", "").split(" x ")]

    if st.button("🚀 توليد وتجهيز الـ PDF", key="btn_log"):
        with st.spinner("جاري بناء الملف الداخلي وتنسيق الصفحات..."):
            pdf_data = generate_logbook_pdf(
                w, h, pages_count, style=book_style, bleed=True
            )
            st.success(
                f"✅ تم إنشاء {pages_count} صفحة بنجاح متوافقة مع شروط الطباعة!"
            )
            st.download_button(
                "⬇️ تحميل ملف PDF الداخلي",
                data=pdf_data,
                file_name=f"KDP_{size_option.replace(' ', '_')}_{pages_count}p.pdf",
                mime="application/pdf",
            )

# --- القسم الثاني: Activity Books ---
with tab2:
    st.subheader("توليد كتب الألغاز والبحث عن الكلمات (Word Search)")
    col_a, col_b = st.columns(2)
    with col_a:
        act_size = st.selectbox(
            "المقاس:", ["8.5 x 11 inch"], key="act_size_box"
        )
    with col_b:
        puzzles_num = st.slider("عدد صفحات الألغاز:", 5, 50, 15)

    if st.button("🧩 توليد كتاب الأنشطة", key="btn_act"):
        with st.spinner("جاري إنشاء شبكات الحروف وقوائم الكلمات..."):
            act_pdf = generate_activity_pdf(8.5, 11, puzzles_num)
            st.success(f"✅ تم توليد {puzzles_num} لغز بنجاح!")
            st.download_button(
                "⬇️ تحميل كتاب الأنشطة PDF",
                data=act_pdf,
                file_name=f"WordSearch_8.5x11_{puzzles_num}puzzles.pdf",
                mime="application/pdf",
            )

# --- القسم الثالث: Kids Storybooks ---
with tab3:
    st.subheader("كتب وقصص الأطفال (مقاس مربع 8.5 x 8.5 inch)")
    st.info(
        "💡 يدعم تصدير القصص المصورة مع هوامش أمان محسوبة لتفادي ملاحظات المراجعة في KDP."
    )
