import os
import json
import numpy as np
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ── Medical Knowledge Base ──────────────────────────────────────────────────
# In a real project this would be loaded from PDFs using PyPDF2
# For now we embed this structured knowledge directly

MEDICAL_KNOWLEDGE = [
    {
        "id": "common_cold",
        "text": "Common Cold: Caused by rhinovirus. Symptoms include runny nose, sneezing, sore throat, mild fever, and cough. Usually resolves in 7-10 days. Rest, hydration, and over-the-counter medicines like paracetamol help. Not caused by bacteria, so antibiotics don't help."
    },
    {
        "id": "flu",
        "text": "Influenza (Flu): Caused by influenza virus. Symptoms include high fever, severe body ache, fatigue, cough, and sore throat. More severe than common cold. Rest and fluids are important. Tamiflu can be prescribed by doctor if caught early."
    },
    {
        "id": "migraine",
        "text": "Migraine: Neurological condition causing severe throbbing headache, often on one side. Triggers include stress, bright lights, certain foods. Symptoms include nausea, vomiting, sensitivity to light and sound. Neurologist consultation recommended."
    },
    {
        "id": "cardiac",
        "text": "Cardiac Issues: Heart problems can cause chest pain, shortness of breath, arm pain, sweating, and fatigue. These are serious symptoms requiring immediate medical attention. Do not ignore chest pain — visit emergency immediately. Cardiologist evaluation is essential."
    },
    {
        "id": "skin_allergy",
        "text": "Skin Allergy: Allergic reactions cause rash, itching, redness, and swelling. Common triggers include food, medications, insects, and plants. Antihistamines like cetirizine provide relief. Avoid scratching. Dermatologist can identify specific allergen."
    },
    {
        "id": "gastroenteritis",
        "text": "Gastroenteritis (Stomach Flu): Inflammation of stomach and intestines. Symptoms include nausea, vomiting, diarrhea, and stomach cramps. Usually caused by viral or bacterial infection. Oral rehydration solution (ORS) prevents dehydration. Avoid solid food initially."
    },
    {
        "id": "arthritis",
        "text": "Arthritis: Joint inflammation causing pain, swelling, and stiffness. Common types include Rheumatoid Arthritis and Osteoarthritis. Morning stiffness is a key symptom. Anti-inflammatory medicines help. Rheumatologist can manage long-term treatment."
    },
    {
        "id": "anaemia",
        "text": "Anaemia: Low haemoglobin in blood. Causes fatigue, weakness, pale skin, dizziness. Common in India due to iron deficiency, especially in women. Iron-rich foods like spinach, lentils, meat help. Iron supplements prescribed by doctor. Blood test confirms diagnosis."
    },
    {
        "id": "asthma",
        "text": "Asthma: Chronic airway inflammation causing wheezing, shortness of breath, chest tightness. Triggered by dust, cold air, exercise, and allergens. Inhalers (bronchodilators) provide quick relief. Pulmonologist manages long-term treatment. Avoid known triggers."
    },
    {
        "id": "diabetes",
        "text": "Diabetes: High blood sugar due to insulin issues. Type 2 is most common. Symptoms include excessive thirst, frequent urination, fatigue, blurred vision, slow healing wounds. Managed with diet, exercise, and medications. Endocrinologist oversees treatment. Regular HbA1c testing important."
    },
    {
        "id": "hypertension",
        "text": "Hypertension (High Blood Pressure): Often called silent killer as it has few symptoms. Can cause headache, dizziness, chest pain. Major risk factor for stroke and heart attack. Low-salt diet, exercise, and medications help. Cardiologist monitors and treats."
    },
    {
        "id": "uti",
        "text": "Urinary Tract Infection (UTI): Bacterial infection of urinary system. Symptoms include burning urination, frequent urination, cloudy urine, pelvic pain. More common in women. Antibiotics prescribed by doctor treat it effectively. Drink plenty of water."
    },
    {
        "id": "conjunctivitis",
        "text": "Conjunctivitis (Pink Eye): Inflammation of the conjunctiva. Causes red eyes, itching, discharge, and watering. Can be viral, bacterial, or allergic. Antibiotic eye drops for bacterial type. Highly contagious — avoid touching eyes. Ophthalmologist should evaluate."
    },
    {
        "id": "ear_infection",
        "text": "Ear Infection: Caused by bacteria or virus in middle ear. Symptoms include ear pain, fever, hearing loss, and discharge. More common in children. ENT specialist should evaluate. Antibiotics prescribed for bacterial infections. Do not insert objects in ear."
    },
    {
        "id": "throat_infection",
        "text": "Throat Infection (Pharyngitis/Tonsillitis): Inflammation of throat. Symptoms include severe sore throat, difficulty swallowing, swollen glands, fever. Can be viral or bacterial (strep throat). Warm salt water gargling helps. ENT specialist or doctor prescribes antibiotics if bacterial."
    },
    {
        "id": "home_remedies",
        "text": "General Home Remedies: For fever - rest, hydration, paracetamol. For cold - steam inhalation, warm water with honey and ginger. For stomach issues - ORS, bland diet (rice, bananas). For headache - rest in dark room, cold compress. For sore throat - warm salt water gargle, turmeric milk."
    },
    {
        "id": "when_emergency",
        "text": "Emergency Warning Signs - Go to hospital immediately: Severe chest pain or pressure, difficulty breathing, sudden severe headache, confusion or loss of consciousness, severe stomach pain, high fever above 104°F (40°C), signs of stroke (face drooping, arm weakness, speech difficulty), severe allergic reaction with throat swelling."
    }
]


