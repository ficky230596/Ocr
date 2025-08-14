import os
import re
import logging
from flask import Flask, render_template, request, redirect, url_for
from PIL import Image, ImageOps
import pytesseract

# Konfigurasi logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Konfigurasi Tesseract
if os.name == 'nt':  # Windows
    pytesseract.pytesseract.tesseract_cmd = r"C:\Users\user\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
else:  # Linux/Unix-based (seperti Replit)
    pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

# Konfigurasi folder upload
UPLOAD_FOLDER = '/tmp/uploads' if 'REPLIT' in os.environ else 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Regex untuk NIK dan field KTP
NIK_REGEX = re.compile(r"\b(\d{16})\b")
FIELD_REGEX = {
    "Nama": re.compile(r"Nama\s*:?\s*(.*)", re.IGNORECASE),
    "Tempat/Tgl Lahir": re.compile(r"Tempat/?Tgl Lahir\s*:?\s*(.*)", re.IGNORECASE),
    "Jenis Kelamin": re.compile(r"Jenis Kelamin\s*:?\s*(.*)", re.IGNORECASE),
    "Agama": re.compile(r"Agama\s*:?\s*(.*)", re.IGNORECASE),
    "Status Perkawinan": re.compile(r"Status Perkawinan\s*:?\s*(.*)", re.IGNORECASE),
    "Pekerjaan": re.compile(r"Pekerjaan\s*:?\s*(.*)", re.IGNORECASE),
    "Gol Darah": re.compile(r"Gol\.?\s?Darah\s*:?\s*(.*)", re.IGNORECASE),
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def preprocess_image(path):
    """Proses gambar: ubah ke grayscale, auto-contrast, dan resize jika kecil"""
    try:
        img = Image.open(path)
        img = ImageOps.exif_transpose(img)  # Perbaiki rotasi
        img = img.convert('L')  # Grayscale
        img = ImageOps.autocontrast(img)

        max_dim = 1600
        if max(img.size) < 1000:
            ratio = max_dim / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        return img
    except Exception as e:
        logger.error(f"Error preprocessing image: {e}")
        raise

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    try:
        # Validasi input
        if 'image' not in request.files or 'name' not in request.form or 'tempat_tgl_lahir' not in request.form or 'alamat' not in request.form or 'agama' not in request.form or 'gol_darah' not in request.form:
            logger.warning("Missing image file or input fields")
            return render_template('index.html', error='Harap unggah gambar dan isi semua field')

        file = request.files['image']
        input_name = request.form['name'].strip()
        input_tempat_tgl_lahir = request.form['tempat_tgl_lahir'].strip()
        input_alamat = request.form['alamat'].strip()
        input_agama = request.form['agama'].strip()
        input_gol_darah = request.form['gol_darah'].strip()

        if file.filename == '':
            logger.warning("No file selected")
            return render_template('index.html', error='Pilih file gambar terlebih dahulu')

        if not allowed_file(file.filename):
            logger.warning(f"Invalid file type: {file.filename}")
            return render_template('index.html', error='File harus berformat PNG, JPG, JPEG, atau BMP')

        # Simpan file dengan nama unik
        filename = f"{os.urandom(8).hex()}_{file.filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        logger.info(f"File saved: {filepath}")

        # Proses gambar
        img = preprocess_image(filepath)

        # OCR
        try:
            text = pytesseract.image_to_string(img, lang='ind')
        except Exception as e:
            logger.warning(f"OCR with lang='ind' failed: {e}, trying default lang")
            text = pytesseract.image_to_string(img)

        # Ekstrak NIK
        niks = NIK_REGEX.findall(text)
        logger.info(f"NIK found: {niks}")

        # Ekstrak field KTP
        data_ktp = {}
        for field, pattern in FIELD_REGEX.items():
            match = pattern.search(text)
            data_ktp[field] = match.group(1).strip() if match else "Tidak ditemukan"

        # Periksa kecocokan setiap input dengan teks mentah
        text_matches = {
            "Nama": "Cocok" if re.search(r"\b" + re.escape(input_name) + r"\b", text, re.IGNORECASE) else "Tidak Cocok",
            "Tempat/Tgl Lahir": "Cocok" if re.search(r"\b" + re.escape(input_tempat_tgl_lahir) + r"\b", text, re.IGNORECASE) else "Tidak Cocok",
            "Alamat": "Cocok" if re.search(r"\b" + re.escape(input_alamat) + r"\b", text, re.IGNORECASE) else "Tidak Cocok",
            "Agama": "Cocok" if re.search(r"\b" + re.escape(input_agama) + r"\b", text, re.IGNORECASE) else "Tidak Cocok",
            "Gol Darah": "Cocok" if re.search(r"\b" + re.escape(input_gol_darah) + r"\b", text, re.IGNORECASE) else "Tidak Cocok",
        }
        logger.info(f"Text check - Input Nama: {input_name}, Match: {text_matches['Nama']}")
        logger.info(f"Text check - Input Tempat/Tgl Lahir: {input_tempat_tgl_lahir}, Match: {text_matches['Tempat/Tgl Lahir']}")
        logger.info(f"Text check - Input Alamat: {input_alamat}, Match: {text_matches['Alamat']}")
        logger.info(f"Text check - Input Agama: {input_agama}, Match: {text_matches['Agama']}")
        logger.info(f"Text check - Input Gol Darah: {input_gol_darah}, Match: {text_matches['Gol Darah']}")

        # Hitung jumlah kecocokan
        match_count = sum(1 for status in text_matches.values() if status == "Cocok")
        logger.info(f"Total matches: {match_count}")

        # Tentukan status keberhasilan
        success = match_count >= 3

        # Hapus file setelah diproses
        os.remove(filepath)
        logger.info(f"File deleted: {filepath}")

        # Arahkan ke berhasil.html dengan status keberhasilan
        return render_template('berhasil.html', input_name=input_name, input_tempat_tgl_lahir=input_tempat_tgl_lahir,
                             input_alamat=input_alamat, input_agama=input_agama, input_gol_darah=input_gol_darah,
                             text_matches=text_matches, success=success, text=text, niks=niks, data_ktp=data_ktp)
    
    except Exception as e:
        logger.error(f"Error in upload: {e}")
        return render_template('index.html', error=f'Terjadi kesalahan: {str(e)}')

if __name__ == '__main__':
    host = '0.0.0.0' if 'REPLIT' in os.environ else '127.0.0.1'
    port = int(os.environ.get('PORT', 8080 if 'REPLIT' in os.environ else 5000))
    app.run(host=host, port=port, debug=not 'REPLIT' in os.environ)