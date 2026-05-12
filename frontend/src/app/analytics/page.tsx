"use client";

import { useEffect, useState } from "react";
import { CalibrationData, fetchCalibrationData } from "@/lib/api";

export default function AnalyticsPage() {
  const [data, setData] = useState<CalibrationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchCalibrationData()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-gray-500">Loading calibration data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-600">Error: {error}</p>
      </div>
    );
  }

  if (!data || data.total_cases === 0) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-yellow-800 mb-2">No Data Available</h2>
        <p className="text-yellow-700">
          Process some documents first to see calibration analytics.
        </p>
      </div>
    );
  }

  const maxCount = Math.max(...data.bins.map((b) => b.count), 1);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Confidence Calibration Analytics</h1>
        <p className="text-gray-600 mt-1">
          Analyzing how well model confidence scores correlate with actual accuracy
        </p>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard label="Total Cases" value={data.total_cases.toString()} />
        <StatCard
          label="Overall Accuracy"
          value={data.overall_accuracy !== null ? `${(data.overall_accuracy * 100).toFixed(1)}%` : "-"}
          color="green"
        />
        <StatCard
          label="Mean Confidence"
          value={data.mean_confidence !== null ? `${(data.mean_confidence * 100).toFixed(1)}%` : "-"}
          color="blue"
        />
        <StatCard
          label="ECE (Lower = Better)"
          value={data.ece !== null ? data.ece.toFixed(3) : "-"}
          color={data.ece !== null && data.ece < 0.1 ? "green" : data.ece !== null && data.ece < 0.2 ? "yellow" : "red"}
        />
      </div>

      {/* Calibration Interpretation */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold mb-4">Interpretation</h2>
        <div className="space-y-2 text-sm">
          {data.ece !== null && data.ece < 0.1 && (
            <p className="text-green-700">Model is well-calibrated (ECE &lt; 0.1)</p>
          )}
          {data.ece !== null && data.ece >= 0.1 && data.ece < 0.2 && (
            <p className="text-yellow-700">Model is reasonably calibrated (0.1 &le; ECE &lt; 0.2)</p>
          )}
          {data.ece !== null && data.ece >= 0.2 && (
            <p className="text-red-700">Model may be over/under-confident (ECE &ge; 0.2)</p>
          )}
          {data.mean_confidence !== null && data.overall_accuracy !== null && (
            <>
              {data.mean_confidence > data.overall_accuracy + 0.1 && (
                <p className="text-orange-700">Model tends to be OVERCONFIDENT</p>
              )}
              {data.mean_confidence < data.overall_accuracy - 0.1 && (
                <p className="text-blue-700">Model tends to be UNDERCONFIDENT</p>
              )}
              {Math.abs(data.mean_confidence - data.overall_accuracy) <= 0.1 && (
                <p className="text-green-700">Confidence roughly matches accuracy</p>
              )}
            </>
          )}
        </div>
      </div>

      {/* Calibration Chart */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold mb-4">Calibration Curve</h2>
        <p className="text-sm text-gray-600 mb-4">
          A well-calibrated model should have bars close to the diagonal line.
          (e.g., 80% confident predictions should be correct ~80% of the time)
        </p>
        <div className="relative h-80">
          <CalibrationChart bins={data.bins} />
        </div>
      </div>

      {/* Confidence Distribution */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold mb-4">Confidence Score Distribution</h2>
        <div className="space-y-2">
          {data.bins.map((bin, i) => (
            <div key={i} className="flex items-center gap-4">
              <span className="text-sm text-gray-600 w-24">
                {(bin.bin_start * 100).toFixed(0)}-{(bin.bin_end * 100).toFixed(0)}%
              </span>
              <div className="flex-1 bg-gray-100 rounded-full h-6 relative">
                <div
                  className="bg-indigo-500 rounded-full h-6 transition-all"
                  style={{ width: `${(bin.count / maxCount) * 100}%` }}
                />
                <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-gray-600">
                  {bin.count} cases
                </span>
              </div>
              <span className="text-sm text-gray-600 w-20 text-right">
                {bin.accuracy !== null ? `${(bin.accuracy * 100).toFixed(0)}% acc` : "-"}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  color = "gray",
}: {
  label: string;
  value: string;
  color?: "gray" | "green" | "blue" | "yellow" | "red";
}) {
  const colorClasses = {
    gray: "text-gray-900",
    green: "text-green-600",
    blue: "text-blue-600",
    yellow: "text-yellow-600",
    red: "text-red-600",
  };

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <p className="text-sm text-gray-500">{label}</p>
      <p className={`text-2xl font-bold ${colorClasses[color]}`}>{value}</p>
    </div>
  );
}

function CalibrationChart({ bins }: { bins: CalibrationData["bins"] }) {
  const chartSize = 300;
  const padding = 40;
  const innerSize = chartSize - padding * 2;

  return (
    <svg viewBox={`0 0 ${chartSize} ${chartSize}`} className="w-full h-full max-w-md mx-auto">
      {/* Grid lines */}
      {[0, 0.25, 0.5, 0.75, 1].map((v) => (
        <g key={v}>
          <line
            x1={padding}
            y1={padding + innerSize * (1 - v)}
            x2={padding + innerSize}
            y2={padding + innerSize * (1 - v)}
            stroke="#e5e7eb"
            strokeWidth={1}
          />
          <line
            x1={padding + innerSize * v}
            y1={padding}
            x2={padding + innerSize * v}
            y2={padding + innerSize}
            stroke="#e5e7eb"
            strokeWidth={1}
          />
          <text
            x={padding - 5}
            y={padding + innerSize * (1 - v)}
            textAnchor="end"
            dominantBaseline="middle"
            className="text-xs fill-gray-500"
          >
            {(v * 100).toFixed(0)}%
          </text>
          <text
            x={padding + innerSize * v}
            y={padding + innerSize + 15}
            textAnchor="middle"
            className="text-xs fill-gray-500"
          >
            {(v * 100).toFixed(0)}%
          </text>
        </g>
      ))}

      {/* Perfect calibration line */}
      <line
        x1={padding}
        y1={padding + innerSize}
        x2={padding + innerSize}
        y2={padding}
        stroke="#9ca3af"
        strokeWidth={2}
        strokeDasharray="5,5"
      />

      {/* Calibration points and line */}
      {bins
        .filter((b) => b.accuracy !== null && b.count > 0)
        .map((bin, i, arr) => {
          const x = padding + bin.mean_confidence * innerSize;
          const y = padding + innerSize * (1 - (bin.accuracy || 0));
          const nextBin = arr[i + 1];

          return (
            <g key={i}>
              {/* Line to next point */}
              {nextBin && nextBin.accuracy !== null && (
                <line
                  x1={x}
                  y1={y}
                  x2={padding + nextBin.mean_confidence * innerSize}
                  y2={padding + innerSize * (1 - (nextBin.accuracy || 0))}
                  stroke="#4f46e5"
                  strokeWidth={2}
                  opacity={0.5}
                />
              )}
              {/* Point */}
              <circle
                cx={x}
                cy={y}
                r={Math.max(4, Math.min(12, bin.count * 2))}
                fill="#4f46e5"
                opacity={0.7}
              />
            </g>
          );
        })}

      {/* Axis labels */}
      <text
        x={chartSize / 2}
        y={chartSize - 5}
        textAnchor="middle"
        className="text-xs fill-gray-600"
      >
        Mean Predicted Confidence
      </text>
      <text
        x={10}
        y={chartSize / 2}
        textAnchor="middle"
        transform={`rotate(-90, 10, ${chartSize / 2})`}
        className="text-xs fill-gray-600"
      >
        Actual Accuracy
      </text>
    </svg>
  );
}
