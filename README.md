# AI Receipt & Booking Data Extractor

AI-powered system for extracting handwritten and unstructured booking data from receipts and automatically transferring structured information to Google Sheets for further processing and CRM integration.

The system allows businesses to digitize paper receipts and booking forms using AI.

---

## Features

- AI extraction of handwritten and printed receipt data
- automatic structuring of unstructured information
- phone number normalization
- date normalization
- automatic price calculation
- transliteration of Cyrillic names to Latin
- upload interface with drag & drop
- visual verification interface with image magnifier
- integration with Google Sheets
- preparation of structured data for CRM systems

---

## Workflow

1. User uploads a receipt image
2. The system sends the image to OpenAI Vision
3. AI extracts booking data into structured JSON
4. Data is normalized and cleaned
5. User verifies extracted information
6. Data is automatically saved to Google Sheets
7. Data can then be processed by CRM systems

---

## Tech Stack

Python  
Flask  
OpenAI API (Vision / GPT-4o)  
Google Sheets API  
gspread  
Bootstrap 5  
Regex data normalization  

---

## System Architecture


Receipt Image
↓
Flask Upload Server
↓
OpenAI Vision Extraction
↓
Data Normalization Layer
↓
User Verification Interface
↓
Google Sheets
↓
CRM Processing


---

## Installation

### 1. Clone repository


git clone https://github.com/yourusername/ai-receipt-extractor.git

cd ai-receipt-extractor


### 2. Install dependencies


pip install -r requirements.txt


### 3. Setup environment variables

Create environment variable:


OPENAI_API_KEY=your_api_key


### 4. Add Google Service Account

Place file:


service_account.json


in project root.

### 5. Configure Google Spreadsheet ID

Update variable in code:


SPREADSHEET_ID = "your_google_sheet_id"


---

## Running the app


python app.py


Open in browser:


http://localhost:5000


---

## Use Case

Tourism agencies, booking operators, and hospitality businesses often receive handwritten receipts and booking forms.

This system automates:

- receipt digitization
- structured data extraction
- CRM data preparation

---

## Future Improvements

- OCR fallback layer
- direct CRM API integration
- PDF receipt support
- automatic duplicate detection
- batch processing

---
