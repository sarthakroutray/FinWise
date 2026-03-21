import React from "react";
import { RouterProvider } from "react-router";
import { router } from "./routes";
import { ThemeProvider } from "./components/ThemeProvider";
import { FinDataProvider } from "./store/useFinData";
import { AuthProvider } from "./auth/AuthProvider";

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <FinDataProvider>
          <RouterProvider router={router} />
        </FinDataProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
