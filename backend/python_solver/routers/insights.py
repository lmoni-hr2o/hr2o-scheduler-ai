
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import json
import pandas as pd
import time
import re
from utils.datastore_helper import get_db
from google.cloud import datastore
from utils.advisor_engine import AdvisorEngine
from utils.demand_profiler import get_demand_profile

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    responses={404: {"description": "Not found"}},
)

# --- MODELS ---
class ScheduleAnalysisRequest(BaseModel):
    environment: str
    schedule: List[Dict[str, Any]] # The generated list of shifts

class PreCheckRequest(BaseModel):
    environment: str
    employees: List[Dict[str, Any]]
    activities: List[Dict[str, Any]]
    constraints: Dict[str, Any]
    config: Dict[str, Any]
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    # We might need additional context like active employees, but schedule implies them

# --- PORTED LOGIC FROM ai_planner.py ---

def _get_gemini_api_key() -> str:
    # Use environment var or fallback logic
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        # Fallback to Datastore AlgorithmConfig
        try:
           client = datastore.Client()
           key_key = client.key('AlgorithmConfig', 'global')
           entity = client.get(key_key)
           if entity and 'gemini_api_key' in entity:
               return entity['gemini_api_key']
        except:
           pass
    return key

def llm_call(prompt: str, system: str = "", model: str = "gemini-1.5-flash", json_only: bool = False) -> str:
    """Simplistic wrapper for Gemini Call - requires google-genai or vertexai installed"""
    api_key = _get_gemini_api_key()
    if not api_key:
        print("WARNING: GEMINI_API_KEY not found.")
        return "ERROR: GEMINI_API_KEY mancante nel Backend."
        
    try:
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=api_key)
        
        user_text = prompt
        if json_only:
            user_text += "\n\nVINCOLO: Rispondi SOLO con JSON valido."

        config = types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=2000,
            response_mime_type="application/json" if json_only else "text/plain",
            system_instruction=system
        )
        
        # Strategy: Use models CONFIRMED by debug endpoint
        models_to_try = [
            "gemini-2.0-flash", 
            "gemini-flash-latest", 
            "gemini-pro-latest",
            "gemini-2.0-flash-lite",
            "gemini-1.5-pro-latest" # Just in case
        ]
        
        # If user specified a model, try that first
        if model not in models_to_try:
            models_to_try.insert(0, model)
        else:
            # Move specified to front
            models_to_try.remove(model)
            models_to_try.insert(0, model)
            
        last_error = None
        
        for m in models_to_try:
            try:
                print(f"DEBUG: Trying Gemini Model: {m}")
                resp = client.models.generate_content(model=m, contents=[user_text], config=config)
                return resp.text or ""
            except Exception as e:
                print(f"Warning: Model {m} failed: {e}")
                last_error = e
                continue
        
        # If all failed
        raise last_error
        
    except ImportError:
        print("WARNING: google-genai library not found.")
        return "ERROR: Libreria google-genai non installata nel Backend."
    except Exception as e:
        print(f"ERROR: LLM Call failed: {e}")
        raise e # Re-raise to be caught by the outer try-except

