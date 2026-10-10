#!/usr/bin/env python3
"""
Empowered Care - Multi-Agent Disease Outbreak Detection System
"""

import logging
import uuid
import io
import json
import cv2
import numpy as np
import pandas as pd
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, status, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import FileResponse, JSONResponse

from models.schemas import (
    OutbreakProcessResponse, QueryResponse, ChatRequest, ChatResponse,
    UserRole, UserInvite, UserAcceptInvite, PasswordResetRequest,
    PasswordResetConfirm, ChangePassword, Token, User, UserBase,
    PatientRecord, PatientRecordResponse, VitalSigns
)
from services.gemini_service import GeminiService, AIQuotaExhausted
from services.llm import get_llm
from services.agents import (
    SuperAgent, DataAssistantAgent, ChatSupervisor,
    ExtractionAgent, ValidationAgent, RiskAnalysisAgent, AlertGenerationAgent
)
from services.auth_service import AuthService

from utils.pdf_utils import pdf_to_images
from utils.security import create_access_token, decode_token
from config import (
    API_TITLE, API_VERSION, LOG_LEVEL, LOG_FORMAT, ALLOWED_ORIGINS, 
    MAX_TEXT_LENGTH, MAX_QUERY_LENGTH, ACCESS_TOKEN_EXPIRE_MINUTES,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT
)
logger = logging.getLogger(__name__)

logger.info("🚀 Starting Empowered Care Unified System...")

# Initialize FastAPI app
app = FastAPI(
    title=API_TITLE,
    description="AI-powered disease outbreak detection and medical document processing",
    version=API_VERSION
)

# Authentication logic
auth_service = AuthService()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    email: str = payload.get("sub")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = auth_service.get_user_by_email(email)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

async def get_current_admin(user: dict = Depends(get_current_user)):
    if user["role"] != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return user

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AIQuotaExhausted)
async def ai_quota_exhausted(request, exc: AIQuotaExhausted):
    """Quota limits are temporary: answer 503 with a plain message instead of a generic 500."""
    logger.warning(f"⏳ {exc}")
    return JSONResponse(status_code=503, content={"detail": str(exc)})

# Initialize core services
logger.info("🔧 Initializing Core Services...")
try:
    gemini_service = GeminiService()  # vision/OCR calls
    llm = get_llm(gemini_service)      # text agents; LLM_PROVIDER selects the vendor
    
    logger.info("✅ Gemini service initialized")
except Exception as e:
    logger.error(f"❌ Failed to initialize core services: {e}")
    raise

# Initialize agents
logger.info("🤖 Initializing Dynamic Agents...")
try:
    super_agent = SuperAgent(llm)
    data_assistant = DataAssistantAgent(llm)
    chat_supervisor = ChatSupervisor(llm, data_assistant)
    
    # Standard agents (can be used individually if needed)
    extraction_agent = ExtractionAgent(llm)
    validation_agent = ValidationAgent(llm)
    risk_agent = RiskAnalysisAgent(llm)
    alert_agent = AlertGenerationAgent(llm)
    
    logger.info("✅ Dynamic Agents and Chatbot initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize agents: {e}")
    raise

# --- SCHEDULER SETUP ---
scheduler = AsyncIOScheduler()
analysis_status = {
    "last_run": None,
    "last_result": None,
    "next_run": None,
    "schedule": None,
    "is_running": False
}

async def scheduled_analysis_job():
    """Background job for scheduled analysis."""
    global analysis_status
    if analysis_status["is_running"]:
        logger.info("⚠️ Scheduled analysis skipped: Job already running")
        return

    analysis_status["is_running"] = True
    logger.info("🕒 Starting scheduled system analysis...")
    try:
        result = await data_assistant.perform_full_analysis()
        analysis_status["last_run"] = str(datetime.now())
        analysis_status["last_result"] = result
        logger.info("✅ Scheduled system analysis complete.")
    except Exception as e:
        logger.error(f"❌ Scheduled analysis failed: {e}")
    finally:
        analysis_status["is_running"] = False

