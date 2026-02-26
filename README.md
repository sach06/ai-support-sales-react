# AI Supported Sales Application — React Edition 🚀

This is the modernized, two-tier architecture of the AI Supported Sales App. It replaces the original Streamlit monolith with a fast, scalable **React (Vite) Frontend** and a **FastAPI Python Backend**.

## Architecture Overview

```text
[ React Frontend (Port 5173) ]  ↔  [ FastAPI Backend (Port 8000) ]  ↔  [ DuckDB + ML Models ]
```

- **Frontend:** Built with React, Vite, Zustand (for state management like Streamlit session state), TanStack react-query (for dynamic data caching), and react-table/react-plotly.
- **Backend:** FastAPI wrapper that directly re-uses all original Python AI logic (XGBoost, GPT-4o generator, DuckDB logic, DOCX generators) without logic rewrites.

## Project Structure

- `/backend` — The Python FastAPI service. Contains `app/` and the original DuckDB database `data/` folder and `models/`.
- `/frontend` — The React UI application.

---

## Setting Up and Running Locally

### 1. Backend Setup

Open a terminal and navigate to the backend folder:
```bash
cd backend
```

**Install requirements:**
```bash
pip install -r requirements.txt
```

**Configure Environment:**
Copy `.env.example` to `.env` and fill in your Azure OpenAI or standard OpenAI keys.

**Run the Backend Server:**
```bash
uvicorn app.main:app --reload
```
*The backend will start at `http://localhost:8000`. You can view the API documentation at `http://localhost:8000/docs`.*

---

### 2. Frontend Setup

Open a separate terminal and navigate to the frontend folder:
```bash
cd frontend
```

**Install Node Dependencies:**
```bash
npm install
```

**Start the Development Server:**
```bash
npm run dev
```

*The application will now be running at `http://localhost:5173`. Any API calls to `/api` made by the frontend will be automatically proxied to the FastAPI backend running on port 8000.*

---

## Features Migrated

✅ **Module 1:** Data Ingestion & DuckDB REST Endpoints  
✅ **Module 2:** XGBoost Priority Ranking Model wrapping  
✅ **Module 3:** Generative Steckbrief LLM profiling & File Export streaming  
✅ **Module 4:** Global Layout, Sidebar Filters, & Zustand State Management  
✅ **Module 5:** Live Dashboard Mapping (Plotly) & Link Data Analysis  
✅ **Module 6:** Full Sorting Priority Ranking Tables & Feature Analysis Charts  
✅ **Module 7:** Deep Dive Customer Profile Gen with Inline Tab Management  

*Developed iteratively mapping monolithic stream-server logic into disjointed, secure REST calls.*
