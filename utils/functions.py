import io
import re
import unicodedata
from functools import partial
import logging
from pathlib import Path

import base64
import cv2
import numpy as np
import pytesseract
from fpdf import FPDF
from pdf2image import convert_from_path
from PIL import Image
import fitz


# Logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(filename)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log")
    ]
)
logger = logging.getLogger(__name__)


# Función para remover acentos
def remove_accents(text: str) -> str:
    """
    Remove the accents from a text using unicode data.
    Returns a text string without accent.

    Args:
        text: string of text
    """
    text = unicodedata.normalize("NFD", text)
    return ''.join(c for c in text if unicodedata.category(c) != "Mn")


# Función para leer y extraer información de cada página
def process_image(image: Image) -> Image:
    """
    Convert image to grayscale color.
    Returns a processed image.

    Args:
        image: Image to process
    """
    image = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(binary)


# Función que extrae el texto de cada página del documento
def extract_text_from_document(doc_path: Path, poppler_path: Path, tesseract_path: Path) -> str:
    """
    Extract text from pages inlucind images.
    Returns a text string of all pages.

    Args:
        doc_path: Local path of the document
        poppler_path: Local path of Poppler
        tesseract_path: Local path of tesseract
    """
    logger.info(f"Document: {doc_path.name}")
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
    # os.environ['TESSDATA_PREFIX'] = r"C:\Users\O014796\AppData\Local\Programs\Tesseract-OCR\tessdata"
    full_text = ""
    pages = convert_from_path(doc_path, dpi=200, poppler_path=poppler_path)
    for i, page in enumerate(pages):
        processed = process_image(page)
        ocr_text = pytesseract.image_to_string(processed, lang="spa", config="--psm 6")
        ocr_text = remove_accents(ocr_text.strip())
        full_text += f"\n\n--- Página {i + 1}---\n\n{ocr_text}"
    return full_text.strip()


# Función para reemplazar texto
def replacement(match: str, exceptions: str) -> str:
    """
    Replaces name regex groups with [NOMBRE].
    Returns [NOMBRE] string

    Args:
        match: str match
        exceptions: regex list of exceptions
    """
    name = match.group(0)
    if any(p.upper() in exceptions for p in name.split()):
        return name
    return '[NOMBRE]'


# Función para anonimizar el texto quitando valores sensibles
def encrypt_text(text: str) -> str:
    """
    Extract text from pages inlucind images.
    Returns a text string of all pages.

    Args:
        doc_path: Local path of the document
    """
    text = text.replace('\xa0', ' ').replace('\u200b', ' ')
    email_regex = re.compile(r'''\b [\w\.-]+ \s* [\(\[\{<]? @|arroba|\(a\)|\[a\] [\)\]\}>]? \s* [\w\.-]+ \.[a-z]{2,} \b''',
        re.IGNORECASE | re.VERBOSE)
    text = re.sub(email_regex, '[CORREO]', text)
    frag_email_regex = re.compile(r'\b\S{1,50}(gmail\.com|hotmail\.com|outlook\.com|yahoo\.com|live\.com|une\.net\.co|icloud\.com)\b',
        re.IGNORECASE)
    text = re.sub(frag_email_regex, '[CORREO]', text)
    text = re.sub(r'\b3\d{2}[\s\-.]?\d{3}[\s\-.]?\d{4}\b','[TELÉFONO]', text)
    text = re.sub(r'(?<!\$)\b\d{8,10}\b', '[CÉDULA]', text)
    text = re.sub(r'(?<!\$)\b\d{1,3}(?:\.\d{3}){2,3}\b', '[CÉDULA]', text)
    # Enmascarar cuentas específicas: 9, 10, 16 o 20 dígitos exactos
    direct_account_regex = re.compile(r'\b(?:\d{9}|\d{10}|\d{16}|\d{20})\b')
    text = re.sub(direct_account_regex, '[CUENTA]', text)
    prompt_account_regex = re.compile(r'\b(?:\d{2,6}[-]){2,4}\d{2,6}\b')
    text = re.sub(prompt_account_regex, '[CUENTA]', text)
    sentence_account_regex = re.compile(r'(Cuenta\s+de\s+(?:Ahorro|Corriente)[\sN°\.]*)(\d{9}|\d{10}|\d{16}|\d{20})',flags=re.IGNORECASE)
    text = re.sub(sentence_account_regex, r'\1[CUENTA]', text)
    text = re.sub(r'\b(Calle|Carrera|Cra|Cr|Kra|Transversal|Diagonal|Av\.?|Avenida|Mz|Manzana|Anillo|Autopista|Circular)\s*\d+[A-Za-z]?\s*(Bis)?\s*(#|No\.?)\s*\d+[A-Za-z]?\s*[-–]?\s*\d+\b(?:[\w\s,°\.#-]{0,40})?', '[DIRECCIÓN]', text, flags=re.IGNORECASE)
    exceptions = {'BBVA','NET','CC','SUPERINTENDENCIA','BANCO','COLOMBIA','SURA','DIAN','ICBF','EPS','ADRES',
                   'Av','Cédula','DERECHO DE PETICIÓN','DERECHOS','NO','NI','PSE','Banco Bilbao Vizcaya','FUNDAMENTOS'}
    names_regex = re.compile(r'\b((?:[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:[\s\u00A0\r\n]+(?:de|del))?[\s\u00A0\r\n]*)+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+|(?:[A-ZÁÉÍÓÚÑ]{2,}(?:[\s\u00A0\r\n]+[A-ZÁÉÍÓÚÑ]{2,}){1,}))\b')
    replacement_exceptions = partial(replacement, exceptions=exceptions)
    text = names_regex.sub(replacement_exceptions, text)
    text = re.sub(r'Atentamente[,:]?\s+[A-ZÁÉÍÓÚÑ ]{3,}', 'Atentamente, [NOMBRE]', text)
    text = re.sub(r'\b[Yy]o,\s*((?:[A-ZÁÉÍÓÚÑ]{2,}(?:\s+|,\s*)){1,6})', 'Yo, [NOMBRE]', text)
    return text


