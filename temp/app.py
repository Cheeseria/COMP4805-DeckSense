# app.py
from flask import Flask, render_template, request
import driver
import os
import markdown

app = Flask(__name__)
os.makedirs("cache", exist_ok=True)

@app.route('/', methods=['GET', 'POST'])
def index():
    primer_html = None
    error = None
    
    if request.method == 'POST':
        # .strip() removes trailing newlines/whitespace that come from the textarea
        deck_url = request.form.get('deck_url', '').strip()
        
        if deck_url:
            try:
                driver.run(deck_url)
                
                deck_id = deck_url.rstrip("/").split("/")[-1].strip()
                primer_path = f"cache/{deck_id}_l4_primer.md"
                
                if os.path.exists(primer_path):
                    with open(primer_path, "r", encoding="utf-8") as f:
                        raw_md = f.read()
                        
                    # Convert Markdown to HTML so the PDF looks clean
                    primer_html = markdown.markdown(raw_md, extensions=['tables', 'fenced_code'])
                else:
                    error = "Pipeline ran but could not find the primer file."
                    
            except Exception as e:
                error = f"An error occurred: {str(e)}"
        else:
            error = "Please enter a deck URL."

    return render_template('index.html', primer=primer_html, error=error)

if __name__ == '__main__':
    app.run(debug=True)