@app.on_event("startup")
async def start_scheduler():
    scheduler.start()
    logger.info("⏰ Scheduler started")

@app.on_event("shutdown")
async def stop_scheduler():
    scheduler.shutdown()
    logger.info("⏰ Scheduler stopped")

logger.info("✅ Empowered Care initialization complete!")

# --- ADMIN ANALYSIS & SCHEDULING ENDPOINTS ---

@app.post("/admin/analyze/manual")
async def manual_analysis(admin: dict = Depends(get_current_admin)):
    """Manually trigger a full system analysis comparing new and historical data."""
    logger.info(f"🚨 Admin {admin['email']} triggered manual full analysis.")
    try:
        result = await data_assistant.perform_full_analysis()
        analysis_status["last_run"] = str(datetime.now())
        analysis_status["last_result"] = result
        return {
            "message": "Full system analysis complete.",
            "timestamp": str(datetime.now()),
            "result": result
        }
    except AIQuotaExhausted:
        raise
    except Exception as e:
        logger.error(f"❌ Manual analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.post("/admin/analyze/schedule")
async def update_analysis_schedule(
    request: dict,
    admin: dict = Depends(get_current_admin)
):
    """Set or update the automatic analysis schedule (cron format)."""
    cron_str = request.get("cron", "0 0 * * *") # Default: Every day at midnight
    # Example: "*/5 * * * *" for every 5 minutes
    
    try:
        # Remove existing job if any
        if scheduler.get_job("analysis_job"):
            scheduler.remove_job("analysis_job")

        # Add new job
        trigger = CronTrigger.from_crontab(cron_str)
        scheduler.add_job(
            scheduled_analysis_job,
            trigger,
            id="analysis_job"
        )
        
        analysis_status["schedule"] = cron_str
        analysis_status["next_run"] = str(scheduler.get_job("analysis_job").next_run_time)

        logger.info(f"⏰ Analysis schedule updated to: {cron_str} by {admin['email']}")
        return {
            "message": f"Analysis schedule updated to {cron_str}",
            "next_run": analysis_status["next_run"]
        }
    except Exception as e:
        logger.error(f"❌ Failed to update schedule: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid cron format: {str(e)}")

@app.get("/admin/analyze/status")
async def get_analysis_status(user: dict = Depends(get_current_user)):
    """Get the current status of the analysis scheduler and last result."""
    if scheduler.get_job("analysis_job"):
        analysis_status["next_run"] = str(scheduler.get_job("analysis_job").next_run_time)
        
    return {
        "status": analysis_status,
        "is_scheduler_running": scheduler.running
    }

# --- GENERAL ENDPOINTS ---

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "Empowered Care - Unified Multi-Agent System",
        "status": "running",
        "version": API_VERSION
    }

@app.get("/health")
async def health_check():
    """Health check endpoint with system status."""
    return {
        "status": "healthy",
        "timestamp": str(datetime.now()),
        "version": API_VERSION,
        "agents": {
            "super_agent": "active",
            "data_assistant": "active",
            "chat_supervisor": "active"
        }
    }

# --- AUTHENTICATION & USER MANAGEMENT ---

@app.post("/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticate a user and return a JWT token."""
    user = await auth_service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["email"]}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user["role"],
        "full_name": user.get("full_name")
    }

@app.post("/admin/invite")
async def invite_user(
    invite_data: UserInvite, 
    admin: dict = Depends(get_current_admin)
):
    """Admin endpoint to invite new employees via email."""
    try:
        return await auth_service.invite_user(invite_data, admin)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/admin/users")
async def get_users(admin: dict = Depends(get_current_admin)):
    """Return a list of all current users."""
    try:
        return await auth_service.get_all_users()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/admin/users/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(get_current_admin)):
    """Delete a user account."""
    try:
        return await auth_service.delete_user(user_id, admin)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auth/register")
