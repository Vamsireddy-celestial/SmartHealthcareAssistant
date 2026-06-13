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

# ── Medicine DB ───────────────────────────────────────────────────────────────
MEDICINE_DB = {
    'Common Cold': [
        {'name': 'Paracetamol (Crocin 500mg)', 'dosage': '500mg', 'frequency': 'Every 6 hours', 'duration': '3-5 days'},
        {'name': 'Cetirizine (Cetzine)', 'dosage': '10mg', 'frequency': 'Once at night', 'duration': '3-5 days'},
        {'name': 'Steam Inhalation', 'dosage': 'Inhale steam', 'frequency': 'Twice daily', 'duration': '5 days'},
    ],
    'Flu': [
        {'name': 'Paracetamol (Crocin 650mg)', 'dosage': '650mg', 'frequency': 'Every 6 hours', 'duration': '5-7 days'},
        {'name': 'Oseltamivir (Tamiflu) - Doctor prescribed', 'dosage': '75mg', 'frequency': 'Twice daily', 'duration': '5 days'},
        {'name': 'Vitamin C + Zinc', 'dosage': '500mg', 'frequency': 'Once daily', 'duration': '7 days'},
    ],
    'COVID-19': [
        {'name': 'Paracetamol (Crocin)', 'dosage': '650mg', 'frequency': 'Every 6 hours if fever', 'duration': 'As needed'},
        {'name': 'Vitamin C', 'dosage': '1000mg', 'frequency': 'Once daily', 'duration': '14 days'},
        {'name': 'Vitamin D3', 'dosage': '60000 IU', 'frequency': 'Once a week', 'duration': '4 weeks'},
        {'name': 'Zinc Supplement', 'dosage': '50mg', 'frequency': 'Once daily', 'duration': '14 days'},
    ],
    'Migraine': [
        {'name': 'Sumatriptan (Suminat)', 'dosage': '50mg', 'frequency': 'At onset of migraine', 'duration': 'As needed'},
        {'name': 'Ibuprofen (Brufen)', 'dosage': '400mg', 'frequency': 'Every 8 hours with food', 'duration': '2-3 days'},
        {'name': 'Domperidone (Domstal)', 'dosage': '10mg', 'frequency': 'For nausea if needed', 'duration': '2-3 days'},
    ],
    'Cardiac Issue': [
        {'name': '🚨 EMERGENCY — Call 108 immediately', 'dosage': '-', 'frequency': '-', 'duration': 'Go to hospital NOW'},
        {'name': 'Aspirin (only if prescribed)', 'dosage': '325mg', 'frequency': 'Once — doctor advice only', 'duration': 'Emergency use'},
    ],
    'Hypertension': [
        {'name': 'Amlodipine (Doctor prescribed)', 'dosage': '5mg', 'frequency': 'Once daily morning', 'duration': 'Ongoing'},
        {'name': 'Avoid salt completely', 'dosage': 'Low sodium diet', 'frequency': 'Daily', 'duration': 'Lifelong'},
        {'name': 'Telmisartan (Doctor prescribed)', 'dosage': '40mg', 'frequency': 'Once daily', 'duration': 'Ongoing'},
    ],
    'Skin Allergy': [
        {'name': 'Cetirizine (Cetzine)', 'dosage': '10mg', 'frequency': 'Once daily at night', 'duration': '5-7 days'},
        {'name': 'Calamine Lotion', 'dosage': 'Apply thin layer', 'frequency': '3 times daily on affected area', 'duration': 'Until rash clears'},
        {'name': 'Hydrocortisone Cream 1%', 'dosage': 'Apply small amount', 'frequency': 'Twice daily', 'duration': '5 days'},
    ],
    'Eczema': [
        {'name': 'Cetaphil Moisturizing Cream', 'dosage': 'Apply generously', 'frequency': '3-4 times daily', 'duration': 'Ongoing'},
        {'name': 'Hydrocortisone Cream 1%', 'dosage': 'Apply thin layer', 'frequency': 'Twice daily on rash', 'duration': '7 days'},
        {'name': 'Cetirizine (Cetzine)', 'dosage': '10mg', 'frequency': 'Once at night for itching', 'duration': '5-7 days'},
    ],
    'Acne': [
        {'name': 'Benzoyl Peroxide Gel 2.5%', 'dosage': 'Apply on pimples', 'frequency': 'Once daily at night', 'duration': '4-6 weeks'},
        {'name': 'Clindamycin Gel (Doctor prescribed)', 'dosage': 'Apply thin layer', 'frequency': 'Twice daily', 'duration': '6 weeks'},
        {'name': 'Salicylic Acid Face Wash', 'dosage': 'Use while washing face', 'frequency': 'Twice daily', 'duration': 'Ongoing'},
    ],
    'Gastroenteritis': [
        {'name': 'ORS (Electral)', 'dosage': '1 sachet in 1L water', 'frequency': 'After every loose motion', 'duration': 'Until recovery'},
        {'name': 'Domperidone (Domstal)', 'dosage': '10mg', 'frequency': 'Before meals 3 times daily', 'duration': '3 days'},
        {'name': 'Loperamide (Imodium)', 'dosage': '2mg', 'frequency': 'After each loose stool max 4/day', 'duration': '2 days'},
        {'name': 'Probiotic (Darolac)', 'dosage': '1 capsule', 'frequency': 'Twice daily', 'duration': '5 days'},
    ],
    'Food Poisoning': [
        {'name': 'ORS (Electral)', 'dosage': '1 sachet in 1L water', 'frequency': 'Every hour', 'duration': 'Until vomiting stops'},
        {'name': 'Ondansetron (Emeset)', 'dosage': '4mg', 'frequency': 'Every 8 hours for vomiting', 'duration': '2-3 days'},
        {'name': 'Activated Charcoal', 'dosage': '500mg', 'frequency': 'Once immediately', 'duration': 'Single dose'},
    ],
    'GERD': [
        {'name': 'Pantoprazole (Pantocid)', 'dosage': '40mg', 'frequency': 'Before breakfast daily', 'duration': '4 weeks'},
        {'name': 'Antacid (Gelusil/Digene)', 'dosage': '2 teaspoons', 'frequency': 'After meals and at bedtime', 'duration': 'As needed'},
        {'name': 'Domperidone (Domstal)', 'dosage': '10mg', 'frequency': '30 mins before meals', 'duration': '2 weeks'},
    ],
    'Gastritis': [
        {'name': 'Pantoprazole (Pantocid)', 'dosage': '40mg', 'frequency': 'Before breakfast daily', 'duration': '2-4 weeks'},
        {'name': 'Antacid (Gelusil)', 'dosage': '2 teaspoons', 'frequency': 'After meals', 'duration': 'As needed'},
        {'name': 'Sucralfate (Sucral)', 'dosage': '1g', 'frequency': 'Before meals 3 times daily', 'duration': '4 weeks'},
    ],
    'IBS': [
        {'name': 'Mebeverine (Colofac)', 'dosage': '135mg', 'frequency': '3 times daily before meals', 'duration': '4 weeks'},
        {'name': 'Isabgol (Psyllium Husk)', 'dosage': '1 teaspoon', 'frequency': 'Twice daily with water', 'duration': 'Ongoing'},
        {'name': 'Probiotic (Darolac)', 'dosage': '1 capsule', 'frequency': 'Once daily', 'duration': '4 weeks'},
    ],
    'Indigestion': [
        {'name': 'Antacid (Digene/Gelusil)', 'dosage': '2 teaspoons', 'frequency': 'After meals', 'duration': 'As needed'},
        {'name': 'Domperidone (Domstal)', 'dosage': '10mg', 'frequency': 'Before meals', 'duration': '5 days'},
        {'name': 'Eno Fruit Salt', 'dosage': '1 sachet in water', 'frequency': 'Once for immediate relief', 'duration': 'As needed'},
    ],
    'Piles': [
        {'name': 'Sitz Bath (warm water 15 mins)', 'dosage': 'Sit in warm water', 'frequency': '3 times daily', 'duration': '1-2 weeks'},
        {'name': 'Docusate Stool Softener', 'dosage': '100mg', 'frequency': 'Once daily', 'duration': '1 week'},
        {'name': 'Anovate Cream (Doctor advised)', 'dosage': 'Apply externally', 'frequency': 'After each bowel movement', 'duration': '1 week'},
    ],
    'Arthritis': [
        {'name': 'Ibuprofen (Brufen)', 'dosage': '400mg', 'frequency': 'Every 8 hours with food', 'duration': 'As needed'},
        {'name': 'Diclofenac Gel (Voltaren)', 'dosage': 'Apply to joint', 'frequency': '3-4 times daily', 'duration': 'As needed'},
        {'name': 'Glucosamine + Chondroitin', 'dosage': '1500mg', 'frequency': 'Once daily', 'duration': '3 months'},
    ],
    'Back Pain': [
        {'name': 'Ibuprofen (Brufen)', 'dosage': '400mg', 'frequency': 'Every 8 hours with food', 'duration': '5-7 days'},
        {'name': 'Diclofenac Gel (Voltaren)', 'dosage': 'Apply to back', 'frequency': '3 times daily', 'duration': '1 week'},
        {'name': 'Thiocolchicoside Muscle Relaxant', 'dosage': '4mg', 'frequency': 'Twice daily', 'duration': '5 days'},
    ],
    'Knee Problem': [
        {'name': 'Ibuprofen (Brufen)', 'dosage': '400mg', 'frequency': 'Every 8 hours with food', 'duration': '5-7 days'},
        {'name': 'Diclofenac Gel', 'dosage': 'Apply on knee', 'frequency': '3 times daily', 'duration': '1-2 weeks'},
        {'name': 'Knee support brace', 'dosage': 'Wear during activity', 'frequency': 'Daily', 'duration': 'As needed'},
    ],
    'Shoulder Problem': [
        {'name': 'Ibuprofen (Brufen)', 'dosage': '400mg', 'frequency': 'Every 8 hours with food', 'duration': '5-7 days'},
        {'name': 'Diclofenac Gel', 'dosage': 'Apply on shoulder', 'frequency': '3 times daily', 'duration': '1 week'},
        {'name': 'Hot water bottle on shoulder', 'dosage': '15 mins', 'frequency': 'Twice daily', 'duration': '1 week'},
    ],
    'Cervical Spondylosis': [
        {'name': 'Ibuprofen (Brufen)', 'dosage': '400mg', 'frequency': 'Every 8 hours with food', 'duration': '5 days'},
        {'name': 'Thiocolchicoside Muscle Relaxant', 'dosage': '4mg', 'frequency': 'Twice daily', 'duration': '5 days'},
        {'name': 'Neck collar support', 'dosage': 'Wear during rest', 'frequency': 'As needed', 'duration': '1-2 weeks'},
    ],
    'Carpal Tunnel Syndrome': [
        {'name': 'Ibuprofen (Brufen)', 'dosage': '400mg', 'frequency': 'Every 8 hours with food', 'duration': '5 days'},
        {'name': 'Wrist splint wear at night', 'dosage': '-', 'frequency': 'Every night', 'duration': '4-6 weeks'},
        {'name': 'Vitamin B6', 'dosage': '50mg', 'frequency': 'Once daily', 'duration': '3 months'},
    ],
    'Plantar Fasciitis': [
        {'name': 'Ibuprofen (Brufen)', 'dosage': '400mg', 'frequency': 'Every 8 hours with food', 'duration': '7 days'},
        {'name': 'Ice pack on heel 10-15 mins', 'dosage': '-', 'frequency': '3 times daily', 'duration': '1-2 weeks'},
        {'name': 'Heel cushion orthotic insoles', 'dosage': 'Wear in shoes', 'frequency': 'Daily', 'duration': 'Ongoing'},
    ],
    'Anaemia': [
        {'name': 'Iron + Folic Acid (Ferrous Sulphate)', 'dosage': '150mg', 'frequency': 'Once daily after meals', 'duration': '3-6 months'},
        {'name': 'Vitamin B12 (Methylcobalamin)', 'dosage': '500mcg', 'frequency': 'Once daily', 'duration': '3 months'},
        {'name': 'Iron-rich foods: spinach, jaggery, dates', 'dosage': 'Daily diet', 'frequency': 'Every meal', 'duration': 'Ongoing'},
    ],
    'Diabetes': [
        {'name': 'Monitor blood sugar (glucometer)', 'dosage': 'Check fasting and post meal', 'frequency': 'Twice daily', 'duration': 'Ongoing'},
        {'name': 'Metformin (Doctor prescribed)', 'dosage': '500mg', 'frequency': 'With meals twice daily', 'duration': 'Ongoing'},
        {'name': 'Avoid sugar, white rice, maida', 'dosage': '-', 'frequency': 'Daily', 'duration': 'Lifelong'},
    ],
    'Asthma': [
        {'name': 'Salbutamol Inhaler (Asthalin)', 'dosage': '2 puffs', 'frequency': 'When breathlessness occurs', 'duration': 'As needed'},
        {'name': 'Budesonide Inhaler (Doctor prescribed)', 'dosage': '200mcg', 'frequency': 'Twice daily', 'duration': 'Ongoing'},
        {'name': 'Montelukast (Montair)', 'dosage': '10mg', 'frequency': 'Once at night', 'duration': 'As advised'},
    ],
    'Pneumonia': [
        {'name': 'Amoxicillin (Doctor prescribed)', 'dosage': '500mg', 'frequency': '3 times daily', 'duration': '7-10 days'},
        {'name': 'Paracetamol (Crocin)', 'dosage': '650mg', 'frequency': 'Every 6 hours for fever', 'duration': 'Until fever resolves'},
        {'name': 'Steam inhalation deep breathing', 'dosage': '-', 'frequency': '3 times daily', 'duration': '7 days'},
    ],
    'Tuberculosis': [
        {'name': 'DOTS Therapy Government free', 'dosage': 'As prescribed by doctor', 'frequency': 'Daily NEVER skip', 'duration': '6-9 months'},
        {'name': 'Visit nearest DOTS centre immediately', 'dosage': '-', 'frequency': '-', 'duration': 'Free treatment available'},
    ],
    'COPD': [
        {'name': 'Tiotropium Inhaler (Spiriva)', 'dosage': '18mcg', 'frequency': 'Once daily', 'duration': 'Ongoing'},
        {'name': 'Salbutamol Inhaler (Asthalin)', 'dosage': '2 puffs', 'frequency': 'As needed for breathlessness', 'duration': 'As needed'},
    ],
    'Bronchitis': [
        {'name': 'Ambroxol (Mucolator)', 'dosage': '30mg', 'frequency': 'Twice daily after meals', 'duration': '5-7 days'},
        {'name': 'Salbutamol Inhaler', 'dosage': '2 puffs', 'frequency': 'If wheezing occurs', 'duration': 'As needed'},
        {'name': 'Steam inhalation with Vicks', 'dosage': '-', 'frequency': 'Twice daily', 'duration': '5 days'},
    ],
    'UTI': [
        {'name': 'Drink 3-4 litres water daily', 'dosage': 'Plenty of water', 'frequency': 'Throughout day', 'duration': 'Until symptoms resolve'},
        {'name': 'Nitrofurantoin (Doctor prescribed)', 'dosage': '100mg', 'frequency': 'Twice daily with food', 'duration': '5-7 days'},
        {'name': 'Cranberry juice unsweetened', 'dosage': '1 glass', 'frequency': 'Twice daily', 'duration': '1 week'},
    ],
    'Kidney Stones': [
        {'name': 'Drink 3-4 litres water daily', 'dosage': 'Maximum water intake', 'frequency': 'Every hour', 'duration': 'Until stone passes'},
        {'name': 'Tamsulosin (Doctor prescribed)', 'dosage': '0.4mg', 'frequency': 'Once daily at night', 'duration': 'Until stone passes'},
        {'name': 'Diclofenac for pain', 'dosage': '50mg', 'frequency': 'Every 8 hours with food', 'duration': 'As needed for pain'},
    ],
    'Prostate Issues': [
        {'name': 'Tamsulosin (Doctor prescribed)', 'dosage': '0.4mg', 'frequency': 'Once daily at night', 'duration': 'As advised'},
        {'name': 'Saw Palmetto supplement', 'dosage': '320mg', 'frequency': 'Once daily', 'duration': '3 months'},
    ],
    'Jaundice': [
        {'name': 'Complete rest no physical activity', 'dosage': '-', 'frequency': 'Daily', 'duration': '2-4 weeks'},
        {'name': 'Liv 52 Liver tonic', 'dosage': '2 tablets', 'frequency': 'Twice daily', 'duration': '4 weeks'},
        {'name': 'Avoid oily food alcohol completely', 'dosage': '-', 'frequency': 'Daily', 'duration': '3 months'},
    ],
    'Liver Disease': [
        {'name': 'Liv 52 (Himalaya)', 'dosage': '2 tablets', 'frequency': 'Twice daily before meals', 'duration': '3 months'},
        {'name': 'Silymarin Milk Thistle', 'dosage': '140mg', 'frequency': '3 times daily', 'duration': '3 months'},
        {'name': 'Avoid alcohol and fatty food completely', 'dosage': '-', 'frequency': 'Daily', 'duration': 'Lifelong'},
    ],
    'Dengue': [
        {'name': 'Paracetamol (Crocin)', 'dosage': '500mg', 'frequency': 'Every 6 hours for fever', 'duration': 'Until fever gone'},
        {'name': 'AVOID Ibuprofen/Aspirin dangerous in dengue', 'dosage': '-', 'frequency': '-', 'duration': '-'},
        {'name': 'ORS + Coconut water', 'dosage': '2-3 litres daily', 'frequency': 'Throughout day', 'duration': 'Until recovery'},
        {'name': 'Platelet monitoring admit if below 50000', 'dosage': '-', 'frequency': 'Daily blood test', 'duration': 'Until platelets normal'},
    ],
    'Malaria': [
        {'name': 'Artemether + Lumefantrine (Coartem) Doctor prescribed', 'dosage': 'As prescribed', 'frequency': 'Twice daily', 'duration': '3 days'},
        {'name': 'Paracetamol (Crocin)', 'dosage': '500mg', 'frequency': 'Every 6 hours for fever', 'duration': '3-5 days'},
        {'name': 'ORS for hydration', 'dosage': '1 sachet in 1L water', 'frequency': 'Throughout day', 'duration': 'Until recovery'},
    ],
    'Typhoid': [
        {'name': 'Azithromycin (Doctor prescribed)', 'dosage': '500mg', 'frequency': 'Once daily', 'duration': '7 days'},
        {'name': 'Paracetamol (Crocin)', 'dosage': '500mg', 'frequency': 'Every 6 hours for fever', 'duration': '5-7 days'},
        {'name': 'Soft liquid diet khichdi dal water coconut water', 'dosage': '-', 'frequency': 'Every meal', 'duration': '2 weeks'},
    ],
    'Viral Fever': [
        {'name': 'Paracetamol (Crocin)', 'dosage': '500mg', 'frequency': 'Every 6 hours', 'duration': '3-5 days'},
        {'name': 'Cetirizine (Cetzine)', 'dosage': '10mg', 'frequency': 'Once at night', 'duration': '3-5 days'},
        {'name': 'Rest + 2-3 litres fluids daily', 'dosage': '-', 'frequency': 'Throughout day', 'duration': 'Until recovery'},
    ],
    'Fever': [
        {'name': 'Paracetamol (Crocin)', 'dosage': '500mg', 'frequency': 'Every 6 hours', 'duration': '3-5 days'},
        {'name': 'Cold water sponging on forehead', 'dosage': '-', 'frequency': 'Every 2 hours if fever high', 'duration': 'Until fever reduces'},
        {'name': 'Rest and 2-3 litres water daily', 'dosage': '-', 'frequency': 'Throughout day', 'duration': 'Until recovery'},
    ],
    'Conjunctivitis': [
        {'name': 'Moxifloxacin Eye Drops (Moxicip)', 'dosage': '1-2 drops', 'frequency': 'Every 4 hours', 'duration': '5-7 days'},
        {'name': 'Sodium Chloride Eye Wash', 'dosage': 'Wash eyes', 'frequency': '3-4 times daily', 'duration': '5 days'},
        {'name': 'Cold compress on eyes', 'dosage': '-', 'frequency': '3 times daily', 'duration': '3-5 days'},
    ],
    'Ear Infection': [
        {'name': 'Ciprofloxacin Ear Drops (Doctor prescribed)', 'dosage': '3-4 drops', 'frequency': '3 times daily', 'duration': '7 days'},
        {'name': 'Paracetamol (Crocin)', 'dosage': '500mg', 'frequency': 'Every 6 hours for pain', 'duration': 'Until pain subsides'},
        {'name': 'Warm cloth compress on ear', 'dosage': '-', 'frequency': '3 times daily', 'duration': '3-5 days'},
    ],
    'Throat Infection': [
        {'name': 'Warm salt water gargle', 'dosage': '1/2 tsp salt in warm water', 'frequency': 'Every 4 hours', 'duration': '5-7 days'},
        {'name': 'Strepsils Lozenges', 'dosage': '1 lozenge', 'frequency': 'Every 3-4 hours', 'duration': '5 days'},
        {'name': 'Amoxicillin Doctor prescribed if bacterial', 'dosage': '500mg', 'frequency': '3 times daily', 'duration': '5-7 days'},
    ],
    'Tonsillitis': [
        {'name': 'Warm salt water gargle', 'dosage': '1/2 tsp salt in warm water', 'frequency': 'Every 3 hours', 'duration': '5-7 days'},
        {'name': 'Ibuprofen (Brufen)', 'dosage': '400mg', 'frequency': 'Every 8 hours with food', 'duration': '3-5 days'},
        {'name': 'Amoxicillin Doctor prescribed', 'dosage': '500mg', 'frequency': '3 times daily', 'duration': '7-10 days'},
    ],
    'Sinusitis': [
        {'name': 'Nasal Saline Spray (Nasivion Saline)', 'dosage': '2 sprays each nostril', 'frequency': '3 times daily', 'duration': '7 days'},
        {'name': 'Steam inhalation with eucalyptus oil', 'dosage': '-', 'frequency': 'Twice daily', 'duration': '7 days'},
        {'name': 'Amoxicillin Doctor prescribed', 'dosage': '500mg', 'frequency': '3 times daily', 'duration': '7-10 days'},
    ],
    'Allergic Rhinitis': [
        {'name': 'Cetirizine (Cetzine)', 'dosage': '10mg', 'frequency': 'Once daily at night', 'duration': 'During allergy season'},
        {'name': 'Nasal Steroid Spray (Flixonase)', 'dosage': '2 sprays each nostril', 'frequency': 'Once daily morning', 'duration': '2-4 weeks'},
        {'name': 'Montelukast (Montair)', 'dosage': '10mg', 'frequency': 'Once at night', 'duration': '2 weeks'},
    ],
    'Vertigo': [
        {'name': 'Betahistine (Vertin)', 'dosage': '16mg', 'frequency': '3 times daily', 'duration': '4-8 weeks'},
        {'name': 'Promethazine for nausea', 'dosage': '25mg', 'frequency': 'Twice daily', 'duration': '3-5 days'},
        {'name': 'Epley maneuver exercises ask doctor', 'dosage': '-', 'frequency': 'Daily exercises', 'duration': '2 weeks'},
    ],
    'Hypothyroidism': [
        {'name': 'Levothyroxine (Thyronorm) Doctor prescribed', 'dosage': 'As per TSH level', 'frequency': 'Empty stomach morning', 'duration': 'Lifelong'},
        {'name': 'Selenium supplement', 'dosage': '200mcg', 'frequency': 'Once daily', 'duration': '3 months'},
    ],
    'Hyperthyroidism': [
        {'name': 'Methimazole Doctor prescribed', 'dosage': 'As prescribed', 'frequency': '3 times daily', 'duration': 'As advised'},
        {'name': 'Propranolol for fast heartbeat', 'dosage': '10-20mg', 'frequency': 'Twice daily', 'duration': 'As advised'},
    ],
    'PCOD': [
        {'name': 'Metformin Doctor prescribed', 'dosage': '500mg', 'frequency': 'Twice daily with meals', 'duration': 'As advised'},
        {'name': 'Inositol supplement', 'dosage': '4g', 'frequency': 'Once daily', 'duration': '3 months'},
        {'name': 'Exercise 30 mins daily + low sugar diet', 'dosage': '-', 'frequency': 'Daily', 'duration': 'Ongoing'},
    ],
    'Dysmenorrhea': [
        {'name': 'Mefenamic Acid (Meftal Spas)', 'dosage': '250mg', 'frequency': 'Every 6 hours start day before period', 'duration': '3-5 days'},
        {'name': 'Ibuprofen (Brufen)', 'dosage': '400mg', 'frequency': 'Every 8 hours with food', 'duration': '3-5 days'},
        {'name': 'Hot water bag on abdomen', 'dosage': '-', 'frequency': 'As needed', 'duration': '3-5 days'},
    ],
    'Anxiety Disorder': [
        {'name': 'Deep breathing exercises 4-7-8 technique', 'dosage': '-', 'frequency': '3 times daily', 'duration': 'Ongoing'},
        {'name': 'Ashwagandha supplement', 'dosage': '300mg', 'frequency': 'Twice daily', 'duration': '8 weeks'},
        {'name': 'Consult psychiatrist for proper medication', 'dosage': '-', 'frequency': '-', 'duration': '-'},
    ],
    'Depression': [
        {'name': 'Please consult a psychiatrist immediately', 'dosage': '-', 'frequency': '-', 'duration': '-'},
        {'name': 'iCall helpline 9152987821', 'dosage': '-', 'frequency': 'Call anytime', 'duration': '-'},
        {'name': 'Daily exercise 30 mins + morning sunlight', 'dosage': '-', 'frequency': 'Every morning', 'duration': 'Ongoing'},
    ],
    'Heart Failure': [
        {'name': 'Visit cardiologist immediately', 'dosage': '-', 'frequency': '-', 'duration': 'Emergency'},
        {'name': 'Furosemide Doctor prescribed', 'dosage': 'As prescribed', 'frequency': 'As directed', 'duration': 'Ongoing'},
        {'name': 'Restrict salt less than 2g daily and fluid intake', 'dosage': '-', 'frequency': 'Every meal', 'duration': 'Lifelong'},
    ],
    'Lupus': [
        {'name': 'Hydroxychloroquine Doctor prescribed', 'dosage': 'As prescribed', 'frequency': 'As directed', 'duration': 'Ongoing'},
        {'name': 'Sunscreen SPF 50+', 'dosage': 'Apply on exposed skin', 'frequency': 'Every 2 hours outdoors', 'duration': 'Daily'},
    ],
    'Psoriasis': [
        {'name': 'Coal Tar Cream (Psorex)', 'dosage': 'Apply on patches', 'frequency': 'Twice daily', 'duration': '4 weeks'},
        {'name': 'Calcipotriol Cream Doctor prescribed', 'dosage': 'Apply thin layer', 'frequency': 'Twice daily', 'duration': '4-8 weeks'},
        {'name': 'Moisturize with Vaseline', 'dosage': 'Apply generously', 'frequency': '3-4 times daily', 'duration': 'Ongoing'},
    ],
    'Ringworm': [
        {'name': 'Clotrimazole Cream (Candid)', 'dosage': 'Apply on affected area', 'frequency': 'Twice daily', 'duration': '4 weeks'},
        {'name': 'Terbinafine Cream (Terbicip)', 'dosage': 'Apply thin layer', 'frequency': 'Once daily', 'duration': '2-4 weeks'},
        {'name': 'Keep area dry and clean daily', 'dosage': '-', 'frequency': 'Daily', 'duration': 'Ongoing'},
    ],
    'Dandruff': [
        {'name': 'Ketoconazole Shampoo (Nizoral)', 'dosage': 'Use on scalp leave 5 mins', 'frequency': 'Twice a week', 'duration': '4 weeks'},
        {'name': 'Selenium Sulfide Shampoo (Selsun)', 'dosage': 'Leave 5 mins before rinsing', 'frequency': 'Twice a week', 'duration': '4 weeks'},
        {'name': 'Coconut oil massage before wash', 'dosage': 'Massage into scalp', 'frequency': 'Before every wash', 'duration': 'Ongoing'},
    ],
    'Alopecia': [
        {'name': 'Minoxidil 5% Solution (Mintop)', 'dosage': '1ml on scalp', 'frequency': 'Twice daily', 'duration': '6-12 months'},
        {'name': 'Biotin supplement', 'dosage': '5000mcg', 'frequency': 'Once daily', 'duration': '6 months'},
        {'name': 'Consult dermatologist for PRP treatment', 'dosage': '-', 'frequency': '-', 'duration': '-'},
    ],
    'Neuropathy': [
        {'name': 'Methylcobalamin Vitamin B12', 'dosage': '500mcg', 'frequency': 'Twice daily', 'duration': '3 months'},
        {'name': 'Alpha Lipoic Acid', 'dosage': '600mg', 'frequency': 'Once daily', 'duration': '3 months'},
        {'name': 'Pregabalin Doctor prescribed', 'dosage': 'As prescribed', 'frequency': 'As directed', 'duration': 'As advised'},
    ],
    'Tension Headache': [
        {'name': 'Paracetamol (Crocin)', 'dosage': '500mg', 'frequency': 'Every 6 hours as needed', 'duration': '1-2 days'},
        {'name': 'Ibuprofen (Brufen)', 'dosage': '400mg', 'frequency': 'Every 8 hours with food', 'duration': '1-2 days'},
        {'name': 'Cold or warm compress on forehead', 'dosage': '-', 'frequency': 'As needed', 'duration': 'Until relief'},
    ],
    'Mouth Ulcers': [
        {'name': 'Benzocaine Gel (Dentogel)', 'dosage': 'Apply on ulcer', 'frequency': '3-4 times daily', 'duration': '5-7 days'},
        {'name': 'Vitamin B12 + B Complex', 'dosage': '1 tablet', 'frequency': 'Once daily', 'duration': '1 month'},
        {'name': 'Warm salt water rinse', 'dosage': '-', 'frequency': '3 times daily', 'duration': 'Until healed'},
    ],
    'Dental Problem': [
        {'name': 'Ibuprofen (Brufen) for pain', 'dosage': '400mg', 'frequency': 'Every 8 hours with food', 'duration': 'Until dentist visit'},
        {'name': 'Clove oil on affected tooth', 'dosage': 'Apply with cotton', 'frequency': 'As needed for pain', 'duration': 'Until dentist visit'},
        {'name': 'Visit dentist immediately do not delay', 'dosage': '-', 'frequency': '-', 'duration': '-'},
    ],
    'Chickenpox': [
        {'name': 'Calamine Lotion on blisters', 'dosage': 'Apply on spots', 'frequency': '4 times daily', 'duration': '7-10 days'},
        {'name': 'Cetirizine (Cetzine) for itching', 'dosage': '10mg', 'frequency': 'Once at night', 'duration': '7 days'},
        {'name': 'Paracetamol (Crocin) for fever', 'dosage': '500mg', 'frequency': 'Every 6 hours', 'duration': 'Until fever gone'},
    ],
    'Dehydration': [
        {'name': 'ORS (Electral)', 'dosage': '1 sachet in 1L water', 'frequency': 'Every hour', 'duration': 'Until rehydrated'},
        {'name': 'Coconut water', 'dosage': '1-2 glasses', 'frequency': 'Every 2 hours', 'duration': 'Until recovery'},
        {'name': 'Drink 3-4 litres of water daily', 'dosage': 'Maximum fluids', 'frequency': 'Throughout day', 'duration': 'Until recovery'},
    ],
    'Low Blood Pressure': [
        {'name': 'ORS + extra salt in diet', 'dosage': 'Increase salt intake slightly', 'frequency': 'Daily', 'duration': 'As needed'},
        {'name': 'Black coffee or strong tea', 'dosage': '1 cup', 'frequency': 'When feeling dizzy', 'duration': 'As needed'},
        {'name': 'Lie down and elevate legs', 'dosage': '-', 'frequency': 'When dizzy', 'duration': 'Until BP normalizes'},
    ],
    'Heat Stroke': [
        {'name': 'EMERGENCY go to hospital immediately', 'dosage': '-', 'frequency': '-', 'duration': 'Emergency'},
        {'name': 'Move to cool shaded area immediately', 'dosage': '-', 'frequency': 'Immediately', 'duration': 'Emergency'},
        {'name': 'Apply cold wet cloth on body', 'dosage': '-', 'frequency': 'Continuously', 'duration': 'Until help arrives'},
    ],
    'Eye Strain': [
        {'name': 'Lubricating Eye Drops (Refresh Tears)', 'dosage': '1-2 drops', 'frequency': 'Every 4 hours', 'duration': 'As needed'},
        {'name': '20-20-20 rule every 20 mins look 20 feet 20 secs', 'dosage': '-', 'frequency': 'Every 20 minutes', 'duration': 'Ongoing'},
        {'name': 'Reduce screen brightness use blue light filter', 'dosage': '-', 'frequency': 'Daily', 'duration': 'Ongoing'},
    ],
    'Meningitis': [
        {'name': 'EMERGENCY Call 108 immediately', 'dosage': '-', 'frequency': '-', 'duration': 'Go to hospital NOW'},
        {'name': 'Requires immediate IV antibiotics in hospital', 'dosage': '-', 'frequency': '-', 'duration': 'Hospital treatment'},
    ],
}

