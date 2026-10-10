import json
import logging
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from models.schemas import OutbreakReport, ValidationResult, RiskAnalysis, AlertMessage, ConsensusResult, ContextData
from services.gemini_service import GeminiService, AIQuotaExhausted
from config import VALID_SYMPTOMS, ENABLE_WEB_RESEARCH
from services.signal_store import SignalStore

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExtractionAgent:
    def __init__(self, gemini_service: GeminiService):
        self.gemini = gemini_service

    async def extract(self, text: str) -> List[OutbreakReport]:
        """Extract multiple structured data records from raw outbreak report text."""
        if not text or not text.strip():
            logger.warning("Empty text provided to extraction agent")
            return [OutbreakReport(
                location="Unknown",
                symptoms=[],
                cases=0,
                additional_info={"error": "Empty input text"}
            )]

        prompt = f"""
        You are an Extraction Agent for disease outbreak detection.
        Convert the following messy text report into a list of structured JSON data.
        
        CRITICAL: The text often contains multiple reports for different locations or different diseases.
        Do NOT group them into one. Create a separate JSON object for EACH unique location and EACH unique disease outbreak mentioned.
        If 5 different cities are mentioned with 5 different issues, you MUST return a list of 5 objects.

        Input text: "{text.strip()}"

        Extract a list of:
        - location: The city, town, or region mentioned.
        - symptoms: List of clinical signs (e.g. fever, cough).
        - cases: Integer number of affected individuals.
        - date: The specific date mentioned for this event.
        - classification: Strictly classify as "Suspected", "Probable", or "Confirmed" based on wording like "suspected case", "likely case", or "lab confirmed". Default to "Suspected".
        - additional_info: Any other relevant clinical or environmental details.

        Return ONLY a JSON list of objects:
        [
          {{
            "location": "string",
            "symptoms": ["symptom1", "symptom2"],
            "cases": number,
            "date": "string or null",
            "classification": "Suspected | Probable | Confirmed",
            "additional_info": {{}}
          }}
        ]
        """

        try:
            logger.info(f"Extracting data from text: {text[:50]}...")
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self.gemini.generate_text, prompt)
            
            # Basic cleanup of response
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()

            raw_data = json.loads(response)
            
            # Ensure it's a list
            if isinstance(raw_data, dict):
                raw_data = [raw_data]
            
            reports = []
            for data in raw_data:
                # Validate required fields
                if not data.get("location"):
                    data["location"] = "Unknown"
                if not data.get("symptoms"):
                    data["symptoms"] = []
                if not isinstance(data.get("cases"), int):
                    try:
                        data["cases"] = int(data.get("cases", 1))
                    except:
                        data["cases"] = 1
                
                # Ensure additional_info is a dictionary
                if not isinstance(data.get("additional_info"), dict):
                    val = data.get("additional_info")
                    data["additional_info"] = {"raw_value": val} if val else {}

                reports.append(OutbreakReport(**data))
            
            logger.info(f"Successfully extracted {len(reports)} records")
            return reports

        except AIQuotaExhausted:
            raise  # surfaced to the user as 'AI quota reached', not stored as an analysis
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return [OutbreakReport(
                location="Unknown",
                symptoms=["Unknown"],
                cases=1,
                additional_info={"raw_text": text, "error": str(e)}
            )]

