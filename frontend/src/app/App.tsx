import React from "react";
import { RouterProvider } from "react-router";
import { router } from "./routes";
import { ThemeProvider } from "./components/ThemeProvider";
import { FinDataProvider } from "./store/useFinData";

export default function App() {
  return (
    <ThemeProvider>
      <FinDataProvider>
        <RouterProvider router={router} />
      </FinDataProvider>
    </ThemeProvider>
  );
}
