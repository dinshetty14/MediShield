"use client";

import { useState } from "react";

interface AgentOutputPanelProps {
  title: string;
  output: Record<string, unknown> | null;
  defaultOpen?: boolean;
}

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
        <div className="p-4 bg-white">
          <pre className="text-sm text-gray-700 overflow-x-auto whitespace-pre-wrap">
            {JSON.stringify(output, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
