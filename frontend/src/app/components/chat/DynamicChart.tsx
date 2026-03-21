import React, { useMemo } from "react";
import {
  ResponsiveContainer,
  LineChart, Line,
  BarChart, Bar,
  AreaChart, Area,
  PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from "recharts";
import { useTheme } from "../ThemeProvider";
import { cn } from "../../utils";
import type { ChartConfig } from "../../store/useChatStore";

const COLORS = ["#6366f1", "#06b6d4", "#f59e0b", "#10b981", "#f43f5e", "#8b5cf6", "#ec4899", "#14b8a6"];

interface Props {
  config: ChartConfig;
}

export function DynamicChart({ config }: Props) {
  const { theme, accentColors: ac } = useTheme();
  const isDark = theme === "dark";

  const { chart_type, chart_data, axis_config, latex_formula, result } = config;
  const xKey = axis_config?.x || "x";
  const yKey = axis_config?.y || "y";
  const xLabel = axis_config?.x_label || xKey;
  const yLabel = axis_config?.y_label || yKey;

  const gridColor = isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.08)";
  const tickFill = isDark ? "#94a3b8" : "#64748b";

  const renderChart = () => {
    switch (chart_type) {
      case "pie":
        return (
          <PieChart>
            <Pie
              data={chart_data}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              outerRadius={80}
              label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
            >
              {chart_data.map((_: any, i: number) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                backgroundColor: isDark ? "#0f172a" : "#fff",
                borderColor: isDark ? "#334155" : "#e2e8f0",
                borderRadius: "0.5rem",
                fontSize: 12,
              }}
              formatter={(v: number) => [`$${v.toLocaleString()}`, "Amount"]}
            />
            <Legend />
          </PieChart>
        );

      case "bar":
        return (
          <BarChart data={chart_data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
            <XAxis dataKey={xKey} tick={{ fill: tickFill, fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: tickFill, fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v.toLocaleString()}`} />
            <Tooltip
              contentStyle={{ backgroundColor: isDark ? "#0f172a" : "#fff", borderColor: isDark ? "#334155" : "#e2e8f0", borderRadius: "0.5rem", fontSize: 12 }}
              formatter={(v: number) => [`$${v.toLocaleString()}`, yLabel]}
            />
            <Bar dataKey={yKey} fill={ac[500]} radius={[4, 4, 0, 0]} />
          </BarChart>
        );

      case "line":
        return (
          <LineChart data={chart_data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
            <XAxis dataKey={xKey} tick={{ fill: tickFill, fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: tickFill, fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v.toLocaleString()}`} />
            <Tooltip
              contentStyle={{ backgroundColor: isDark ? "#0f172a" : "#fff", borderColor: isDark ? "#334155" : "#e2e8f0", borderRadius: "0.5rem", fontSize: 12 }}
              formatter={(v: number) => [`$${v.toLocaleString()}`, yLabel]}
            />
            <Line type="monotone" dataKey={yKey} stroke={ac[500]} strokeWidth={2} dot={false} />
          </LineChart>
        );

      case "area":
      default:
        return (
          <AreaChart data={chart_data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <defs>
              <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={ac[500]} stopOpacity={0.3} />
                <stop offset="95%" stopColor={ac[500]} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
            <XAxis dataKey={xKey} tick={{ fill: tickFill, fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: tickFill, fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v.toLocaleString()}`} />
            <Tooltip
              contentStyle={{ backgroundColor: isDark ? "#0f172a" : "#fff", borderColor: isDark ? "#334155" : "#e2e8f0", borderRadius: "0.5rem", fontSize: 12 }}
              formatter={(v: number) => [`$${v.toLocaleString()}`, yLabel]}
            />
            <Area type="monotone" dataKey={yKey} stroke={ac[500]} strokeWidth={2} fill="url(#areaGrad)" />
            {/* Render contributions line if present */}
            {chart_data[0] && "contributions" in chart_data[0] && (
              <Area type="monotone" dataKey="contributions" stroke="#94a3b8" strokeWidth={1} strokeDasharray="4 4" fill="none" />
            )}
          </AreaChart>
        );
    }
  };

  return (
    <div className={cn(
      "rounded-xl border p-4 my-2",
      isDark ? "bg-slate-800/50 border-slate-700" : "bg-slate-50 border-slate-200"
    )}>
      {result !== undefined && (
        <div className="flex items-baseline gap-2 mb-2">
          <span className={cn("text-2xl font-bold", isDark ? "text-slate-100" : "text-slate-900")}>
            ${typeof result === "number" ? result.toLocaleString(undefined, { minimumFractionDigits: 2 }) : result}
          </span>
        </div>
      )}
      <div className="h-48 w-full">
        <ResponsiveContainer width="100%" height="100%">
          {renderChart()}
        </ResponsiveContainer>
      </div>
      {latex_formula && (
        <div className={cn(
          "mt-3 px-3 py-2 rounded-lg font-mono text-xs overflow-x-auto",
          isDark ? "bg-slate-900/60 text-slate-300" : "bg-white text-slate-600 border border-slate-200"
        )}>
          {latex_formula}
        </div>
      )}
    </div>
  );
}