DEFAULT_MEDICINE = [
    {'name': 'Paracetamol (Crocin)', 'dosage': '500mg', 'frequency': 'Every 6 hours', 'duration': '3 days'},
    {'name': 'Rest and drink plenty of water', 'dosage': '2-3 litres', 'frequency': 'Throughout day', 'duration': 'Until recovery'},
]

MEDICAL_CAMPS = [
    {'id':1,'name':'Rural Health Awareness Camp','location':'Community Center, Old Resapuvanipalem, Visakhapatnam','date':'2026-06-15','time':'9:00 AM - 4:00 PM','services':'Free consultation, Basic medicines','contact':'9347336769','active':True},
    {'id':2,'name':'Cardiac Health Camp','location':'GHMC Health Center, Dwaraka Nagar, Visakhapatnam','date':'2026-06-20','time':'8:00 AM - 6:00 PM','services':'ECG, BP check, Cardiac consultation','contact':'0891-2755555','active':True},
    {'id':3,'name':'Gynaecology & Child Health Camp','location':'PHC Gajuwaka, Visakhapatnam','date':'2026-07-01','time':'9:00 AM - 5:00 PM','services':'Gynaecology, Paediatrics, Immunisation','contact':'0891-2587412','active':True},
    {'id':4,'name':'Diabetes & Hypertension Screening','location':'Town Hall, Seethammadhara, Visakhapatnam','date':'2026-07-10','time':'10:00 AM - 3:00 PM','services':'Blood sugar test, BP check, Diet counselling','contact':'9848012345','active':True},
]

