import os, json, random, string, traceback
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import quote
from flask import Flask, render_template, request, jsonify, session, send_file, redirect, url_for, flash
from dotenv import load_dotenv
from collections import defaultdict, Counter
import time

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'SmartHealth@2026#Vizag$Secure!Key')
app.permanent_session_lifetime = timedelta(hours=2)

# ── Rate Limiting ────────────────────────────────────────────────────────────
request_counts = defaultdict(list)
def rate_limit(max_calls=15, window=60):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.remote_addr
            now = time.time()
            request_counts[ip] = [t for t in request_counts[ip] if now - t < window]
            if len(request_counts[ip]) >= max_calls:
                return jsonify({'error': 'Too many requests. Please wait.'}), 429
            request_counts[ip].append(now)
            return f(*args, **kwargs)
        return wrapped
    return decorator

# ── Admin Auth ───────────────────────────────────────────────────────────────
def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return wrapped

# ── Imports ──────────────────────────────────────────────────────────────────
try:
    from predictor import predictor
    print("✅ Predictor loaded")
except Exception as e:
    print(f"❌ Predictor: {e}"); traceback.print_exc(); predictor = None

try:
    from claude_helper import get_disease_explanation, extract_symptoms_from_text, chat_with_assistant, get_medicine_info
    print("✅ Claude helper loaded")
except Exception as e:
    print(f"⚠️  Claude: {e}")
    get_disease_explanation = extract_symptoms_from_text = chat_with_assistant = get_medicine_info = None

try:
    from rag_engine import rag_engine
    print("✅ RAG engine loaded")
except Exception as e:
    print(f"⚠️  RAG: {e}"); rag_engine = None

# ── Data ─────────────────────────────────────────────────────────────────────
MEDICINE_DB = {
    'Common Cold': [
        {'name': 'Paracetamol (Crocin)', 'dosage': '500mg', 'frequency': 'Every 6 hours', 'duration': '3-5 days'},
        {'name': 'Cetirizine (Cetzine)', 'dosage': '10mg', 'frequency': 'Once daily at night', 'duration': '3-5 days'},
    ],
    'Flu': [
        {'name': 'Paracetamol (Crocin)', 'dosage': '650mg', 'frequency': 'Every 6 hours', 'duration': '5-7 days'},
        {'name': 'Vitamin C', 'dosage': '500mg', 'frequency': 'Once daily', 'duration': '7 days'},
    ],
    'Migraine': [
        {'name': 'Ibuprofen (Brufen)', 'dosage': '400mg', 'frequency': 'Every 8 hours with food', 'duration': '2-3 days'},
        {'name': 'Paracetamol (Crocin)', 'dosage': '500mg', 'frequency': 'Every 6 hours', 'duration': '2-3 days'},
    ],
    'Cardiac Issue': [
        {'name': '🚨 EMERGENCY — Call 108 immediately', 'dosage': '-', 'frequency': '-', 'duration': 'Go to hospital NOW'},
    ],
    'Skin Allergy': [
        {'name': 'Cetirizine (Cetzine)', 'dosage': '10mg', 'frequency': 'Once daily', 'duration': '3-5 days'},
        {'name': 'Calamine Lotion', 'dosage': 'Apply thin layer', 'frequency': '2-3 times daily', 'duration': 'Until rash clears'},
    ],
    'Gastroenteritis': [
        {'name': 'ORS (Electral)', 'dosage': '1 sachet in 1L water', 'frequency': 'After every loose motion', 'duration': 'Until recovery'},
        {'name': 'Domperidone (Domstal)', 'dosage': '10mg', 'frequency': 'Before meals', 'duration': '3 days'},
    ],
    'Arthritis': [
        {'name': 'Ibuprofen (Brufen)', 'dosage': '400mg', 'frequency': 'Every 8 hours with food', 'duration': 'As needed'},
        {'name': 'Diclofenac Gel', 'dosage': 'Apply to joint', 'frequency': '3 times daily', 'duration': 'As needed'},
    ],
    'Anaemia': [
        {'name': 'Iron + Folic Acid (Ferrous)', 'dosage': '100mg', 'frequency': 'Once daily after meals', 'duration': '3 months'},
    ],
    'Asthma': [
        {'name': 'Salbutamol Inhaler (Asthalin)', 'dosage': '2 puffs', 'frequency': 'When needed', 'duration': 'As prescribed'},
    ],
    'Conjunctivitis': [
        {'name': 'Sodium Chloride Eye Drops', 'dosage': '2 drops', 'frequency': 'Every 4 hours', 'duration': '3-5 days'},
    ],
    'Ear Infection': [
        {'name': 'Paracetamol for pain', 'dosage': '500mg', 'frequency': 'Every 6 hours', 'duration': 'Until doctor visit'},
    ],
    'Throat Infection': [
        {'name': 'Warm Salt Water Gargle', 'dosage': '1/2 tsp salt in warm water', 'frequency': '3-4 times daily', 'duration': '5 days'},
        {'name': 'Strepsils Lozenges', 'dosage': '1 lozenge', 'frequency': 'Every 3-4 hours', 'duration': '5 days'},
    ],
    'UTI': [
        {'name': 'Drink plenty of water', 'dosage': '8-10 glasses', 'frequency': 'Throughout day', 'duration': 'Until doctor visit'},
    ],
    'Diabetes': [
        {'name': 'Monitor blood sugar regularly', 'dosage': '-', 'frequency': 'As directed', 'duration': 'Ongoing'},
    ],
    'Hypertension': [
        {'name': 'Reduce salt intake', 'dosage': 'Low sodium diet', 'frequency': 'Daily', 'duration': 'Ongoing'},
    ],
}
DEFAULT_MEDICINE = [{'name': 'Paracetamol (Crocin)', 'dosage': '500mg', 'frequency': 'Every 6 hours', 'duration': '3 days'}]

