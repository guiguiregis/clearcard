import React, { useEffect, useState } from "react";
import { SafeAreaView, StyleSheet, Text, View } from "react-native";
import * as Linking from "expo-linking";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { fetchMobileHealth } from "./src/lib/apiClient";

const queryClient = new QueryClient();

function OnboardingShell() {
  const [handoffUrl, setHandoffUrl] = useState<string | null>(null);
  const { data, isLoading, isError } = useQuery({
    queryKey: ["mobile-health"],
    queryFn: fetchMobileHealth,
  });

  useEffect(() => {
    Linking.getInitialURL().then((url) => {
      if (url) setHandoffUrl(url);
    });
    const sub = Linking.addEventListener("url", ({ url }) => setHandoffUrl(url));
    return () => sub.remove();
  }, []);

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.card}>
        <Text style={styles.title}>ClearCard Mobile</Text>
        <Text style={styles.subtitle}>Cross-platform card acquisition surface</Text>
        <Text style={styles.badge}>
          API: {isLoading ? "Checking..." : isError ? "Offline" : data?.status.toUpperCase()}
        </Text>
        {handoffUrl ? (
          <Text style={styles.handoff}>Resumed via deep link: {handoffUrl}</Text>
        ) : null}
      </View>
    </SafeAreaView>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <OnboardingShell />
    </QueryClientProvider>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F8FAFC", justifyContent: "center", padding: 24 },
  card: { backgroundColor: "#FFFFFF", borderRadius: 12, padding: 20, borderWidth: 1, borderColor: "#E2E8F0" },
  title: { fontSize: 22, fontWeight: "700", color: "#0F172A" },
  subtitle: { fontSize: 14, color: "#475569", marginTop: 4 },
  badge: { marginTop: 16, fontSize: 12, fontWeight: "600", color: "#4F46E5" },
  handoff: { marginTop: 12, fontSize: 12, color: "#059669" },
});