/**
 * E2E — Module 6: Navigation, Edge Cases, Search API
 * Nav: Logo = <Link href="/"> (a[href="/"]), Pipeline = <Link href="/pipeline"> (a[href="/pipeline"])
 * Both are in the fixed nav header — use waitForURL after click.
 */
import { test, expect } from "@playwright/test";
import { createProject, deleteProject, uploadTextDocument } from "./helpers";

let projectId: number;

test.beforeAll(async () => {
  const p = await createProject("Edge Cases Project", "Edge Client");
  projectId = p.id;
});

test.afterAll(async () => {
  await deleteProject(projectId).catch(() => {});
});

// ── 404 / not-found ───────────────────────────────────────────────────────────

test("TC-49 | Non-existent project shows error state", async ({ page }) => {
  await page.goto("/projects/999999");
  await expect(page.getByText(/not found|error|go back/i).first()).toBeVisible({ timeout: 8_000 });
});

test("TC-50 | Non-existent position shows error state", async ({ page }) => {
  await page.goto("/positions/999999");
  await expect(page.getByText(/not found|error|go back/i).first()).toBeVisible({ timeout: 8_000 });
});

test("TC-51 | Non-existent candidate shows error state", async ({ page }) => {
  await page.goto("/candidates/999999");
  await expect(page.getByText(/not found|go back/i).first()).toBeVisible({ timeout: 8_000 });
});

test("TC-52 | Non-existent team member shows error state", async ({ page }) => {
  await page.goto("/team/999999");
  await expect(page.getByText(/not found|error|go back/i).first()).toBeVisible({ timeout: 8_000 });
});

// ── Navigation ────────────────────────────────────────────────────────────────

test("TC-53 | Logo link navigates to dashboard", async ({ page }) => {
  await page.goto(`/projects/${projectId}`);
  await Promise.all([
    page.waitForURL("http://localhost:3000/"),
    page.locator("a[href='/']").first().click(),
  ]);
  await expect(page.url()).toMatch(/localhost:3000\/?$/);
});

test("TC-54 | Pipeline nav link navigates to /pipeline", async ({ page }) => {
  await page.goto("/");
  await Promise.all([
    page.waitForURL("**/pipeline"),
    page.locator("a[href='/pipeline']").click(),
  ]);
  await expect(page.url()).toContain("/pipeline");
});

test("TC-55 | Dashboard nav link navigates from pipeline to home", async ({ page }) => {
  await page.goto("/pipeline");
  await Promise.all([
    page.waitForURL("http://localhost:3000/"),
    page.locator("a[href='/']").first().click(),
  ]);
  await expect(page.url()).toMatch(/localhost:3000\/?$/);
});

test("TC-56 | No unhandled JS errors on main pages", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => {
    if (!err.message.includes("Warning:") && !err.message.includes("hydrat")) {
      errors.push(err.message);
    }
  });

  await page.goto("/");
  await page.goto("/pipeline");
  await page.goto(`/projects/${projectId}`);

  expect(errors, `JS errors: ${errors.join(", ")}`).toHaveLength(0);
});

// ── AI Analysis tab ───────────────────────────────────────────────────────────

test("TC-57 | AI Analysis tab renders", async ({ page }) => {
  await page.goto(`/projects/${projectId}`);
  await page.getByRole("tab", { name: "AI Analysis" }).click();
  await expect(page.locator("body")).not.toContainText("500");
});

test("TC-58 | Timeline tab renders", async ({ page }) => {
  await page.goto(`/projects/${projectId}`);
  await page.getByRole("tab", { name: "Timeline" }).click();
  await expect(page.getByText(/timeline/i).first()).toBeVisible();
});

// ── Search API ────────────────────────────────────────────────────────────────

test("TC-59 | Search API returns valid response for keyword query", async () => {
  await uploadTextDocument(
    projectId,
    "Senior TypeScript developer with 5 years React and Node.js experience",
    "resume",
    "search_seed_api.txt",
  );

  await new Promise((r) => setTimeout(r, 2_000));

  const res = await fetch("http://localhost:8000/api/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query: "TypeScript developer", project_id: String(projectId), top_k: 5 }),
  });

  expect(res.ok).toBe(true);
  const data = await res.json() as { results: unknown[] };
  expect(Array.isArray(data.results)).toBe(true);
});

test("TC-60 | Search API returns valid JSON for no-match query", async () => {
  const res = await fetch("http://localhost:8000/api/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: "xyzzy_nonexistent_term_abc_12345",
      project_id: String(projectId),
      top_k: 5,
    }),
  });

  expect(res.ok).toBe(true);
  const data = await res.json() as { results: unknown[]; total: number };
  expect(Array.isArray(data.results)).toBe(true);
});
