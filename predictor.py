import os
import pickle
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.model_selection import train_test_split

class DiseasePredictor:
    def __init__(self, model_path=None):
        if model_path is None:
            base = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(base, 'models', 'disease_predictor.pkl')
        self.model_path = model_path
        self.model = None
        self.mlb = MultiLabelBinarizer()
        self.specialization_map = {}
        self.symptom_synonyms = {
            'fever': ['fever','high fever','temperature','pyrexia'],
            'cough': ['cough','coughing','dry cough','coughing at night'],
            'headache': ['headache','head pain','severe headache'],
            'body ache': ['body ache','body pain','muscle ache','myalgia'],
            'sore throat': ['sore throat','throat pain','throat soreness'],
            'shortness of breath': ['shortness of breath','breathing difficulty','breathlessness'],
            'chest pain': ['chest pain','chest tightness','chest heaviness'],
            'nausea': ['nausea','feeling sick','queasy'],
            'fatigue': ['fatigue','tiredness','weakness','lethargy'],
            'dizziness': ['dizziness','lightheadedness','vertigo'],
            'itching': ['itching','itchy','pruritus'],
            'rash': ['rash','skin rash','hives'],
            'joint pain': ['joint pain','arthralgia','joint stiffness'],
            'stomach pain': ['stomach pain','abdominal pain','belly pain','stomach cramps'],
            'vomiting': ['vomiting','throwing up'],
        }
        self._load_or_train()

    def _load_or_train(self):
        if os.path.exists(self.model_path):
            try:
                with open(self.model_path, 'rb') as f:
                    data = pickle.load(f)
                self.model = data['model']
                self.mlb = data['mlb']
                self.specialization_map = data['specialization_map']
                print("Model loaded from cache.")
                return
            except Exception:
                pass
        self.train()

    def train(self, data_path=None):
        if data_path is None:
            base = os.path.dirname(os.path.abspath(__file__))
            data_path = os.path.join(base, 'data', 'medical_training_data.csv')
        print("Training ML model...")
        df = pd.read_csv(data_path)
        # CSV columns: symptoms (quoted comma-separated), disease, specialization
        df['symptoms_list'] = df['symptoms'].apply(
            lambda x: [s.strip().lower() for s in str(x).split(',') if s.strip()]
        )
        X = self.mlb.fit_transform(df['symptoms_list'])
        y = df['disease'].values

        for _, row in df.iterrows():
            self.specialization_map[row['disease']] = row['specialization']

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        self.model = RandomForestClassifier(
            n_estimators=200, random_state=42,
            max_depth=30, class_weight='balanced'
        )
        self.model.fit(X_train, y_train)
        acc = self.model.score(X_test, y_test)
        print(f"Model trained! Accuracy: {acc:.0%}")

        os.makedirs(os.path.dirname(self.model_path) if os.path.dirname(self.model_path) else '.', exist_ok=True)
        with open(self.model_path, 'wb') as f:
            pickle.dump({'model': self.model, 'mlb': self.mlb,
                         'specialization_map': self.specialization_map}, f)

    def _normalize(self, symptoms):
        result = []
        for s in symptoms:
            sl = s.lower().strip()
            matched = False
            for standard, synonyms in self.symptom_synonyms.items():
                if any(sl == syn or syn in sl or sl in syn for syn in synonyms):
                    result.append(standard)
                    matched = True
                    break
            if not matched:
                result.append(sl)
        return list(set(result))

    def predict(self, symptoms):
        if not symptoms:
            return 'Unknown', 0.0, 'General Physician'
        normalized = self._normalize(symptoms)
        try:
            encoded = self.mlb.transform([normalized])
            pred = self.model.predict(encoded)[0]
            conf = float(max(self.model.predict_proba(encoded)[0]))
            if conf < 0.3:
                return self._fallback(symptoms)
            spec = self.specialization_map.get(pred, 'General Physician')
            return pred, conf, spec
        except Exception:
            return self._fallback(symptoms)

    def _fallback(self, symptoms):
        sl = [s.lower() for s in symptoms]
        rules = [
            (['chest pain','shortness of breath','heart palpitations','arm pain'], 'Cardiac Issue', 'Cardiologist'),
            (['wheezing','chest tightness','asthma'], 'Asthma', 'Pulmonologist'),
            (['fever','cough','sore throat','body ache','chills'], 'Flu', 'General Physician'),
            (['fever','cough','headache'], 'Common Cold', 'General Physician'),
            (['severe headache','sensitivity to light','nausea','vomiting'], 'Migraine', 'Neurologist'),
            (['rash','itching','redness','hives'], 'Skin Allergy', 'Dermatologist'),
            (['stomach pain','nausea','vomiting','diarrhoea'], 'Gastroenteritis', 'Gastroenterologist'),
            (['joint pain','stiffness','swelling'], 'Arthritis', 'Rheumatologist'),
            (['fatigue','weakness','pale skin'], 'Anaemia', 'General Physician'),
            (['frequent urination','burning sensation'], 'UTI', 'Urologist'),
            (['excessive thirst','frequent urination'], 'Diabetes', 'Endocrinologist'),
        ]
        scores = {}
        for patterns, disease, spec in rules:
            score = sum(1 for s in sl for p in patterns if p in s or s in p)
            if score > 0 and (disease not in scores or score > scores[disease][0]):
                scores[disease] = (score, spec)
        if scores:
            best = max(scores.items(), key=lambda x: x[1][0])
            return best[0], min(0.75, 0.4 + best[1][0] * 0.1), best[1][1]
        return 'General Health Concern', 0.5, 'General Physician'

    def get_all_symptoms(self):
        if hasattr(self.mlb, 'classes_'):
            return sorted(list(self.mlb.classes_))
        return []

predictor = DiseasePredictor()