async def register_user(accept_data: UserAcceptInvite):
    """Register a new user using the invitation token from email."""
    try:
        return await auth_service.register_user(accept_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auth/forgot-password")
async def forgot_password(request: PasswordResetRequest):
    """Request a password reset link to be sent via email."""
    try:
        return await auth_service.request_password_reset(request.email, request.frontend_url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auth/reset-password")
async def reset_password(confirm_data: PasswordResetConfirm):
    """Reset password using the reset token from email."""
    try:
        return await auth_service.reset_password(confirm_data.token, confirm_data.new_password)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auth/change-password")
async def change_password(
    password_data: ChangePassword,
    user: dict = Depends(get_current_user)
):
    """Change password for an authenticated user."""
    try:
        return await auth_service.change_password(
            user["id"], password_data.old_password, password_data.new_password
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Get information about the currently logged-in user."""
    return {
        "email": user["email"],
        "full_name": user.get("full_name"),
        "role": user["role"],
        "created_at": user["created_at"]
    }

# --- OUTBREAK DETECTION ENDPOINTS ---

@app.post("/outbreak/process", response_model=List[OutbreakProcessResponse])
async def process_outbreak_report(
    request: dict,
    user: dict = Depends(get_current_user)
):
    """Process one or more outbreak reports through the dynamic multi-agent pipeline."""
    text = request.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text field is required and cannot be empty")

    if len(text) > MAX_TEXT_LENGTH:
        raise HTTPException(status_code=400, detail=f"Text input too long (max {MAX_TEXT_LENGTH} characters)")

    start_time = datetime.now()
    logger.info(f"--- 🚨 Outbreak Report Processing (Dynamic Multi-Record) ---")
    
    try:
        # Get historical context for AI comparison
        history = data_assistant.get_historical_context()
        
        # SuperAgent now returns a LIST of results
        batch_results = await super_agent.process_outbreak_parallel(text, history)
        
        response_list = []
        for result in batch_results:
            session_id = str(uuid.uuid4())
            # Store in data assistant with full context
            data_assistant.add_report(
                result["extracted_data"],
                session_id=session_id,
                risk_analysis=result["risk_analysis"].model_dump(mode='json') if hasattr(result["risk_analysis"], "model_dump") else result["risk_analysis"],
                alert=result["alert"].model_dump(mode='json') if hasattr(result["alert"], "model_dump") else result["alert"],
                context_research=result["context_research"].model_dump(mode='json') if result.get("context_research") and hasattr(result["context_research"], "model_dump") else result.get("context_research"),
                raw_report=text,
                validation=result["validation"].model_dump(mode='json') if hasattr(result["validation"], "model_dump") else result["validation"],
                consensus=result["consensus"].model_dump(mode='json') if hasattr(result["consensus"], "model_dump") else result["consensus"],
                source_type="report",
                submitted_by=user["email"],
            )

            response_list.append(OutbreakProcessResponse(
                extracted_data=result["extracted_data"],
                validation=result["validation"],
                risk_analysis=result["risk_analysis"],
                consensus=result["consensus"],
                context_research=result["context_research"],
                alert=result["alert"],
                session_id=session_id,
                metadata={
                    "processed_at": str(datetime.now()),
                    "orchestrator": "SuperAgent",
                    "consensus_reached": result["consensus"].consensus_reached
                },
                message="🚨 Signal processed.",
                human_validation_required=result["consensus"].final_risk_level in ["HIGH", "MEDIUM"]
            ))

        processing_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"--- ✅ Outbreak Processing Complete: {len(response_list)} records ({processing_time:.2f}s) ---")

        return response_list
    except AIQuotaExhausted:
        raise
    except Exception as e:
        logger.error(f"❌ Processing error: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.post("/outbreak/upload", response_model=List[OutbreakProcessResponse])
async def upload_outbreak_file(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    """Upload and process an outbreak report file (PDF, CSV, or Image)."""
    start_time = datetime.now()
    
    logger.info(f"--- 📂 Processing Uploaded File: {file.filename} ---")
    
    content = await file.read()
    extracted_text = ""
    
    try:
        # Branch processing by file type
        filename = file.filename.lower()
        content_type = (file.content_type or "").lower()
        
        if content_type == "text/csv" or filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
            extracted_text = "Outbreak CSV Dump:\n" + df.to_string()
            
        elif content_type == "application/pdf" or filename.endswith(".pdf"):
            images = pdf_to_images(content)
            if not images:
                raise HTTPException(status_code=400, detail="Failed to extract images from PDF. Ensure the file is not corrupt.")
            
            all_text = []
            prompt = "Extract all text from this medical/epidemiological report page. Return ONLY the text."
            for img_np in images:
                _, img_encoded = cv2.imencode('.jpg', img_np)
                text = await asyncio.to_thread(gemini_service.generate_vision_text, img_encoded.tobytes(), prompt)
                all_text.append(text)
            extracted_text = "\n".join(all_text)
            
        elif content_type.startswith("image/") or filename.endswith((".jpg", ".jpeg", ".png")):
            prompt = "Extract all text from this medical note/report. Return ONLY the text."
            extracted_text = await asyncio.to_thread(gemini_service.generate_vision_text, content, prompt)
            
        else:
            extracted_text = content.decode("utf-8", errors="ignore")

        if not extracted_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract any text from the provided file.")

        # Get historical context
        history = data_assistant.get_historical_context()

        # Feed extracted text to SuperAgent
        batch_results = await super_agent.process_outbreak_parallel(extracted_text, history)
        
        response_list = []
        for result in batch_results:
            session_id = str(uuid.uuid4())
            # Store in data assistant with full context
            data_assistant.add_report(
                result["extracted_data"],
                session_id=session_id,
                risk_analysis=result["risk_analysis"].model_dump(mode='json') if hasattr(result["risk_analysis"], "model_dump") else result["risk_analysis"],
                alert=result["alert"].model_dump(mode='json') if hasattr(result["alert"], "model_dump") else result["alert"],
                context_research=result["context_research"].model_dump(mode='json') if result.get("context_research") and hasattr(result["context_research"], "model_dump") else result.get("context_research"),
                raw_report=extracted_text,
                validation=result["validation"].model_dump(mode='json') if hasattr(result["validation"], "model_dump") else result["validation"],
                consensus=result["consensus"].model_dump(mode='json') if hasattr(result["consensus"], "model_dump") else result["consensus"],
                source_type="upload",
                submitted_by=user["email"],
            )

            response_list.append(OutbreakProcessResponse(
                extracted_data=result["extracted_data"],
                validation=result["validation"],
                risk_analysis=result["risk_analysis"],
                consensus=result["consensus"],
                context_research=result["context_research"],
                alert=result["alert"],
                session_id=session_id,
                metadata={
                    "processed_at": str(datetime.now()),
                    "file_name": file.filename
                },
                message=f"🚨 Record extracted.",
                human_validation_required=result["consensus"].final_risk_level in ["HIGH", "MEDIUM"]
            ))

        processing_time = (datetime.now() - start_time).total_seconds()
        return response_list

    except (AIQuotaExhausted, HTTPException):
        raise
    except Exception as e:
        logger.error(f"❌ File processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"File processing failed: {str(e)}")

@app.post("/outbreak/approve/{session_id}")
async def approve_alert(
    session_id: str, 
    request: dict = None,
    user: dict = Depends(get_current_admin)
):
    """Human validation endpoint for alerts (Admin Only)."""
    approved = request.get("approved", True) if request else True
    status = "approved" if approved else "rejected"
    
    logger.info(f"Alert {status} for session {session_id}")
    
    # Update status in persistent store
    success = data_assistant.update_report_status(session_id, status, reviewer=user["email"])
    
    if not success:
        raise HTTPException(status_code=404, detail="Report session not found")

    return {
        "session_id": session_id,
        "approved": approved,
        "message": f"Alert {status} and updated in intelligence vault.",
        "timestamp": str(datetime.now())
    }

@app.post("/outbreak/query", response_model=QueryResponse)
async def query_outbreak_data(
    request: dict,
    user: dict = Depends(get_current_user)
):
    """Query the outbreak data using the Data Assistant Agent."""
    query = request.get("query", "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query field is required")

    logger.info(f"--- 🔍 Data Query: {query} ---")
    try:
        result = await data_assistant.query(query)
        return QueryResponse(**result)
    except AIQuotaExhausted:
        raise
    except Exception as e:
        logger.error(f"❌ Query error: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

@app.get("/outbreak/summary")
async def get_outbreak_summary(user: dict = Depends(get_current_user)):
    """Get a summary of all outbreak reports."""
    try:
        records = data_assistant.data_store
        total_reports = len(records)
        locations = list(set(r["extracted_data"].get("location") for r in records if r["extracted_data"].get("location") not in (None, "Unknown")))
        total_cases = sum(r["extracted_data"].get("cases") or 0 for r in records)

        return {
            "total_reports": total_reports,
            "total_cases": total_cases,
            "locations": locations,
            "timestamp": str(datetime.now()),
            "data_points": total_reports
        }
    except Exception as e:
        logger.error(f"❌ Summary error: {e}")
        raise HTTPException(status_code=500, detail=f"Summary failed: {str(e)}")

@app.get("/outbreak/reports")
async def get_all_reports(user: dict = Depends(get_current_user)):
    """Get all processed reports from the data store."""
    return data_assistant.data_store

# --- CHATBOT ENDPOINTS ---

@app.post("/outbreak/chat", response_model=ChatResponse)
async def chat_with_assistant(
    request: ChatRequest,
    user: dict = Depends(get_current_user)
):
    """Powerful multi-agent chatbot with memory and data awareness."""
    try:
        result = await chat_supervisor.chat(request.message, request.session_id)
        return ChatResponse(**result)
    except AIQuotaExhausted:
        raise
    except Exception as e:
        logger.error(f"❌ Chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

@app.delete("/outbreak/chat/{session_id}")
async def clear_chat_session(session_id: str, user: dict = Depends(get_current_user)):
    """Clear the conversation history for a specific session."""
    if chat_supervisor.clear_session(session_id):
        return {"message": f"Session {session_id} cleared successfully"}
    else:
        return {"message": f"Session {session_id} not found or already empty"}

# --- PATIENT RECORD ENDPOINTS ---

PATIENT_RECORDS_FILE = Path("data") / "patient_records.json"
PATIENT_RECORDS_FILE.parent.mkdir(exist_ok=True)


def _load_patient_records() -> List[dict]:
    if PATIENT_RECORDS_FILE.exists():
        try:
            with open(PATIENT_RECORDS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_patient_records(records: List[dict]):
    with open(PATIENT_RECORDS_FILE, "w") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


@app.post("/patient/record", response_model=PatientRecordResponse)
async def save_patient_record(
    record: PatientRecord,
    user: dict = Depends(get_current_user)
):
    """Save a manually entered patient record (form submission)."""
    records = _load_patient_records()
    record_id = str(uuid.uuid4())
    saved_at = datetime.now().isoformat()

    entry = {
        "id": record_id,
        "saved_at": saved_at,
        "saved_by": user["email"],
        **record.model_dump()
    }
    records.append(entry)
    _save_patient_records(records)

    logger.info(
        f"📋 Patient record saved: {record.patient_name} "
        f"(ID: {record_id}) by {user['email']}"
    )
    return PatientRecordResponse(
        id=record_id,
        message="✅ Patient record saved successfully.",
        patient_name=record.patient_name,
        mrn=record.mrn,
        saved_at=saved_at
    )


@app.get("/patient/records")
async def get_patient_records(user: dict = Depends(get_current_user)):
    """Return patient records.
    
    - admin: all records
    - data_entry: only records saved by this user
    """
    records = _load_patient_records()
    if user["role"] == "data_entry":
        records = [r for r in records if r.get("saved_by") == user["email"]]
    return {"total": len(records), "records": records}


@app.get("/patient/record/{record_id}")
async def get_patient_record(
    record_id: str,
    user: dict = Depends(get_current_user)
):
    """Return a single patient record by ID."""
    for r in _load_patient_records():
        if r["id"] == record_id:
            return r
    raise HTTPException(status_code=404, detail="Record not found")


if __name__ == "__main__":
    import uvicorn
    logger.info(f"🚀 Starting server on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