class ValidationAgent:
    def __init__(self, gemini_service: GeminiService):
        self.gemini = gemini_service

    async def validate(self, report: OutbreakReport) -> ValidationResult:
        """Validate outbreak report using LLM reasoning."""
        logger.info(f"Validating report for {report.location}")

        # Move all logic to LLM for non-hardcoded evaluation
        prompt = f"""
        You are an Epidemiological Validation Expert. 
        Analyze the plausibility of this outbreak report:

        Location: {report.location}
        Symptoms: {', '.join(report.symptoms)}
        Cases: {report.cases}
        Date: {report.date or 'Not specified'}
        Additional: {json.dumps(report.additional_info)}

        Instructions:
        - Check for statistical outliers or impossible case counts.
        - Evaluate clinical plausibility of symptoms for the location.
        - Detect missing critical data points.
        - Be critical but fair: unusual is not always invalid.

        Return valid JSON ONLY:
        {{
          "valid": true/false,
          "confidence": 0.0-1.0,
          "issues": ["list of reasons or improvement suggestions"]
        }}
        """

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self.gemini.generate_text, prompt)
            
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
                
            data = json.loads(response)
            return ValidationResult(
                valid=data.get("valid", True),
                confidence=data.get("confidence", 0.7),
                issues=data.get("issues", [])
            )
        except AIQuotaExhausted:
            raise  # surfaced to the user as 'AI quota reached', not stored as an analysis
        except Exception as e:
            logger.error(f"AI validation failed: {e}")
            return ValidationResult(valid=True, confidence=0.5, issues=["Validation engine failure, defaulting to valid"])

class RiskAnalysisAgent:
    def __init__(self, gemini_service: GeminiService):
        self.gemini = gemini_service

    @staticmethod
    def _context_blocks(context: ContextData = None, historical_context: str = "") -> tuple:
        context_info = ""
        if context:
            context_info = f"""
            Additional Context from Web Research:
            - Security Status: {context.security_status}
            - Water Quality: {context.water_quality}
            - Environmental (Temp): {context.temperature}
            - Conflict Zone: {"Yes" if context.conflict_zone else "No"}
            - Recent News: {', '.join(context.recent_news)}
            """
        history_info = ""
        if historical_context:
            history_info = f"\nHistorical Data Summary for Comparison:\n{historical_context}"
        return context_info, history_info

    @staticmethod
    def _to_risk(data: dict) -> RiskAnalysis:
        risk_level = str(data.get("risk_level", "UNKNOWN")).upper()
        if risk_level not in ["HIGH", "MEDIUM", "LOW"]:
            risk_level = "MEDIUM"
        return RiskAnalysis(
            risk_level=risk_level,
            confidence=str(data.get("confidence", "50%")),
            possible_disease=data.get("possible_disease", "Unknown"),
            reason=data.get("reason", "Analysis completed")
        )

    async def analyze_risk_perspectives(self, report: OutbreakReport, perspectives: List[str], context: ContextData = None, historical_context: str = "") -> List[RiskAnalysis]:
        """All perspectives in one model call (one request instead of one per perspective)."""
        logger.info(f"Analyzing risk for {report.location} from perspectives: {', '.join(perspectives)}")
        context_info, history_info = self._context_blocks(context, historical_context)

        prompt = f"""
        You are a panel of Risk Analysis Sub-Agents. Each member assesses this potential disease
        outbreak independently, from one perspective only.

        Location: {report.location}
        Symptoms: {', '.join(report.symptoms)}
        Cases: {report.cases}
        Date: {report.date or 'Not specified'}
        {context_info}
        {history_info}

        Perspectives:
        - 'symptoms': Focus on clinical patterns and disease matches.
        - 'statistical': Focus on case count growth and population density. Compare with historical baseline for THIS location if provided.
        - 'historical': Focus on seasonal trends and known regional hotspots. Analyze if this follows past patterns for THIS location.
        - 'environmental': Focus on how water, security, and conflict impact transmission.

        Risk levels: HIGH, MEDIUM, LOW

        Return a JSON list with exactly one object per perspective, in this order: {', '.join(perspectives)}
        [
          {{
            "perspective": "symptoms",
            "risk_level": "HIGH/MEDIUM/LOW",
            "confidence": "percentage",
            "possible_disease": "most likely disease",
            "reason": "brief explanation based on this perspective only"
          }}
        ]
        """

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self.gemini.generate_text, prompt)
            data = json.loads(response)
            if isinstance(data, dict):
                data = data.get("opinions") or data.get("perspectives") or [data]
            by_name = {str(d.get("perspective", "")).lower(): d for d in data if isinstance(d, dict)}
            opinions = []
            for i, p in enumerate(perspectives):
                d = by_name.get(p) or (data[i] if i < len(data) and isinstance(data[i], dict) else None)
                if d is None:
                    raise ValueError(f"no opinion returned for the '{p}' perspective")
                opinions.append(self._to_risk(d))
            return opinions

        except AIQuotaExhausted:
            raise  # surfaced to the user as 'AI quota reached', not stored as an analysis
        except Exception as e:
            logger.error(f"Risk analysis failed: {e}")
            return [RiskAnalysis(
                risk_level="UNKNOWN",
                confidence="0%",
                possible_disease="Unknown",
                reason=f"Analysis failed: {str(e)}"
            ) for _ in perspectives]

    async def analyze_risk(self, report: OutbreakReport, perspective: str = "general", context: ContextData = None, historical_context: str = "") -> RiskAnalysis:
        """Analyze outbreak risk level from a specific perspective."""
        logger.info(f"Analyzing risk for {report.location} from perspective: {perspective}")
        context_info, history_info = self._context_blocks(context, historical_context)

        prompt = f"""
        You are a Risk Analysis Sub-Agent specializing in {perspective}.
        Analyze the risk level for this potential disease outbreak:

        Location: {report.location}
        Symptoms: {', '.join(report.symptoms)}
        Cases: {report.cases}
        Date: {report.date or 'Not specified'}
        {context_info}
        {history_info}

        Perspective Specific Instructions:
        - If perspective is 'symptoms': Focus on clinical patterns and disease matches.
        - If perspective is 'statistical': Focus on case count growth and population density. Compare with historical baseline for THIS location if provided.
        - If perspective is 'historical': Focus on seasonal trends and known regional hotspots. Analyze if this follows past patterns for THIS location.
        - If perspective is 'environmental': Focus on how water, security, and conflict impact transmission.
        - Otherwise: Provide a general epidemiological risk assessment.

        Risk levels: HIGH, MEDIUM, LOW

        Return JSON:
        {{
          "risk_level": "HIGH/MEDIUM/LOW",
          "confidence": "percentage",
          "possible_disease": "most likely disease",
          "reason": "brief explanation based on your perspective"
        }}
        """

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self.gemini.generate_text, prompt)
            return self._to_risk(json.loads(response))

        except AIQuotaExhausted:
            raise  # surfaced to the user as 'AI quota reached', not stored as an analysis
        except Exception as e:
            logger.error(f"Risk analysis ({perspective}) failed: {e}")
            return RiskAnalysis(
                risk_level="UNKNOWN",
                confidence="0%",
                possible_disease="Unknown",
                reason=f"Analysis failed: {str(e)}"
            )

