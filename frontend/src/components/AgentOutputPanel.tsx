"use client";

import { useState } from "react";

interface AgentOutputPanelProps {
  title: string;
  output: Record<string, unknown> | null;
  defaultOpen?: boolean;
}

// Format field names to be human-readable
function formatFieldName(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/([A-Z])/g, " $1")
    .replace(/^./, (str) => str.toUpperCase())
    .trim();
}

// Format field values for display
function formatValue(value: unknown): string | JSX.Element {
  if (value === null || value === undefined) {
    return <span className="text-gray-400">-</span>;
  }
  if (typeof value === "boolean") {
    return value ? (
      <span className="text-green-600 font-medium">Yes</span>
    ) : (
      <span className="text-red-600 font-medium">No</span>
    );
  }
  if (typeof value === "number") {
    // Format percentages and scores
    if (value >= 0 && value <= 1) {
      return `${(value * 100).toFixed(0)}%`;
    }
    // Format processing time
    if (value < 100) {
      return value.toFixed(2);
    }
    return value.toLocaleString();
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="text-gray-400">None</span>;
    }
    return (
      <div className="flex flex-wrap gap-1">
        {value.map((item, i) => (
          <span
            key={i}
            className="inline-block px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded"
          >
            {String(item)}
          </span>
        ))}
      </div>
    );
  }
  if (typeof value === "string") {
    // Format timestamps
    if (value.match(/^\d{4}-\d{2}-\d{2}T/)) {
      return new Date(value).toLocaleString();
    }
    return value;
  }
  return JSON.stringify(value);
}

// Get badge color based on risk level
function getRiskBadge(level: string): JSX.Element {
  const colors: Record<string, string> = {
    LOW: "bg-green-100 text-green-800",
    MEDIUM: "bg-yellow-100 text-yellow-800",
    HIGH: "bg-red-100 text-red-800",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-sm font-medium ${colors[level] || "bg-gray-100"}`}>
      {level}
    </span>
  );
}

// Fields to hide from the table (shown elsewhere or not useful)
const HIDDEN_FIELDS = ["agent_name", "timestamp", "errors", "confidence", "processing_time_seconds"];

// Field display order and grouping
const FIELD_ORDER: Record<string, string[]> = {
  classifier: ["doc_type", "routing_tags"],
  kyc: ["kyc_passed", "document_type", "is_expired", "expiry_date", "tampering_flags", "validation_notes"],
  claims: ["claim_amount", "currency", "provider_name", "service_date", "diagnosis", "icd_10_codes", "cpt_codes", "schema_valid", "validation_errors"],
  policy: ["covered", "coverage_percentage", "exclusions", "matching_clauses"],
  fraud: ["fraud_score", "risk_level", "duplicate_claim_detected", "frequency_anomaly", "anomalies"],
};

export default function AgentOutputPanel({
  title,
  output,
  defaultOpen = false,
}: AgentOutputPanelProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  if (!output) {
    return null;
  }

  const confidence = output.confidence as number | undefined;
  const errors = output.errors as string[] | undefined;
  const processingTime = output.processing_time_seconds as number | undefined;
  const agentName = output.agent_name as string | undefined;

  // Determine field order based on agent type
  const agentType = agentName || title.toLowerCase().replace(" agent", "");
  const fieldOrder = FIELD_ORDER[agentType] || [];

  // Get fields to display, sorted by preferred order
  const displayFields = Object.entries(output)
    .filter(([key]) => !HIDDEN_FIELDS.includes(key))
    .sort((a, b) => {
      const aIndex = fieldOrder.indexOf(a[0]);
      const bIndex = fieldOrder.indexOf(b[0]);
      if (aIndex === -1 && bIndex === -1) return a[0].localeCompare(b[0]);
      if (aIndex === -1) return 1;
      if (bIndex === -1) return -1;
      return aIndex - bIndex;
    });

  return (
    <div className="border rounded-lg overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 bg-gray-50 flex items-center justify-between hover:bg-gray-100 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="font-medium text-gray-900">{title}</span>
          {confidence !== undefined && (
            <span
              className={`text-sm px-2 py-0.5 rounded ${
                confidence >= 0.8
                  ? "bg-green-100 text-green-800"
                  : confidence >= 0.6
                  ? "bg-yellow-100 text-yellow-800"
                  : "bg-red-100 text-red-800"
              }`}
            >
              {(confidence * 100).toFixed(0)}% confidence
            </span>
          )}
          {processingTime !== undefined && (
            <span className="text-sm text-gray-500">
              {processingTime.toFixed(2)}s
            </span>
          )}
          {errors && errors.length > 0 && (
            <span className="text-sm px-2 py-0.5 rounded bg-red-100 text-red-800">
              {errors.length} error(s)
            </span>
          )}
        </div>
        <svg
          className={`w-5 h-5 text-gray-500 transition-transform ${
            isOpen ? "rotate-180" : ""
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>
      {isOpen && (
        <div className="bg-white">
          <table className="w-full text-sm">
            <tbody className="divide-y divide-gray-100">
              {displayFields.map(([key, value]) => (
                <tr key={key} className="hover:bg-gray-50">
                  <td className="px-4 py-2 text-gray-500 font-medium w-1/3">
                    {formatFieldName(key)}
                  </td>
                  <td className="px-4 py-2 text-gray-900">
                    {key === "risk_level" ? (
                      getRiskBadge(value as string)
                    ) : key === "fraud_score" ? (
                      <span className={`font-medium ${
                        (value as number) >= 0.5 ? "text-red-600" :
                        (value as number) >= 0.3 ? "text-yellow-600" : "text-green-600"
                      }`}>
                        {((value as number) * 100).toFixed(0)}%
                      </span>
                    ) : key === "coverage_percentage" ? (
                      `${value}%`
                    ) : key === "claim_amount" ? (
                      <span className="font-medium">
                        {output.currency || "INR"} {(value as number).toLocaleString()}
                      </span>
                    ) : (
                      formatValue(value)
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {errors && errors.length > 0 && (
            <div className="px-4 py-3 bg-red-50 border-t border-red-100">
              <p className="text-sm font-medium text-red-800 mb-1">Errors:</p>
              <ul className="text-sm text-red-700 list-disc list-inside">
                {errors.map((error, i) => (
                  <li key={i}>{error}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
