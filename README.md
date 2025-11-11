# 🗺️ WanderGenie

> Your AI-powered travel planning assistant - transforming fuzzy prompts into concrete, bookable itineraries

## 🌟 What is WanderGenie?

WanderGenie is an intelligent travel planning assistant that uses **multi-agent AI** to transform natural language travel desires into complete, personalized itineraries. Simply tell us your travel plans, and we'll handle the rest.

### The Problem
Travel planning today means juggling multiple tabs: Google for attractions, Maps for routes, spreadsheets for schedules, booking sites for hotels and flights. It's fragmented, time-consuming, and overwhelming.

### Our Solution
**One conversational interface. Complete trip planning.**

Type: *"5 days in NYC from Buffalo, Dec 20-25, with a teen, love views & pizza, avoid long lines"*

Get:
- ✅ Day-by-day personalized itinerary with times & travel estimates
- ✅ Interactive map with location pins
- ✅ Calendar integration (Google Calendar or .ics export)
- ✅ Pre-filled booking links (flights, hotels, attractions)
- ✅ Conversational edits: "Swap Day 3 afternoon for MoMA" → updates instantly

---

## 🎥 Demo Video

**See WanderGenie in action!**

[![WanderGenie Demo](https://img.shields.io/badge/▶️_Watch_Demo-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://youtu.be/_Yy45dD6OKo?si=JRJoXCLChYxToToi)

> *[4-minute demo showcasing trip planning from natural language input to complete itinerary with maps, timeline, and booking links]*

---

## 🎯 Key Features

### 🤖 Multi-Agent Architecture
Powered by **LangGraph** with three specialized AI agents:
- **Planner Agent**: Interprets your travel intent and preferences
- **Researcher Agent**: Discovers and enriches points of interest using VectorDB + GraphDB
- **Packager-Executor Agent**: Builds optimized day-by-day schedules with smart routing

### 🧠 Intelligent Memory Systems
- **VectorDB (pgvector)**: Retrieval-augmented generation for booking tips, local insights, and constraints
- **GraphDB (Neo4j)**: Relationship-aware clustering for neighborhoods, similar attractions, and ticket vendors
- **Smart Caching**: Offline fallbacks ensure demos never break

### 💬 Conversational Editing
Make changes naturally:
- "Add Joe's Pizza to Day 2 lunch"
- "Move the Statue of Liberty to Day 1 morning"
- "Replace outdoor activities with museums on Day 3"

The entire itinerary, map, and calendar update automatically.

### 🗺️ Visual Planning
- **Interactive Maps**: Mapbox/Leaflet integration with pins, routes, and day-by-day clustering
- **Timeline View**: Clean, scannable schedule with travel time estimates
- **Progress Indicators**: Watch agents work in real-time with status chips

### 🔗 Smart Booking Integration
- **Google Flights**: Pre-filled origin, destination, and dates
- **Hotels**: Booking.com with accurate check-in/check-out dates and guest count
- **Attractions**: Direct links to official booking sites (Statue Cruises, museum tickets, etc.)

### 🌍 Universal City Support (NEW!)
- **LLM-Powered POI Generation**: Works for any city worldwide, not just pre-seeded locations
- **Intelligent Caching**: First-time generated POIs are saved to the database for faster future requests
- **State Name Inference**: "Florida" automatically converts to "Miami, FL" for better results
- **Growing Knowledge Base**: Every new city query enriches the system's POI database

---

## 🏗️ Architecture

### Tech Stack
- **Backend**: Python + FastAPI + LangGraph
- **LLM**: AWS Bedrock (AWS Nova Pro) with OpenAI fallback
- **Memory Layer**:
  - VectorDB: Supabase pgvector
  - GraphDB: Neo4j Aura Free
  - State Store: Supabase (PostgreSQL)
- **Frontend**: React + TypeScript + Tailwind CSS + Mapbox GL
- **Deployment**: Cloud-ready (Docker support included)

### High-Level Flow

```
User Prompt
    ↓
Planner Agent → Parse intent (city, dates, preferences)
    ↓
Researcher Agent → Find POIs
    ├─ Check VectorDB cache first
    ├─ Query OpenTripMap + GraphDB
    └─ LLM Fallback (if needed) → Save to cache
    ↓
Packager-Executor → Build schedule + Generate map/calendar/links
    ↓
Validator → Schema check + Auto-patch issues
    ↓
Complete trip.json → UI Update
```

See [ARCHITECTURE.md](./docs/ARCHITECTURE.md) for detailed diagrams and data flows.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+
- AWS Account (Bedrock access)
- Supabase Account (or local PostgreSQL + pgvector)
- Neo4j Aura Account (free tier)

### Environment Setup

1. **Clone the repository**
```bash
git clone https://github.com/PatilPrajakta14/WanderGenie-ai-travel-assistant.git
cd WanderGenie-ai-travel-assistant
```

2. **Backend Setup**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. **Frontend Setup**
```bash
cd Frontend/wandergenie
npm install
```

4. **Configure Environment Variables**

Create `.env` in the root directory:
```env
# LLM
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
OPENAI_API_KEY=your_openai_key

# Databases
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# APIs
OPENTRIPMAP_API_KEY=your_opentripmap_key
GOOGLE_CLIENT_ID=your_google_client_id  # Optional
GOOGLE_CLIENT_SECRET=your_google_secret  # Optional
```

5. **Seed Databases** (Optional - system will auto-generate POIs via LLM)
```bash
# Seed VectorDB (pre-load NYC data)
python backend/scripts/seed_vectordb.py

# Seed GraphDB (pre-load NYC relationships)
python backend/scripts/seed_graphdb.py
```

6. **Run Development Servers**
```bash
# Terminal 1: Backend
cd backend
python3 -m uvicorn backend.main:app --reload --port 8000

# Terminal 2: Frontend
cd Frontend/wandergenie
npm start
```

Visit `http://localhost:3000` to see WanderGenie in action! 🎉

---

## 📂 Project Structure

```
WanderGenie-ai-travel-assistant/
├── Frontend/
│   └── wandergenie/      # React application (TypeScript)
│       ├── src/
│       │   ├── components/   # React components
│       │   ├── hooks/        # Custom hooks
│       │   ├── pages/        # Page components
│       │   ├── services/     # API client
│       │   └── utils/        # Utilities
│       └── public/           # Static assets
├── backend/              # FastAPI + LangGraph
│   ├── agents/           # Planner, Researcher, Packager
│   ├── tools/            # POI search, distance, links, etc.
│   ├── memory/           # VectorDB + GraphDB clients
│   ├── routes/           # API endpoints
│   ├── schemas/          # Pydantic models
│   └── scripts/          # Database seeding scripts
├── data/                 # Seed data & fallback caches
│   ├── nyc_pois.json
│   ├── poi_facts.csv
│   └── neo4j_seed.cypher
├── docs/                 # Documentation
│   ├── ARCHITECTURE.md
│   ├── API.md
│   └── VECTORDB_IMPLEMENTATION.md
└── tests/                # Test suite
```

## 🤝 Team

**UB Hacking 2025 - Team WanderGenie**
- Sweta Sahu - LLM/Agent Lead
- Gautam Arora - Backend/API Lead
- Arpit Sharma - Frontend Lead
- Prajakta Patil - DevOps/Data Lead

**GitHub**: https://github.com/PatilPrajakta14/WanderGenie-ai-travel-assistant

---

Made with ❤️ at UB Hacking 2025 | November 8-9, 2025

