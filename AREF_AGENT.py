import streamlit as st
import PyPDF2
import json
import time
import requests
import re
from pdfminer.high_level import extract_text as fallback_extract_text

# --- API CONFIGURATION ---
GROQ_API_KEY = "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"

def generate_with_groq(text_input, mode):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}", 
        "Content-Type": "application/json"
    }
    
    # 1. تنظيف أولي للنص وتقليله لتجنب تجاوز حدود التوكنز
    safe_text = text_input[:120000].replace('"', "'")
    
    # 2. تحديد التعليمات بناءً على الوضع المختار بدقة عالية
    if mode == "Solved Q&A Bank":
        instruction = (
            "You are an expert data extractor. "
            "Extract questions and their CORRECT answers from this solved bank. "
            "Ignore context text, focus only on Q&A pairs."
        )
    elif mode == "Unsolved Q&A Bank":
        instruction = (
            "You are a university professor. "
            "Solve the following question bank based on the provided text and general academic knowledge. "
            "Provide the most accurate correct answer for each question."
        )
    else:  # Lecture Mode (تم تحسين هذا الجزء جداً)
        instruction = (
            "You are a professional exam setter for university students. "
            "Analyze the provided lecture text carefully. "
            "Generate 20 to 25 high-quality, exam-oriented multiple choice questions (MCQs). "
            "CRITICAL RULES: "
            "1. Ignore headers, footers, page numbers, and references. "
            "2. Questions must be based ONLY on the core concepts in the text. "
            "3. Do not generate questions if the text is just garbage or metadata. "
        )

    # 3. صياغة البرومبت لضمان شكل الـ JSON
    prompt = (
        f"{instruction}\n"
        "IMPORTANT OUTPUT FORMAT: \n"
        "You must return ONLY a valid JSON array. Do not add any Markdown (```) or conversational text. "
        "The 'answer' field MUST contain the exact text string of the correct option (e.g., ' Mitochondria'), NOT just the letter 'A'.\n"
        "Format: [{\"question\": \"...\", \"options\": [\"Option A\", \"Option B\", \"Option C\", \"Option D\"], \"answer\": \"Option A\"}]\n\n"
        f"TEXT CONTENT:\n{safe_text}"
    )
    
    payload = {
        "model": "llama-3.1-70b-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3, # تقليل العشوائية لزيادة الدقة
        "max_tokens": 6000
    }
    
    try:
        # 4. زيادة وقت الانتظار إلى 60 ثانية للملفات الكبيرة
        response = requests.post("[https://api.groq.com/openai/v1/chat/completions](https://api.groq.com/openai/v1/chat/completions)", headers=headers, json=payload, timeout=60)
        
        if response.status_code != 200:
            st.error(f"⚠️ API Error: {response.status_code} - {response.text}")
            return []

        res_json = response.json()
        if 'choices' in res_json:
            content = res_json['choices'][0]['message']['content'].strip()
            
            # 5. تنظيف الرد من أي شوائب (مثل ```json)
            content = content.replace("```json", "").replace("```", "")
            
            # محاولة استخراج المصفوفة فقط
            start = content.find('[')
            end = content.rfind(']')
            
            if start != -1 and end != -1:
                clean_json = content[start:end+1]
                return json.loads(clean_json)
            else:
                return []
        return []
    except Exception as e:
        st.error(f"⚠️ Connection Error: {e}")
        return []

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="AREF AGENT | AI VISION", layout="centered")

# --- CUSTOM CSS (STYLES) ---
st.markdown("""
    <style>
    .stApp { background-image: url("https://i.pinimg.com/736x/d7/82/af/d782af00f9f7e36b7bd89b01926f1c06.jpg"); background-size: cover; background-attachment: fixed; }
    .stApp > div:first-child { background-color: rgba(0, 0, 0, 0.9); min-height: 100vh; }
    
    /* Animations */
    @keyframes shake { 0%, 100% { transform: translateX(0); } 25% { transform: translateX(-7px); } 75% { transform: translateX(7px); } }
    .error-box { animation: shake 0.2s; border: 3px solid #ff4b4b !important; box-shadow: 0 0 30px #ff4b4b !important; }
    
    @keyframes glow { 0%, 100% { box-shadow: 0 0 10px #00ffcc; } 50% { box-shadow: 0 0 30px #00ffcc; } }
    .success-box { animation: glow 1s infinite; border: 3px solid #00ffcc !important; }
    
    @keyframes pulse-red { 0%, 100% { color: #ff4b4b; text-shadow: 0 0 5px #ff4b4b; } 50% { color: #fff; text-shadow: 0 0 20px #ff4b4b; } }
    .timer-critical { animation: pulse-red 0.5s infinite; font-weight: bold; }
    
    .neon-title { color: #00d4ff; text-shadow: 0 0 20px #00d4ff; text-align: center; font-size: 4rem; font-weight: 900; }
    .question-card { background: rgba(15, 15, 15, 0.95); padding: 30px; border-radius: 20px; border: 1px solid #444; }
    
    .status-container { display: flex; justify-content: space-around; align-items: center; background: rgba(0, 212, 255, 0.07); padding: 20px; border-radius: 20px; border: 1px solid rgba(0, 212, 255, 0.3); margin-bottom: 25px; backdrop-filter: blur(10px); }
    .stat-item { text-align: center; }
    .stat-label { font-size: 0.7rem; color: #888; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px; }
    .stat-value { font-size: 1.4rem; font-weight: bold; color: #00d4ff; }
    </style>
    """, unsafe_allow_html=True)

