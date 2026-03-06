import os
import base64
import json
import re
from datetime import datetime
from flask import Flask, request, send_from_directory, redirect, url_for, render_template_string
from openai import OpenAI
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from werkzeug.utils import secure_filename

# ========================= # CONFIG # =========================

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Замените на ваши реальные данные
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
LOG_FILE = "gpt_raw_log.txt"

# Маппинг ключей JSON к колонкам в Google Таблице
COLUMN_MAP = {
    "CustomerName": "G", "Phone": "H", "Hotel": "B", "Tour": "Q",
    "Price": "J", "DateIn": "S", "Deposit": "K", "Guests": "D",
    "Room": "F", "PickupTime": "I", "Remainder": "L", "DateOut": "P", "TicketNo": "O"
}

# ========================= # INIT # =========================

app = Flask(__name__)
client = OpenAI() # Ожидает переменную окружения OPENAI_API_KEY

# Настройка Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)
    gs_client = gspread.authorize(creds)
    sheet = gs_client.open_by_key(SPREADSHEET_ID).sheet1
except Exception as e:
    print(f"Ошибка доступа к Google Таблицам: {e}")

# ========================= # HELPERS # =========================

def normalize_phone(phone: str) -> str:
    if not phone: return ""
    # Разбиваем строку, если несколько номеров (через пробел, запятую, слеш и т.п.)
    parts = re.split(r"[\/,;]+|\s+", phone)
    normalized_parts = []
    for part in parts:
        if not part:
            continue
        digits = re.sub(r"\D", "", part)
        if not digits:
            continue
        if len(digits) == 10:
            digits = "7" + digits
        elif len(digits) == 11 and (digits.startswith("8") or digits.startswith("7")):
            digits = "7" + digits[1:]
        normalized_parts.append(digits)
    return "/".join(normalized_parts)

def normalize_date(date_str: str) -> str:
    if not date_str: return ""
    # Оставляет только цифры и заменяет разделители на слеши
    cleaned = re.sub(r"[^\d]+", "/", date_str).strip("/")
    return cleaned

def normalize_total(value: str) -> str:
    """
    Если в строке несколько чисел — суммируем и возвращаем сумму с символом $.
    """
    if not value:
        return ""
    numbers = re.findall(r"\d+", value)
    if not numbers:
        return value
    total = sum(int(n) for n in numbers)
    # Требуемый формат: 45$ (знак после числа)
    return f"{total}$"

def transliterate(text: str) -> str:
    if not text: return ""
    dic = {"А":"A","Б":"B","В":"V","Г":"G","Д":"D","Е":"E","Ё":"E","Ж":"Zh","З":"Z","И":"I",
           "Й":"Y","К":"K","Л":"L","М":"M","Н":"N","О":"O","П":"P","Р":"R","С":"S","Т":"T",
           "У":"U","Ф":"F","Х":"Kh","Ц":"Ts","Ч":"Ch","Ш":"Sh","Щ":"Sch","Ы":"Y","Э":"E",
           "Ю":"Yu","Я":"Ya","ь":"","ъ":""}
    res = "".join([dic.get(c.upper(), c).lower() if c.islower() else dic.get(c.upper(), c) for c in text])
    return res

# ========================= # GPT CORE # =========================

def extract_data_from_image(image_path):
    with open(image_path, "rb") as img_file:
        base64_image = base64.b64encode(img_file.read()).decode("utf-8")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract receipt data. Return ONLY valid JSON with keys: CustomerName, Phone, Hotel, Tour, Price, DateIn, Deposit, Guests, Room, PickupTime, Remainder, DateOut, TicketNo. CustomerName is printed in Cyrillic on the receipt: read and return it exactly in Cyrillic as on the receipt (do NOT transliterate or translate), the server will convert it to Latin later. For Price: if there is a '$' symbol, take the numeric value immediately before this '$', going backwards until the nearest space. If a key is missing, return an empty string. No markdown."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ],
            }
        ]
    )
    text_output = response.choices[0].message.content.strip()
    text_output = re.sub(r"```json|```", "", text_output).strip()
    
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        log.write(f"\n--- {datetime.now()} ---\n{text_output}\n")
    
    return json.loads(text_output)

# ========================= # ROUTES # =========================