MEDICAL_CAMPS = [
    {'id':1,'name':'Rural Health Awareness Camp','location':'Community Center, Old Resapuvanipalem, Visakhapatnam','date':'2026-06-15','time':'9:00 AM - 4:00 PM','services':'Free consultation, Basic medicines','contact':'9347336769','active':True},
    {'id':2,'name':'Cardiac Health Camp','location':'GHMC Health Center, Dwaraka Nagar, Visakhapatnam','date':'2026-06-20','time':'8:00 AM - 6:00 PM','services':'ECG, BP check, Cardiac consultation','contact':'0891-2755555','active':True},
    {'id':3,'name':'Gynaecology & Child Health Camp','location':'PHC Gajuwaka, Visakhapatnam','date':'2026-07-01','time':'9:00 AM - 5:00 PM','services':'Gynaecology, Paediatrics, Immunisation','contact':'0891-2587412','active':True},
    {'id':4,'name':'Diabetes & Hypertension Screening','location':'Town Hall, Seethammadhara, Visakhapatnam','date':'2026-07-10','time':'10:00 AM - 3:00 PM','services':'Blood sugar test, BP check, Diet counselling','contact':'9848012345','active':True},
]

consultation_log = []

def gen_token(): return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
def sanitize(t, n=200): return str(t).strip()[:n] if t else ''

def build_whatsapp_url(name, token, disease, specialization, symptoms):
    msg = (f"🏥 *Smart Healthcare Assistant*\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"👤 Patient: {name}\n"
           f"🔑 Token: {token}\n"
           f"🔬 Predicted: *{disease}*\n"
           f"👨‍⚕️ See: {specialization}\n"
           f"🤒 Symptoms: {', '.join(symptoms)}\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"⚠️ This is an AI advisory only. Please consult a doctor.\n"
           f"📱 Smart Healthcare Assistant — Dr. LBCE, Visakhapatnam")
    return f"https://wa.me/?text={quote(msg)}"

