import { useQuery } from "@tanstack/react-query";
import { checkApiHealth } from "./lib/apiClient";

export default function App() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["api-health"],
    queryFn: checkApiHealth,
  });

  return (
    <main className="mx-auto max-w-3xl p-8">
      <header className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-4">
        <div>
          <h1 className="text-2xl font-semibold">ClearCard Acquisition</h1>
          <p className="text-sm text-[var(--text-muted)]">
            Transparent card onboarding &amp; underwriting funnel
          </p>
        </div>
        <span className="rounded-full border border-[var(--border-subtle)] bg-[var(--surface-card)] px-3 py-1 text-xs font-medium">
          API:{" "}
          {isLoading
            ? "Checking..."
            : isError
              ? "Offline"
              : data?.status.toUpperCase()}
        </span>
      </header>
    </main>
  );
}