import os, zipfile
import pdfplumber
import pandas as pd
from docx import Document

def parse_uploaded_folder(uploaded_file_path):
    extracted_texts = []
    if uploaded_file_path.endswith(".zip"):
        extract_dir = "/tmp/citedeck_folder"
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(uploaded_file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        walk_dir = extract_dir
    else:
        walk_dir = os.path.dirname(uploaded_file_path)
        # For single file, parse directly
        file = os.path.basename(uploaded_file_path)
        path = uploaded_file_path
        try:
            if file.endswith(".pdf"):
                with pdfplumber.open(path) as pdf:
                    text = "\n".join([p.extract_text() or "" for p in pdf.pages[:5]])
                    return [{"file": file, "type": "pdf", "text": text[:8000]}]
            elif file.endswith((".xlsx", ".xls")):
                df = pd.read_excel(path)
                return [{"file": file, "type": "excel", "text": df.head(20).to_string()}]
        except Exception as e:
            return [{"file": file, "type": "error", "text": str(e)}]
    
    for root, dirs, files in os.walk(walk_dir):
        for file in files:
            path = os.path.join(root, file)
            try:
                if file.endswith(".pdf"):
                    with pdfplumber.open(path) as pdf:
                        text = "\n".join([p.extract_text() or "" for p in pdf.pages[:5]])
                        extracted_texts.append({"file": file, "type": "pdf", "text": text[:8000]})
                elif file.endswith((".xlsx", ".xls")):
                    df = pd.read_excel(path)
                    extracted_texts.append({"file": file, "type": "excel", "text": df.head(20).to_string()})
                elif file.endswith(".csv"):
                    df = pd.read_csv(path)
                    extracted_texts.append({"file": file, "type": "csv", "text": df.head(20).to_string()})
                elif file.endswith(".docx"):
                    doc = Document(path)
                    text = "\n".join([p.text for p in doc.paragraphs])
                    extracted_texts.append({"file": file, "type": "docx", "text": text[:8000]})
            except Exception as e:
                extracted_texts.append({"file": file, "type": "error", "text": str(e)})
    return extracted_texts
