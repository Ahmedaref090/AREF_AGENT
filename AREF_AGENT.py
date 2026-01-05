import streamlit as st
import PyPDF2
import json
import time
import requests
import re
from pdfminer.high_level import extract_text as fallback_extract_text

# --- API CONFIGURATION ---
# تم وضع الرابط في متغير وتنظيفه لضمان عدم حدوث خطأ Connection Adapter
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions".strip()
GROQ_API_KEY = "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"

def generate_with_groq(text_input, mode):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}", 
        "Content-Type": "application/json"
    }
    
    # تنظيف النص وتقليله لتجنب تجاوز حدود التوكنز (الحد الأقصى للنص المستخلص)
    safe_text = text_input[:90000].replace('"', "'")
    
    # تخصيص التعليمات بدقة لكل وضع
    if mode == "Solved Q&A Bank":
        instruction = (
            "Extract questions and their CORRECT answers from this solved bank. "
            "Ignore any metadata or headers. Focus on Q&A pairs."
        )
    elif mode == "Unsolved Q&A Bank":
        instruction = (
            "You are a professor. Solve the following question bank accurately. "
            "Provide the correct option text for each question."
        )
    else:  # Lecture Mode (تحسين الأوبشن الثالث)
        instruction = (
            "You are a university examiner. Read the lecture text carefully. "
            "Generate 15-20 high-quality MCQs that cover the core concepts. "
            "Ignore headers, footers, and page numbers. Focus on academic facts."
        )

    # بناء البرومبت بصيغة JSON صارمة
    prompt = (
        f"{instruction}\n"
        "OUTPUT FORMAT: Return ONLY a valid JSON array. No conversational text or Markdown. "
        "The 'answer' field MUST be the exact text of the correct option.\n"
        "Example Format: [{\"question\": \"What is X?\", \"options\": [\"A\", \"B\", \"C\", \"D\"], \"answer\": \"A\"}]\n\n"
        f"CONTENT TO ANALYZE:\n{safe_text}"
    )
    
    payload = {
        "model": "llama-3.1-70b-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2, # درجة حرارة منخفضة لضمان الدقة وعدم التزييف
        "max_tokens": 4000
    }
    
    try:
        # زيادة الـ Timeout لضمان معالجة المحاضرات الطويلة
        response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=60)
        
        if response.status_code != 200:
            st.error(f"⚠️ API Error {response.status_code}: {response.text}")
            return []

        res_json = response.json()
        if 'choices' in res_json:
            content = res_json['choices'][0]['message']['content'].strip()
            
            # تنظيف الرد من أي علامات Markdown
            content = content.replace("```json", "").replace("```", "").strip()
            
            # استخراج مصفوفة الـ JSON فقط باستخدام Regex أو البحث عن الأقواس
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            else:
                st.warning("Could not parse JSON from AI response.")
        return []
    except Exception as e:
        st.error(f"⚠️ Neural Link Error: {str(e)}")
        return []

# --- STREAMLIT UI ---
st.set_page_config(page_title="AREF AGENT | AI VISION", layout="centered")

st.markdown("""
    <style>
    .stApp { background-image: url("https://i.pinimg.com/736x/d7/82/af/d782af00f9f7e36b7bd89b01926f1c06.jpg"); background-size: cover; background-attachment: fixed; }
    .stApp > div:first-child { background-color: rgba(0, 0, 0, 0.9); min-height: 100vh; }
    @keyframes shake { 0%, 100% { transform: translateX(0); } 25% { transform: translateX(-7px); } 75% { transform: translateX(7px); } }
    .error-box { animation: shake 0.2s; border: 3px solid #ff4b4b !important; box-shadow: 0 0 30px #ff4b4b !important; }
    @keyframes glow { 0%, 100% { box-shadow: 0 0 10px #00ffcc; } 50% { box-shadow: 0 0 30px #00ffcc; } }
    .success-box { animation: glow 1s infinite; border: 3px solid #00ffcc !important; }
    .neon-title { color: #00d4ff; text-shadow: 0 0 20px #00d4ff; text-align: center; font-size: 4rem; font-weight: 900; }
    .question-card { background: rgba(15, 15, 15, 0.95); padding: 30px; border-radius: 20px; border: 1px solid #444; }
    .status-container { display: flex; justify-content: space-around; align-items: center; background: rgba(0, 212, 255, 0.07); padding: 20px; border-radius: 20px; border: 1px solid rgba(0, 212, 255, 0.3); margin-bottom: 25px; backdrop-filter: blur(10px); }
    .stat-value { font-size: 1.4rem; font-weight: bold; color: #00d4ff; }
    .timer-critical { animation: pulse-red 0.5s infinite; color: #ff4b4b !important; }
    @keyframes pulse-red { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
    </style>
    """, unsafe_allow_html=True)

