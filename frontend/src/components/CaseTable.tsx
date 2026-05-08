"use client";

import Link from "next/link";
import { Case } from "@/lib/api";
import StatusBadge from "./StatusBadge";

interface CaseTableProps {
  cases: Case[];
}

export default function CaseTable({ cases }: CaseTableProps) {
  if (cases.length === 0) {
    return (
      <div className="text-center py-12 bg-white rounded-lg border">
        <p className="text-gray-500">No cases found</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto bg-white rounded-lg shadow">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Case ID
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Filename
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Type
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Status
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Decision
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Confidence
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Time
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Created
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {cases.map((c) => (
            <tr key={c.id} className="hover:bg-gray-50">
              <td className="px-6 py-4 whitespace-nowrap">
                <Link
                  href={`/cases/${c.id}`}
                  className="text-indigo-600 hover:text-indigo-900 font-medium"
                >
                  {c.id.slice(0, 8)}...
                </Link>
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                {c.filename.length > 20
                  ? c.filename.slice(0, 20) + "..."
                  : c.filename}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {c.doc_type || "-"}
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <StatusBadge status={c.status} />
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm">
                {c.decision ? (
                  <span
                    className={`font-medium ${
                      c.decision === "approve"
                        ? "text-green-600"
                        : c.decision === "reject"
                        ? "text-red-600"
                        : "text-yellow-600"
                    }`}
                  >
                    {c.decision.toUpperCase()}
                  </span>
                ) : (
                  "-"
                )}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {c.decision_confidence
                  ? `${(c.decision_confidence * 100).toFixed(0)}%`
                  : "-"}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {c.processing_time_seconds
                  ? `${c.processing_time_seconds.toFixed(1)}s`
                  : "-"}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {new Date(c.created_at).toLocaleDateString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