class AlertGenerationAgent:
    def __init__(self, gemini_service: GeminiService):
        self.gemini = gemini_service

    async def generate_alert(self, report: OutbreakReport, risk: Union[RiskAnalysis, ConsensusResult]) -> AlertMessage:
        """Generate human-readable alert message based on merged analysis."""
        
        # Determine the data to use
        if isinstance(risk, ConsensusResult):
            risk_level = risk.final_risk_level
            reasoning = risk.final_reasoning
            disease = risk.agent_opinions[0].possible_disease if risk.agent_opinions else "Potential Disease Outbreak"
        else:
            risk_level = risk.risk_level
            reasoning = risk.reason
            disease = risk.possible_disease

        logger.info(f"Generating alert for {risk_level} risk in {report.location}")

        prompt = f"""
        Generate a clear, actionable alert message for this outbreak:

        Location: {report.location}
        Symptoms: {', '.join(report.symptoms)}
        Cases: {report.cases}
        Risk Level: {risk_level}
        Possible Disease: {disease}
        Merged Analysis: {reasoning}

        Create a response in JSON format including:
        - title: Clear, urgent title
        - message: Detailed summary
        - recommendations: List of immediate actions
        - prevention_strategy: A simple, easy-to-understand solution on how to prevent further cases.
        - why_urgent: A very simple explanation of why this alert was generated (the risk factors).

        Keep the language simple for the general public.

        Return JSON:
        {{
          "title": "Alert title",
          "message": "Detailed summary",
          "recommendations": ["rec1", "rec2"],
          "prevention_strategy": "Simple prevention steps...",
          "why_urgent": "Why this matters now..."
        }}
        """

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self.gemini.generate_text, prompt)
            data = json.loads(response)

            return AlertMessage(
                title=data.get("title", f"Health Alert: {report.location}"),
                message=data.get("message", f"Potential outbreak in {report.location}"),
                recommendations=data.get("recommendations", ["Seek medical attention", "Follow local health guidelines"]),
                prevention_strategy=data.get("prevention_strategy", "Maintain good hygiene and follow local health advice."),
                why_urgent=data.get("why_urgent", f"Identified a cluster of {report.cases} cases in {report.location}.")
            )

        except AIQuotaExhausted:
            raise  # surfaced to the user as 'AI quota reached', not stored as an analysis
        except Exception as e:
            logger.error(f"Alert generation failed: {e}")
            return AlertMessage(
                title="Health Alert",
                message=f"Potential outbreak in {report.location}. Risk level: {risk_level}.",
                recommendations=["Seek medical attention", "Follow local health guidelines"]
            )