# ════════════════════════════════════════════════════════════════════════════
# PUBLIC ROUTES
# ════════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    symptoms_list = predictor.get_all_symptoms() if predictor else []
    return render_template('index.html', symptoms_list=symptoms_list)

@app.route('/predict', methods=['POST'])
@rate_limit(max_calls=15, window=60)
def predict():
    try:
        name     = sanitize(request.form.get('name','Patient'))
        age_str  = sanitize(request.form.get('age',''))
        gender   = sanitize(request.form.get('gender',''))
        severity = sanitize(request.form.get('severity','Moderate'))
        duration = sanitize(request.form.get('duration','3-5 days'))
        symptoms = request.form.getlist('symptoms')

        errors = []
        if not name or len(name) < 2: errors.append('Please enter a valid name.')
        if not age_str.isdigit() or not (1 <= int(age_str) <= 100): errors.append('Age must be between 1 and 100.')
        if gender not in ('Male','Female','Other'): errors.append('Please select a valid gender.')
        if not symptoms: errors.append('Please select at least one symptom.')
        if len(symptoms) > 20: errors.append('Maximum 20 symptoms allowed.')
        if errors:
            return render_template('index.html',
                symptoms_list=predictor.get_all_symptoms() if predictor else [],
                errors=errors), 400

        age = int(age_str)
        if predictor:
            disease, confidence, specialization = predictor.predict(symptoms)
        else:
            disease, confidence, specialization = 'General Health Concern', 0.5, 'General Physician'

        # Bump confidence for severe cases
        if severity == 'Severe': confidence = min(confidence + 0.1, 0.99)

        if get_disease_explanation:
            try:
                explanation = get_disease_explanation(symptoms, disease, confidence, specialization)
            except Exception as ce:
                print(f"Claude: {ce}")
                explanation = (f"**Why this prediction:**\nThese symptoms are commonly associated with {disease}.\n\n"
                               f"**Immediate care tips:**\nRest well, stay hydrated, avoid strenuous activity.\n\n"
                               f"**Important warning:**\nThis is NOT a medical diagnosis. Please consult a {specialization}.")
        else:
            explanation = (f"**Why this prediction:**\nThese symptoms are commonly associated with {disease}.\n\n"
                           f"**Immediate care tips:**\nRest well, stay hydrated, avoid strenuous activity.\n\n"
                           f"**Important warning:**\nThis is NOT a medical diagnosis. Please consult a {specialization}.")

        medicines = MEDICINE_DB.get(disease, DEFAULT_MEDICINE)
        if get_medicine_info:
            try: medicine_note = get_medicine_info(disease, [m['name'] for m in medicines])
            except: medicine_note = "Temporary suggestions only. Please consult a doctor."
        else:
            medicine_note = "Temporary suggestions only. Please consult a doctor."

        token = gen_token()
        now   = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        whatsapp_url = build_whatsapp_url(name, token, disease, specialization, symptoms)

        consultation = {
            'name':name,'age':age,'gender':gender,'symptoms':symptoms,
            'disease':disease,'confidence':f"{confidence:.0%}",
            'specialization':specialization,'token':token,'datetime':now,
            'explanation':explanation,'medicines':medicines,
            'medicine_note':medicine_note,'severity':severity,'duration':duration
        }
        session['consultation'] = consultation

        # History (last 5)
        history = session.get('history', [])
        history.insert(0, {
            'token':token,'name':name,'age':age,'gender':gender,
            'symptoms':symptoms,'disease':disease,
            'confidence':f"{confidence:.0%}",'specialization':specialization,
            'severity':severity,'duration':duration,'datetime':now
        })
        session['history'] = history[:5]

        # Global log
        consultation_log.append({
            'token':token,'name':name,'age':age,'gender':gender,
            'disease':disease,'specialization':specialization,
            'confidence':f"{confidence:.0%}",'severity':severity,'datetime':now
        })
        if len(consultation_log) > 200: consultation_log.pop(0)

        return render_template('result.html',
            name=name, age=age, gender=gender, symptoms=symptoms,
            disease=disease, confidence=f"{confidence:.0%}",
            specialization=specialization, token=token,
            explanation=explanation, medicines=medicines,
            medicine_note=medicine_note, severity=severity,
            duration=duration, whatsapp_url=whatsapp_url,
            camps=[c for c in MEDICAL_CAMPS if c.get('active',True)])

    except Exception as e:
        traceback.print_exc()
        return f"<h2 style='color:red'>Error: {e}</h2><a href='/'>← Go Back</a>", 500

