/**
 * Searching the catalogue is explicit.
 *
 * The box used to search as you typed, on a 300ms timer, which made the
 * results depend on how fast the reader typed: a pause partway through
 * "deep" searched for "dee", and a query typed briskly could leave the
 * previous results on screen. These tests pin the replacement -- a query
 * runs on Enter or on the Search button, and at no other time -- by counting
 * the requests the page actually makes.
 */

import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import BrowseProjects from "./BrowseProjects";

vi.mock("../api/client", () => ({
  projectsApi: {
    list: vi.fn(),
    facets: vi.fn(),
  },
}));

const { projectsApi } = await import("../api/client");

/** Every query the page has asked the server for, oldest first. */
function requestedQueries() {
  return projectsApi.list.mock.calls.map(([params]) => params.q ?? "");
}

function renderPage(initialEntry = "/projects") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <BrowseProjects />
    </MemoryRouter>
  );
}

async function settled() {
  // The page issues its initial list and facet requests on mount; wait for
  // that to finish so a later assertion counts only what typing caused.
  await waitFor(() => expect(projectsApi.list).toHaveBeenCalled());
}

/**
 * Let any pending timer fire, and let React process what it caused.
 *
 * The `act` wrapper is the point. Advancing timers on its own schedules the
 * state update but never flushes it, so an assertion that no search happened
 * would hold whether or not a timer was waiting to start one -- the test
 * would pass against the very bug it exists to catch. Verified by putting the
 * debounce back and watching these tests fail.
 */
async function elapse(ms) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe("catalogue search", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    projectsApi.list.mockResolvedValue({
      data: [],
      pagination: { page: 1, pages: 1, count: 0 },
    });
    projectsApi.facets.mockResolvedValue({ data: {} });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("does not search while the reader is typing", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderPage();
    await settled();
    const before = projectsApi.list.mock.calls.length;

    await user.type(screen.getByRole("searchbox"), "deep");

    // Long enough that the old 300ms timer would have fired several times.
    await elapse(2000);

    expect(projectsApi.list.mock.calls.length).toBe(before);
    expect(requestedQueries()).not.toContain("dee");
  });

  it("searches the whole query when Enter is pressed", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderPage();
    await settled();

    await user.type(screen.getByRole("searchbox"), "deep{Enter}");

    await waitFor(() => expect(requestedQueries()).toContain("deep"));
    // Never a prefix of it: no partial query was ever sent.
    for (const partial of ["d", "de", "dee"]) {
      expect(requestedQueries()).not.toContain(partial);
    }
  });

  it("searches when the Search button is clicked", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderPage();
    await settled();

    await user.type(screen.getByRole("searchbox"), "tomato");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => expect(requestedQueries()).toContain("tomato"));
  });

  it("keeps unsubmitted text in the box without searching for it", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderPage("/projects?q=deep");
    await settled();

    // Edited but never emptied, so nothing counts as an explicit act.
    const box = screen.getByRole("searchbox");
    await user.type(box, " tomato");
    await elapse(2000);

    // The reader sees what they typed, and the results still answer the
    // query they actually submitted.
    expect(box).toHaveValue("deep tomato");
    expect(requestedQueries()).not.toContain("deep tomato");
    expect(requestedQueries().at(-1)).toBe("deep");
  });

  it("trims surrounding whitespace on submit", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderPage();
    await settled();

    await user.type(screen.getByRole("searchbox"), "  deep  {Enter}");

    await waitFor(() => expect(requestedQueries()).toContain("deep"));
  });

  it("submitting an empty box clears the query rather than searching for it",
    async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderPage("/projects?q=deep");
      await settled();

      await user.clear(screen.getByRole("searchbox"));
      await user.click(screen.getByRole("button", { name: "Search" }));

      await waitFor(() => expect(requestedQueries().at(-1)).toBe(""));
    });

  it("clearing the box clears the search without waiting for Enter", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderPage("/projects?q=cybersecurity");
    await settled();

    await user.clear(screen.getByRole("searchbox"));

    await waitFor(() => expect(requestedQueries().at(-1)).toBe(""));
  });

  it("shows the submitted query when one arrives in the URL", async () => {
    renderPage("/projects?q=deep");
    await settled();

    expect(screen.getByRole("searchbox")).toHaveValue("deep");
    expect(requestedQueries()).toEqual(["deep"]);
  });
});