consultation_log = []

# ── Patient User Store ────────────────────────────────────────────────────────
import hashlib, secrets as _secrets

PATIENT_USERS = {}

def _hash_pwd(password):
    salt   = _secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{hashed}"

def _verify_pwd(password, stored):
    try:
        salt, hashed = stored.split(':')
        return hashlib.sha256((salt + password).encode()).hexdigest() == hashed
    except:
        return False

PATIENT_OTP_STORE = {}

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
    if not session.get('patient_logged_in'):
        return redirect(url_for('patient_login'))
    symptoms_list = predictor.get_all_symptoms() if predictor else []
    return render_template('index.html',
        symptoms_list=symptoms_list,
        patient_name=session.get('patient_name', 'Patient'))

@app.route('/predict', methods=['POST'])
@rate_limit(max_calls=15, window=60)
def predict():
    try:
        name     = sanitize(request.form.get('name', 'Patient'))
        age_str  = sanitize(request.form.get('age', ''))
        gender   = sanitize(request.form.get('gender', ''))
        severity = sanitize(request.form.get('severity', 'Moderate'))
        duration = sanitize(request.form.get('duration', '3-5 days'))
        symptoms = request.form.getlist('symptoms')

        # ── Validation ───────────────────────────────────────────────────
        errors = []

        # Name validation
        if not name or len(name.strip()) < 2:
            errors.append('Please enter a valid name (minimum 2 characters).')
        elif any(char.isdigit() for char in name):
            errors.append('Name cannot contain numbers. Please enter your real name.')
        elif not all(char.isalpha() or char.isspace() or char in ".-'" for char in name):
            errors.append('Name can only contain letters, spaces, hyphens or apostrophes.')

        # Age validation
        if not age_str:
            errors.append('Please enter your age.')
        elif not age_str.isdigit():
            errors.append('Age must be a number.')
        elif not (1 <= int(age_str) <= 100):
            errors.append('Age must be between 1 and 100 years only.')

        # Gender validation
        if gender not in ('Male', 'Female', 'Other'):
            errors.append('Please select a valid gender.')

        # Symptoms validation
        if not symptoms:
            errors.append('Please select at least one symptom.')
        if len(symptoms) > 20:
            errors.append('Maximum 20 symptoms allowed.')

        if errors:
            return render_template('index.html',
                symptoms_list=predictor.get_all_symptoms() if predictor else [],
                errors=errors), 400

        age = int(age_str)

        # ML Prediction
        if predictor:
            disease, confidence, specialization = predictor.predict(symptoms)
        else:
            disease, confidence, specialization = 'General Health Concern', 0.5, 'General Physician'

        if severity == 'Severe':
            confidence = min(confidence + 0.1, 0.99)

        # Claude Explanation
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
            try:
                medicine_note = get_medicine_info(disease, [m['name'] for m in medicines])
            except:
                medicine_note = "Temporary suggestions only. Please consult a doctor before taking any medication."
        else:
            medicine_note = "Temporary suggestions only. Please consult a doctor before taking any medication."

        token = gen_token()
        now   = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        whatsapp_url = build_whatsapp_url(name, token, disease, specialization, symptoms)

        consultation = {
            'name': name, 'age': age, 'gender': gender, 'symptoms': symptoms,
            'disease': disease, 'confidence': f"{confidence:.0%}",
            'specialization': specialization, 'token': token, 'datetime': now,
            'explanation': explanation, 'medicines': medicines,
            'medicine_note': medicine_note, 'severity': severity, 'duration': duration
        }
        session['consultation'] = consultation

        # History (last 5)
        history = session.get('history', [])
        history.insert(0, {
            'token': token, 'name': name, 'age': age, 'gender': gender,
            'symptoms': symptoms, 'disease': disease,
            'confidence': f"{confidence:.0%}", 'specialization': specialization,
            'severity': severity, 'duration': duration, 'datetime': now
        })
        session['history'] = history[:5]

        # Global log
        consultation_log.append({
            'token': token, 'name': name, 'age': age, 'gender': gender,
            'disease': disease, 'specialization': specialization,
            'confidence': f"{confidence:.0%}", 'severity': severity, 'datetime': now
        })
        if len(consultation_log) > 200:
            consultation_log.pop(0)

        return render_template('result.html',
            name=name, age=age, gender=gender, symptoms=symptoms,
            disease=disease, confidence=f"{confidence:.0%}",
            specialization=specialization, token=token,
            explanation=explanation, medicines=medicines,
            medicine_note=medicine_note, severity=severity,
            duration=duration, whatsapp_url=whatsapp_url,
            camps=[c for c in MEDICAL_CAMPS if c.get('active', True)])

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
        user_message = sanitize(data.get('message', ''), 500)
        if not user_message:
            return jsonify({'error': 'Empty message'}), 400

        history = session.get('chat_history', [])

        if chat_with_assistant:
            try:
                reply = chat_with_assistant(history, user_message)
            except:
                reply = "I'm having trouble connecting. Please select symptoms manually."
        else:
            reply = "AI chat requires an Anthropic API key in your .env file."

        extracted = []
        if extract_symptoms_from_text:
            try:
                extracted = extract_symptoms_from_text(user_message)
            except:
                pass

        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": reply})
        session['chat_history'] = history[-20:]
        return jsonify({'reply': reply, 'extracted_symptoms': extracted})
    except Exception as e:
        return jsonify({'reply': 'Error occurred.', 'extracted_symptoms': []})