@app.route('/history')
def history_page():
    history = session.get('history', [])
    return render_template('history.html', history=history)

@app.route('/chat')
def chat_page():
    session['chat_history'] = []
    return render_template('chat.html')

@app.route('/chat/message', methods=['POST'])
@rate_limit(max_calls=30, window=60)
def chat_message():
    try:
        data = request.json
        user_message = sanitize(data.get('message',''), 500)
        if not user_message: return jsonify({'error':'Empty message'}), 400

        history = session.get('chat_history', [])

        if chat_with_assistant:
            try: reply = chat_with_assistant(history, user_message)
            except: reply = "I'm having trouble connecting. Please select symptoms manually."
        else:
            reply = "AI chat requires an Anthropic API key in your .env file."

        extracted = []
        if extract_symptoms_from_text:
            try: extracted = extract_symptoms_from_text(user_message)
            except: pass

        history.append({"role":"user","content":user_message})
        history.append({"role":"assistant","content":reply})
        session['chat_history'] = history[-20:]
        return jsonify({'reply':reply,'extracted_symptoms':extracted})
    except Exception as e:
        return jsonify({'reply':'Error occurred.','extracted_symptoms':[]})

@app.route('/rag/ask', methods=['POST'])
@rate_limit(max_calls=20, window=60)
def rag_ask():
    try:
        data = request.json
        question = sanitize(data.get('question',''), 300)
        symptoms = data.get('symptoms', [])[:20]
        disease  = sanitize(data.get('disease',''))
        if not question: return jsonify({'error':'No question'}), 400
        if rag_engine:
            result = rag_engine.answer_with_rag(question, symptoms, disease)
        else:
            result = {'answer':'RAG not available. Check your API key.','sources_used':0}
        return jsonify(result)
    except Exception as e:
        return jsonify({'answer':f'Error: {e}','sources_used':0})

