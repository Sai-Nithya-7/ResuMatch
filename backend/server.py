import os
import io
import csv
from flask import Flask, request, jsonify, render_template, url_for
from pymongo import MongoClient
import cohere
from PyPDF2 import PdfReader

app = Flask(__name__)

# MongoDB connection setup
client = MongoClient("mongodb://localhost:27017/")
db = client["grok_ai_db"]
results_collection = db["results"]

# Instantiate the Cohere client with your API key
co = cohere.Client("P7aypS8sGQai3e8ZfffsEwrczeGRPRM4amzIbssI")  # Replace with your actual Cohere API key

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/resume_upload')
def resume_upload():
    return render_template("resume_upload.html")

@app.route('/upload', methods=['POST'])
def upload():
    try:
        # Retrieve the uploaded PDF file and job description from the form data
        pdf_file = request.files.get('pdf')
        user_string = request.form.get('user_string')
        
        if not pdf_file or not user_string:
            return jsonify({"error": "Both a PDF file and an input string are required."}), 400

        # Save the uploaded PDF temporarily
        temp_path = os.path.join("/tmp", pdf_file.filename)
        pdf_file.save(temp_path)
        
        # Extract text from the PDF using PyPDF2
        reader = PdfReader(temp_path)
        pdf_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pdf_text += text + "\n"
        
        # Construct the prompt for Cohere to generate CSV formatted output.
        prompt = (
            "Given the following resume and job description, extract the key relevant details "
            "and generate a CSV formatted output. The CSV should include two columns: 'Section' and 'Details'.\n\n"
            "Resume:\n" + pdf_text + "\n"
            "Job Description:\n" + user_string + "\n\n"
            "CSV Output:\nSection,Details\n"
        )
        
        # Call Cohere's generate endpoint to produce the CSV output
        response = co.generate(
            model='command-xlarge-nightly',  # Choose a model appropriate for your needs
            prompt=prompt,
            max_tokens=300,
            temperature=0.3,
            stop_sequences=["\n\n"]
        )
        
        csv_text = response.generations[0].text.strip()
        
        # Parse the CSV content into a list of dictionaries using csv.DictReader
        csv_file_io = io.StringIO(csv_text)
        reader = csv.DictReader(csv_file_io)
        parsed_data = list(reader)
        
        # Store the input details and the CSV results in MongoDB
        document = {
            "pdf_filename": pdf_file.filename,
            "user_string": user_string,
            "csv_raw": csv_text,
            "csv_parsed": parsed_data
        }
        results_collection.insert_one(document)
        
        # Remove the temporary file
        os.remove(temp_path)
        
        # Return the parsed CSV data as JSON to display the result in a copyable format
        return jsonify({
            "result": parsed_data
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