@app.route('/rag/ask', methods=['POST'])
@rate_limit(max_calls=20, window=60)
def rag_ask():
    try:
        data     = request.json
        question = sanitize(data.get('question', ''), 300)
        symptoms = data.get('symptoms', [])[:20]
        disease  = sanitize(data.get('disease', ''))
        if not question:
            return jsonify({'error': 'No question'}), 400
        if rag_engine:
            result = rag_engine.answer_with_rag(question, symptoms, disease)
        else:
            result = {'answer': 'RAG not available. Check your API key.', 'sources_used': 0}
        return jsonify(result)
    except Exception as e:
        return jsonify({'answer': f'Error: {e}', 'sources_used': 0})


@app.route('/download_receipt')
def download_receipt():
    try:
        from fpdf import FPDF
        c = session.get('consultation')
        if not c:
            return "<h2>No consultation found.</h2><a href='/'>← Back</a>", 404

        pdf = FPDF()
        pdf.add_page()
        pdf.set_fill_color(26, 43, 74)
        pdf.rect(0, 0, 210, 38, 'F')
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Arial', 'B', 16)
        pdf.set_y(8)
        pdf.cell(0, 10, 'Smart Healthcare Assistant', ln=True, align='C')
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 7, 'AI-Powered Medical Guidance | Dr. Lankapalli Bullayya College, Visakhapatnam', ln=True, align='C')
        pdf.cell(0, 7, 'Powered by Claude AI + Machine Learning', ln=True, align='C')
        pdf.set_text_color(0, 0, 0)
        pdf.set_y(46)
        pdf.set_font('Arial', 'B', 12)
        pdf.set_fill_color(239, 246, 255)
        pdf.cell(0, 9, f"  Token: {c['token']}   |   Date: {c['datetime']}", ln=True, fill=True)
        pdf.ln(3)

        def section(title):
            pdf.set_font('Arial', 'B', 11)
            pdf.set_fill_color(26, 43, 74)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(0, 8, f'  {title}', ln=True, fill=True)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font('Arial', '', 10)

        section('Patient Details')
        pdf.cell(0, 7, f"  Name: {c['name']}   |   Age: {c['age']}   |   Gender: {c['gender']}   |   Severity: {c['severity']}", ln=True)
        pdf.ln(2)
        section('Symptoms')
        pdf.multi_cell(0, 7, '  ' + ', '.join(c['symptoms']))
        pdf.ln(2)
        section('AI Prediction')
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 7, f"  Predicted: {c['disease']}  (Confidence: {c['confidence']})", ln=True)
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 7, f"  Recommended Specialist: {c['specialization']}", ln=True)
        pdf.ln(2)
        section('AI Analysis (Claude)')
        pdf.set_font('Arial', '', 9)
        pdf.multi_cell(0, 6, c['explanation'].replace('**', '').replace('*', ''))
        pdf.ln(2)
        section('Temporary Medicine Suggestions')
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(65, 7, 'Medicine', border=1)
        pdf.cell(28, 7, 'Dosage', border=1)
        pdf.cell(48, 7, 'Frequency', border=1)
        pdf.cell(38, 7, 'Duration', border=1, ln=True)
        pdf.set_font('Arial', '', 9)
        for m in c['medicines']:
            pdf.cell(65, 7, str(m['name'])[:32], border=1)
            pdf.cell(28, 7, str(m['dosage']), border=1)
            pdf.cell(48, 7, str(m['frequency']), border=1)
            pdf.cell(38, 7, str(m['duration']), border=1, ln=True)
        pdf.ln(3)
        pdf.set_fill_color(255, 243, 205)
        pdf.set_font('Arial', 'B', 9)
        pdf.multi_cell(0, 6, 'IMPORTANT: AI advisory only — NOT a medical diagnosis. Consult a qualified doctor.', fill=True)

        import tempfile
        tmp = os.path.join(tempfile.gettempdir(), f'receipt_{os.urandom(4).hex()}.pdf')
        pdf.output(tmp)
        return send_file(tmp, as_attachment=True,
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


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
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
    age_groups     = {'0-18': 0, '19-35': 0, '36-50': 0, '51-65': 0, '65+': 0}
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
        'name':     sanitize(request.form.get('name', '')),
        'location': sanitize(request.form.get('location', '')),
        'date':     sanitize(request.form.get('date', '')),
        'time':     sanitize(request.form.get('time', '')),
        'services': sanitize(request.form.get('services', '')),
        'contact':  sanitize(request.form.get('contact', '')),
        'active':   True,
        'added_by': session.get('admin_user', 'admin'),
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


# ── User Management ────────────────────────────────────────────────────────────
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
        role_label  = ROLE_LABELS.get(session.get('admin_role', 'viewer')))


