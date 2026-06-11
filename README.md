# 🏥 Smart Healthcare Assistant

An AI-powered healthcare guidance web application built with **Flask**, **Claude API**, **RAG**, and **Machine Learning**.

Developed by **B. Chandra Vamsireddy** — Software Developer | B.Tech (CSE) Graduate | AI & Machine Learning Enthusiast.

---

## 🚀 Live Demo

> Deployed on Render — [Link coming soon]

---

## ✨ Features

- 🔬 **ML Disease Prediction** — Random Forest model predicts disease from symptoms
- 🤖 **Claude AI Explanation** — Claude API explains predictions in simple language
- 🧠 **RAG Medical Q&A** — Ask any health question, answered from a medical knowledge base
- 🎤 **Voice Input** — Speak symptoms in English or Telugu (auto-translated)
- 🌐 **Telugu Language Support** — Full UI toggle between English and Telugu
- 🚨 **Emergency Detection** — Automatic alert for cardiac/emergency symptoms
- ⚠️ **Symptom Severity** — Mild / Moderate / Severe assessment
- 📱 **WhatsApp Sharing** — Share consultation receipt on WhatsApp
- 📄 **PDF Receipt** — Download digital consultation receipt
- 🖨️ **Print Support** — Print-friendly result pages
- 🌙 **Dark Mode** — Full dark/light theme toggle
- 📋 **Patient History** — Last 5 consultations in session
- 🔐 **Role-Based Access Control** — Super Admin, Admin, Doctor, Viewer roles
- 📊 **Admin Dashboard** — Live charts, consultation logs, camp management

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask |
| AI/LLM | Anthropic Claude API (claude-sonnet-4) |
| ML | Scikit-learn, Random Forest |
| RAG | Custom keyword-based retrieval + Claude |
| PDF | FPDF2 |
| Frontend | HTML, CSS, JavaScript, Chart.js |
| Auth | Session-based RBAC with SHA-256 hashed passwords |

---

## 🏃 Run Locally

```bash
# Clone the repo
git clone https://github.com/vamsireddyboyi/SmartHealthcareAssistant.git
cd SmartHealthcareAssistant

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "ANTHROPIC_API_KEY=your_key_here" > .env
echo "SECRET_KEY=your_secret_key" >> .env

# Run
python app.py
```

Open **http://localhost:5000**

---

## 🔐 Admin Access

| URL | Credentials |
|---|---|
| `/admin/login` | username: `admin` / password: `Health@Admin2026` |

---

## 📁 Project Structure

```
SmartHealthcareAssistant/
├── app.py              ← Main Flask application
├── predictor.py        ← ML disease prediction model
├── claude_helper.py    ← Claude API integration
├── rag_engine.py       ← RAG medical knowledge base
├── auth_manager.py     ← RBAC user management
├── data/
│   └── training_data.csv
├── templates/          ← HTML templates
└── static/             ← CSS, JS assets
```

---

## 👨‍💻 Developer

**B. Chandra Vamsireddy**
- GitHub: [github.com/vamsireddyboyi](https://github.com/Vamsireddy-celestial)
- College: Dr. Lankapalli Bullayya College of Engineering, Visakhapatnam
- Degree: B.Tech CSE (Lateral Entry) 2023–2026

---

## ⚠️ Disclaimer

This is an AI advisory tool only — **NOT a medical diagnosis system**. Always consult a qualified healthcare professional for medical decisions.
