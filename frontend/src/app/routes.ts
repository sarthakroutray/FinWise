import { createBrowserRouter } from "react-router";
import { Layout } from "./components/Layout";
import { Dashboard } from "./components/Dashboard";
import { Transactions } from "./components/Transactions";
import { Insights } from "./components/Insights";
import { AIAssistant } from "./components/AIAssistant";
import { Settings } from "./components/Settings";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Layout,
    children: [
      { index: true, Component: Dashboard },
      { path: "transactions", Component: Transactions },
      { path: "insights", Component: Insights },
      { path: "assistant", Component: AIAssistant },
      { path: "settings", Component: Settings },
    ],
  },
]);
