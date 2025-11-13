import os
import io
import json
from flask import Flask, request, jsonify
from google import genai
from PyPDF2 import PdfReader
# Bibliotek för att hantera .docx
from docx import Document 

# Vercel-kompatibel Flask-app
app = Flask(__name__)

# --- Filhantering & Parsing ---

def parse_file_to_text(file_stream, filename):
    """Parsar en filström baserat på filändelsen."""
    try:
        filename_lower = filename.lower()

        # Hantera PDF
        if filename_lower.endswith('.pdf'):
            reader = PdfReader(file_stream)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text

        # Hantera DOCX (Word-dokument)
        elif filename_lower.endswith('.docx'):
            document = Document(file_stream)
            return "\n".join([p.text for p in document.paragraphs])

        # Hantera ren text (.txt)
        elif filename_lower.endswith('.txt'):
            return file_stream.read().decode('utf-8')

        else:
            return None # Ogiltig filtyp

    except Exception as e:
        print(f"Fil parsing error: {e}")
        # Returnerar ett felmeddelande som AI kan hantera som kontext
        return f"FEL: Kunde inte tolka filen. Textinnehållet är tomt eller ogiltigt. Det tekniska felet var: {e}"

# --- AI Logik ---

def generate_quiz_with_ai(context_text):
    """Anropar Gemini API för att generera quizet."""

    # Skär av texten om den är för lång (för att spara tokens/kostnad)
    context_limit = 20000 
    truncated_text = context_text[:context_limit]

    prompt = f"""
    Baserat på följande text/kontext, generera 10 flervalsfrågor. Om texten är kort, generera färre frågor.
    Varje fråga måste ha 4 unika svarsalternativ.
    Returnera svaret strikt som en JSON-array. 
    JSON-objektet ska ha exakt dessa fält: 'question' (sträng), 'options' (array av strängar), och 'correctIndex' (heltal 0-3 för det rätta svaret). Svaret får INTE innehålla något annat än den rena JSON-arrayen.

    KONTEXT:
    ---
    {truncated_text}
    """

    try:
        AI_API_KEY = os.getenv("GEMINI_API_KEY")
        if not AI_API_KEY:
             raise ValueError("API-nyckel saknas")

        client = genai.Client(api_key=AI_API_KEY)

        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=prompt
        )

        # Renar texten (tar bort eventuella '```json' och '```')
        json_string = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(json_string)

    except Exception as e:
        print(f"AI-anrop eller JSON-fel: {e}")
        # Skickar ett tekniskt fel tillbaka för display
        return None 

# --- API Endpoint ---

@app.route('/api/quiz', methods=['POST'])
def handler():
    if 'doc_file' not in request.files:
        return jsonify({"error": "Ingen fil hittades. Använd fältnamnet 'doc_file'."}), 400

    doc_file = request.files['doc_file']

    # Läs filen i minnet som en binär ström
    file_stream = io.BytesIO(doc_file.read())

    # Parsa filen
    context_text = parse_file_to_text(file_stream, doc_file.filename)

    if not context_text or context_text.startswith("FEL:"):
        return jsonify({"error": context_text or "Kunde inte tolka filen. Filtypen kanske inte stöds."}), 500

    # Anropa AI
    quiz_data = generate_quiz_with_ai(context_text)

    if quiz_data is None:
        return jsonify({"error": "AI-genereringen misslyckades. Kontrollera API-nyckeln och serverloggarna."}), 500

    # Returnera quizet
    return jsonify(quiz_data), 200

# Vercel kräver en 'main' funktion i API-filen för att fungera som Serverless
# Även om vi använder Flask, rekommenderas ibland en Vercel-wrapper
# För enkelhetens skull låter vi Flask-appen hantera '/api/quiz'