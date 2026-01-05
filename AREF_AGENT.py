import streamlit as st
import PyPDF2
import json
import time
import requests
import re
from pdfminer.high_level import extract_text as fallback_extract_text

# مفتاح API
GROQ_API_KEY = "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"

def generate_with_groq(text_input, mode):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    # تنظيف النص وتقليصه لضمان سرعة الاستجابة
    safe_text = text_input[:15000].replace('"', "'")
    
    if mode == "Solved Q&A Bank":
        instruction = "Extract all Q&A. Return ONLY JSON."
    elif mode == "Unsolved Q&A Bank":
        instruction = "Solve these questions. Return ONLY JSON."
    else: 
        instruction = "Generate 10-15 MCQs. Return ONLY JSON."

    prompt = (
        f"{instruction}\n"
        "FORMAT: [{\"question\": \"...\", \"options\": [\"A\", \"B\", \"C\", \"D\"], \"answer\": \"correct text\"}]\n"
        f"TEXT: {safe_text}"
    )
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1 # تقليل التحرر لضمان الالتزام بتنسيق JSON
    }
    
    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=45)
        
        # التأكد من نجاح الطلب
        if response.status_code != 200:
            st.error(f"Groq API Error: {response.status_code} - {response.text}")
            return []

        res_json = response.json()
        content = res_json['choices'][0]['message']['content'].strip()
        
        # محاولة استخراج الـ JSON باستخدام Regex بشكل أقوى
        match = re.search(r'\[\s*\{.*\}\s*\]', content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        else:
            # إذا فشل الـ Regex، نحاول تحويل المحتوى كاملاً
            return json.loads(content)
            
    except Exception as e:
        st.error(f"System Error: {str(e)}")
        return []

# --- إعدادات الواجهة ---
st.set_page_config(page_title="AREF AGENT", layout="centered")

if 'questions' not in st.session_state:
    st.session_state.update({'questions': [], 'current_idx': 0, 'score': 0, 'is_finished': False, 'answered': False, 'status': 'normal', 'start_time': None})

st.markdown('<h1 style="text-align:center; color:#00d4ff;">AREF AGENT AI</h1>', unsafe_allow_html=True)

# واجهة الرفع
if not st.session_state.questions and not st.session_state.is_finished:
    data_mode = st.radio("SELECT MODE:", ["Solved Q&A Bank", "Unsolved Q&A Bank", "Lecture"])
    file = st.file_uploader("UPLOAD PDF", type="pdf")
    
    if file and st.button("START ANALYSIS"):
        with st.spinner("🧬 Processing..."):
            file.seek(0)
            try:
                reader = PyPDF2.PdfReader(file)
                full_text = " ".join([p.extract_text() for p in reader.pages if p.extract_text()])
                if not full_text:
                    file.seek(0)
                    full_text = fallback_extract_text(file)
            except:
                full_text = ""

            if full_text:
                data = generate_with_groq(full_text, data_mode)
                if data:
                    st.session_state.questions = data
                    st.session_state.start_time = time.time()
                    st.rerun()
                else:
                    st.warning("الموديل لم يستطع استخراج أسئلة. تأكد أن الملف يحتوي على نص واضح وليس صوراً.")

# واجهة الأسئلة (نفس منطق الكود السابق مع تحسينات بسيطة)
elif st.session_state.questions and not st.session_state.is_finished:
    # (بقية كود عرض الأسئلة كما في المرة السابقة...)
    st.write(f"Question {st.session_state.current_idx + 1}")
    q = st.session_state.questions[st.session_state.current_idx]
    st.subheader(q['question'])
    # ... تكملة الكود
    if st.button("RESET"): # زر طوارئ للمسح
        st.session_state.clear()
        st.rerun()
