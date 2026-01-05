import streamlit as st
import PyPDF2
import json
import time
import re
import io

# استيراد pdfminer
try:
    from pdfminer.high_level import extract_text as fallback_extract_text
except ImportError:
    fallback_extract_text = None

def extract_text_from_pdf(file):
    """استخراج النص من PDF بطريقتين"""
    file.seek(0)
    
    # الطريقة 1: PyPDF2
    try:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"
        
        if text.strip() and len(text.strip()) > 100:
            return text.strip(), "PyPDF2", len(reader.pages)
    except Exception as e:
        st.warning(f"⚠️ PyPDF2 issue: {str(e)[:100]}")
    
    # الطريقة 2: pdfminer
    if fallback_extract_text:
        try:
            file.seek(0)
            text = fallback_extract_text(file)
            if text.strip() and len(text.strip()) > 100:
                file.seek(0)
                reader = PyPDF2.PdfReader(file)
                return text.strip(), "pdfminer", len(reader.pages)
        except Exception as e:
            st.warning(f"⚠️ pdfminer issue: {str(e)[:100]}")
    
    file.seek(0)
    try:
        reader = PyPDF2.PdfReader(file)
        return "", "Failed", len(reader.pages)
    except:
        return "", "Failed", 0

async def generate_with_claude(text_input, mode):
    """توليد الأسئلة باستخدام Claude API"""
    
    safe_text = text_input[:100000].replace('"', "'").strip()
    
    if mode == "Solved Q&A Bank":
        instruction = "Extract all questions and their correct answers from this solved bank."
    elif mode == "Unsolved Q&A Bank":
        instruction = "Solve all questions in this question bank and provide the correct answers."
    else: 
        instruction = "Generate 15 to 20 clear, exam-oriented multiple choice questions (MCQs) based on this content."
    
    prompt = f"""{instruction}

CRITICAL INSTRUCTIONS:
1. Return ONLY a valid JSON array - no introduction, no explanation, no markdown
2. Each question must have exactly 4 options
3. The 'answer' field must contain the FULL TEXT of the correct option, not just a letter
4. Format: [{{"question": "...", "options": ["Option A", "Option B", "Option C", "Option D"], "answer": "Option A"}}]

Content to analyze:
{safe_text[:50000]}"""
    
    try:
        response = await fetch("https://api.anthropic.com/v1/messages", {{
            method: "POST",
            headers: {{
                "Content-Type": "application/json",
            }},
            body: JSON.stringify({{
                model: "claude-sonnet-4-20250514",
                max_tokens: 4000,
                messages: [
                    {{ role: "user", content: prompt }}
                ]
            }})
        }})
        
        data = await response.json()
        
        if data.content && data.content.length > 0:
            let content = data.content[0].text.trim()
            
            // استخراج JSON من الرد
            let match = content.match(/\[[\s\S]*\]/)
            if (match) {
                return JSON.parse(match[0])
            }
        }
        
        return []
    } catch (error) {
        console.error("Claude API Error:", error)
        return []
    }

st.set_page_config(page_title="AREF AGENT | AI VISION", layout="centered")

