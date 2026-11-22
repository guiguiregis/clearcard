import {
    ApplicationResponse,
    ApplicationResponseSchema,
    CreateApplicationRequestSchema,
  } from "@clearcard/contracts";
  import { z } from "zod";
  
  const API_BASE = import.meta.env.VITE_API_URL ?? "/api";
  
  export async function checkApiHealth(): Promise<{ status: string }> {
    const res = await fetch(`${API_BASE}/health`, {
      headers: { "X-Request-Id": crypto.randomUUID() },
    });
    if (!res.ok) throw new Error(`API health check failed (${res.status})`);
    return res.json();
  }
  
  export async function createApplication(
    payload: z.infer<typeof CreateApplicationRequestSchema>,
    idempotencyKey: string
  ): Promise<ApplicationResponse> {
    const validPayload = CreateApplicationRequestSchema.parse(payload);
  
    const res = await fetch(`${API_BASE}/applications`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
        "X-Request-Id": crypto.randomUUID(),
      },
      body: JSON.stringify(validPayload),
    });
  
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(err.detail ?? "Failed to create application");
    }
  
    return ApplicationResponseSchema.parse(await res.json());
  }