class RAGEngine:
    def __init__(self):
        self.knowledge_base = MEDICAL_KNOWLEDGE
        self.embeddings_cache = {}
        self._build_simple_index()

    def _build_simple_index(self):
        """
        Build a keyword-based index for retrieval.
        In production, you'd use real embeddings with FAISS.
        This approach works without GPU and API embedding costs.
        """
        self.keyword_index = {}
        for doc in self.knowledge_base:
            words = doc['text'].lower().split()
            for word in words:
                clean = word.strip('.,():;')
                if len(clean) > 3:
                    if clean not in self.keyword_index:
                        self.keyword_index[clean] = []
                    if doc['id'] not in self.keyword_index[clean]:
                        self.keyword_index[clean].append(doc['id'])

    def retrieve(self, query, top_k=3):
        """
        Retrieve most relevant documents for a query using keyword matching.
        """
        query_words = query.lower().split()
        doc_scores = {}

        for word in query_words:
            clean = word.strip('.,():;')
            if clean in self.keyword_index:
                for doc_id in self.keyword_index[clean]:
                    doc_scores[doc_id] = doc_scores.get(doc_id, 0) + 1

        # Sort by score
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        top_ids = [doc_id for doc_id, _ in sorted_docs[:top_k]]

        # Always include emergency info
        if 'when_emergency' not in top_ids:
            top_ids.append('when_emergency')

        # Return full text of top documents
        results = []
        for doc in self.knowledge_base:
            if doc['id'] in top_ids:
                results.append(doc['text'])

        return results

    def answer_with_rag(self, question, symptoms=None, disease=None):
        """
        Answer a medical question using RAG - retrieve relevant knowledge then ask Claude.
        """
        # Build retrieval query
        query_parts = [question]
        if symptoms:
            query_parts.extend(symptoms)
        if disease:
            query_parts.append(disease)
        query = ' '.join(query_parts)

        # Retrieve relevant context
        relevant_docs = self.retrieve(query, top_k=3)
        context = '\n\n'.join(relevant_docs)

        # Ask Claude with retrieved context
        prompt = f"""You are a helpful medical assistant. Use the following medical knowledge to answer the patient's question.

MEDICAL KNOWLEDGE:
{context}

PATIENT QUESTION: {question}
{f"PATIENT SYMPTOMS: {', '.join(symptoms)}" if symptoms else ""}
{f"PREDICTED CONDITION: {disease}" if disease else ""}

Answer the question using the medical knowledge provided. Keep the answer:
- Simple and easy to understand
- 3-4 sentences maximum
- Always end with advice to consult a doctor
- Do not invent medical facts not in the knowledge base"""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )

        return {
            "answer": response.content[0].text,
            "sources_used": len(relevant_docs)
        }


# Singleton instance
rag_engine = RAGEngine()
