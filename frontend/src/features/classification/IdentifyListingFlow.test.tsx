import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import IdentifyWaste from "./IdentifyWaste";
import Marketplace from "../marketplace/Marketplace";

type Listing = { id: string; is_mine: boolean; category_code: string; quantity_grams: number; condition: string | null; description: string; status: string; created_at: string; offer_count: number };

function Harness() {
  const [role, setRole] = useState("RECYCLER");
  return <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={["/identify"]}>
      <Routes>
        <Route path="/identify" element={<IdentifyWaste onCreateListing={() => setRole("USER")} />} />
        <Route path="/marketplace" element={<Marketplace activeRole={role} />} />
      </Routes>
    </MemoryRouter>
  </QueryClientProvider>;
}

describe("image to marketplace listing flow", () => {
  beforeEach(() => {
    let saved: Listing[] = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      if (path.endsWith("/api/v1/ai/status")) return { ok: true, status: 200, json: async () => ({ ready: false, status: "unavailable", message: "Trained model is not installed." }) };
      if (path.endsWith("/api/v1/ai/history")) return { ok: true, status: 200, json: async () => [] };
      if (path.endsWith("/api/v1/listings") && method === "POST") {
        const payload = JSON.parse(String(init?.body)) as { category_code: string; quantity_grams: number; description: string; classification_id?: string };
        const created: Listing = { id: "listing-1", is_mine: true, category_code: payload.category_code, quantity_grams: payload.quantity_grams, condition: null, description: payload.description, status: "OPEN", created_at: new Date().toISOString(), offer_count: 0 };
        saved = [created];
        return { ok: true, status: 201, json: async () => created };
      }
      if (path.endsWith("/api/v1/listings")) return { ok: true, status: 200, json: async () => saved };
      return { ok: false, status: 404, json: async () => ({ detail: "Not found" }) };
    }));
  });

  it("carries a selected photo category into a saved listing and refreshes the marketplace", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    const image = new File(["photo"], "cardboard.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("Choose waste photo"), { target: { files: [image] } });
    await user.selectOptions(await screen.findByLabelText("Material category"), "paper");
    await user.click(screen.getByRole("button", { name: "Create listing from this photo" }));

    expect(await screen.findByText(/carried over paper from your image review/i)).toBeInTheDocument();
    expect(screen.getByLabelText("Material")).toHaveValue("paper");
    await user.type(screen.getByLabelText("Pickup address"), "12 College Road, Pune");
    await user.clear(screen.getByLabelText("Approximate mass (grams)"));
    await user.type(screen.getByLabelText("Approximate mass (grams)"), "2500");
    await user.type(screen.getByLabelText("Latitude"), "18.5204");
    await user.type(screen.getByLabelText("Longitude"), "73.8567");
    await user.click(screen.getByRole("button", { name: "Publish listing" }));

    expect(await screen.findByRole("status")).toHaveTextContent(/listing created and saved/i);
    await waitFor(() => expect(screen.getByText(/paper · 2\.50 kg/i)).toBeInTheDocument());
  });
});
