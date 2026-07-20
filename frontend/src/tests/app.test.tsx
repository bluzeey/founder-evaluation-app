import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import App from "@/App";

beforeEach(() => {
  vi.stubGlobal("localStorage", {
    getItem: vi.fn().mockReturnValue(null),
    setItem: vi.fn(),
  });
});

describe("app shell", () => {
  it("shows Discovery and Recommended without role switching", () => {
    const html = renderToString(
      <MemoryRouter initialEntries={["/discovery"]}>
        <App />
      </MemoryRouter>
    );

    expect(html).toContain("Discovery");
    expect(html).toContain("Recommended");
    expect(html).not.toContain("Analyst");
    expect(html).not.toContain("Partner");
  });
});