if 'questions' not in st.session_state:
    st.session_state.update({
        'questions': [], 'current_idx': 0, 'score': 0, 
        'is_finished': False, 'answered': False, 'status': 'normal',
        'correct_text_to_show': "", 'start_time': None
    })

st.markdown('<h1 class="neon-title">AREF AGENT</h1>', unsafe_allow_html=True)

# 1. المرحلة الأولى: رفع الملف وتوليد الأسئلة
if not st.session_state.questions and not st.session_state.is_finished:
    data_mode = st.radio("SELECT DATA TYPE:", ["Solved Q&A Bank", "Unsolved Q&A Bank", "Lecture"], index=2)
    file = st.file_uploader("UPLOAD SYSTEM DATA (PDF)", type="pdf")
    
    if file and st.button("ACTIVATE NEURAL LINK"):
        with st.spinner("🧬 ANALYZING NEURAL DATA..."):
            try:
                reader = PyPDF2.PdfReader(file)
                full_text = "".join([p.extract_text() for p in reader.pages])
                if not full_text.strip(): raise Exception("Text Empty")
            except:
                file.seek(0)
                full_text = fallback_extract_text(file)

            data = generate_with_groq(full_text, data_mode)
            if data:
                st.session_state.questions = data
                st.session_state.start_time = time.time()
                st.rerun()
            else:
                st.error("Failed to extract meaningful questions. Try another PDF.")

# 2. المرحلة الثانية: الاختبار
elif st.session_state.questions and not st.session_state.is_finished:
    idx = st.session_state.current_idx
    q = st.session_state.questions[idx]
    
    elapsed = time.time() - st.session_state.start_time
    remaining_time = max(0, 45 - int(elapsed))
    
    if remaining_time == 0 and not st.session_state.answered:
        st.session_state.answered = True
        st.session_state.status = 'wrong'
        st.session_state.correct_text_to_show = q['answer']
        st.rerun()

    st.markdown(f"""
    <div class="status-container">
        <div class="stat-item"><div class="stat-value">{st.session_state.score} / {len(st.session_state.questions)}</div></div>
        <div class="stat-item"><div class="stat-value {'timer-critical' if remaining_time <= 10 else ''}">{remaining_time}s</div></div>
    </div>
    """, unsafe_allow_html=True)

    card_class = "question-card " + ("success-box" if st.session_state.status == 'correct' else "error-box" if st.session_state.status == 'wrong' else "")
    st.markdown(f"<div class='{card_class}'><h3>NODE {idx+1}</h3><p>{q['question']}</p></div>", unsafe_allow_html=True)
    
    choice = st.radio("SELECT RESPONSE:", q['options'], key=f"q_{idx}", disabled=st.session_state.answered)
    
    if st.button("VERIFY", use_container_width=True, disabled=st.session_state.answered):
        st.session_state.answered = True
        if choice == q['answer']:
            st.session_state.score += 1
            st.session_state.status = 'correct'
            st.balloons()
        else:
            st.session_state.status = 'wrong'
            st.session_state.correct_text_to_show = q['answer']
        st.rerun()
    
    if st.session_state.answered:
        if st.session_state.status == 'wrong':
            st.error(f"CORRECT ANSWER: {st.session_state.correct_text_to_show}")
        if st.button("NEXT NODE ➡️", use_container_width=True):
            if idx + 1 < len(st.session_state.questions):
                st.session_state.update({'current_idx': idx+1, 'answered': False, 'status': 'normal', 'start_time': time.time()})
                st.rerun()
            else:
                st.session_state.is_finished = True
                st.rerun()

    if not st.session_state.answered:
        time.sleep(1)
        st.rerun()

# 3. المرحلة الأخيرة: النتيجة
else:
    st.markdown(f"<div class='question-card' style='text-align:center;'><h1>SCORE: {st.session_state.score}</h1></div>", unsafe_allow_html=True)
    if st.button("REBOOT"):
        st.session_state.clear()
        st.rerun()
