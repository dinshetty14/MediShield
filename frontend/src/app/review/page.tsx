"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import StatusBadge from "@/components/StatusBadge";
import { fetchEscalatedCases, overrideDecision, getCaseImageUrl, Case } from "@/lib/api";

export default function ReviewQueuePage() {
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCase, setSelectedCase] = useState<Case | null>(null);
  const [overrideForm, setOverrideForm] = useState({
    decision: "approve" as "approve" | "reject",
    overrideBy: "",
    reason: "",
  });
  const [submitting, setSubmitting] = useState(false);

  const loadCases = async () => {
    try {
      setLoading(true);
      const data = await fetchEscalatedCases();
      setCases(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load cases");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCases();
  }, []);

  const handleOverride = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCase) return;

    setSubmitting(true);
    try {
      await overrideDecision(
        selectedCase.id,
        overrideForm.decision,
        overrideForm.overrideBy,
        overrideForm.reason
      );
      setSelectedCase(null);
      setOverrideForm({ decision: "approve", overrideBy: "", reason: "" });
      loadCases();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to override");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">
            Human Review Queue
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Review and override escalated cases
          </p>
        </div>

        {error && (
          <div className="mb-4 p-4 bg-red-50 text-red-700 rounded-lg">
            {error}
          </div>
        )}

        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin h-8 w-8 border-4 border-indigo-600 border-t-transparent rounded-full mx-auto"></div>
            <p className="mt-2 text-gray-500">Loading cases...</p>
          </div>
        ) : cases.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-lg border">
            <svg
              className="mx-auto h-12 w-12 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <p className="mt-2 text-gray-500">No cases pending review</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Case List */}
            <div className="space-y-4">
              <h2 className="font-medium text-gray-900">
                Pending Review ({cases.length})
              </h2>
              {cases.map((c) => (
                <div
                  key={c.id}
                  onClick={() => setSelectedCase(c)}
                  className={`bg-white rounded-lg shadow p-4 cursor-pointer border-2 transition-colors ${
                    selectedCase?.id === c.id
                      ? "border-indigo-500"
                      : "border-transparent hover:border-gray-200"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <Link
                      href={`/cases/${c.id}`}
                      className="text-indigo-600 hover:text-indigo-800 font-medium"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {c.id.slice(0, 8)}...
                    </Link>
                    <StatusBadge status={c.status} />
                  </div>
                  <p className="text-sm text-gray-900">{c.filename}</p>
                  <p className="text-sm text-gray-500 mt-1">
                    Type: {c.doc_type || "Unknown"}
                  </p>
                  {c.decision_justification && (
                    <p className="text-sm text-gray-600 mt-2 bg-yellow-50 p-2 rounded">
                      {c.decision_justification}
                    </p>
                  )}
                </div>
              ))}
            </div>

            {/* Override Form */}
            {selectedCase && (
              <div className="bg-white rounded-lg shadow">
                <div className="p-4 border-b bg-gray-50">
                  <h2 className="font-medium text-gray-900">Override Decision</h2>
                  <p className="text-sm text-gray-500">
                    Case: {selectedCase.id.slice(0, 8)}...
                  </p>
                </div>

                {/* Preview Image */}
                <div className="p-4 border-b">
                  <img
                    src={getCaseImageUrl(selectedCase.id)}
                    alt="Document"
                    className="w-full h-48 object-contain rounded border bg-gray-50"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = "none";
                    }}
                  />
                </div>

                <form onSubmit={handleOverride} className="p-4 space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">
                      New Decision
                    </label>
                    <select
                      value={overrideForm.decision}
                      onChange={(e) =>
                        setOverrideForm((f) => ({
                          ...f,
                          decision: e.target.value as "approve" | "reject",
                        }))
                      }
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                    >
                      <option value="approve">Approve</option>
                      <option value="reject">Reject</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">
                      Reviewer Name
                    </label>
                    <input
                      type="text"
                      required
                      value={overrideForm.overrideBy}
                      onChange={(e) =>
                        setOverrideForm((f) => ({
                          ...f,
                          overrideBy: e.target.value,
                        }))
                      }
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                      placeholder="Your name"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">
                      Reason (min 10 characters)
                    </label>
                    <textarea
                      required
                      minLength={10}
                      rows={3}
                      value={overrideForm.reason}
                      onChange={(e) =>
                        setOverrideForm((f) => ({
                          ...f,
                          reason: e.target.value,
                        }))
                      }
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                      placeholder="Explain your decision..."
                    />
                  </div>

                  <div className="flex gap-3">
                    <button
                      type="submit"
                      disabled={submitting}
                      className="flex-1 bg-indigo-600 text-white py-2 px-4 rounded-md hover:bg-indigo-700 disabled:opacity-50"
                    >
                      {submitting ? "Submitting..." : "Submit Override"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setSelectedCase(null)}
                      className="px-4 py-2 border rounded-md text-gray-700 hover:bg-gray-50"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