@app.route("/")
def index():
    saved = request.args.get("saved")
    return render_template_string("""
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Receipt Processor</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background-color: #f4f7f6; transition: 0.3s; overflow-x: hidden; }
            .drop-zone { border: 2px dashed #adb5bd; border-radius: 15px; padding: 100px 20px; text-align: center; background: white; cursor: pointer; transition: 0.3s; }
            .drop-zone.dragover { border-color: #0d6efd; background: #e9ecef; }
            
            /* Sidebar */
            #sidebar {
                position: fixed; right: -360px; top: 0; width: 350px; height: 100%;
                background: white; border-left: 1px solid #dee2e6; box-shadow: -5px 0 15px rgba(0,0,0,0.05);
                transition: 0.4s cubic-bezier(0.4, 0, 0.2, 1); padding: 30px; z-index: 1050;
            }
            #sidebar.active { right: 0; }
            .status-step { margin-bottom: 30px; opacity: 0.2; transition: 0.3s; }
            .status-step.active { opacity: 1; font-weight: bold; color: #0d6efd; }
            .status-step.done { opacity: 1; color: #198754; }
            .spinner-border-sm { display: none; margin-right: 10px; }
            .active .spinner-border-sm { display: inline-block; }
        </style>
    </head>
    <body>

    <div class="container py-5">
        <div class="row justify-content-center">
            <div class="col-md-7">
                {% if saved %}<div class="alert alert-success shadow-sm border-0">✓ Данные успешно сохранены в таблицу!</div>{% endif %}
                
                <div class="card border-0 shadow-sm">
                    <div class="card-body p-5 text-center">
                        <h3 class="mb-4 fw-bold">Загрузка Чека</h3>
                        <div class="drop-zone" id="dropZone">
                            <p class="mb-0 text-muted">Перетащите изображение чека сюда</p>
                            <small class="text-secondary">или нажмите для выбора файла</small>
                        </div>
                        <input type="file" id="fileInput" style="display:none" accept="image/*">
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div id="sidebar">
        <h4 class="mb-4">Обработка...</h4>
        <div id="step-upload" class="status-step">
            <div class="spinner-border spinner-border-sm text-primary"></div>
            1. Загрузка файла
            <div class="progress mt-2" style="height: 6px;">
                <div id="uploadProgress" class="progress-bar progress-bar-striped progress-bar-animated" style="width: 0%"></div>
            </div>
        </div>
        <div id="step-ai" class="status-step">
            <div class="spinner-border spinner-border-sm text-primary"></div>
            2. ИИ распознает текст...
        </div>
        <div id="step-final" class="status-step">
            3. Подготовка формы...
        </div>
    </div>

    <script>
        const dropZone = document.getElementById("dropZone");
        const fileInput = document.getElementById("fileInput");
        const sidebar = document.getElementById("sidebar");

        dropZone.onclick = () => fileInput.click();
        fileInput.onchange = (e) => uploadFile(e.target.files[0]);
        dropZone.ondragover = (e) => { e.preventDefault(); dropZone.classList.add("dragover"); };
        dropZone.ondragleave = () => dropZone.classList.remove("dragover");
        dropZone.ondrop = (e) => { e.preventDefault(); uploadFile(e.dataTransfer.files[0]); };

        function setStep(stepId, status) {
            const el = document.getElementById(stepId);
            if(status === 'active') el.classList.add("active");
            if(status === 'done') { el.classList.remove("active"); el.classList.add("done"); }
        }

        function uploadFile(file) {
            if(!file) return;
            sidebar.classList.add("active");
            setStep("step-upload", "active");

            const fd = new FormData();
            fd.append("file", file);

            const xhr = new XMLHttpRequest();
            xhr.open("POST", "/upload", true);

            xhr.upload.onprogress = (e) => {
                if (e.lengthComputable) {
                    const percent = Math.round((e.loaded / e.total) * 100);
                    document.getElementById("uploadProgress").style.width = percent + "%";
                    if(percent === 100) {
                        setStep("step-upload", "done");
                        setStep("step-ai", "active");
                    }
                }
            };

            xhr.onload = () => {
                if (xhr.status === 200) {
                    setStep("step-ai", "done");
                    setStep("step-final", "active");
                    setTimeout(() => {
                        document.open();
                        document.write(xhr.responseText);
                        document.close();
                    }, 600);
                } else {
                    alert("Ошибка при обработке файла");
                    sidebar.classList.remove("active");
                }
            };
            xhr.send(fd);
        }
    </script>
    </body></html>
    """, saved=saved)

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if not file: return "No file", 400
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    try:
        data = extract_data_from_image(filepath)
    except Exception as e:
        return f"Ошибка ИИ: {e}", 500
    
    # Приоритетное поле total для суммы
    total_raw = data.get("total") or data.get("Total")
    if total_raw:
        data["Price"] = normalize_total(total_raw)
    elif "Price" in data and data["Price"]:
        data["Price"] = normalize_total(data["Price"])

    # Нормализация данных
    if "CustomerName" in data: data["CustomerName"] = transliterate(data["CustomerName"])
    if "Phone" in data: data["Phone"] = normalize_phone(data["Phone"])
    if "DateIn" in data: data["DateIn"] = normalize_date(data["DateIn"])
    if "DateOut" in data: data["DateOut"] = normalize_date(data["DateOut"])

    return render_template_string("""
    <!doctype html>
    <html lang="en">
    <head>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <title>Confirm Data</title>
        <style>
            body { background: #f4f7f6; padding: 40px 0; }
            
            /* Стили Лупы-курсора */
            .img-magnifier-container { 
                position: relative; 
                display: inline-block; 
                width: 100%; 
                cursor: none; /* Прячем обычный курсор */
            }
            .img-magnifier-glass {
                position: absolute;
                border: 3px solid #333;
                border-radius: 50%;
                width: 200px;
                height: 200px;
                display: none;
                pointer-events: none; /* Пропускает клики сквозь себя */
                box-shadow: 0 0 20px rgba(0,0,0,0.4);
                z-index: 1000;
                transform: translate(-50%, -50%); /* Центрирование */
            }
            #receipt-img { width: 100%; border-radius: 10px; display: block; }
        </style>
    </head>
    <body>
    <div class="container">
        <div class="row">
            <!-- Просмотр чека с лупой -->
            <div class="col-md-5 mb-4">
                <div class="card shadow-sm border-0 sticky-top" style="top: 20px;">
                    <div class="card-body p-2">
                        <div class="img-magnifier-container" id="magnifierArea">
                            <img id="receipt-img" src="/uploads/{{fn}}">
                        </div>
                        <p class="text-center text-muted small mt-3">Используйте лупу для проверки данных</p>
                    </div>
                </div>
            </div>
            
            <!-- Форма подтверждения -->
            <div class="col-md-7">
                <div class="card shadow-sm border-0"><div class="card-body p-4">
                    <h4 class="mb-4">Проверьте данные</h4>
                    <form action="/confirm" method="post" class="row g-3">
                        {% for k, v in data.items() %}
                        <div class="col-md-6">
                            <label class="form-label small text-uppercase text-muted fw-bold">{{k}}</label>
                            <input type="text" name="{{k}}" value="{{v}}" class="form-control">
                        </div>
                        {% endfor %}
                        <div class="col-12 mt-4">
                            <button type="submit" class="btn btn-primary btn-lg w-100 shadow-sm">Подтвердить и сохранить</button>
                            <a href="/" class="btn btn-link w-100 mt-2 text-secondary">Отмена</a>
                        </div>
                    </form>
                </div></div>
            </div>
        </div>
    </div>

    <script>
    function magnify(imgID, zoom) {
        var img = document.getElementById(imgID);
        var glass = document.createElement("DIV");
        glass.setAttribute("class", "img-magnifier-glass");
        img.parentElement.insertBefore(glass, img);

        glass.style.backgroundImage = "url('" + img.src + "')";
        glass.style.backgroundRepeat = "no-repeat";

        img.addEventListener("mousemove", moveMagnifier);
        img.addEventListener("mouseenter", () => glass.style.display = "block");
        img.addEventListener("mouseleave", () => glass.style.display = "none");

        function moveMagnifier(e) {
            var pos, x, y, bw = 3;
            pos = getCursorPos(e);
            x = pos.x; y = pos.y;

            // Обновляем параметры фона
            glass.style.backgroundSize = (img.width * zoom) + "px " + (img.height * zoom) + "px";
            
            // Центрируем лупу по курсору
            glass.style.left = x + "px";
            glass.style.top = y + "px";

            // Вычисляем смещение картинки внутри лупы
            var w = glass.offsetWidth / 2;
            var h = glass.offsetHeight / 2;
            var bgX = (x * zoom) - w + bw;
            var bgY = (y * zoom) - h + bw;

            glass.style.backgroundPosition = "-" + bgX + "px -" + bgY + "px";
        }

        function getCursorPos(e) {
            var a = img.getBoundingClientRect();
            var x = e.clientX - a.left;
            var y = e.clientY - a.top;
            return {x: x, y: y};
        }
    }

    window.onload = function() {
        magnify("receipt-img", 3); // 3x увеличение
    };
    </script>
    </body></html>
    """, data=data, fn=filename)

@app.route("/confirm", methods=["POST"])
def confirm():
    data = request.form.to_dict()
    
    # Подготовка строки (19 колонок A-S)
    row_data = [""] * 19
    for key, col_letter in COLUMN_MAP.items():
        col_idx = ord(col_letter.upper()) - ord("A")
        if col_idx < 19:
            row_data[col_idx] = data.get(key, "")

    # Поиск следующей строки в таблице
    try:
        existing = sheet.get_all_values()
        next_row = max(4, len(existing) + 1)
        sheet.insert_row(row_data, next_row, value_input_option='USER_ENTERED')
    except Exception as e:
        print(f"Sheets Write Error: {e}")

    return redirect(url_for("index", saved=1))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == "__main__":
    app.run(debug=True, port=5000)