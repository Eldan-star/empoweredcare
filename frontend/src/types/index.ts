export interface OutbreakReportPayload {
  location: string;
  symptoms: string[];
  cases: number;
  date?: string | null;
  classification?: 'Suspected' | 'Probable' | 'Confirmed';
  additional_info: Record<string, any>;
}

export interface ValidationResult {
  valid: boolean;
  confidence: number;
  issues: string[];
}

export interface RiskAnalysis {
  risk_level: 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN';
  confidence: string;
  possible_disease: string;
  reason: string;
}

export interface ConsensusResult {
  final_risk_level: string;
  average_confidence: number;
  consensus_reached: boolean;
  agent_opinions: RiskAnalysis[];
  final_reasoning: string;
}

export interface AlertMessage {
  title: string;
  message: string;
  recommendations: string[];
  prevention_strategy?: string;
  why_urgent?: string;
}

export interface ContextData {
  location: string;
  security_status?: string;
  water_quality?: string;
  temperature?: string;
  conflict_zone: boolean;
  nearby_facilities: string[];
  recent_news: string[];
  last_updated: string;
}

export interface OutbreakProcessResponse {
  extracted_data: OutbreakReportPayload;
  validation: ValidationResult;
  risk_analysis: RiskAnalysis;
  consensus?: ConsensusResult;
  context_research?: ContextData;
  alert: AlertMessage;
  session_id: string;
  metadata: Record<string, any>;
  message: string;
  human_validation_required: boolean;
  status?: 'pending' | 'approved' | 'rejected';
  created_at?: string;
  raw_report?: string;
}

export interface OutbreakReport extends OutbreakProcessResponse {
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
  /** Last activity time; set by the backend when reports are merged. */
  timestamp?: string;
  raw_report: string;
}

export interface QueryResponse {
  query: string;
  response: string;
  data_summary: Record<string, any>;
}

export interface SummaryData {
  total_reports: number;
  total_cases?: number;
  locations: string[];
  timestamp: string;
  data_points?: number;
}

export interface HealthStatus {
  status: string;
  timestamp?: string;
  version?: string;
  agents?: Record<string, string>;
  detail?: string;
}

export type AgentStep = 'extractor' | 'validator' | 'risk_analyzer' | 'alert_generator';

export interface AgentPipelineState {
  currentStep: AgentStep | null;
  completedSteps: AgentStep[];
  isProcessing: boolean;
  result: OutbreakReport | null;
  pipelineResults: OutbreakReport[];
  error: string | null;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
}

export interface ChatResponse {
  response: string;
  session_id: string;
  agent_used: string;
  history_count: number;
}
