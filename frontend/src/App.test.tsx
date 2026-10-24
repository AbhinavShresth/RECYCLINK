import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

describe("RecycLink application shell", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => Promise.resolve({
      ok: true,
      json: async () => String(url).includes("/auth/me")
        ? { id: "test-user", email: "person@example.test", full_name: "Test Person", preferred_language: "en", roles: ["USER"], created_at: "2026-01-01T00:00:00Z" }
        : { status: "ready", database: "connected" },
    })));
  });

  it("shows an account dashboard and honest empty collection state", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={queryClient}><MemoryRouter><App/></MemoryRouter></QueryClientProvider>);
    expect(await screen.findByRole("heading", { name: /give useful materials their next destination/i })).toBeInTheDocument();
    expect(screen.getByText(/waste submitted/i)).toBeInTheDocument();
    expect(await screen.findByText(/no collections in your account yet/i)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /identify waste/i }).every((link) => link.getAttribute("href") === "/identify")).toBe(true);
  });
});
