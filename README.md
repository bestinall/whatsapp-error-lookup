# WhatsApp Error Lookup

Powered by Gemini API

An internal Technical Support Engineer (TSE) tool for rapid error analysis and client communication generation.

---

## Overview

WhatsApp Error Lookup streamlines error investigation by mapping Meta WhatsApp error codes to Karix internal codes and generating AI-powered responses. TSEs can instantly understand errors and produce professionally formatted client communications in seconds.

---

## Features

- **Error Code Mapping**: Maps Meta WhatsApp error codes to Karix internal error codes
- **Instant Error Lookup**: Manual error code entry with immediate error meaning display
- **AI-Powered Analysis**: Generate Root Cause Analysis (RCA), Solution, and client responses with one click
- **Multi-Format Client Responses**: Three professionally formatted response styles
  - Formal Response (Style 1)
  - Formal Response (Style 2)
  - Technical Response
- **Response Standardization**: All client responses follow standard format with greeting and closing
- **Security**: Karix internal error codes never exposed in client-facing output
- **Search History**: Sidebar displays recently searched error codes as quick-access chips
- **Most Searched Errors**: View popular errors with search count badges
- **TSE Tips**: Quick reference guide for Technical Support Engineers
- **Keyboard Shortcuts**: Full keyboard support for efficient workflow

---

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Google Gemini API key

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/adityashelke04/whatsapp_error_lookup.git
cd whatsapp-error-lookup
```

### 2. Create a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and add your Gemini API key:

```plaintext
GEMINI_API_KEY=your_key_here
```

To obtain a Gemini API Key:
1. Visit [Google AI Studio](https://ai.google.dev)
2. Click "Get API Key"
3. Copy the key into your `.env` file

---

## How to Run

Start the FastAPI development server:

```bash
uvicorn main:app --reload
```

The application will be available at `http://localhost:8000`

---

## How to Use

### Basic Workflow

1. **Enter Error Code**: Input a Meta WhatsApp error code in the search field
2. **View Error Meaning**: The tool displays what the error means
3. **Analyze**: Click "Analyze This Error" to generate AI responses
4. **View Results**: The tool generates:
   - Root Cause Analysis (RCA)
   - Recommended solution
   - Three client-facing response options
5. **Copy Response**: Select and copy the appropriate response style for your client
6. **Reference History**: Use the sidebar to access recently searched errors and TSE tips

### Client Response Format

All client-facing responses follow this standard:
- **Opening**: "Hi {Client Name},"
- **Body**: Solution and guidance
- **Closing**: "If you need any further assistance, we are happy to help."

---

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Focus search | `/` |
| Look up error | `Enter` |
| Generate responses | `G` |
| Clear and reset | `Esc` |

---

## Project Structure

```
whatsapp-error-lookup/
├── main.py
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
├── DESIGN.md
├── README.md
├── error_codes.json
├── skills-lock.json
├── test_api.py
├── static/
│   └── index.html
└── .agents/
    └── skills/
```

---

## Technology Stack

- **Backend**: FastAPI (Python)
- **Frontend**: HTML, CSS, JavaScript
- **AI Engine**: Google Gemini 2.5 Flash Lite API
- **Environment Management**: python-dotenv

---

## Environment Variables

Required:

```plaintext
GEMINI_API_KEY=your_key_here
```

---

## Internal Use Only

**CONFIDENTIAL**: This tool is exclusively for Karix Technical Support Engineers. Unauthorized access, distribution, or use is strictly prohibited. Error codes and internal analysis information must never be shared outside of Karix.
