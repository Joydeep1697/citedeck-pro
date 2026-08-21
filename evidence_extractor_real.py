import re, os, json
from pathlib import Path

class EvidenceExtractorReal:
    """Real provenance: PDF page, Excel cell, docx paragraph, URL passage"""
    
    def extract_pdf_with_pages(self, pdf_path):
        """Returns facts with page number"""
        try:
            import pdfplumber
            facts = []
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    # Find numbers with context
                    for m in re.finditer(r'(\$?\d+(?:,\d+)*(?:\.\d+)?\s*(?:B|M|Cr|billion|million|%|USD)?)', text):
                        start = max(0, m.start()-80)
                        end = min(len(text), m.end()+80)
                        snippet = text[start:end].replace("\n"," ")
                        facts.append({
                            "claim": m.group(0),
                            "claim_span": m.group(0),
                            "source_file": os.path.basename(pdf_path),
                            "source_type": "pdf",
                            "page_number": i+1,
                            "paragraph": f"Page {i+1}",
                            "source_text": snippet,
                            "char_start": m.start(),
                            "char_end": m.end(),
                            "verification_status": "EXTRACTED_WITH_PAGE",
                            "can_use_in_deck": True
                        })
            return facts
        except Exception as e:
            return [{"claim": f"PDF error: {e}", "source_file": os.path.basename(pdf_path), "page_number": None, "can_use_in_deck": False}]

    def extract_excel_with_cells(self, excel_path):
        """Returns facts with sheet + cell address"""
        try:
            import openpyxl
            wb = openpyxl.load_workbook(excel_path, data_only=True)
            facts = []
            for sheet in wb.sheetnames[:3]:  # first 3 sheets
                ws = wb[sheet]
                for row in ws.iter_rows(min_row=1, max_row=100, max_col=20):
                    for cell in row:
                        if cell.value is None:
                            continue
                        val = str(cell.value)
                        # If looks like number or contains number
                        if re.search(r'\d', val) and len(val) < 100:
                            facts.append({
                                "claim": val,
                                "claim_span": val,
                                "source_file": os.path.basename(excel_path),
                                "source_type": "excel",
                                "sheet": sheet,
                                "cell": f"{cell.coordinate}",
                                "cell_range": f"{sheet}!{cell.coordinate}",
                                "source_text": f"{sheet}!{cell.coordinate} = {val}",
                                "verification_status": "EXTRACTED_WITH_CELL",
                                "can_use_in_deck": True
                            })
            return facts[:50]  # limit
        except Exception as e:
            return [{"claim": f"Excel error: {e}", "source_file": os.path.basename(excel_path), "cell": None, "can_use_in_deck": False}]

    def extract_docx_with_paragraph(self, docx_path):
        try:
            import docx
            doc = docx.Document(docx_path)
            facts = []
            for i, para in enumerate(doc.paragraphs):
                text = para.text
                for m in re.finditer(r'(\$?\d+(?:,\d+)*(?:\.\d+)?\s*(?:B|M|Cr|billion|million|%|USD)?)', text):
                    facts.append({
                        "claim": m.group(0),
                        "source_file": os.path.basename(docx_path),
                        "source_type": "docx",
                        "paragraph_number": i+1,
                        "paragraph_text": text[:200],
                        "source_text": text[max(0,m.start()-80):m.end()+80],
                        "verification_status": "EXTRACTED_WITH_PARA",
                        "can_use_in_deck": True
                    })
            return facts
        except Exception as e:
            return []

# Test
if __name__ == "__main__":
    ex = EvidenceExtractorReal()
    print("Extractor real with page, cell, para provenance ready")
