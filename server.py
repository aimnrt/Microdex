import os
import io
import json
from flask import Flask, request, jsonify
# Importera Google GenAI SDK
from google import genai
# Importera bibliotek för att läsa PDF/Docx
# OBS: PyPDF2 hanterar PDF. Docx/andra kräver andra bibliotek (t.ex. python-docx)
from PyPDF2 import PdfReader 
from docx import Document 

app = Flask(__name__)

# --- AI Setup: Läser din API-nyckel från miljövariabeln ---
AI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=AI_API_KEY)


# --- Helper Functions ---

def parse_file_to_text(file_stream, filename):
    """Parsar en filström baserat på filändelsen och returnerar text."""
    try:
        # Hantera PDF
        if filename.lower().endswith('.pdf'):
            reader = PdfReader(file_stream)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text
        
        # Hantera DOCX (Word-dokument)
        elif filename.lower().endswith('.docx'):
            document = Document(file_stream)
            return "\n".join([p.text for p in document.paragraphs])

        # Hantera ren text
        elif filename.lower().endswith('.txt'):
            return file_stream.read().decode('utf-8')

        return "Kunde inte tolka filtypen. Standardtext om ekologi används."

    except Exception as e:
        print(f"Fil parsing error: {e}")
        return "Ett fel uppstod vid tolkning. Här är en fallback-text om ekologi."


def generate_quiz_with_ai(context_text):
    """Anropar Gemini API för att generera quizet."""

    prompt = f"""
    Baserat på följande text, generera 10 flervalsfrågor.
    Varje fråga måste ha 4 unika svarsalternativ.
    Returnera svaret strikt som en JSON-array. 
    JSON-objektet ska ha fälten 'question' (sträng), 'options' (array av strängar), och 'correctIndex' (heltal 0-3 för det rätta svaret).
    
    TEXT:
    ---
    {context_text}
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-pro', # Bra modell för strukturerat svar
            contents=prompt
        )
        
        # Renar texten (tar bort eventuella '```json' och '```')
        json_string = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(json_string)

    except Exception as e:
        print(f"AI-anrop eller JSON-fel: {e}")
        # Hårdkodad fallback vid misslyckad AI-generering
        return [{"question": "AI-generering misslyckades. Kontrollera API-nyckel eller text.", "options": ["A", "B", "C", "D"], "correctIndex": 0}]

# --- API Endpoint ---

@app.route('/api/generate-quiz', methods=['POST'])
def handle_quiz_generation():
    if not AI_API_KEY:
         return jsonify({"error": "GEMINI_API_KEY är inte konfigurerad på servern."}), 500

    if 'pdf_file' not in request.files:
        return jsonify({"error": "Ingen fil hittades. Använd fältnamnet 'pdf_file'."}), 400
    
    pdf_file = request.files['pdf_file']
    
    # Läs filen i minnet som en binär ström
    file_stream = io.BytesIO(pdf_file.read())
    
    # Parsa filen
    context_text = parse_file_to_text(file_stream, pdf_file.filename)
    
    # Anropa AI
    quiz_data = generate_quiz_with_ai(context_text)
    
    # Returnera quizet
    return jsonify(quiz_data), 200

# Endpoint för att testa att servern körs
@app.route('/')
def home():
    return "Quiz Backend Server Körs. Skicka POST till /api/generate-quiz."

if __name__ == '__main__':
    # Kör lokalt: flask --app server run
    app.run(debug=True, port=5000)