@app.route('/admin/users/add', methods=['POST'])
@admin_required
@require_permission('manage_users')
def admin_add_user():
    success, msg = add_user(
        username   = request.form.get('username', '').strip(),
        password   = request.form.get('password', ''),
        name       = request.form.get('name', '').strip(),
        email      = request.form.get('email', '').strip(),
        role       = request.form.get('role', 'viewer'),
        created_by = session.get('admin_user', 'admin')
    )
    flash(('✅ ' if success else '❌ ') + msg, 'success' if success else 'error')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/edit/<username>', methods=['POST'])
@admin_required
@require_permission('manage_users')
def admin_edit_user(username):
    data = {
        'name':  request.form.get('name', '').strip(),
        'email': request.form.get('email', '').strip(),
        'role':  request.form.get('role', 'viewer'),
    }
    if request.form.get('password', '').strip():
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

# ════════════════════════════════════════════════════════════════════════════
# PATIENT AUTH ROUTES
# ════════════════════════════════════════════════════════════════════════════

def patient_login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get('patient_logged_in'):
            return redirect(url_for('patient_login'))
        return f(*args, **kwargs)
    return wrapped

@app.route('/signup', methods=['GET', 'POST'])
def patient_signup():
    error = None
    if session.get('patient_logged_in'):
        return redirect(url_for('index'))
    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        phone    = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        if not name or len(name) < 2:
            error = 'Please enter your full name.'
        elif any(char.isdigit() for char in name):
            error = 'Name cannot contain numbers.'
        elif not email or '@' not in email:
            error = 'Please enter a valid email address.'
        elif email in PATIENT_USERS:
            error = 'Email already registered. Please login.'
        elif len(password) < 6:
            error = 'Password must be at least 6 characters.'
        elif password != confirm:
            error = 'Passwords do not match.'
        elif not phone.isdigit() or len(phone) != 10:
            error = 'Please enter a valid 10-digit phone number.'
        else:
            PATIENT_USERS[email] = {
                'name': name, 'email': email, 'phone': phone,
                'password': _hash_pwd(password),
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
            session['patient_logged_in'] = True
            session['patient_email']     = email
            session['patient_name']      = name
            flash(f"Welcome {name}! Account created successfully.", 'success')
            return redirect(url_for('index'))
    return render_template('patient_signup.html', error=error)

@app.route('/login', methods=['GET', 'POST'])
def patient_login():
    error = None
    if session.get('patient_logged_in'):
        return redirect(url_for('index'))
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user     = PATIENT_USERS.get(email)
        if user and _verify_pwd(password, user['password']):
            session['patient_logged_in'] = True
            session['patient_email']     = email
            session['patient_name']      = user['name']
            flash(f"Welcome back, {user['name']}!", 'success')
            return redirect(url_for('index'))
        else:
            error = 'Invalid email or password.'
    return render_template('patient_login.html', error=error)

@app.route('/patient-logout')
def patient_logout():
    session.pop('patient_logged_in', None)
    session.pop('patient_email',     None)
    session.pop('patient_name',      None)
    session.pop('chat_history',      None)
    session.pop('history',           None)
    return redirect(url_for('patient_login'))

@app.route('/patient-forgot-password', methods=['GET', 'POST'])
def patient_forgot_password():
    step  = request.args.get('step', '1')
    error = None
    if request.method == 'POST':
        step = request.form.get('step', '1')
        if step == '1':
            email = request.form.get('email', '').strip().lower()
            if email not in PATIENT_USERS:
                error = 'Email not found. Please check and try again.'
            else:
                otp     = str(random.randint(100000, 999999))
                expires = time.time() + 600
                PATIENT_OTP_STORE[email] = {'otp': otp, 'expires': expires}
                session['reset_patient_email'] = email
                flash(f"OTP for demo: {otp}", 'success')
                return redirect(url_for('patient_forgot_password', step='2'))
        elif step == '2':
            email        = session.get('reset_patient_email', '')
            otp          = request.form.get('otp', '').strip()
            new_password = request.form.get('new_password', '')
            confirm      = request.form.get('confirm_password', '')
            entry        = PATIENT_OTP_STORE.get(email)
            if not entry:
                error = 'OTP expired. Please start again.'
            elif time.time() > entry['expires']:
                error = 'OTP expired. Please request a new one.'
                PATIENT_OTP_STORE.pop(email, None)
            elif entry['otp'] != otp:
                error = 'Invalid OTP. Please try again.'
            elif len(new_password) < 6:
                error = 'Password must be at least 6 characters.'
            elif new_password != confirm:
                error = 'Passwords do not match.'
            else:
                PATIENT_USERS[email]['password'] = _hash_pwd(new_password)
                PATIENT_OTP_STORE.pop(email, None)
                session.pop('reset_patient_email', None)
                flash('Password reset successful! Please login.', 'success')
                return redirect(url_for('patient_login'))
    return render_template('patient_forgot_password.html',
        step=step, error=error,
        email=session.get('reset_patient_email', ''))
@app.route('/translate', methods=['POST'])
def translate_text():
    try:
        data      = request.json
        text      = sanitize(data.get('text', ''), 500)
        from_lang = data.get('from', 'Telugu')
        to_lang   = data.get('to', 'English')
        if not text:
            return jsonify({'translated': text})
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": (f"Translate the following {from_lang} medical text to {to_lang}. "
                            f"Return ONLY the translated text, nothing else.\n\nText: {text}")
            }]
        )
        return jsonify({'translated': response.content[0].text.strip(), 'original': text})
    except Exception as e:
        return jsonify({'translated': data.get('text', ''), 'error': str(e)})


# ── Forgot Password ────────────────────────────────────────────────────────────
@app.route('/admin/forgot-password', methods=['GET', 'POST'])
def admin_forgot_password():
    step    = request.args.get('step', '1')
    error   = None
    if request.method == 'POST':
        step = request.form.get('step', '1')
        if step == '1':
            username     = request.form.get('username', '').strip().lower()
            success, otp = generate_reset_otp(username)
            if success:
                session['reset_username'] = username
                flash(f"✅ OTP generated! For this demo, your OTP is: {otp}", 'success')
                return redirect(url_for('admin_forgot_password', step='2'))
            else:
                error = otp
        elif step == '2':
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
        step=step, error=error, message=None,
        username=session.get('reset_username', ''))


# ── Change Password ────────────────────────────────────────────────────────────
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
            ok, msg = change_password(session.get('admin_user'), old_password, new_password)
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
    port  = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)