@app.route('/download_receipt')
def download_receipt():
    try:
        from fpdf import FPDF
        c = session.get('consultation')
        if not c: return "<h2>No consultation found.</h2><a href='/'>← Back</a>", 404

        pdf = FPDF()
        pdf.add_page()
        pdf.set_fill_color(26,43,74); pdf.rect(0,0,210,38,'F')
        pdf.set_text_color(255,255,255); pdf.set_font('Arial','B',16)
        pdf.set_y(8); pdf.cell(0,10,'Smart Healthcare Assistant',ln=True,align='C')
        pdf.set_font('Arial','',10)
        pdf.cell(0,7,'AI-Powered Medical Guidance | Dr. Lankapalli Bullayya College, Visakhapatnam',ln=True,align='C')
        pdf.cell(0,7,'Powered by Claude AI + Machine Learning',ln=True,align='C')
        pdf.set_text_color(0,0,0); pdf.set_y(46)
        pdf.set_font('Arial','B',12); pdf.set_fill_color(239,246,255)
        pdf.cell(0,9,f"  Token: {c['token']}   |   Date: {c['datetime']}",ln=True,fill=True)
        pdf.ln(3)
        def section(title):
            pdf.set_font('Arial','B',11); pdf.set_fill_color(26,43,74); pdf.set_text_color(255,255,255)
            pdf.cell(0,8,f'  {title}',ln=True,fill=True); pdf.set_text_color(0,0,0); pdf.set_font('Arial','',10)
        section('Patient Details')
        pdf.cell(0,7,f"  Name: {c['name']}   |   Age: {c['age']}   |   Gender: {c['gender']}   |   Severity: {c['severity']}",ln=True); pdf.ln(2)
        section('Symptoms')
        pdf.multi_cell(0,7,'  '+', '.join(c['symptoms'])); pdf.ln(2)
        section('AI Prediction')
        pdf.set_font('Arial','B',10)
        pdf.cell(0,7,f"  Predicted: {c['disease']}  (Confidence: {c['confidence']})",ln=True)
        pdf.set_font('Arial','',10)
        pdf.cell(0,7,f"  Recommended Specialist: {c['specialization']}",ln=True); pdf.ln(2)
        section('AI Analysis (Claude)')
        pdf.set_font('Arial','',9)
        pdf.multi_cell(0,6,c['explanation'].replace('**','').replace('*','')); pdf.ln(2)
        section('Temporary Medicine Suggestions')
        pdf.set_font('Arial','B',9)
        pdf.cell(65,7,'Medicine',border=1); pdf.cell(28,7,'Dosage',border=1)
        pdf.cell(48,7,'Frequency',border=1); pdf.cell(38,7,'Duration',border=1,ln=True)
        pdf.set_font('Arial','',9)
        for m in c['medicines']:
            pdf.cell(65,7,str(m['name'])[:32],border=1); pdf.cell(28,7,str(m['dosage']),border=1)
            pdf.cell(48,7,str(m['frequency']),border=1); pdf.cell(38,7,str(m['duration']),border=1,ln=True)
        pdf.ln(3); pdf.set_fill_color(255,243,205); pdf.set_font('Arial','B',9)
        pdf.multi_cell(0,6,'IMPORTANT: AI advisory only — NOT a medical diagnosis. Consult a qualified doctor.',fill=True)
        import tempfile
        tmp = os.path.join(tempfile.gettempdir(), f'receipt_{os.urandom(4).hex()}.pdf')
        pdf.output(tmp)
        return send_file(tmp,as_attachment=True,
                         download_name=f"SmartHealth_{c['token']}.pdf",
                         mimetype='application/pdf')
    except Exception as e:
        traceback.print_exc()
        return f"<h2>PDF Error: {e}</h2><a href='/'>← Back</a>", 500

# ════════════════════════════════════════════════════════════════════════════
# ADMIN ROUTES — Full RBAC
# ════════════════════════════════════════════════════════════════════════════
from auth_manager import (
    login_user, get_all_users, add_user,
    update_user, toggle_user, delete_user,
    has_permission, ROLE_PERMISSIONS, ROLE_LABELS,
    generate_reset_otp, verify_otp_and_reset, change_password
)

def require_permission(permission):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not session.get('admin_logged_in'):
                return redirect(url_for('admin_login'))
            role = session.get('admin_role', 'viewer')
            if not has_permission(role, permission):
                return render_template('admin_403.html',
                    admin_user=session.get('admin_user'),
                    admin_role=role,
                    required=permission), 403
            return f(*args, **kwargs)
        return wrapped
    return decorator

@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username','').strip().lower()
        password = request.form.get('password','')
        user     = login_user(username, password)
        if user:
            session['admin_logged_in'] = True
            session['admin_user']      = user['username']
            session['admin_name']      = user['name']
            session['admin_role']      = user['role']
            flash(f"Welcome back, {user['name']}! 👋", 'success')
            return redirect(url_for('admin_dashboard'))
        error = 'Invalid username or password.'
    return render_template('admin_login.html', error=error)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_user',      None)
    session.pop('admin_name',      None)
    session.pop('admin_role',      None)
    return redirect(url_for('admin_login'))

