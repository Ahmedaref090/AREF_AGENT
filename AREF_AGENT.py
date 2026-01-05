import streamlit as st
import PyPDF2
import json
import time
import requests
import re
from pdfminer.high_level import extract_text as fallback_extract_text

# ================== CONFIG ==================
GROQ_API_KEY = "PUT_YOUR_KEY_HERE"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# ================== GROQ FUNCTION ==================
def generate_with_groq(text_input, mode):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    CHUNK_SIZE = 30000
    all_results = []

    if mode == "Solved Q&A Bank":
        instruction = "Extract all questions and their correct answers exactly as written."

    elif mode == "Unsolved Q&A Bank":
        instruction = "Solve all questions and provide the correct answers."

    else:  # LECTURE
        instruction = (
            "You are a university exam question generator. "
            "Generate multiple choice questions strictly based on the provided lecture text only. "
            "Do not use any external knowledge. "
            "Questions must be directly answerable from the lecture text."
        )

    for i in range(0, len(text_input), CHUNK_SIZE):
        chunk = text_input[i:i + CHUNK_SIZE]

        prompt = f"""
{instruction}

Return ONLY valid JSON in the following format:
[
  {{
    "question": "string",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "answer": "exact correct option text"
  }}
]

Lecture text:
{chunk}
"""

        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2
        }

        try:
            response = requests.post(
                GROQ_URL,
                headers=headers,
                json=payload,
                timeout=60
            )

            res_json = response.json()
            content = res_json["choices"][0]["message"]["content"]

            match = re.search(r'\[\s*{[\s\S]*?}\s*\]', content)
            if match:
                data = json.loads(match.group())
                if isinstance(data, list):
                    all_results.extend(data)

        except:
            continue

    return all_results

# ================== STREAMLIT UI ==================
st.set_page_config(page_title="AREF AGENT", layout="centered")
st.title("🧠 AREF AGENT")

if "questions" not in st.session_state:
    st.session_state.questions = []
    st.session_state.idx = 0
    st.session_state.score = 0
    st.session_state.finished = False

if not st.session_state.questions and not st.session_state.finished:
    mode = st.radio(
        "SELECT DATA TYPE:",
        ["Solved Q&A Bank", "Unsolved Q&A Bank", "Lecture"],
        index=2
    )

    file = st.file_uploader("UPLOAD PDF FILE", type="pdf")

    if file and st.button("PROCESS"):
        with st.spinner("Processing PDF..."):
            try:
                reader = PyPDF2.PdfReader(file)
                text = "".join(p.extract_text() or "" for p in reader.pages)
                if not text.strip():
                    raise Exception()
            except:
                file.seek(0)
                text = fallback_extract_text(file)

            questions = generate_with_groq(text, mode)
            if questions:
                st.session_state.questions = questions
                st.session_state.idx = 0
                st.session_state.score = 0
                st.rerun()
            else:
                st.error("No questions generated. Try another file.")

elif st.session_state.questions and not st.session_state.finished:
    q = st.session_state.questions[st.session_state.idx]

    st.subheader(f"Question {st.session_state.idx + 1}")
    st.write(q["question"])

    choice = st.radio("Choose answer:", q["options"], key=st.session_state.idx)

    if st.button("Submit"):
        if choice == q["answer"]:
            st.session_state.score += 1
            st.success("Correct ✅")
        else:
            st.error(f"Correct answer: {q['answer']}")

        if st.button("Next"):
            st.session_state.idx += 1
            if st.session_state.idx >= len(st.session_state.questions):
                st.session_state.finished = True
            st.rerun()

else:
    total = len(st.session_state.questions)
    score = st.session_state.score
    st.success(f"Finished 🎉  Score: {score}/{total}")

    if st.button("Restart"):
        st.session_state.clear()
        st.rerun()
