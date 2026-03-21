import { initializeApp, getApps, type FirebaseApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

const requiredKeys: Array<keyof typeof firebaseConfig> = [
  "apiKey",
  "authDomain",
  "projectId",
  "appId",
];

export function isFirebaseConfigured(): boolean {
  return requiredKeys.every((key) => Boolean(firebaseConfig[key]));
}

function getFirebaseApp(): FirebaseApp | null {
  if (!isFirebaseConfigured()) {
    return null;
  }
  if (getApps().length > 0) {
    return getApps()[0];
  }
  return initializeApp(firebaseConfig);
}

export function getAuthInstance(): Auth | null {
  const app = getFirebaseApp();
  if (!app) {
    return null;
  }
  return getAuth(app);
}

export async function getFirebaseIdToken(): Promise<string | null> {
  const auth = getAuthInstance();
  const user = auth?.currentUser;
  if (!user) {
    return null;
  }
  return user.getIdToken();
}