@app.route('/admin')
@app.route('/admin/dashboard')
@admin_required
@require_permission('view_dashboard')
def admin_dashboard():
    role           = session.get('admin_role', 'viewer')
    disease_counts = dict(Counter(c['disease'] for c in consultation_log).most_common(8))
    age_groups     = {'0-18':0,'19-35':0,'36-50':0,'51-65':0,'65+':0}
    for c in consultation_log:
        a = c.get('age', 0)
        if   a <= 18: age_groups['0-18']  += 1
        elif a <= 35: age_groups['19-35'] += 1
        elif a <= 50: age_groups['36-50'] += 1
        elif a <= 65: age_groups['51-65'] += 1
        else:         age_groups['65+']   += 1
    stats = {
        'total_consultations': len(consultation_log),
        'today':        sum(1 for c in consultation_log if c['datetime'].startswith(datetime.now().strftime('%Y-%m-%d'))),
        'active_camps': sum(1 for c in MEDICAL_CAMPS if c.get('active', True)),
        'total_camps':  len(MEDICAL_CAMPS),
        'top_disease':  Counter(c['disease'] for c in consultation_log).most_common(1)[0][0] if consultation_log else 'N/A',
        'disease_counts': disease_counts,
        'age_groups':     age_groups,
        'total_users':    len(get_all_users()),
    }
    return render_template('admin.html',
        camps            = MEDICAL_CAMPS,
        consultation_log = list(reversed(consultation_log[-20:])),
        stats            = stats,
        admin_user       = session.get('admin_user', 'Admin'),
        admin_name       = session.get('admin_name', 'Admin'),
        admin_role       = role,
        role_label       = ROLE_LABELS.get(role, role),
        permissions      = ROLE_PERMISSIONS.get(role, []))

@app.route('/admin/camp/add', methods=['POST'])
@admin_required
@require_permission('manage_camps')
def admin_add_camp():
    new_id = max((c['id'] for c in MEDICAL_CAMPS), default=0) + 1
    MEDICAL_CAMPS.append({
        'id':       new_id,
        'name':     sanitize(request.form.get('name','')),
        'location': sanitize(request.form.get('location','')),
        'date':     sanitize(request.form.get('date','')),
        'time':     sanitize(request.form.get('time','')),
        'services': sanitize(request.form.get('services','')),
        'contact':  sanitize(request.form.get('contact','')),
        'active':   True,
        'added_by': session.get('admin_user','admin'),
    })
    flash('✅ Camp added successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/camp/delete/<int:camp_id>')
@admin_required
@require_permission('manage_camps')
def admin_delete_camp(camp_id):
    global MEDICAL_CAMPS
    MEDICAL_CAMPS = [c for c in MEDICAL_CAMPS if c['id'] != camp_id]
    flash('Camp deleted.', 'info')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/camp/toggle/<int:camp_id>')
@admin_required
@require_permission('manage_camps')
def admin_toggle_camp(camp_id):
    for c in MEDICAL_CAMPS:
        if c['id'] == camp_id:
            c['active'] = not c.get('active', True)
            break
    flash('Camp status updated.', 'success')
    return redirect(url_for('admin_dashboard'))

# ── User Management ───────────────────────────────────────────────────────────
@app.route('/admin/users')
@admin_required
@require_permission('manage_users')
def admin_users():
    users = get_all_users()
    return render_template('admin_users.html',
        users       = users,
        role_labels = ROLE_LABELS,
        roles       = list(ROLE_PERMISSIONS.keys()),
        admin_user  = session.get('admin_user'),
        admin_name  = session.get('admin_name'),
        admin_role  = session.get('admin_role'),
        role_label  = ROLE_LABELS.get(session.get('admin_role','viewer')))

@app.route('/admin/users/add', methods=['POST'])
@admin_required
@require_permission('manage_users')
def admin_add_user():
    success, msg = add_user(
        username   = request.form.get('username','').strip(),
        password   = request.form.get('password',''),
        name       = request.form.get('name','').strip(),
        email      = request.form.get('email','').strip(),
        role       = request.form.get('role','viewer'),
        created_by = session.get('admin_user','admin')
    )
    flash(('✅ ' if success else '❌ ') + msg, 'success' if success else 'error')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/edit/<username>', methods=['POST'])
