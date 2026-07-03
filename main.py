import os
import json
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pdfplumber
import google.generativeai as genai
from crewai import Agent, Task, Crew, Process, LLM
from crewai_tools import SerperDevTool
from dotenv import load_dotenv  # <-- ADD THIS LINE

# Load the variables from your .env file into the system environment
load_dotenv()

app = FastAPI(title="ElevateAI API Services")

# Enable CORS so your React Vite frontend can safely talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. SETUP API CONFIGURATIONS
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_KEY:
    raise ValueError("CRITICAL ERROR: Missing GEMINI_API_KEY inside the .env configuration.")

crew_llm = LLM(model="gemini/gemini-2.5-flash", api_key=GEMINI_KEY)

# 2. INTERACTIVE CHATBOT ENDPOINT
genai.configure(api_key=GEMINI_KEY)
chat_model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction="You are 'ElevateAI Coach', a friendly technical recruiter. You are chatting with a student inside their dashboard. Keep answers actionable, short, and highly professional."
)
chat_sessions = {}

class ChatRequest(BaseModel):
    session_id: str
    message: str

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        if request.session_id not in chat_sessions:
            chat_sessions[request.session_id] = chat_model.start_chat(history=[])
        
        session = chat_sessions[request.session_id]
        response = session.send_message(request.message)
        return {"response": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat Error: {str(e)}")

# 3. MULTI-AGENT EXECUTION PIPELINE (CrewAI)
def run_career_crew(resume_text: str, target_role: str):
    search_tool = SerperDevTool()

    matcher = Agent(
        role='ATS Optimization Expert',
        goal='Analyze engineer profiles against structural target roles to uncover technical skill gaps and compute an accurate ATS index score.',
        backstory='You operate exactly like an advanced enterprise applicant tracking scanner inspecting technical keywords.',
        llm=crew_llm,
        verbose=True
    )

    strategist = Agent(
        role='Tech Career Placement Strategist',
        goal='Map parsed candidate profiles to 3 specific tech corporations that actively recruit for this specific stack.',
        backstory='You track global engineering hiring trends and know which teams are hunting for specific frameworks.',
        tools=[search_tool],
        llm=crew_llm,
        verbose=True
    )

    coach = Agent(
        role='Technical Interview Coach',
        goal='Formulate precise company-specific technical interview questions and package a realistic 7-day learning guide.',
        backstory='You are a seasoned hiring manager who has sat behind the desk for hundreds of system architecture loops.',
        llm=crew_llm,
        verbose=True
    )

    json_formatting_instruction = """
    Return the response string STRICTLY as a valid JSON object. Do not wrap the JSON output inside markdown code blocks (do not include ```json or ```). It must start with {{ and end with }}. Use this exact template:
    {
      "ats_score": 78,
      "missing_skills": ["Docker", "Kubernetes", "Redis"],
      "companies": [
        {"name": "Amazon", "reason": "Actively scaling backends and looking for system optimization skills."}
      ],
      "interview_questions": {
        "Amazon": ["How do you scale an application horizontally?", "Design a rate limiter.", "Explain database sharding."]
      },
      "learning_roadmap": "### Day 1: Docker Basics\\n\\nLearn Docker fundamentals...\\n\\n### Day 2: Advanced Orchestration"
    }
    """

    task_ats = Task(
        description=f"Parse the following resume text: '{resume_text}' and evaluate it against the target job profile: '{target_role}'. Identify missing key tools, frameworks, or methodologies.",
        expected_output="A list of core missing skills and structural critique points.",
        agent=matcher
    )

    task_companies = Task(
        description="Identify 3 market companies actively scaling or operating with this technology stack based on missing gaps. Provide short reasoning loops.",
        expected_output="An exact mapping list matching the profile to target enterprises.",
        agent=strategist
    )

    task_package_report = Task(
        description=f"Compile the company details and missing skills. Generate exactly 3 technical interview questions customized for EACH recommended company, and write a brief 7-day study template. {json_formatting_instruction}",
        expected_output="A single structured JSON block string containing all final computed reports.",
        agent=coach
    )

    crew = Crew(
        agents=[matcher, strategist, coach],
        tasks=[task_ats, task_companies, task_package_report],
        process=Process.sequential
    )

    return crew.kickoff(inputs={'resume_text': resume_text, 'target_role': target_role})

@app.post("/analyze")
async def analyze_resume(file: UploadFile = File(...), target_role: str = Form(...)):
    try:
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Please upload a valid PDF file.")

        resume_text = ""
        with pdfplumber.open(file.file) as pdf:
            for page in pdf.pages:
                extracted_text = page.extract_text()
                if extracted_text:
                    resume_text += extracted_text + "\n"
        
        if not resume_text.strip():
            raise HTTPException(status_code=400, detail="The PDF file appears to be unparsable or empty.")
        
        raw_crew_result = run_career_crew(resume_text, target_role)
        clean_json_string = str(raw_crew_result).strip().replace("```json", "").replace("```", "")
        response_payload = json.loads(clean_json_string)
        return response_payload

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"System Error: {str(e)}")