class SuperAgent:
    def __init__(self, gemini_service: GeminiService):
        self.gemini = gemini_service
        self.extractor = ExtractionAgent(gemini_service)
        self.validator = ValidationAgent(gemini_service)
        self.risk_agent = RiskAnalysisAgent(gemini_service)
        self.alert_agent = AlertGenerationAgent(gemini_service)
        self.research_agent = None
        if ENABLE_WEB_RESEARCH:
            # crawl4ai is heavy and only needed when web research is switched on.
            from services.research_agent import ContextResearchAgent
            self.research_agent = ContextResearchAgent(gemini_service)

    async def process_outbreak_parallel(self, text: str, historical_context: str = "") -> List[Dict[str, Any]]:
        """Dynamic hierarchical processing of outbreak reports (Supports multiple records)."""
        logger.info(f"🧠 SuperAgent: Initializing dynamic pipeline for: {text[:50]}...")
        
        # 1. Dynamic Extraction Scaling
        all_extracted_reports = await self.extractor.extract(text)
        
        results = []
        for report in all_extracted_reports:
            # 2. Dynamic Research Agent (per location)
            context_data = None
            if ENABLE_WEB_RESEARCH and report.location and report.location != "Unknown":
                logger.info(f"🧠 SuperAgent: Spawning Research Agent for {report.location}...")
                context_data = await self.research_agent.research(report.location)

            # 3. Dynamic Validation
            validation_result = await self.validator.validate(report)
            
            # 4. Dynamic Risk Sub-Agents (PERSPECTIVE-BASED)
            # Use research data AND historical context if available
            perspectives = ["symptoms", "statistical", "historical", "environmental"]
            logger.info(f"🧠 SuperAgent: Asking {len(perspectives)} risk perspectives in one call for {report.location}...")
            
            risk_opinions = await self.risk_agent.analyze_risk_perspectives(report, perspectives, context_data, historical_context)
            
            # 5. Merge Layer / Consensus
            consensus = self._reach_consensus(risk_opinions)
            
            # 6. Alert Generation
            alert = await self.alert_agent.generate_alert(report, consensus)
            
            results.append({
                "extracted_data": report,
                "validation": validation_result,
                "risk_analysis": risk_opinions[0],
                "consensus": consensus,
                "context_research": context_data,
                "alert": alert
            })
            
        return results

    def _reach_consensus(self, opinions: List[RiskAnalysis]) -> ConsensusResult:
        """Consensus logic: Voting + Confidence Averaging."""
        logger.info("🧠 SuperAgent: Reaching consensus among Risk Sub-Agents...")
        
        risk_values = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}
        risk_names = {v: k for k, v in risk_values.items()}
        
        total_risk_score = 0
        total_confidence = 0
        
        for op in opinions:
            total_risk_score += risk_values.get(op.risk_level, 0)
            # Parse confidence string (e.g. "75%")
            try:
                conf = float(op.confidence.strip('%'))
            except:
                conf = 50.0
            total_confidence += conf
            
        avg_risk_score = round(total_risk_score / len(opinions))
        final_risk = risk_names.get(avg_risk_score, "MEDIUM")
        avg_conf = total_confidence / len(opinions)
        
        final_reasoning = "Consensus reached from multiple perspectives: " + \
                        " | ".join([f"{op.risk_level}: {op.reason}" for op in opinions])
        
        return ConsensusResult(
            final_risk_level=final_risk,
            average_confidence=avg_conf,
            consensus_reached=True,
            agent_opinions=opinions,
            final_reasoning=final_reasoning
        )

