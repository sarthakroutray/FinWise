import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import {
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut,
  type User,
} from "firebase/auth";
import { getAuthInstance, isFirebaseConfigured } from "./firebase";

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isConfigured: boolean;
  error: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const configured = isFirebaseConfigured();

  useEffect(() => {
    const auth = getAuthInstance();
    if (!auth) {
      setIsLoading(false);
      return;
    }

    const unsub = onAuthStateChanged(
      auth,
      (nextUser) => {
        setUser(nextUser);
        setIsLoading(false);
      },
      (authError) => {
        setError(authError.message);
        setIsLoading(false);
      }
    );

    return () => unsub();
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      isLoading,
      isConfigured: configured,
      error,
      signIn: async (email: string, password: string) => {
        const auth = getAuthInstance();
        if (!auth) {
          throw new Error("Firebase Auth is not configured.");
        }
        setError(null);
        await signInWithEmailAndPassword(auth, email, password);
      },
      signUp: async (email: string, password: string) => {
        const auth = getAuthInstance();
        if (!auth) {
          throw new Error("Firebase Auth is not configured.");
        }
        setError(null);
        await createUserWithEmailAndPassword(auth, email, password);
      },
      logout: async () => {
        const auth = getAuthInstance();
        if (!auth) {
          return;
        }
        await signOut(auth);
      },
    }),
    [configured, error, isLoading, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