# Función para crear PDF a partir del texto
def create_pdf(text: str, output_path: Path, font_path: Path) -> Path:
    """
    Create a new pdf from all pages text.
    Returns the new document local path.

    Args:
        text: Pages string
        output_path: Local path of the new document
        font_path: Local path of the font
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("Noto", "", font_path, uni=True)
    pdf.set_font("Noto", size=12)
    pdf.set_auto_page_break(auto=True, margin=15)
    for linea in text.split("\n"):
        pdf.multi_cell(0, 10, linea)
    pdf.output(output_path)
    logger.info(f"Generated document: {output_path.name}")
    return None


# Función para generar documento encriptado
def encrypt_document(doc_path: Path, output_path: Path, poppler_path: Path, tesseract_path: Path, font_path: Path) -> str:
    """
    Extract all info from document including text and image
    using pytesseract. After that cleanses the text from
    sensitive data and returns a new .pdf file.

    Args:
        doc_path: Local path of the pqrs file
    """
    try:
        ocr_text = extract_text_from_document(doc_path, poppler_path, tesseract_path)
        logger.info("Extracted text from document")
    except Exception as e:
        logger.error(f"Error extracting text: {e}")
        return None
    try:
        encrypted_text = encrypt_text(ocr_text)
        logger.info("Encrypted text")
    except Exception as e:
        logger.error(f"Error encrypting text: {e}")
        return None
    try:
        create_pdf(encrypted_text, output_path, font_path)
    except Exception as e:
        logger.error(f"Error creating pdf: {e}")
        return None
    return None


# Función para leer las paginas del pdf y convertirlas en base64
def doc_to_base64(doc_path: Path) -> list[dict]:
    """
    Returns a list of dict with base64 images for
    each page of a given document.

    Args:
        doc_path: Local Path of the document
    """

    pdf_document = fitz.open(doc_path)
    n_pages = len(pdf_document)
    # Para cada una de las paginas del pdf
    # Le pedimos que la convierta en un mapa de pixeles y
    # eso es lo que convertimos en base64 para que lo lea el llm
    base64_data = []
    for page_index in range(0, n_pages):
        page = pdf_document.load_page(page_index)
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        codified_page = base64.b64encode(buffer.getvalue()).decode("utf-8")
        # Guardamos en la lista de todas las paginas
        # base64_data.append(codified_page)
        # Alternativamente podemos dejar de una
        # Cada imagen en el formato del message
        msg_dict = {
            "type": "image",
            "source_type": "base64",
            "data": codified_page,
            "mime_type": "image/png"
        }
        base64_data.append(msg_dict)
    logger.info("Document pages converted")

    return base64_data