class DataAssistantAgent:
    def __init__(self, gemini_service: GeminiService, store: Optional[SignalStore] = None):
        self.gemini = gemini_service
        if store is None:
            from db.session import SessionLocal
            from services.geocoder import Geocoder
            with SessionLocal() as session:
                geocoder = Geocoder.from_db(session)
            store = SignalStore(SessionLocal, geocoder if geocoder.units else None)
            logger.info(f"Geocoder: {len(geocoder.units)} administrative units loaded"
                        if geocoder.units else "Geocoder: no boundaries loaded yet (scripts/load_boundaries.py)")
        self.store = store
        logger.info(f"Data Assistant initialized with {self.store.count()} reports in the database")

    @property
    def data_store(self) -> List[Dict[str, Any]]:
        """All reports, newest first, in the dictionary shape the API returns."""
        return self.store.all_records()

    def add_report(self, report: Union[OutbreakReport, Dict[str, Any]], session_id: str = None, risk_analysis: Dict[str, Any] = None, alert: Dict[str, Any] = None, context_research: Dict[str, Any] = None, raw_report: str = "", validation: Dict[str, Any] = None, consensus: Dict[str, Any] = None, source_type: str = "report", submitted_by: str = None):
        """Store one analysed report. Reports for the same place and disease within 14 days
        share a cluster_id instead of being merged into one record."""
        record = self.store.add(
            report, session_id=session_id, raw_text=raw_report, source_type=source_type,
            validation=validation, risk_analysis=risk_analysis, consensus=consensus,
            context_research=context_research, alert=alert, submitted_by=submitted_by,
        )
        logger.info(f"Stored report {record['session_id']} for {record['extracted_data'].get('location')}")
        return record

    def update_report_status(self, session_id: str, status: str, reviewer: str = None):
        """Update the approval status of a report."""
        found = self.store.set_status(session_id, status, reviewer)
        if found:
            logger.info(f"Updated status for session {session_id} to {status}")
        return found

    async def query(self, query_text: str) -> Dict[str, Any]:
        """Answer queries about outbreak data."""
        logger.info(f"Processing query: {query_text}")

        records = self.data_store
        total_reports = len(records)
        locations = list(set(r["extracted_data"].get("location") for r in records if r["extracted_data"].get("location") not in (None, "Unknown")))
        total_cases = sum(r["extracted_data"].get("cases") or 0 for r in records)

        data_summary = {
            "total_reports": total_reports,
            "total_cases": total_cases,
            "locations": locations
        }

        prompt = f"""
        You are a Senior Data Analyst for Empowered Care, a high-performance multi-agent disease outbreak monitoring system. 
        Your goal is to provide intelligent, professional insights about epidemiological data.

        USER QUERY: "{query_text}"
        
        AGGREGATE DATA SUMMARY:
        {json.dumps(data_summary, indent=2)}
        
        DETAILED ENTRIES (Most Recent):
        {json.dumps([r["extracted_data"] for r in records[:10]], indent=2)}
        
        INSTRUCTIONS:
        1. IDENTITY: You are part of Empowered Care. 
        2. PROFESSIONAL ANALYSIS: Interpret the data in the context of public health safety.
        3. NATURAL LANGUAGE: Respond in a fluid, authoritative, and helpful manner.
        4. ACCURACY: Base your answer strictly on the provided data. 
        5. NO DATA SCENARIO: If there is zero data in the context above, acknowledge it professionally and explain that Empowered Care is currently in monitoring mode, awaiting data ingestion from field reports.
        """

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self.gemini.generate_text, prompt)
            return {
                "query": query_text,
                "response": response,
                "data_summary": data_summary
            }
        except AIQuotaExhausted:
            raise  # surfaced to the user as 'AI quota reached', not stored as an analysis
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return {
                "query": query_text,
                "response": "Unable to process query.",
                "data_summary": data_summary
            }

    def get_historical_context(self, location: str = None) -> str:
        """Get a summarized text of historical data for AI comparison."""
        relevant_data = self.store.all_records(limit=None if location else 20)
        if not relevant_data:
            return "No historical data available."

        # Filter by location if specified
        if location:
            relevant_data = [r for r in relevant_data if r["extracted_data"].get("location") == location]
        
        # Limit to last 20 relevant records to provide more depth
        summary_data = []
        for r in relevant_data[:20]:
            summary_data.append({
                "date": r["extracted_data"].get("date") or r.get("timestamp"),
                "cases": r["extracted_data"].get("cases"),
                "symptoms": r["extracted_data"].get("symptoms"),
                "risk": (r["risk_analysis"] or {}).get("risk_level"),
                "disease": (r["risk_analysis"] or {}).get("possible_disease")
            })
        
        return json.dumps(summary_data)

    async def perform_full_analysis(self) -> Dict[str, Any]:
        """Perform a deep analysis comparing new data with historical trends."""
        logger.info("Performing full system analysis and comparison...")
        
        records = self.store.all_records(limit=25)
        if not records:
            return {
                "status": "No data available",
                "analysis": "No data points collected yet for analysis.",
                "timestamp": str(datetime.now())
            }

        # Newest are at the beginning (index 0)
        new_data = [r["extracted_data"] for r in records[:5]]
        old_data = [r["extracted_data"] for r in records[5:25]] # Compare with next 20

        prompt = f"""
        You are a Senior Epidemiological Analyst. Perform a full system analysis.
        
        HISTORICAL DATA (Summarized):
        {json.dumps(old_data) if old_data else "No historical data."}
        
        NEW RECENT DATA (Last 5 reports):
        {json.dumps(new_data)}
        
        TASK:
        1. Compare the new data with historical trends.
        2. Identify if any new outbreaks are emerging or if existing ones are worsening.
        3. Provide a 'Result' summary including an overall risk level (LOW/MEDIUM/HIGH).
        4. Detect anomalies (e.g., sudden case spikes in new locations).
        
        Format your response as valid JSON:
        {{
          "overall_risk": "string",
          "comparison_summary": "string",
          "anomalies_detected": ["string"],
          "trend_analysis": "string",
          "recommendations": ["string"]
        }}
        """

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self.gemini.generate_text, prompt)
            analysis_result = json.loads(response)
            analysis_result["timestamp"] = str(datetime.now())
            analysis_result["data_points_analyzed"] = self.store.count()
            return analysis_result
        except AIQuotaExhausted:
            raise  # surfaced to the user as 'AI quota reached', not stored as an analysis
        except Exception as e:
            logger.error(f"Full analysis failed: {e}")
            return {
                "error": str(e),
                "status": "Analysis failed",
                "timestamp": str(datetime.now())
            }

