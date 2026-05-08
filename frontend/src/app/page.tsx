"use client";

import { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import FileUpload from "@/components/FileUpload";
import CaseTable from "@/components/CaseTable";
import { fetchCases, fetchStats, Case, Stats } from "@/lib/api";

export default function Dashboard() {
  const [cases, setCases] = useState<Case[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");

  const loadData = async () => {
    try {
      setLoading(true);
      const [casesRes, statsRes] = await Promise.all([
        fetchCases({ status: statusFilter || undefined }),
        fetchStats(),
      ]);
      setCases(casesRes.cases);
      setStats(statsRes);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [statusFilter]);

  const handleUploadComplete = (newCase: Case) => {
    setCases((prev) => [newCase, ...prev]);
    loadData(); // Refresh stats
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">
            Document Intake Dashboard
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Upload and process insurance documents
          </p>
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
            <div className="bg-white p-4 rounded-lg shadow">
              <p className="text-sm text-gray-500">Total</p>
              <p className="text-2xl font-bold">{stats.total}</p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow">
              <p className="text-sm text-gray-500">Approved</p>
              <p className="text-2xl font-bold text-green-600">
                {stats.by_status.approved || 0}
              </p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow">
              <p className="text-sm text-gray-500">Rejected</p>
              <p className="text-2xl font-bold text-red-600">
                {stats.by_status.rejected || 0}
              </p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow">
              <p className="text-sm text-gray-500">Escalated</p>
              <p className="text-2xl font-bold text-yellow-600">
                {stats.by_status.escalated || 0}
              </p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow">
              <p className="text-sm text-gray-500">Processing</p>
              <p className="text-2xl font-bold text-blue-600">
                {stats.by_status.processing || 0}
              </p>
            </div>
          </div>
        )}

        {/* Upload */}
        <div className="bg-white p-6 rounded-lg shadow mb-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">
            Upload Document
          </h2>
          <FileUpload onUploadComplete={handleUploadComplete} />
        </div>

        {/* Filter */}
        <div className="mb-4 flex items-center gap-4">
          <label className="text-sm font-medium text-gray-700">
            Filter by status:
          </label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm"
          >
            <option value="">All</option>
            <option value="received">Received</option>
            <option value="processing">Processing</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="escalated">Escalated</option>
          </select>
          <button
            onClick={loadData}
            className="text-sm text-indigo-600 hover:text-indigo-800"
          >
            Refresh
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 p-4 bg-red-50 text-red-700 rounded-lg">
            {error}
          </div>
        )}

        {/* Cases Table */}
        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin h-8 w-8 border-4 border-indigo-600 border-t-transparent rounded-full mx-auto"></div>
            <p className="mt-2 text-gray-500">Loading cases...</p>
          </div>
        ) : (
          <CaseTable cases={cases} />
        )}
      </main>
    </div>
  );
}
