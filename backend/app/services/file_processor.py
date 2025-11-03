import os
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import PyPDF2
from docx import Document
import openpyxl
from PIL import Image
# Note: python-magic not installed, using extension-based MIME type detection


class FileProcessor:
    """Service for processing uploaded files and extracting text content"""
    
    @staticmethod
    def extract_text(filepath: str, mime_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract text content from a file
        
        Returns:
            dict with 'text' and 'metadata' keys
        """
        path = Path(filepath)
        
        if not mime_type:
            # Guess MIME type from extension
            ext = path.suffix.lower()
            mime_types = {
                '.pdf': 'application/pdf',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                '.doc': 'application/msword',
                '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                '.xls': 'application/vnd.ms-excel',
                '.txt': 'text/plain',
                '.md': 'text/markdown',
            }
            mime_type = mime_types.get(ext, 'application/octet-stream')
        
        text = ""
        metadata: Dict[str, Any] = {
            "mime_type": mime_type,
            "file_size": path.stat().st_size,
        }
        
        try:
            if mime_type == "application/pdf":
                text, metadata = FileProcessor._extract_from_pdf(filepath)
            elif mime_type in [
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/msword",
            ]:
                text, metadata = FileProcessor._extract_from_docx(filepath)
            elif mime_type in [
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-excel",
            ]:
                text, metadata = FileProcessor._extract_from_xlsx(filepath)
            elif mime_type.startswith("text/"):
                text, metadata = FileProcessor._extract_from_text(filepath)
            elif mime_type.startswith("image/"):
                # For images, we can't extract text directly
                # Would need OCR (like Tesseract) for this
                text = ""
                metadata["is_image"] = True
            else:
                text = ""
                metadata["unsupported"] = True
        except Exception as e:
            metadata["error"] = str(e)
            text = ""
        
        return {
            "text": text,
            "metadata": metadata,
        }
    
    @staticmethod
    def _extract_from_pdf(filepath: str) -> Tuple[str, Dict[str, Any]]:
        """Extract text from PDF"""
        text_parts = []
        metadata = {"pages": 0}
        
        with open(filepath, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            metadata["pages"] = len(pdf_reader.pages)
            
            for page in pdf_reader.pages:
                text_parts.append(page.extract_text())
        
        return "\n\n".join(text_parts), metadata
    
    @staticmethod
    def _extract_from_docx(filepath: str) -> Tuple[str, Dict[str, Any]]:
        """Extract text from Word document"""
        doc = Document(filepath)
        text_parts = [paragraph.text for paragraph in doc.paragraphs]
        
        metadata = {
            "paragraphs": len(doc.paragraphs),
        }
        
        return "\n\n".join(text_parts), metadata
    
    @staticmethod
    def _extract_from_xlsx(filepath: str) -> Tuple[str, Dict[str, Any]]:
        """Extract text from Excel file"""
        workbook = openpyxl.load_workbook(filepath)
        text_parts = []
        
        metadata = {
            "sheets": workbook.sheetnames,
            "sheet_count": len(workbook.sheetnames),
        }
        
        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
            sheet_text = []
            
            for row in sheet.iter_rows(values_only=True):
                row_text = "\t".join(str(cell) if cell else "" for cell in row)
                sheet_text.append(row_text)
            
            text_parts.append(f"Sheet: {sheet_name}\n" + "\n".join(sheet_text))
        
        return "\n\n".join(text_parts), metadata
    
    @staticmethod
    def _extract_from_text(filepath: str) -> Tuple[str, Dict[str, Any]]:
        """Extract text from plain text file"""
        with open(filepath, "r", encoding="utf-8", errors="ignore") as file:
            text = file.read()
        
        metadata = {
            "lines": len(text.splitlines()),
        }
        
        return text, metadata