# --- NEW POWERFUL CHATBOT SYSTEM ---

class ChatSpecialistAgent:
    def __init__(self, gemini_service: GeminiService, role: str, expertise: str):
        self.gemini = gemini_service
        self.role = role
        self.expertise = expertise

    async def respond(self, message: str, history: List[Dict[str, str]], data_context: str) -> str:
        history_str = "\n".join([f"{m['role']}: {m['content']}" for m in history])
        
        prompt = f"""
        You are the {self.role} for Empowered Care. 
        Your expertise is {self.expertise}.

        CONVERSATION GUIDELINES:
        1. CASUAL CHAT: If the user says "hi", "bye", "how are you", or other casual greetings, respond naturally and briefly as a human-like assistant. DO NOT explain your system architecture or list data unless specifically asked.
        2. DATA TASKS: If the user asks for reports, trends, or insights, extract the highest quality patterns from the provided DATA CONTEXT. Be precise.
        3. IDENTITY: You are Empowered Care Assistant.
        4. HISTORICAL AWARENESS: Consider past reports in the context to identify emerging trends or anomalies.

        DATA CONTEXT:
        {data_context}
        
        CONVERSATION HISTORY:
        {history_str}
        
        USER REQUEST:
        "{message}"
        """
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.gemini.generate_text, prompt)

