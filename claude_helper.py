import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def get_disease_explanation(symptoms, predicted_disease, confidence, specialization):
    """
    Use Claude to generate a clear explanation of the disease prediction.
    """
    prompt = f"""You are a helpful medical assistant in a Smart Healthcare Assistant app.

A patient has reported the following symptoms: {', '.join(symptoms)}

Our ML model predicted: {predicted_disease} (Confidence: {confidence:.0%})
Recommended specialist: {specialization}

Please provide:
1. A brief, simple explanation (2-3 sentences) of why these symptoms suggest {predicted_disease}
2. 3 immediate home care tips the patient can follow right now
3. A clear warning that this is NOT a medical diagnosis and they must consult a doctor

Keep the language simple and easy to understand. Do not use complex medical terms.
Format your response in 3 clear sections with these exact headings:
**Why this prediction:**
**Immediate care tips:**
**Important warning:**"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


def extract_symptoms_from_text(user_text):
    """
    Use Claude to extract symptoms from natural language text.
    Returns a list of symptoms.
    """
    prompt = f"""You are a medical symptom extractor. 

The patient said: "{user_text}"

Extract all medical symptoms mentioned. Return ONLY a JSON array of symptom strings in lowercase.
Example output: ["fever", "headache", "cough"]

If no clear symptoms are found, return: []
Return ONLY the JSON array, nothing else."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=200,
        messages=[
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": "["}
        ]
    )

    import json
    try:
        raw = "[" + response.content[0].text
        # Clean up and parse
        raw = raw.strip()
        if not raw.endswith(']'):
            raw += ']'
        symptoms = json.loads(raw)
        return [s.lower().strip() for s in symptoms if isinstance(s, str)]
    except Exception:
        return []


def chat_with_assistant(conversation_history, user_message, patient_context=None):
    """
    Multi-turn chat with Claude acting as a healthcare assistant.
    conversation_history: list of {"role": "user/assistant", "content": "..."}
    """
    system_prompt = """You are a compassionate Smart Healthcare Assistant for rural and underserved communities in India.

Your role:
- Help patients understand their symptoms in simple language (Telugu/Hindi phrases welcome if needed)
- Extract symptoms naturally from conversation
- Give general health guidance and home remedies
- Always recommend consulting a real doctor for diagnosis
- Be warm, friendly, and supportive

Rules:
- NEVER diagnose definitively - always say "this may suggest" or "could be related to"
- Always end with encouragement to visit a doctor
- Keep responses short and clear (3-5 sentences max)
- If patient seems to be in emergency (severe chest pain, difficulty breathing), immediately tell them to call emergency services"""

    if patient_context:
        system_prompt += f"\n\nPatient context: {patient_context}"

    messages = conversation_history + [{"role": "user", "content": user_message}]

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=400,
        system=system_prompt,
        messages=messages
    )

    return response.content[0].text


def get_medicine_info(disease, medicines):
    """
    Use Claude to provide safe medicine information context.
    """
    prompt = f"""For a patient with {disease}, the system suggests these temporary medicines: {', '.join(medicines)}.

Provide a 2-sentence safety note about taking these medicines temporarily before seeing a doctor.
Keep it simple and cautionary. Emphasize doctor consultation."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
