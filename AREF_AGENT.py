import streamlit as st
import PyPDF2
import json
import time
import requests
import re
from pdfminer.high_level import extract_text as fallback_extract_text

# مفتاح API الخاص بك
GROQ_API_KEY = "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"

def generate_with_groq(text_input, mode):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    # تحديد حجم النص بحد أقصى لضمان عدم فشل الـ API (حوالي 25000 حرف كافية جداً لـ 20 سؤال)
    safe_text = text_input[:25000].replace('"', "'")
    
    if mode == "Solved Q&A Bank":
        instruction = "Extract all questions and their correct answers from this solved bank."
    elif mode == "Unsolved Q&A Bank":
        instruction = "Solve this question bank and provide the correct answers."
    else: 
        instruction = "Generate 15 to 20 clear, exam-oriented multiple choice questions (MCQs) based on the text."

    prompt = (
        f"{instruction} "
        "IMPORTANT: You MUST return ONLY a valid JSON array. Do not include any introductory text. "
        "The 'answer' field MUST contain the exact text of the correct option. "
        "Format: [{\"question\": \"...\", \"options\": [\"Option A\", \"Option B\", \"Option C\", \"Option D\"], \"answer\": \"Option A\"}]. "
        f"Text: {safe_text}"
    )
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }
    
    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=60)
        res_json = response.json()
        if 'choices' in res_json:
            content = res_json['choices'][0]['message']['content'].strip()
            match = re.search(r'\[\s*\{.*\}\s*\]', content, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        return []
    except Exception:
        return []

def reset_session():
    """دالة لتنظيف الذاكرة عند رفع ملف جديد"""
    for key in list(st.session_state.keys()):
        del st.session_state[key]

st.set_page_config(page_title="AREF AGENT | AI VISION", layout="centered")

# CSS المطور الخاص بك
st.markdown("""
    <style>
    .stApp { background-image: url("https://i.pinimg.com/736x/d7/82/af/d782af00f9f7e36b7bd89b01926f1c06.jpg"); background-size: cover; background-attachment: fixed; }
    .stApp > div:first-child { background-color: rgba(0, 0, 0, 0.9); min-height: 100vh; }
    .neon-title { color: #00d4ff; text-shadow: 0 0 20px #00d4ff; text-align: center; font-size: 4rem; font-weight: 900; padding: 20px; }
    .question-card { background: rgba(15, 15, 15, 0.95); padding: 30px; border-radius: 20px; border: 1px solid #444; margin-bottom: 20px; }
    .status-container { display: flex; justify-content: space-around; align-items: center; background: rgba(0, 212, 255, 0.07); padding: 20px; border-radius: 20px; border: 1px solid rgba(0, 212, 255, 0.3); margin-bottom: 25px; }
    .stat-value { font-size: 1.4rem; font-weight: bold; color: #00d4ff; }
    .timer-critical { color: #ff4b4b; animation: pulse 0.5s infinite; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    </style>
    """, unsafe_allow_html=True)

# تهيئة المتغيرات في session_state
if 'questions' not in st.session_state:
    st.session_state.update({
        'questions': [], 'current_idx': 0, 'score': 0, 
        'is_finished': False, 'answered': False, 'status': 'normal',
        'correct_text_to_show': "", 'start_time': None
    })

st.markdown('<h1 class="neon-title">AREF AGENT</h1>', unsafe_allow_html=True)

# واجهة رفع الملفات
if not st.session_state.questions and not st.session_state.is_finished:
    data_mode = st.radio("SELECT DATA TYPE:", ["Solved Q&A Bank", "Unsolved Q&A Bank", "Lecture"], index=2)
    # استخدام on_change لضمان تصفير البرنامج عند تغيير الملف
    file = st.file_uploader("UPLOAD SYSTEM DATA (PDF)", type="pdf", on_change=None)
    
    if file and st.button("ACTIVATE NEURAL LINK"):
        with st.spinner("🧬 ANALYZING DATA..."):
            try:
                # التأكد من قراءة الملف من بدايته
                file.seek(0)
                reader = PyPDF2.PdfReader(file)
                full_text = ""
                # قراءة أول 30 صفحة كحد أقصى لتجنب تعليق البرنامج
                max_pages = min(len(reader.pages), 30)
                for p_idx in range(max_pages):
                    full_text += reader.pages[p_idx].extract_text()
                
                if not full_text.strip(): 
                    file.seek(0)
                    full_text = fallback_extract_text(file)
            except Exception as e:
                st.error("Error reading PDF file.")
                full_text = ""

            if full_text:
                data = generate_with_groq(full_text, data_mode)
                if data:
                    st.session_state.questions = data
                    st.session_state.start_time = time.time()
                    st.rerun()
                else:
                    st.error("Failed to generate questions. Try a smaller file or different mode.")

# واجهة الاختبار
elif st.session_state.questions and not st.session_state.is_finished:
    idx = st.session_state.current_idx
    total = len(st.session_state.questions)
    q = st.session_state.questions[idx]
    
    elapsed = time.time() - st.session_state.start_time
    remaining_time = max(0, 45 - int(elapsed))
    
    # عرض العداد والإحصائيات
    st.markdown(f"""
    <div class="status-container">
        <div style="text-align:center;"><div style="color:#888; font-size:0.7rem;">NODE</div><div class="stat-value">{idx+1}/{total}</div></div>
        <div style="text-align:center;"><div style="color:#888; font-size:0.7rem;">TIMER</div><div class="stat-value {'timer-critical' if remaining_time <= 10 else ''}">{remaining_time}s</div></div>
        <div style="text-align:center;"><div style="color:#888; font-size:0.7rem;">SCORE</div><div class="stat-value" style="color:#00ffcc;">{st.session_state.score}</div></div>
    </div>
    """, unsafe_allow_html=True)

    # عرض السؤال
    st.markdown(f"<div class='question-card'><h3>QUESTION {idx+1}</h3><p style='font-size:1.2rem;'>{q['question']}</p></div>", unsafe_allow_html=True)
    
    choice = st.radio("SELECT RESPONSE:", q['options'], key=f"q_{idx}", disabled=st.session_state.answered)
    
    if remaining_time == 0 and not st.session_state.answered:
        st.session_state.answered = True
        st.session_state.status = 'wrong'
        st.session_state.correct_text_to_show = q['answer']
        st.rerun()

    c1, c2 = st.columns(2)
    with c1:
        if st.button("VERIFY DATA", use_container_width=True, disabled=st.session_state.answered):
            st.session_state.answered = True
            if choice == q['answer']:
                st.session_state.score += 1
                st.session_state.status = 'correct'
                st.balloons()
            else:
                st.session_state.status = 'wrong'
                st.session_state.correct_text_to_show = q['answer']
            st.rerun()
    
    with c2:
        if st.session_state.answered:
            if st.session_state.status == 'wrong':
                st.error(f"CORRECT: {st.session_state.correct_text_to_show}")
            else:
                st.success("SUCCESS ✅")

            if st.button("NEXT NODE ➡️", use_container_width=True):
                if idx + 1 < total:
                    st.session_state.update({
                        'current_idx': idx + 1, 'answered': False, 'status': 'normal',
                        'correct_text_to_show': "", 'start_time': time.time()
                    })
                    st.rerun()
                else:
                    st.session_state.is_finished = True
                    st.rerun()

    if not st.session_state.answered and remaining_time > 0:
        time.sleep(1)
        st.rerun()

# واجهة النهاية
else:
    st.markdown(f"""
        <div class='question-card' style='text-align:center;'>
            <h1>MISSION COMPLETE</h1>
            <p style='font-size:2rem;'>FINAL SCORE: {st.session_state.score}/{len(st.session_state.questions)}</p>
        </div>
    """, unsafe_allow_html=True)
    
    if st.button("REBOOT SYSTEM (NEW FILE)", use_container_width=True):
        reset_session()
        st.rerun()