st.markdown("""
    <style>
    .stApp { background-image: url("https://i.pinimg.com/736x/d7/82/af/d782af00f9f7e36b7bd89b01926f1c06.jpg"); background-size: cover; background-attachment: fixed; }
    .stApp > div:first-child { background-color: rgba(0, 0, 0, 0.9); min-height: 100vh; }
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

if 'questions' not in st.session_state:
    st.session_state.update({
        'questions': [], 'current_idx': 0, 'score': 0, 
        'is_finished': False, 'answered': False, 'status': 'normal',
        'correct_text_to_show': "", 'start_time': None
    })

st.markdown('<h1 class="neon-title">AREF AGENT</h1>', unsafe_allow_html=True)

if not st.session_state.questions and not st.session_state.is_finished:
    st.info("⚠️ **Note**: Groq API limit reached. Using Claude API instead (better quality!)")
    
    data_mode = st.radio("SELECT DATA TYPE:", ["Solved Q&A Bank", "Unsolved Q&A Bank", "Lecture"], index=2)
    file = st.file_uploader("UPLOAD SYSTEM DATA (PDF)", type="pdf")
    
    if file and st.button("ACTIVATE NEURAL LINK"):
        with st.spinner("🧬 ANALYZING DATA..."):
            full_text, method, num_pages = extract_text_from_pdf(file)
            
            if not full_text or len(full_text.strip()) < 50:
                st.error("❌ FILE ERROR: Could not extract readable text from PDF.")
                st.info(f"📄 PDF Info: {num_pages} pages detected")
                st.markdown("""
                ### 💡 Possible solutions:
                - **Scanned PDF** - Use text-based PDF instead
                - **Password protected** - Remove protection
                - **Corrupted file** - Try another PDF
                """)
            else:
                st.success(f"✅ Text extracted using **{method}** ({len(full_text)} chars from {num_pages} pages)")
                
                with st.expander("📄 Preview extracted text"):
                    st.text(full_text[:300].replace('\n', ' ') + "...")
                
                st.info("🤖 Generating questions with Claude AI...")
                
                # هنا المفروض يستدعي Claude API
                # لكن Streamlit مش بيدعم async بشكل مباشر
                # هنحتاج نستخدم HTML/React artifact بدلاً من Streamlit
                
                st.warning("⚠️ To use Claude API, we need to convert this to a web app (HTML/React).")
                st.info("Would you like me to create an HTML version that works with Claude API?")

elif st.session_state.questions and not st.session_state.is_finished:
    idx = st.session_state.current_idx
    total = len(st.session_state.questions)
    remaining_nodes = total - (idx + 1)
    q = st.session_state.questions[idx]
    
    elapsed = time.time() - st.session_state.start_time
    remaining_time = max(0, 45 - int(elapsed))
    t_class = "stat-value"
    if remaining_time <= 10: t_class += " timer-critical"

    if remaining_time == 0 and not st.session_state.answered:
        st.session_state.answered = True
        st.session_state.status = 'wrong'
        st.session_state.correct_text_to_show = q['answer']
        st.rerun()

    st.markdown(f"""
    <div class="status-container">
        <div class="stat-item"><div class="stat-label">Total Nodes</div><div class="stat-value">{total}</div></div>
        <div class="stat-item"><div class="stat-label">Remaining</div><div class="stat-value" style="color:#ffcc00;">{remaining_nodes}</div></div>
        <div class="stat-item"><div class="stat-label">Timer</div><div class="{t_class}">{remaining_time}s</div></div>
        <div class="stat-item"><div class="stat-label">Score</div><div class="stat-value" style="color:#00ffcc;">{st.session_state.score}</div></div>
    </div>
    """, unsafe_allow_html=True)

    b_style = "question-card"
    if st.session_state.status == 'correct': b_style += " success-box"
    elif st.session_state.status == 'wrong': b_style += " error-box"

    st.markdown(f"<div class='{b_style}'><h3>NODE {idx+1}</h3><p style='font-size:1.4rem;'>{q['question']}</p></div>", unsafe_allow_html=True)
    
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
                st.error(f"CORRECT: {st.session_state.correct_text_to_show}")
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

    if not st.session_state.answered and remaining_time > 0:
        time.sleep(1)
        st.rerun()

else:
    score = st.session_state.score
    total_questions = len(st.session_state.questions)
    st.markdown(f"""
        <div class='question-card' style='text-align:center;'>
            <h1>MISSION COMPLETE</h1>
            <p style='font-size:2rem;'>FINAL SCORE: {score}/{total_questions}</p>
        </div>
    """, unsafe_allow_html=True)
    
    if score == total_questions:
        st.snow()
        st.success("GOD MODE ACTIVATED 😂 🦾")
    elif score >= int(total_questions/2):
        st.warning("PASS ✓ - ارجع بصمج تاني 😂")
    else:
        st.warning("FAIL ✗ - قوم ذاكر 😂")
                
    if st.button("REBOOT SYSTEM", use_container_width=True):
        st.session_state.clear()
        st.rerun()
