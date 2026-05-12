// API client for MediShield backend

const API_BASE = "/api";

export interface Case {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: string;
  doc_type: string | null;
  queue: string | null;
  decision: string | null;
  decision_confidence: number | null;
  decision_justification: string | null;
  processing_time_seconds: number | null;
  created_at: string;
  updated_at: string;
  overridden: boolean;
  override_by: string | null;
  override_reason: string | null;
  override_decision: string | null;
}

export interface CaseDetail extends Case {
  classifier_output: Record<string, unknown> | null;
  kyc_output: Record<string, unknown> | null;
  claims_output: Record<string, unknown> | null;
  policy_output: Record<string, unknown> | null;
  fraud_output: Record<string, unknown> | null;
}

export interface CaseListResponse {
  cases: Case[];
  total: number;
  limit: number;
  offset: number;
}

export interface Stats {
  total: number;
  by_status: Record<string, number>;
}

export async function fetchCases(params?: {
  status?: string;
  doc_type?: string;
  limit?: number;
  offset?: number;
}): Promise<CaseListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set("status", params.status);
  if (params?.doc_type) searchParams.set("doc_type", params.doc_type);
  if (params?.limit) searchParams.set("limit", params.limit.toString());
  if (params?.offset) searchParams.set("offset", params.offset.toString());

  const url = `${API_BASE}/cases${searchParams.toString() ? `?${searchParams}` : ""}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch cases");
  return res.json();
}

export async function fetchCase(id: string): Promise<CaseDetail> {
  const res = await fetch(`${API_BASE}/cases/${id}`);
  if (!res.ok) throw new Error("Failed to fetch case");
  return res.json();
}

export async function fetchEscalatedCases(): Promise<Case[]> {
  const res = await fetch(`${API_BASE}/cases/escalated`);
  if (!res.ok) throw new Error("Failed to fetch escalated cases");
  return res.json();
}

export async function fetchStats(): Promise<Stats> {
  const res = await fetch(`${API_BASE}/cases/stats`);
  if (!res.ok) throw new Error("Failed to fetch stats");
  return res.json();
}

export async function uploadDocument(file: File): Promise<Case> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/cases`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) throw new Error("Failed to upload document");
  return res.json();
}

export async function overrideDecision(
  caseId: string,
  decision: "approve" | "reject",
  overrideBy: string,
  reason: string
): Promise<Case> {
  const res = await fetch(`${API_BASE}/cases/${caseId}/override`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      decision,
      override_by: overrideBy,
      reason,
    }),
  });

  if (!res.ok) throw new Error("Failed to override decision");
  return res.json();
}

export function getCaseImageUrl(caseId: string): string {
  return `${API_BASE}/cases/${caseId}/image`;
}

export function getCaseReportUrl(caseId: string): string {
  return `${API_BASE}/cases/${caseId}/report`;
}

export interface CalibrationBin {
  bin_start: number;
  bin_end: number;
  count: number;
  accuracy: number | null;
  mean_confidence: number;
}

export interface CalibrationData {
  predictions: Array<{
    case_id: string;
    confidence: number;
    correct: boolean;
    decision: string;
  }>;
  bins: CalibrationBin[];
  ece: number | null;
  overall_accuracy: number | null;
  mean_confidence: number | null;
  total_cases: number;
}

export async function fetchCalibrationData(): Promise<CalibrationData> {
  const res = await fetch(`${API_BASE}/analytics/calibration`);
  if (!res.ok) throw new Error("Failed to fetch calibration data");
  return res.json();
}
