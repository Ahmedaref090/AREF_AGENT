import streamlit as st
import PyPDF2
import json
import time
import requests
import re
from pdfminer.high_level import extract_text as fallback_extract_text

GROQ_API_KEY = "PUT_YOUR_KEY_HERE"

def generate_with_groq(text_input, mode):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    CHUNK_SIZE = 35000
    all_results = []

    if mode == "Solved Q&A Bank":
        instruction = "Extract all and every questions and their correct answers from this solved bank."

    elif mode == "Unsolved Q&A Bank":
        instruction = "Solve all and every this question bank and provide the correct answers."

    else:  # 🔥 LECTURE (المعدل)
        instruction = (
            "You are a strict university exam generator. "
            "Using ONLY the information explicitly stated in the provided lecture text, "
            "generate multiple choice questions (MCQs). "
            "Do NOT use any external knowledge, assumptions, or interpretations. "
            "Do NOT invent examples, scenarios, or applications. "
            "Every question MUST be directly answerable from the lecture text word-for-word. "
            "Focus strictly on definitions, stated facts, key concepts, and explanations exactly as written in the lecture."
        )

    for i in range(0, len(text_input), CHUNK_SIZE):
        chunk = text_input[i:i+CHUNK_SIZE].replace('"', "'")

        prompt = (
            f"{instruction} "
            "IMPORTANT: You MUST return ONLY a valid JSON array. Do not include any introductory or concluding text. "
            "The 'answer' field MUST contain the exact text of the correct option, not just a letter. "
            "Format: [{\"question\": \"...\", "
            "\"options\": [\"Option A\", \"Option B\", \"Option C\", \"Option D\"], "
            "\"answer\": \"Option A\"}]. "
            f"Text to analyze: {chunk}"
        )

        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.15  # أقل شطحات
        }

        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=40
            )
            res_json = response.json()

            if 'choices' in res_json:
                content = res_json['choices'][0]['message']['content']
                match = re.search(r'\[\s*\{.*\}\s*\]', content, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    all_results.extend(data)

        except:
            continue

    return all_results


# ================= STREAMLIT UI (UNCHANGED) =================

st.set_page_config(page_title="AREF AGENT | AI VISION", layout="centered")

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

st.title("AREF AGENT")

if not st.session_state.questions and not st.session_state.is_finished:
    data_mode = st.radio("SELECT DATA TYPE:", ["Solved Q&A Bank", "Unsolved Q&A Bank", "Lecture"], index=2)
    file = st.file_uploader("UPLOAD SYSTEM DATA (PDF)", type="pdf")

    if file and st.button("ACTIVATE NEURAL LINK"):
        with st.spinner("🧬 ANALYZING DATA..."):
            try:
                reader = PyPDF2.PdfReader(file)
                full_text = "".join([p.extract_text() for p in reader.pages])
                if not full_text.strip():
                    raise Exception("Empty")
            except:
                file.seek(0)
                full_text = fallback_extract_text(file)

            data = generate_with_groq(full_text, data_mode)
            if data:
                st.session_state.questions = data
                st.session_state.start_time = time.time()
                st.rerun()

elif st.session_state.questions and not st.session_state.is_finished:
    idx = st.session_state.current_idx
    q = st.session_state.questions[idx]

    st.subheader(f"QUESTION {idx+1}")
    st.write(q['question'])

    choice = st.radio("SELECT RESPONSE:", q['options'], key=f"q_{idx}")

    if st.button("VERIFY DATA"):
        if choice == q['answer']:
            st.session_state.score += 1
            st.success("SUCCESS ✅")
        else:
            st.error(f"CORRECT ANSWER: {q['answer']}")

        if st.button("NEXT ➡️"):
            st.session_state.current_idx += 1
            if st.session_state.current_idx >= len(st.session_state.questions):
                st.session_state.is_finished = True
            st.rerun()

else:
    score = st.session_state.score
    total = len(st.session_state.questions)
    st.success(f"MISSION COMPLETE — SCORE: {score}/{total}")