class ChatSupervisor:
    def __init__(self, gemini_service: GeminiService, data_assistant: DataAssistantAgent):
        self.gemini = gemini_service
        self.data_assistant = data_assistant
        self.sessions: Dict[str, List[Dict[str, Any]]] = {}
        
        # Initialize specialists
        self.specialists = {
            "location": ChatSpecialistAgent(gemini_service, "Location Specialist", "Geographic trends, hotspots, and area-specific data."),
            "infection": ChatSpecialistAgent(gemini_service, "Infection Specialist", "Symptoms, disease types, risk levels, and clinical details."),
            "history": ChatSpecialistAgent(gemini_service, "History Specialist", "Timelines, dates, and historical comparison of reports."),
            "general": ChatSpecialistAgent(gemini_service, "General Assistant", "Overall summaries and general epidemiological support.")
        }

    def _get_history(self, session_id: str) -> List[Dict[str, Any]]:
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        return self.sessions[session_id]

    async def chat(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        sid = session_id or str(uuid.uuid4())
        history = self._get_history(sid)
        
        # 1. Route the query to the correct agent
        route_prompt = f"""
        You are the Routing Logic for Empowered Care, a sophisticated multi-agent system.
        Analyze the USER MESSAGE and route it to the best specialist agent.
        
        MESSAGE: "{message}"
        
        AVAILABLE SPECIALISTS:
        - "location": Geospatial surveillance and hotspots.
        - "infection": Symptoms, clinical details, and risk levels.
        - "history": Timelines, dates, and historical comparison.
        - "general": Greetings, overall system summaries, or broad requests.
        
        Return ONLY the single word (lower case): location, infection, history, or general.
        """
        
        loop = asyncio.get_event_loop()
        agent_key = await loop.run_in_executor(None, self.gemini.generate_text, route_prompt)
        agent_key = agent_key.lower().strip()
        if agent_key not in self.specialists:
            agent_key = "general"
            
        # 2. Prepare data context (Enhanced with a more complete summary)
        records = self.data_assistant.data_store
        total_reports = len(records)
        locations = list(set(r["extracted_data"].get("location") for r in records if r["extracted_data"].get("location") not in (None, "Unknown")))
        total_cases = sum(r["extracted_data"].get("cases") or 0 for r in records)
        
        data_summary = {
            "total_system_reports": total_reports,
            "aggregate_cases": total_cases,
            "monitored_locations": locations,
            "most_recent_entries": [r["extracted_data"] for r in records[:15]]
        }
        data_context = json.dumps(data_summary, indent=2)
        
        # 3. Get response from specialist
        agent = self.specialists[agent_key]
        logger.info(f"🤖 Chat: Routing to {agent_key} agent for session {sid}")
        
        response_text = await agent.respond(message, history, data_context)
        
        # 4. Update history
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": response_text})
        
        # Keep history manageable (last 10 turns)
        if len(history) > 20:
            self.sessions[sid] = history[-20:]
            
        return {
            "response": response_text,
            "session_id": sid,
            "agent_used": agent_key,
            "history_count": len(history) // 2
        }

    def clear_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False