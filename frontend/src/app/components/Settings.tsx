import React, { useState } from "react";
import { User, Shield, Bell, CreditCard, Plug, LogOut, Sun, Moon, Check, Globe, Smartphone } from "lucide-react";
import { cn } from "../utils";
import { useTheme, accentPresets, type AccentName } from "./ThemeProvider";
import { toast } from "sonner";

const sections = [
  { id: "profile", name: "Profile", icon: User, desc: "Manage your personal information." },
  { id: "security", name: "Security & Fraud", icon: Shield, desc: "Configure ML fraud detection." },
  { id: "notifications", name: "Notifications", icon: Bell, desc: "Set up alert thresholds." },
  { id: "accounts", name: "Accounts", icon: CreditCard, desc: "Link bank accounts." },
  { id: "integrations", name: "AI Settings", icon: Plug, desc: "Manage model preferences." },
];

export function Settings() {
  const [activeTab, setActiveTab] = useState("profile");
  const { theme, toggleTheme, accent, setAccent, accentColors } = useTheme();
  const isDark = theme === "dark";
  const ac = accentColors;

  const cardBg = isDark ? "bg-slate-900 border-slate-800" : "bg-white border-slate-200";
  const textPrimary = isDark ? "text-slate-200" : "text-slate-800";
  const textSecondary = isDark ? "text-slate-400" : "text-slate-500";
  const inputBg = isDark ? "bg-slate-800 border-slate-700 text-slate-200" : "bg-slate-50 border-slate-200 text-slate-800";
  const sectionBorder = isDark ? "border-slate-800" : "border-slate-200";

  const Toggle = ({ defaultChecked = false }: { defaultChecked?: boolean }) => (
    <label className="relative inline-flex items-center cursor-pointer">
      <input type="checkbox" className="sr-only peer" defaultChecked={defaultChecked} />
      <div className={cn(
        "w-11 h-6 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all",
        isDark ? "bg-slate-700" : "bg-slate-300"
      )} style={{ ['--tw-peer-checked-bg' as any]: ac[500] }}><style>{`.peer:checked ~ div { background-color: ${ac[500]} !important; }`}</style></div>
    </label>
  );

  return (
    <div className="max-w-4xl mx-auto space-y-5 sm:space-y-6">
      <div>
        <h1 className={cn("text-2xl font-bold", isDark ? "text-slate-100" : "text-slate-900")}>Settings</h1>
        <p className={cn("text-sm mt-1", textSecondary)}>Configure your FinWise AI experience.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-5 sm:gap-6">
        {/* Navigation */}
        <div className="md:col-span-1 space-y-1">
          {sections.map((sec) => (
            <button
              key={sec.id}
              onClick={() => setActiveTab(sec.id)}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors text-left",
                activeTab !== sec.id && (isDark ? "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50" : "text-slate-500 hover:text-slate-800 hover:bg-slate-100")
              )}
              style={activeTab === sec.id ? { color: ac[400], backgroundColor: `rgba(${ac.rgb},0.1)`, border: `1px solid rgba(${ac.rgb},0.2)` } : undefined}
            >
              <sec.icon className="h-4 w-4 shrink-0" />
              {sec.name}
            </button>
          ))}
          <div className={cn("pt-4 mt-4 border-t", sectionBorder)}>
            <button className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 transition-colors">
              <LogOut className="h-4 w-4" />
              Log Out
            </button>
          </div>
        </div>

        {/* Content Area */}
        <div className={cn("md:col-span-3 border rounded-2xl shadow-xl overflow-hidden p-4 sm:p-6", cardBg)}>
          
          {/* Profile Tab */}
          {activeTab === "profile" && (
            <div className="space-y-6">
              <div className={cn("border-b pb-4", sectionBorder)}>
                <h2 className={cn("text-lg font-semibold", textPrimary)}>Profile & Appearance</h2>
                <p className={cn("text-sm mt-1", textSecondary)}>Update your personal info and display preferences.</p>
              </div>

              <div className="flex items-center gap-3 sm:gap-4 mb-6">
                <div className="h-16 w-16 rounded-full flex items-center justify-center text-white text-xl font-bold" style={{ background: `linear-gradient(135deg, ${ac[600]}, ${ac[400]})` }}>JS</div>
                <div>
                  <p className={cn("text-sm font-semibold", textPrimary)}>John Smith</p>
                  <p className={cn("text-xs", textSecondary)}>john.smith@email.com</p>
                  <button className="text-xs mt-1" style={{ color: ac[400] }}>Change Avatar</button>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className={cn("text-xs font-medium block mb-1.5", textSecondary)}>Full Name</label>
                  <input defaultValue="John Smith" className={cn("w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-current/50", inputBg)} />
                </div>
                <div>
                  <label className={cn("text-xs font-medium block mb-1.5", textSecondary)}>Email</label>
                  <input defaultValue="john.smith@email.com" className={cn("w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-current/50", inputBg)} />
                </div>
                <div>
                  <label className={cn("text-xs font-medium block mb-1.5", textSecondary)}>Currency</label>
                  <select className={cn("w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-current/50", inputBg)}>
                    <option>USD ($)</option>
                    <option>EUR</option>
                    <option>INR</option>
                    <option>GBP</option>
                  </select>
                </div>
                <div>
                  <label className={cn("text-xs font-medium block mb-1.5", textSecondary)}>Monthly Income</label>
                  <input defaultValue="$5,500" className={cn("w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-current/50", inputBg)} />
                </div>
              </div>

              {/* Theme Toggle */}
              <div className={cn("flex flex-col sm:flex-row sm:items-center justify-between gap-3 py-4 border-y", sectionBorder)}>
                <div className="flex items-center gap-3">
                  {isDark ? <Moon className="h-5 w-5" style={{ color: ac[400] }} /> : <Sun className="h-5 w-5 text-amber-500" />}
                  <div>
                    <h3 className={cn("text-sm font-medium", textPrimary)}>Appearance</h3>
                    <p className={cn("text-xs mt-0.5", textSecondary)}>Currently using {isDark ? "dark" : "light"} mode</p>
                  </div>
                </div>
                <button
                  onClick={toggleTheme}
                  className={cn(
                    "flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors",
                    isDark ? "bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700" : "bg-slate-100 border-slate-200 text-slate-600 hover:bg-slate-200"
                  )}
                >
                  {isDark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
                  Switch to {isDark ? "Light" : "Dark"}
                </button>
              </div>

              {/* Accent Color Theme */}
              <div className={cn("py-4 border-b", sectionBorder)}>
                <div className="mb-4">
                  <h3 className={cn("text-sm font-medium", textPrimary)}>Color Theme</h3>
                  <p className={cn("text-xs mt-0.5", textSecondary)}>Choose an accent color for the interface</p>
                </div>
                <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-7 gap-3">
                  {(Object.entries(accentPresets) as [AccentName, typeof accentPresets.indigo][]).map(([name, colors]) => (
                    <button
                      key={name}
                      onClick={() => { setAccent(name); toast.success(`Theme changed to ${colors.label}`); }}
                      className={cn(
                        "flex flex-col items-center gap-2 p-3 rounded-xl border-2 transition-all",
                        accent === name
                          ? "scale-105"
                          : (isDark ? "border-slate-800 hover:border-slate-700" : "border-slate-200 hover:border-slate-300")
                      )}
                      style={accent === name ? { borderColor: colors[500], backgroundColor: `rgba(${colors.rgb},0.08)` } : undefined}
                    >
                      <div className="relative">
                        <div
                          className="w-8 h-8 rounded-full shadow-sm"
                          style={{
                            background: name === "mono"
                              ? `linear-gradient(135deg, #71717a, #a1a1aa)`
                              : `linear-gradient(135deg, ${colors[600]}, ${colors[400]})`,
                          }}
                        />
                        {accent === name && (
                          <div className="absolute inset-0 flex items-center justify-center">
                            <Check className="h-4 w-4 text-white drop-shadow" />
                          </div>
                        )}
                      </div>
                      <span className={cn(
                        "text-[10px] font-medium",
                        accent === name ? "" : textSecondary
                      )} style={accent === name ? { color: colors[isDark ? 400 : 600] } : undefined}>
                        {colors.label}
                      </span>
                    </button>
                  ))}
                </div>
                {/* Preview */}
                <div className={cn("mt-4 p-3 rounded-lg border flex items-center gap-3", isDark ? "border-slate-800 bg-slate-800/30" : "border-slate-100 bg-slate-50")}>
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: ac[500] }} />
                  <span className={cn("text-xs", textSecondary)}>Preview:</span>
                  <span className="text-xs font-medium" style={{ color: ac[isDark ? 400 : 600] }}>Active accent color</span>
                  <button className="ml-auto px-2.5 py-1 rounded text-[10px] font-medium text-white" style={{ backgroundColor: ac[500] }}>Button</button>
                </div>
              </div>

              <div className={cn("pt-2 flex justify-end")}>
                <button
                  onClick={() => toast.success("Profile updated successfully!")}
                  className="px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors"
                  style={{ backgroundColor: ac[600] }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = ac[500])}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = ac[600])}
                >
                  Save Changes
                </button>
              </div>
            </div>
          )}

          {/* Security Tab */}
          {activeTab === "security" && (
            <div className="space-y-6">
              <div className={cn("border-b pb-4", sectionBorder)}>
                <h2 className={cn("text-lg font-semibold", textPrimary)}>Fraud Detection (Isolation Forest)</h2>
                <p className={cn("text-sm mt-1", textSecondary)}>Configure how sensitive the AI should be when flagging anomalous transactions.</p>
              </div>

              <div className="space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <h3 className={cn("text-sm font-medium", textPrimary)}>Sensitivity Level</h3>
                    <p className={cn("text-xs mt-1", textSecondary)}>Higher sensitivity may result in more false positives.</p>
                  </div>
                  <div className={cn("flex items-center gap-2 p-1 rounded-lg border", isDark ? "bg-slate-800 border-slate-700" : "bg-slate-100 border-slate-200")}>
                    {["Low", "Medium", "High"].map(level => (
                      <button key={level} className={cn(
                        "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                        level === "Medium" ? "shadow" : (isDark ? "text-slate-400 hover:text-white" : "text-slate-500 hover:text-slate-800")
                      )} style={level === "Medium" ? { backgroundColor: `rgba(${ac.rgb},0.2)`, color: ac[400] } : undefined}>{level}</button>
                    ))}
                  </div>
                </div>

                <div className={cn("flex flex-col sm:flex-row sm:items-center justify-between gap-3 py-4 border-y", sectionBorder)}>
                  <div>
                    <h3 className={cn("text-sm font-medium", textPrimary)}>Auto-block High Risk</h3>
                    <p className={cn("text-xs mt-1", textSecondary)}>Automatically block transactions with anomaly score {'>'} 0.95.</p>
                  </div>
                  <Toggle defaultChecked />
                </div>

                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <h3 className={cn("text-sm font-medium", textPrimary)}>Geographic Anomalies</h3>
                    <p className={cn("text-xs mt-1", textSecondary)}>Flag transactions far from your usual locations.</p>
                  </div>
                  <Toggle defaultChecked />
                </div>

                <div className={cn("flex flex-col sm:flex-row sm:items-center justify-between gap-3 py-4 border-t", sectionBorder)}>
                  <div>
                    <h3 className={cn("text-sm font-medium", textPrimary)}>Two-Factor Authentication</h3>
                    <p className={cn("text-xs mt-1", textSecondary)}>Add an extra layer of security to your account.</p>
                  </div>
                  <Toggle defaultChecked />
                </div>
              </div>

              <div className={cn("pt-2 border-t flex justify-end", sectionBorder)}>
                <button
                  onClick={() => toast.success("Security preferences saved!")}
                  className="px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors"
                  style={{ backgroundColor: ac[600] }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = ac[500])}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = ac[600])}
                >
                  Save Preferences
                </button>
              </div>
            </div>
          )}

          {/* Notifications Tab */}
          {activeTab === "notifications" && (
            <div className="space-y-6">
              <div className={cn("border-b pb-4", sectionBorder)}>
                <h2 className={cn("text-lg font-semibold", textPrimary)}>Alerts & Notifications</h2>
                <p className={cn("text-sm mt-1", textSecondary)}>Choose what you want to be notified about.</p>
              </div>

              <div className="space-y-5">
                {[
                  { title: "Anomaly Alerts", desc: "Get notified when Isolation Forest flags a transaction.", default: true },
                  { title: "Weekly Spending Summary", desc: "Receive a weekly AI-generated report of your finances.", default: true },
                  { title: "Savings Goal Updates", desc: "Track progress toward your financial goals.", default: true },
                  { title: "Budget Threshold Alerts", desc: "Alert when category spending exceeds your set limit.", default: false },
                  { title: "LSTM Prediction Alerts", desc: "Get notified about predicted overspending or low balances.", default: true },
                ].map((item, i) => (
                  <div key={i} className={cn("flex flex-col sm:flex-row sm:items-center justify-between gap-3", i > 0 && cn("pt-5 border-t", sectionBorder))}>
                    <div>
                      <h3 className={cn("text-sm font-medium", textPrimary)}>{item.title}</h3>
                      <p className={cn("text-xs mt-1", textSecondary)}>{item.desc}</p>
                    </div>
                    <Toggle defaultChecked={item.default} />
                  </div>
                ))}
              </div>

              <div className={cn("pt-6 border-t flex justify-end", sectionBorder)}>
                <button
                  onClick={() => toast.success("Notification preferences updated!")}
                  className="px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors"
                  style={{ backgroundColor: ac[600] }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = ac[500])}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = ac[600])}
                >
                  Update Preferences
                </button>
              </div>
            </div>
          )}

          {/* Accounts Tab */}
          {activeTab === "accounts" && (
            <div className="space-y-6">
              <div className={cn("border-b pb-4", sectionBorder)}>
                <h2 className={cn("text-lg font-semibold", textPrimary)}>Connected Accounts</h2>
                <p className={cn("text-sm mt-1", textSecondary)}>Link your bank accounts for real-time transaction monitoring.</p>
              </div>

              <div className="space-y-3">
                {[
                  { bank: "Chase Bank", type: "Checking", last4: "4829", connected: true },
                  { bank: "Wells Fargo", type: "Savings", last4: "7712", connected: true },
                ].map((acc, i) => (
                  <div key={i} className={cn("flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl border", isDark ? "bg-slate-800/40 border-slate-700/50" : "bg-slate-50 border-slate-200")}>
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: `rgba(${ac.rgb},0.1)`, color: ac[400], border: `1px solid rgba(${ac.rgb},0.2)` }}>
                        <CreditCard className="h-5 w-5" />
                      </div>
                      <div>
                        <p className={cn("text-sm font-medium", textPrimary)}>{acc.bank}</p>
                        <p className={cn("text-xs", textSecondary)}>{acc.type} ****{acc.last4}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="flex items-center gap-1 text-xs text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded-md border border-emerald-500/20">
                        <Check className="h-3 w-3" /> Connected
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              <button
                className={cn(
                  "w-full py-3 rounded-xl border-2 border-dashed text-sm font-medium transition-colors",
                  isDark ? "border-slate-700 text-slate-400" : "border-slate-300 text-slate-500"
                )}
                onMouseEnter={(e) => { e.currentTarget.style.borderColor = `rgba(${ac.rgb},0.5)`; e.currentTarget.style.color = ac[isDark ? 400 : 600]; }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = ''; e.currentTarget.style.color = ''; }}
              >
                + Link New Account
              </button>
            </div>
          )}

          {/* AI Settings Tab */}
          {activeTab === "integrations" && (
            <div className="space-y-6">
              <div className={cn("border-b pb-4", sectionBorder)}>
                <h2 className={cn("text-lg font-semibold", textPrimary)}>AI Model Preferences</h2>
                <p className={cn("text-sm mt-1", textSecondary)}>Configure your LLM and ML model settings.</p>
              </div>

              <div className="space-y-5">
                <div>
                  <label className={cn("text-xs font-medium block mb-1.5", textSecondary)}>LLM Provider</label>
                  <select className={cn("w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-current/50", inputBg)}>
                    <option>GPT-4o (Recommended)</option>
                    <option>Claude 3.5 Sonnet</option>
                    <option>Gemini Pro</option>
                  </select>
                </div>
                <div>
                  <label className={cn("text-xs font-medium block mb-1.5", textSecondary)}>API Key</label>
                  <input type="password" defaultValue="sk-••••••••••••••••" className={cn("w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-current/50 font-mono", inputBg)} />
                </div>

                <div className={cn("flex flex-col sm:flex-row sm:items-center justify-between gap-3 py-4 border-y", sectionBorder)}>
                  <div>
                    <h3 className={cn("text-sm font-medium", textPrimary)}>RAG Context Window</h3>
                    <p className={cn("text-xs mt-1", textSecondary)}>How many months of data to include in AI context.</p>
                  </div>
                  <div className={cn("flex items-center gap-2 p-1 rounded-lg border", isDark ? "bg-slate-800 border-slate-700" : "bg-slate-100 border-slate-200")}>
                    {["1M", "3M", "6M", "All"].map(range => (
                      <button key={range} className={cn(
                        "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                        range === "3M" ? "shadow" : (isDark ? "text-slate-400 hover:text-white" : "text-slate-500 hover:text-slate-800")
                      )} style={range === "3M" ? { backgroundColor: `rgba(${ac.rgb},0.2)`, color: ac[400] } : undefined}>{range}</button>
                    ))}
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <h3 className={cn("text-sm font-medium", textPrimary)}>LSTM Auto-Retrain</h3>
                    <p className={cn("text-xs mt-1", textSecondary)}>Automatically retrain the prediction model weekly.</p>
                  </div>
                  <Toggle defaultChecked />
                </div>
              </div>

              <div className={cn("pt-6 border-t flex justify-end", sectionBorder)}>
                <button
                  onClick={() => toast.success("AI model settings saved!")}
                  className="px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors"
                  style={{ backgroundColor: ac[600] }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = ac[500])}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = ac[600])}
                >
                  Save AI Settings
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}