@admin_required
@require_permission('manage_users')
def admin_edit_user(username):
    data = {
        'name':  request.form.get('name','').strip(),
        'email': request.form.get('email','').strip(),
        'role':  request.form.get('role','viewer'),
    }
    if request.form.get('password','').strip():
        data['password'] = request.form.get('password')
    success, msg = update_user(username, data, session.get('admin_user'))
    flash(('✅ ' if success else '❌ ') + msg, 'success' if success else 'error')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/toggle/<username>')
@admin_required
@require_permission('manage_users')
def admin_toggle_user(username):
    success, msg = toggle_user(username, session.get('admin_user'))
    flash(('✅ ' if success else '❌ ') + msg, 'success' if success else 'error')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/delete/<username>')
@admin_required
@require_permission('manage_users')
def admin_delete_user(username):
    success, msg = delete_user(username, session.get('admin_user'))
    flash(('✅ ' if success else '❌ ') + msg, 'success' if success else 'error')
    return redirect(url_for('admin_users'))

@app.route('/translate', methods=['POST'])
def translate_text():
    try:
        data = request.json
        text = sanitize(data.get('text', ''), 500)
        from_lang = data.get('from', 'Telugu')
        to_lang   = data.get('to', 'English')

        if not text:
            return jsonify({'translated': text})

        import anthropic, os
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": (f"Translate the following {from_lang} medical text to {to_lang}. "
                            f"Return ONLY the translated text, nothing else.\n\n"
                            f"Text: {text}")
            }]
        )
        translated = response.content[0].text.strip()
        return jsonify({'translated': translated, 'original': text})

    except Exception as e:
        print(f"Translation error: {e}")
        return jsonify({'translated': data.get('text', ''), 'error': str(e)})

# ── Forgot Password ───────────────────────────────────────────────────────────
@app.route('/admin/forgot-password', methods=['GET', 'POST'])
def admin_forgot_password():
    step    = request.args.get('step', '1')
    message = None
    error   = None

    if request.method == 'POST':
        step = request.form.get('step', '1')

        if step == '1':
            # Request OTP
            username     = request.form.get('username', '').strip().lower()
            success, otp = generate_reset_otp(username)
            if success:
                # Store username in session for next step
                session['reset_username'] = username
                flash(f"✅ OTP generated! For this demo, your OTP is: {otp}", 'success')
                return redirect(url_for('admin_forgot_password', step='2'))
            else:
                error = otp  # otp contains error message here

        elif step == '2':
            # Verify OTP and reset password
            username     = session.get('reset_username', '')
            otp          = request.form.get('otp', '').strip()
            new_password = request.form.get('new_password', '')
            confirm      = request.form.get('confirm_password', '')

            if new_password != confirm:
                error = "Passwords do not match."
            else:
                success, msg = verify_otp_and_reset(username, otp, new_password)
                if success:
                    session.pop('reset_username', None)
                    flash('✅ ' + msg, 'success')
                    return redirect(url_for('admin_login'))
                else:
                    error = msg

    return render_template('admin_forgot_password.html',
        step=step, error=error, message=message,
        username=session.get('reset_username', ''))


# ── Change Password (logged in) ───────────────────────────────────────────────
@app.route('/admin/change-password', methods=['GET', 'POST'])
@admin_required
def admin_change_password():
    error   = None
    success = None

    if request.method == 'POST':
        old_password = request.form.get('old_password', '')
        new_password = request.form.get('new_password', '')
        confirm      = request.form.get('confirm_password', '')

        if new_password != confirm:
            error = "New passwords do not match."
        else:
            ok, msg = change_password(
                session.get('admin_user'), old_password, new_password
            )
            if ok:
                success = msg
            else:
                error = msg

    return render_template('admin_change_password.html',
        error      = error,
        success    = success,
        admin_user = session.get('admin_user'),
        admin_name = session.get('admin_name'),
        admin_role = session.get('admin_role'),
        role_label = ROLE_LABELS.get(session.get('admin_role', 'viewer')))


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)
