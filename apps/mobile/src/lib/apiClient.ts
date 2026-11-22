import { Platform } from "react-native";

// Android emulator reaches host localhost via 10.0.2.2; iOS simulator uses localhost
const DEFAULT_HOST = Platform.OS === "android" ? "http://10.0.2.2:8000" : "http://localhost:8000";
export const API_BASE = process.env.EXPO_PUBLIC_API_URL ?? DEFAULT_HOST;

export async function fetchMobileHealth(): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error("Mobile API health check failed");
  return res.json();
}