# --- SESSION STATE INITIALIZATION ---
if 'questions' not in st.session_state:
    st.session_state.update({
        'questions': [], 
        'current_idx': 0, 
        'score': 0, 
        'is_finished': False, 
        'answered': False, 
        'status': 'normal',
        'correct_text_to_show': "", 
        'start_time': None
    })

# --- TITLE ---
st.markdown('<h1 class="neon-title">AREF AGENT</h1>', unsafe_allow_html=True)

# --- MAIN LOGIC ---

# 1. SETUP PHASE (Upload & Generate)
if not st.session_state.questions and not st.session_state.is_finished:
    data_mode = st.radio("SELECT DATA TYPE:", ["Solved Q&A Bank", "Unsolved Q&A Bank", "Lecture"], index=2)
    file = st.file_uploader("UPLOAD SYSTEM DATA (PDF)", type="pdf")
    
    if file and st.button("ACTIVATE NEURAL LINK"):
        with st.spinner("🧬 ANALYZING DATA STREAM..."):
            full_text = ""
            try:
                # محاولة 1: PyPDF2
                reader = PyPDF2.PdfReader(file)
                full_text = "".join([p.extract_text() for p in reader.pages])
            except:
                pass # الانتقال للمحاولة التالية بصمت
            
            # محاولة 2: Fallback (إذا فشلت الأولى أو كان النص فارغاً)
            if not full_text or len(full_text.strip()) < 50:
                file.seek(0)
                try:
                    full_text = fallback_extract_text(file)
                except Exception as e:
                    st.error("FAILED TO READ PDF DATA CORRUPTED.")
            
            if full_text:
                data = generate_with_groq(full_text, data_mode)
                if data:
                    st.session_state.questions = data
                    st.session_state.start_time = time.time()
                    st.rerun()
                else:
                    st.error("NEURAL LINK SEVERED: COULD NOT GENERATE QUESTIONS. TRY A DIFFERENT FILE.")
            else:
                st.error("EMPTY DATA STREAM.")

# 2. QUIZ PHASE
elif st.session_state.questions and not st.session_state.is_finished:
    idx = st.session_state.current_idx
    total = len(st.session_state.questions)
    
    # تأكد من أن العداد لا يتجاوز المصفوفة (أمان)
    if idx >= total:
        st.session_state.is_finished = True
        st.rerun()

    q = st.session_state.questions[idx]
    remaining_nodes = total - (idx + 1)
    
    # Timer Logic
    elapsed = time.time() - st.session_state.start_time
    remaining_time = max(0, 45 - int(elapsed))
    
    t_class = "stat-value"
    if remaining_time <= 10: t_class += " timer-critical"

    # Timeout Handler
    if remaining_time == 0 and not st.session_state.answered:
        st.session_state.answered = True
        st.session_state.status = 'wrong'
        st.session_state.correct_text_to_show = q['answer']
        st.rerun()

    # Dashboard
    st.markdown(f"""
    <div class="status-container">
        <div class="stat-item"><div class="stat-label">Total Nodes</div><div class="stat-value">{total}</div></div>
        <div class="stat-item"><div class="stat-label">Remaining</div><div class="stat-value" style="color:#ffcc00;">{remaining_nodes}</div></div>
        <div class="stat-item"><div class="stat-label">Timer</div><div class="{t_class}">{remaining_time}s</div></div>
        <div class="stat-item"><div class="stat-label">Score</div><div class="stat-value" style="color:#00ffcc;">{st.session_state.score}</div></div>
    </div>
    """, unsafe_allow_html=True)

    # Question Display
    b_style = "question-card"
    if st.session_state.status == 'correct': b_style += " success-box"
    elif st.session_state.status == 'wrong': b_style += " error-box"

    st.markdown(f"<div class='{b_style}'><h3>NODE {idx+1}</h3><p style='font-size:1.4rem;'>{q['question']}</p></div>", unsafe_allow_html=True)
    
    # Options
    choice = st.radio("SELECT RESPONSE:", q['options'], key=f"q_{idx}", disabled=st.session_state.answered)
    
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
                st.error(f"CORRECT RESPONSE: {st.session_state.correct_text_to_show}")
            else:
                st.success("SUCCESS ✅")

            if st.button("NEXT NODE ➡️", use_container_width=True):
                if idx + 1 < total:
                    st.session_state.update({
                        'current_idx': idx + 1,
                        'answered': False,
                        'status': 'normal',
                        'correct_text_to_show': "",
                        'start_time': time.time()
                    })
                    st.rerun()
                else:
                    st.session_state.is_finished = True
                    st.rerun()
    
    # Auto-refresh for timer
    if not st.session_state.answered and remaining_time > 0:
        time.sleep(1)
        st.rerun()

# 3. END SCREEN
else:
    score = st.session_state.score
    total_questions = len(st.session_state.questions)
    
    st.markdown(f"""
        <div class='question-card' style='text-align:center;'>
            <h1>MISSION COMPLETE</h1>
            <p style='font-size:2rem;'>FINAL SCORE: {score}/{total_questions}</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Final Rank Logic
    if total_questions > 0:
        percentage = (score / total_questions) * 100
    else:
        percentage = 0

    if percentage == 100:
        st.snow()
        st.success("GOD MODE: ACTIVATED 😂 🦾 تمت البصمجه بنجاح !")
    elif percentage >= 50:
        st.warning("AGENT RANK: C (PASSABLE) - مش بطال بس ركز شوية")
    else:
        st.error("AGENT RANK: F (SYSTEM FAILURE) - 😂 ارجع بصمج تاني يابني")
                
    if st.button("REBOOT SYSTEM", use_container_width=True):
        st.session_state.clear()
        st.rerun()
