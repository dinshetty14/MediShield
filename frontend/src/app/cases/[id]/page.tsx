"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import StatusBadge from "@/components/StatusBadge";
import AgentOutputPanel from "@/components/AgentOutputPanel";
import { fetchCase, getCaseImageUrl, CaseDetail } from "@/lib/api";

export default function CaseDetailPage() {
  const params = useParams();
  const caseId = params.id as string;

  const [caseData, setCaseData] = useState<CaseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadCase = async () => {
      try {
        setLoading(true);
        const data = await fetchCase(caseId);
        setCaseData(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load case");
      } finally {
        setLoading(false);
      }
    };

    loadCase();
  }, [caseId]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <div className="flex items-center justify-center h-96">
          <div className="animate-spin h-8 w-8 border-4 border-indigo-600 border-t-transparent rounded-full"></div>
        </div>
      </div>
    );
  }

  if (error || !caseData) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <div className="max-w-7xl mx-auto py-6 px-4">
          <div className="bg-red-50 text-red-700 p-4 rounded-lg">
            {error || "Case not found"}
          </div>
          <Link href="/" className="mt-4 inline-block text-indigo-600">
            &larr; Back to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-6">
          <Link
            href="/"
            className="text-indigo-600 hover:text-indigo-800 text-sm"
          >
            &larr; Back to Dashboard
          </Link>
          <div className="mt-2 flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                Case: {caseData.id.slice(0, 8)}...
              </h1>
              <p className="text-sm text-gray-500">{caseData.filename}</p>
            </div>
            <StatusBadge status={caseData.status} />
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Document Image */}
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="p-4 border-b bg-gray-50">
              <h2 className="font-medium text-gray-900">Document Image</h2>
            </div>
            <div className="p-4">
              <img
                src={getCaseImageUrl(caseData.id)}
                alt="Document"
                className="w-full h-auto rounded border"
                onError={(e) => {
                  (e.target as HTMLImageElement).src =
                    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='300'%3E%3Crect fill='%23f3f4f6' width='400' height='300'/%3E%3Ctext fill='%239ca3af' x='50%25' y='50%25' text-anchor='middle'%3EImage not available%3C/text%3E%3C/svg%3E";
                }}
              />
            </div>
          </div>

          {/* Decision Panel */}
          <div className="space-y-6">
            {/* Final Decision */}
            <div className="bg-white rounded-lg shadow">
              <div className="p-4 border-b bg-gray-50">
                <h2 className="font-medium text-gray-900">Final Decision</h2>
              </div>
              <div className="p-4">
                {caseData.decision ? (
                  <div>
                    <div className="flex items-center gap-4 mb-4">
                      <span
                        className={`text-2xl font-bold ${
                          caseData.decision === "approve"
                            ? "text-green-600"
                            : caseData.decision === "reject"
                            ? "text-red-600"
                            : "text-yellow-600"
                        }`}
                      >
                        {caseData.decision.toUpperCase()}
                      </span>
                      {caseData.decision_confidence && (
                        <span className="text-sm text-gray-500">
                          {(caseData.decision_confidence * 100).toFixed(0)}%
                          confidence
                        </span>
                      )}
                    </div>
                    {caseData.decision_justification && (
                      <p className="text-sm text-gray-700 bg-gray-50 p-3 rounded">
                        {caseData.decision_justification}
                      </p>
                    )}
                    {caseData.overridden && (
                      <div className="mt-4 p-3 bg-yellow-50 rounded border border-yellow-200">
                        <p className="text-sm font-medium text-yellow-800">
                          Overridden to: {caseData.override_decision?.toUpperCase()}
                        </p>
                        <p className="text-sm text-yellow-700">
                          By: {caseData.override_by}
                        </p>
                        <p className="text-sm text-yellow-700">
                          Reason: {caseData.override_reason}
                        </p>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-gray-500">No decision yet</p>
                )}
              </div>
            </div>

            {/* Case Info */}
            <div className="bg-white rounded-lg shadow">
              <div className="p-4 border-b bg-gray-50">
                <h2 className="font-medium text-gray-900">Case Information</h2>
              </div>
              <div className="p-4 grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-gray-500">Document Type</p>
                  <p className="font-medium">{caseData.doc_type || "-"}</p>
                </div>
                <div>
                  <p className="text-gray-500">Queue</p>
                  <p className="font-medium">{caseData.queue || "-"}</p>
                </div>
                <div>
                  <p className="text-gray-500">Processing Time</p>
                  <p className="font-medium">
                    {caseData.processing_time_seconds
                      ? `${caseData.processing_time_seconds.toFixed(2)}s`
                      : "-"}
                  </p>
                </div>
                <div>
                  <p className="text-gray-500">Created</p>
                  <p className="font-medium">
                    {new Date(caseData.created_at).toLocaleString()}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Agent Outputs */}
        <div className="mt-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">
            Agent Outputs
          </h2>
          <div className="space-y-3">
            <AgentOutputPanel
              title="Classifier Agent"
              output={caseData.classifier_output}
              defaultOpen
            />
            <AgentOutputPanel title="KYC Agent" output={caseData.kyc_output} />
            <AgentOutputPanel
              title="Claims Agent"
              output={caseData.claims_output}
            />
            <AgentOutputPanel
              title="Policy Agent"
              output={caseData.policy_output}
            />
            <AgentOutputPanel
              title="Fraud Detection Agent"
              output={caseData.fraud_output}
            />
          </div>
        </div>
      </main>
    </div>
  );
}