def build_planner_digest(schedule_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Summarizes the schedule into key stats for the LLM.
    Ported/Adapted from build_planner_digest in ai_planner.py
    """
    df = pd.DataFrame(schedule_data)
    if df.empty:
        return {"error": "Empty schedule"}

    # Basic stats
    digest = {}
    
    # 1. Commesse (Activities) Analysis
    # Group by activity_id -> sum hours, count unassigned
    if "is_unassigned" not in df.columns:
        df["is_unassigned"] = False
        
    # Helper to calculate hours
    def calc_hours(r):
        try:
            h1, m1 = map(int, r["start_time"].split(':'))
            h2, m2 = map(int, r["end_time"].split(':'))
            dur = (h2*60+m2) - (h1*60+m1)
            if dur < 0: dur += 1440
            return dur / 60.0
        except: return 0.0

    df["hours"] = df.apply(calc_hours, axis=1)

    # Top Activities by Load
    act_load = df.groupby("activity_id")["hours"].sum().reset_index().sort_values("hours", ascending=False).head(10)
    digest["top_activities"] = act_load.to_dict(orient="records")
    
    # Unassigned Gaps
    unassigned = df[df["is_unassigned"] == True]
    if not unassigned.empty:
        gaps = unassigned.groupby("activity_id")["hours"].sum().reset_index().sort_values("hours", ascending=False).head(10)
        digest["unassigned_gaps"] = gaps.to_dict(orient="records")
        digest["total_unassigned_hours"] = unassigned["hours"].sum()
    else:
        digest["unassigned_gaps"] = []
        digest["total_unassigned_hours"] = 0

    # 2. Employees Analysis
    # Top loaded employees
    assigned = df[df["is_unassigned"] == False]
    if not assigned.empty:
        emp_load = assigned.groupby("employee_name")["hours"].sum().reset_index().sort_values("hours", ascending=False).head(10)
        digest["top_employees_load"] = emp_load.to_dict(orient="records")
        
        # Risk Analysis (if we had risk data in schedule - currently not passed explicitly in result list, 
        # but we can infer if high risk people are assigned? 
        # For now, just load)
    
    return digest

def generate_report_text(digest: Dict[str, Any]) -> Dict[str, Any]:
    """ Calls Gemini to generate the report """
    if "error" in digest:
        return {"summary": "Nessun dato scedulato.", "risks": [], "actions": []}

    prompt = f"""
    REPORT POST-GENERAZIONE SCHEDULING:
    Digest dei Dati Generati:
    {json.dumps(digest, indent=2)}
    
    OBIETTIVI DEL REPORT (ANALISI ECONOMICO-TECNICA):
    1. Analisi dei Costi e dell'Efficienza: Fornisci un parere sulla saturazione delle risorse. (es. 'Efficienza alta, solo 2% di ore non assegnate').
    2. Rispetto dei Contratti: Segnala se qualcuno sta superando le proprie ore contrattuali o se ci sono rischi di sforamento budget orario.
    3. Parere Tecnico Legale: Verifica (a grandi linee) se i riposi di 11 ore e i massimali settimanali sono stati rispettati globalmente.
    4. NON dare suggerimenti sulla qualità dei turni (es. 'potevi mettere X al posto di Y'), dato che la schedulazione è già considerata al massimo della sua possibilità tecnica.
    5. Suggerisci azioni SOLO se di natura economica o contrattuale (es. 'Valuta assunzione part-time per coprire i gap ricorrenti').

    Formato JSON richiesto:
    {{
      "summary": "Analisi dell'efficienza economica e tecnica dello scheduling...",
      "risks": [ {{ "title": "Rischio Economico/Contrattuale", "severity": "HIGH/MEDIUM/LOW", "description": "..." }} ],
      "actions": [ {{ 
          "title": "Azione Strategica", 
          "priority": "HIGH/MEDIUM", 
          "description": "Consiglio tecnico/economico...",
          "type": "update_config", 
          "payload": {{ "field": value }} 
      }} ]
    }}
    """
    
    system = "Sei un analista esperto di pianificazione risorse umane. Sii conciso e prammatico."
    
    try:
        txt = llm_call(prompt, system=system, json_only=True)
    except Exception as e:
        print(f"Generate Report Error: {e}")
        return {
            "summary": f"Errore AI: {str(e)}",
            "risks": [{"title": "Eccezione Servizio", "severity": "HIGH", "description": f"Dettagli: {str(e)}"}],
            "actions": []
        }

    if not txt:
        return {
            "summary": "Impossibile generare il report AI. Risposta vuota dal modello.",
            "risks": [],
            "actions": []
        }

    # Parse JSON robustly
    try:
        # Strip fences if present
        txt = txt.strip()
        if txt.startswith("```json"): txt = txt[7:]
        elif txt.startswith("```"): txt = txt[3:] # Handle fenced block without language
        
        if txt.endswith("```"): txt = txt[:-3]
        
        return json.loads(txt)
    except Exception as e:
        print(f"Error parsing LLM response: {e}. Raw text: {txt[:100]}...")
        return {
            "summary": "Errore nel parsing del report AI.", 
            "risks": [{"title": "Errore Formato", "severity": "LOW", "description": f"Risposta LLM non valida: {str(e)}"}], 
            "actions": []
        }

@router.post("/analysis")
async def analyze_schedule(request: ScheduleAnalysisRequest):
    """
    Analizza uno scheduling già generato e restituisce un report AI.
    """
    digest = build_planner_digest(request.schedule)
    report = generate_report_text(digest)
    return report

@router.post("/pre-check")
async def analyze_pre_check(request: PreCheckRequest):
    """
    Analizza i parametri PRIMA della generazione usando il MOTORE AI INTERNO.
    """
    try:
        # 1. Fetch Demand Profile
        profile = get_demand_profile(request.environment)
        
        # 2. Run Deterministic Advisor Engine
        result = AdvisorEngine.analyze(
            environment=request.environment,
            employees=request.employees,
            activities=request.activities,
            config=request.config,
            start_date=request.start_date,
            end_date=request.end_date,
            demand_profile=profile
        )
        
        return result
        
    except Exception as e:
        print(f"Pre-check Error (Internal Engine): {e}")
        return {
            "summary": f"Analisi pre-check non disponibile (Motore Interno): {str(e)}",
            "suggestions": []
        }


@router.get("/debug-models-public")
def debug_models_public():
    """Debug endpoint to list available models. Public for diagnosis."""
    api_key = _get_gemini_api_key()
    if not api_key:
        return {"error": "No API Key configured"}
        
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        # Try listing - format depends on SDK version
        # google-genai 0.3 pattern
        models = []
        try:
             # V1 SDK usually exposes models via client.models.list()
             for m in client.models.list():
                 # Inspect available attributes safely
                 models.append({
                     "name": getattr(m, "name", "unknown"),
                     "display_name": getattr(m, "display_name", ""),
                     "supported_generation_methods": getattr(m, "supported_generation_methods", [])
                 })
        except Exception as e:
             return {"error": f"List failed: {e}", "details": str(e)}
             
        return {"models": models, "count": len(models)}
        
    except ImportError:
        return {"error": "Library google-genai not found"}
    except Exception as e:
        return {"error": f"Client init failed: {e}"}

