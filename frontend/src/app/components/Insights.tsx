import React, { useMemo } from "react";
import { BrainCircuit, TrendingDown, TrendingUp, AlertTriangle, ShieldCheck, Zap, Activity } from "lucide-react";
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  Legend
} from "recharts";
import { cn } from "../utils";
import { useTheme } from "./ThemeProvider";
import { useFinData } from "../store/useFinData";

export function Insights() {
  const { theme, accentColors } = useTheme();
  const isDark = theme === "dark";
  const ac = accentColors;
  const { data: finData } = useFinData();
  const cardBg = isDark ? "bg-slate-900 border-slate-800" : "bg-white border-slate-200";
  const textPrimary = isDark ? "text-slate-200" : "text-slate-800";
  const textSecondary = isDark ? "text-slate-400" : "text-slate-500";
  const textMuted = isDark ? "text-slate-500" : "text-slate-400";

  const predictionData = useMemo(() => {
    if (!finData?.forecast || finData.forecast.length === 0) return [];
    return finData.forecast.slice(0, 6).map((pt) => ({
      month: new Date(pt.date).toLocaleDateString('en-US', { month: 'short' }),
      predicted: Math.round(pt.predicted_amount),
    }));
  }, [finData]);

  const projectedTotal = useMemo(() => {
    if (!finData?.forecast || finData.forecast.length === 0) return "$0";
    const total = finData.forecast.reduce((s, p) => s + p.predicted_amount, 0);
    return `${total >= 0 ? '+' : ''}$${Math.abs(Math.round(total)).toLocaleString()}`;
  }, [finData]);

  const recommendations = useMemo(() => {
    if (!finData?.recommendations || finData.recommendations.length === 0) return [];
    return finData.recommendations.map((rec, i) => ({
      title: rec.split('.')[0] || rec.slice(0, 40),
      desc: rec,
      action: "Review",
      priority: i === 0 ? "High" : "Medium",
    }));
  }, [finData]);

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className={cn("text-2xl font-bold flex items-center gap-2", isDark ? "text-slate-100" : "text-slate-900")}>
          <BrainCircuit className="h-6 w-6" style={{ color: ac[400] }} />
          Financial Intelligence
        </h1>
        <p className={cn("text-sm mt-1", textSecondary)}>Deep analysis powered by Machine Learning and AI.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* ML Prediction Card */}
        <div className={cn("border rounded-2xl p-6 shadow-xl col-span-1 md:col-span-2 relative overflow-hidden", cardBg)}>
          <div className="absolute top-0 right-0 w-64 h-64 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" style={{ backgroundColor: `rgba(${ac.rgb},0.05)` }}></div>
          
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-8 relative z-10">
            <div>
              <h2 className={cn("text-lg font-bold flex items-center gap-2", textPrimary)}>
                Savings Trajectory Predictor
                <span className="px-2 py-0.5 rounded text-[10px] font-bold" style={{ backgroundColor: `rgba(${ac.rgb},0.2)`, color: ac[400], border: `1px solid rgba(${ac.rgb},0.2)` }}>LSTM Network</span>
              </h2>
              <p className={cn("text-sm mt-1", textSecondary)}>Forecasting your savings rate for the next 3 months based on historical behavior.</p>
            </div>
            <div className={cn("mt-4 sm:mt-0 px-4 py-2 rounded-xl border flex items-center gap-3", isDark ? "bg-slate-800/80 border-slate-700" : "bg-slate-50 border-slate-200")}>
              <div className="text-right">
                <p className={cn("text-xs font-medium uppercase tracking-wider", textMuted)}>Projected Q2</p>
                <p className="text-lg font-bold text-emerald-400">{projectedTotal}</p>
              </div>
              <TrendingUp className="h-8 w-8 text-emerald-500/50" />
            </div>
          </div>

          <div className="h-[300px] w-full relative z-10">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={predictionData} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid key="grid" strokeDasharray="3 3" vertical={false} stroke={isDark ? "#334155" : "#e2e8f0"} opacity={0.4} />
                <XAxis key="xaxis" dataKey="month" stroke={isDark ? "#94a3b8" : "#64748b"} tick={{ fill: isDark ? '#94a3b8' : '#64748b', fontSize: 12 }} axisLine={false} tickLine={false} dy={10} />
                <YAxis key="yaxis" stroke={isDark ? "#94a3b8" : "#64748b"} tick={{ fill: isDark ? '#94a3b8' : '#64748b', fontSize: 12 }} axisLine={false} tickLine={false} tickFormatter={(val) => `$${val}`} />
                <Tooltip 
                  key="tooltip"
                  contentStyle={{ backgroundColor: isDark ? '#0f172a' : '#fff', borderColor: isDark ? '#334155' : '#e2e8f0', borderRadius: '0.75rem', color: isDark ? '#f8fafc' : '#0f172a', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                  itemStyle={{ color: isDark ? '#e2e8f0' : '#334155' }}
                />
                <Legend key="legend" iconType="circle" wrapperStyle={{ fontSize: '12px', color: isDark ? '#94a3b8' : '#64748b', paddingTop: '20px' }} />
                
                <Line 
                  key="line-predicted"
                  type="monotone" 
                  dataKey="predicted" 
                  name="AI Prediction" 
                  stroke="#8b5cf6" 
                  strokeWidth={2} 
                  strokeDasharray="5 5"
                  dot={{ r: 4, fill: '#8b5cf6', strokeWidth: 2, stroke: isDark ? '#0f172a' : '#fff' }}
                  activeDot={{ r: 6, fill: '#8b5cf6', strokeWidth: 0 }}
                />
                <Line 
                  key="line-savings"
                  type="monotone" 
                  dataKey="savings" 
                  name="Actual Savings" 
                  stroke="#10b981" 
                  strokeWidth={3}
                  dot={{ r: 5, fill: '#10b981', strokeWidth: 2, stroke: isDark ? '#0f172a' : '#fff' }}
                  activeDot={{ r: 7, fill: '#10b981', strokeWidth: 0 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Behavioral Analysis */}
        <div className={cn("border rounded-2xl p-6 shadow-xl", cardBg)}>
          <h2 className={cn("text-lg font-bold flex items-center gap-2 mb-6", textPrimary)}>
            <Activity className="h-5 w-5 text-sky-400" />
            Behavioral Patterns
          </h2>
          
          <div className="space-y-4">
            <div className={cn("p-4 rounded-xl border flex gap-4", isDark ? "bg-slate-800/40 border-slate-700/50" : "bg-slate-50 border-slate-200")}>
              <div className="w-10 h-10 rounded-full bg-rose-500/10 flex items-center justify-center shrink-0 border border-rose-500/20">
                <AlertTriangle className="h-5 w-5 text-rose-400" />
              </div>
              <div>
                <h3 className={cn("text-sm font-semibold", textPrimary)}>Impulsive Spending Detected</h3>
                <p className={cn("text-xs mt-1 leading-relaxed", textSecondary)}>
                  You have made 4 unplanned purchases above $50 in the "Electronics" category late at night. Our model flags this as an impulsive behavior pattern.
                </p>
                <button className="mt-3 text-xs font-medium text-rose-400 hover:text-rose-300 flex items-center gap-1 transition-colors">
                  Review instances <TrendingDown className="h-3 w-3" />
                </button>
              </div>
            </div>

            <div className={cn("p-4 rounded-xl border flex gap-4", isDark ? "bg-slate-800/40 border-slate-700/50" : "bg-slate-50 border-slate-200")}>
              <div className="w-10 h-10 rounded-full bg-emerald-500/10 flex items-center justify-center shrink-0 border border-emerald-500/20">
                <ShieldCheck className="h-5 w-5 text-emerald-400" />
              </div>
              <div>
                <h3 className={cn("text-sm font-semibold", textPrimary)}>Consistent Utility Payments</h3>
                <p className={cn("text-xs mt-1 leading-relaxed", textSecondary)}>
                  Your fixed expenses are highly consistent and well within the healthy 30% margin of your total income. Excellent stability.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* AI Actionable Recs */}
        <div className={cn("border rounded-2xl p-6 shadow-xl")} style={isDark ? { background: `linear-gradient(to bottom right, rgba(${ac.rgb},0.15), #0f172a)`, borderColor: `rgba(${ac.rgb},0.2)` } : { background: `linear-gradient(to bottom right, rgba(${ac.rgb},0.08), white)`, borderColor: `rgba(${ac.rgb},0.3)` }}>
          <h2 className={cn("text-lg font-bold flex items-center gap-2 mb-6", textPrimary)}>
            <Zap className="h-5 w-5 text-amber-400" />
            Actionable Recommendations
          </h2>

          <ul className="space-y-3">
            {recommendations.map((rec, i) => (
              <li key={i} className={cn(
                "flex flex-col sm:flex-row gap-3 sm:items-center justify-between p-3 rounded-lg border transition-colors",
                isDark ? "bg-slate-800/60 border-slate-700/50 hover:bg-slate-800" : "bg-white/80 border-slate-200 hover:bg-white"
              )}>
                <div>
                  <div className="flex items-center gap-2">
                    <span className={cn(
                      "w-2 h-2 rounded-full",
                      rec.priority === 'High' ? "bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.6)]" : "bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)]"
                    )}></span>
                    <h3 className={cn("text-sm font-semibold", textPrimary)}>{rec.title}</h3>
                  </div>
                  <p className={cn("text-xs mt-1 pl-4", textSecondary)}>{rec.desc}</p>
                </div>
                <button className="self-start sm:self-center shrink-0 px-3 py-1.5 rounded-md text-xs font-medium text-white transition-colors" style={{ backgroundColor: ac[600] }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = ac[500])}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = ac[600])}
                >
                  {rec.action}
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
