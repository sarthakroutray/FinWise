import React, { useState, useRef, useEffect } from "react";
import { Link, Outlet, useLocation } from "react-router";
import {
  LayoutDashboard,
  Wallet,
  ShieldAlert,
  Sparkles,
  Settings,
  Menu,
  Bell,
  Search,
  MessageSquare,
  Sun,
  Moon,
  X,
  Check,
  AlertTriangle,
  TrendingUp,
  ChevronRight,
  Wifi,
  WifiOff
} from "lucide-react";
import { cn } from "../utils";
import { motion, AnimatePresence } from "motion/react";
import { useTheme } from "./ThemeProvider";
import { Toaster } from "sonner";
import { healthCheck } from "../services/api";

const navItems = [
  { name: "Overview", icon: LayoutDashboard, path: "/" },
  { name: "Transactions", icon: Wallet, path: "/transactions" },
  { name: "Insights & Risk", icon: ShieldAlert, path: "/insights" },
  { name: "AI Advisor", icon: Sparkles, path: "/assistant", special: true },
];

const notifications = [
  { id: 1, title: "Anomaly Detected", desc: "Unusual $142.50 charge at Starbucks flagged by Isolation Forest.", time: "2 min ago", type: "alert", read: false },
  { id: 2, title: "Savings Goal Update", desc: "You're 68% toward your vacation goal. Keep it up!", time: "1 hr ago", type: "success", read: false },
  { id: 3, title: "Weekly Report Ready", desc: "Your AI-generated weekly spending summary is available.", time: "3 hrs ago", type: "info", read: true },
  { id: 4, title: "Duplicate Charge", desc: "Netflix charged $45.00 twice. Review recommended.", time: "1 day ago", type: "alert", read: true },
];

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [searchFocused, setSearchFocused] = useState(false);
  const location = useLocation();
  const { theme, toggleTheme, accentColors } = useTheme();
  const notifRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  const isDark = theme === "dark";
  const unreadCount = notifications.filter(n => !n.read).length;
  const ac = accentColors;
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);

  // Check backend health on mount
  useEffect(() => {
    healthCheck()
      .then(() => setBackendOnline(true))
      .catch(() => setBackendOnline(false));
  }, []);

  // Close notification dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setNotifOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // "/" to focus search
      if (e.key === "/" && !searchFocused && document.activeElement?.tagName !== "INPUT" && document.activeElement?.tagName !== "TEXTAREA") {
        e.preventDefault();
        searchRef.current?.focus();
      }
      // Escape to close panels
      if (e.key === "Escape") {
        setNotifOpen(false);
        setSidebarOpen(false);
        searchRef.current?.blur();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [searchFocused]);

  // Close sidebar on route change
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  return (
    <div className={cn(
      "flex h-screen w-full overflow-hidden font-sans transition-colors duration-200",
      isDark ? "bg-slate-950 text-slate-50" : "bg-slate-50 text-slate-900"
    )}>
      {/* Mobile Sidebar Overlay */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black/60 md:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-64 transform border-r transition-all duration-300 md:relative md:translate-x-0 flex flex-col",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
          isDark ? "bg-slate-900 border-slate-800" : "bg-white border-slate-200"
        )}
      >
        <div className={cn("flex items-center h-16 px-6 border-b shrink-0", isDark ? "border-slate-800" : "border-slate-200")}>
          <div className="flex items-center gap-2 font-semibold text-lg tracking-wide" style={{ color: ac[500] }}>
            <Sparkles className="h-6 w-6" />
            FinWise<span className={isDark ? "text-white" : "text-slate-900"}>AI</span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto py-6 px-4 space-y-1">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all relative",
                  !isActive && !item.special && (isDark ? "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50" : "text-slate-500 hover:text-slate-800 hover:bg-slate-100"),
                  !isActive && item.special && (isDark ? "hover:text-slate-300" : "hover:bg-slate-50"),
                )}
                style={
                  isActive && !item.special ? { color: ac[400], backgroundColor: `rgba(${ac.rgb},0.1)` } :
                  isActive && item.special ? { color: ac[400], background: `linear-gradient(to right, rgba(${ac.rgb},0.15), rgba(139,92,246,0.15))`, border: `1px solid rgba(${ac.rgb},0.2)` } :
                  item.special ? { color: `${ac[400]}cc` } : undefined
                }
              >
                {isActive && (
                  <motion.div
                    layoutId="sidebar-indicator"
                    className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 rounded-r-full"
                    style={{ backgroundColor: ac[isDark ? 400 : 600] }}
                    transition={{ type: "spring", stiffness: 300, damping: 30 }}
                  />
                )}
                <item.icon className="h-5 w-5" />
                {item.name}
              </Link>
            );
          })}
        </div>

        <div className={cn("p-4 border-t shrink-0", isDark ? "border-slate-800" : "border-slate-200")}>
          <Link
            to="/settings"
            className={cn(
              "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
              location.pathname !== "/settings" && (isDark ? "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50" : "text-slate-500 hover:text-slate-800 hover:bg-slate-100")
            )}
            style={location.pathname === "/settings" ? { color: ac[400], backgroundColor: `rgba(${ac.rgb},0.1)` } : undefined}
          >
            <Settings className="h-5 w-5" />
            Settings
          </Link>
          <div className="mt-4 flex items-center gap-3 px-3">
            <div className="h-8 w-8 rounded-full flex items-center justify-center text-white text-xs font-bold" style={{ background: `linear-gradient(135deg, ${ac[500]}, ${ac[400]})` }}>
              JS
            </div>
            <div className="flex-1 min-w-0">
              <p className={cn("text-sm font-medium truncate", isDark ? "text-white" : "text-slate-900")}>John Smith</p>
              <p className={cn("text-xs truncate", isDark ? "text-slate-400" : "text-slate-500")}>Pro Member</p>
            </div>
          </div>
          <div className={cn("mt-3 flex items-center gap-2 px-3 text-xs", isDark ? "text-slate-500" : "text-slate-400")}>
            <div className={cn("w-2 h-2 rounded-full", backendOnline === true ? "bg-emerald-400" : backendOnline === false ? "bg-rose-400" : "bg-slate-500 animate-pulse")} />
            {backendOnline === true ? "Backend connected" : backendOnline === false ? "Backend offline" : "Checking..."}
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
        {/* Header */}
        <header className={cn(
          "h-16 flex items-center justify-between px-4 sm:px-6 lg:px-8 border-b backdrop-blur-xl shrink-0 z-20",
          isDark ? "bg-slate-900/50 border-slate-800/50" : "bg-white/80 border-slate-200"
        )}>
          <button
            className={cn("md:hidden p-2 rounded-lg transition-colors", isDark ? "text-slate-400 hover:text-white hover:bg-slate-800" : "text-slate-500 hover:text-slate-900 hover:bg-slate-100")}
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="h-6 w-6" />
          </button>
          
          <div className={cn(
            "hidden md:flex items-center flex-1 max-w-md rounded-full px-3 py-1.5 border transition-all",
            isDark 
              ? "bg-slate-800/50 border-slate-700/50 focus-within:bg-slate-800" 
              : "bg-slate-100 border-slate-200 focus-within:bg-white focus-within:shadow-sm",
          )}
          style={searchFocused ? { borderColor: `rgba(${ac.rgb},0.5)`, boxShadow: `0 0 0 2px rgba(${ac.rgb},0.2)` } : undefined}
          >
            <Search className={cn("h-4 w-4", isDark ? "text-slate-400" : "text-slate-400")} />
            <input
              type="text"
              placeholder="Ask AI or search transactions..."
              ref={searchRef}
              className={cn(
                "bg-transparent border-none outline-none text-sm ml-2 w-full",
                isDark ? "text-slate-200 placeholder:text-slate-500" : "text-slate-800 placeholder:text-slate-400"
              )}
              onFocus={() => setSearchFocused(true)}
              onBlur={() => setSearchFocused(false)}
            />
            <kbd className={cn(
              "hidden lg:inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono",
              isDark ? "bg-slate-700 text-slate-400 border border-slate-600" : "bg-slate-200 text-slate-500 border border-slate-300"
            )}>
              /
            </kbd>
          </div>

          <div className="flex items-center gap-2 ml-auto">
            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className={cn(
                "p-2 rounded-full transition-all",
                isDark ? "text-slate-400 hover:text-amber-400 hover:bg-slate-800" : "text-slate-500 hover:bg-slate-100"
              )}
              style={!isDark ? { ['--hover-color' as any]: ac[600] } : undefined}
              onMouseEnter={(e) => { if (!isDark) e.currentTarget.style.color = ac[600]; }}
              onMouseLeave={(e) => { if (!isDark) e.currentTarget.style.color = ''; }}
              title={isDark ? "Switch to Light Mode" : "Switch to Dark Mode"}
            >
              <AnimatePresence mode="wait">
                {isDark ? (
                  <motion.div key="sun" initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 90, opacity: 0 }} transition={{ duration: 0.15 }}>
                    <Sun className="h-5 w-5" />
                  </motion.div>
                ) : (
                  <motion.div key="moon" initial={{ rotate: 90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: -90, opacity: 0 }} transition={{ duration: 0.15 }}>
                    <Moon className="h-5 w-5" />
                  </motion.div>
                )}
              </AnimatePresence>
            </button>

            {/* Notifications */}
            <div className="relative" ref={notifRef}>
              <button
                onClick={() => setNotifOpen(!notifOpen)}
                className={cn(
                  "relative p-2 rounded-full transition-colors",
                  isDark ? "text-slate-400 hover:text-white hover:bg-slate-800" : "text-slate-500 hover:text-slate-900 hover:bg-slate-100"
                )}
              >
                <Bell className="h-5 w-5" />
                {unreadCount > 0 && (
                  <span className={cn("absolute top-1 right-1 h-4 w-4 rounded-full text-[10px] font-bold flex items-center justify-center border-2", isDark ? "bg-rose-500 text-white border-slate-900" : "bg-rose-500 text-white border-white")}>
                    {unreadCount}
                  </span>
                )}
              </button>

              <AnimatePresence>
                {notifOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: -8, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -8, scale: 0.95 }}
                    transition={{ duration: 0.15 }}
                    className={cn(
                      "absolute right-0 top-12 w-80 sm:w-96 rounded-2xl border shadow-2xl overflow-hidden z-50",
                      isDark ? "bg-slate-900 border-slate-800" : "bg-white border-slate-200"
                    )}
                  >
                    <div className={cn("flex items-center justify-between px-4 py-3 border-b", isDark ? "border-slate-800" : "border-slate-100")}>
                      <h3 className={cn("text-sm font-semibold", isDark ? "text-slate-200" : "text-slate-800")}>Notifications</h3>
                      <button className="text-xs hover:opacity-80 transition-opacity" style={{ color: ac[400] }}>Mark all read</button>
                    </div>
                    <div className="max-h-80 overflow-y-auto custom-scrollbar">
                      {notifications.map(n => (
                        <div key={n.id} className={cn(
                          "px-4 py-3 border-b flex gap-3 transition-colors cursor-pointer",
                          isDark ? "border-slate-800/50 hover:bg-slate-800/50" : "border-slate-50 hover:bg-slate-50",
                          !n.read && (isDark ? `bg-[rgba(${ac.rgb},0.05)]` : `bg-[rgba(${ac.rgb},0.05)]`)
                        )}>
                          <div className={cn(
                            "w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-0.5",
                            n.type === "alert" ? "bg-rose-500/10 text-rose-400" :
                            n.type === "success" ? "bg-emerald-500/10 text-emerald-400" : ""
                          )} style={n.type !== "alert" && n.type !== "success" ? { backgroundColor: `rgba(${ac.rgb},0.1)`, color: ac[400] } : undefined}>
                            {n.type === "alert" ? <AlertTriangle className="h-4 w-4" /> :
                             n.type === "success" ? <TrendingUp className="h-4 w-4" /> :
                             <Bell className="h-4 w-4" />}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <p className={cn("text-sm font-medium truncate", isDark ? "text-slate-200" : "text-slate-800")}>{n.title}</p>
                              {!n.read && <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: ac[500] }}></span>}
                            </div>
                            <p className={cn("text-xs mt-0.5 line-clamp-2", isDark ? "text-slate-400" : "text-slate-500")}>{n.desc}</p>
                            <p className={cn("text-[10px] mt-1", isDark ? "text-slate-500" : "text-slate-400")}>{n.time}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                    <Link
                      to="/settings"
                      onClick={() => setNotifOpen(false)}
                      className={cn(
                        "flex items-center justify-center gap-1 px-4 py-2.5 text-xs font-medium transition-colors",
                        isDark ? "hover:bg-slate-800/50" : "hover:bg-slate-50"
                      )}
                      style={{ color: ac[isDark ? 400 : 600] }}
                    >
                      View all notifications <ChevronRight className="h-3 w-3" />
                    </Link>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <div className={cn("flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 custom-scrollbar", isDark ? "" : "bg-slate-50")}>
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2 }}
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </div>
        
        {/* Floating Quick AI Button */}
        {location.pathname !== '/assistant' && (
          <Link
            to="/assistant"
            className="absolute bottom-6 right-6 h-14 w-14 rounded-full flex items-center justify-center shadow-lg transition-transform hover:scale-105 active:scale-95 text-white z-20 group"
            style={{ backgroundColor: ac[600], boxShadow: `0 10px 15px -3px rgba(${ac.rgb},0.3)` }}
          >
            <span className="absolute inset-0 rounded-full animate-ping opacity-20 group-hover:opacity-0" style={{ backgroundColor: ac[500] }}></span>
            <MessageSquare className="h-6 w-6 relative z-10" />
          </Link>
        )}
      </main>

      <Toaster
        theme={isDark ? "dark" : "light"}
        position="bottom-right"
        richColors
        toastOptions={{
          style: {
            borderRadius: '0.75rem',
          }
        }}
      />
    </div>
  );
}