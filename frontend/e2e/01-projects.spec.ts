/**
 * E2E — Module 1: Dashboard & Projects
 */
import { test, expect } from "@playwright/test";
import { createProject, deleteProject } from "./helpers";

test.describe("Dashboard", () => {
  test("loads with correct title and logo", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/TalentLens/i);
    await expect(page.locator("span").filter({ hasText: "TalentLens" }).first()).toBeVisible();
  });

  test("shows stat cards", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/Active Projects/i).first()).toBeVisible();
    await expect(page.getByText(/Open Positions/i).first()).toBeVisible();
  });

  test("page body contains no 500 errors", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("body")).not.toContainText("500");
    await expect(page.locator("body")).not.toContainText("Internal Server Error");
  });
});

test.describe("Project CRUD", () => {
  let projectId = 0;

  test("TC-01 | Create project via UI dialog", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /new project/i }).click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();

    await dialog.getByPlaceholder(/Platform Team/i).fill("E2E Test Project");
    await dialog.getByPlaceholder(/TechCorp/i).fill("E2E Client Corp");
    await dialog.getByPlaceholder(/Optional/i).fill("Created by Playwright");
    await dialog.getByRole("button", { name: "Create Project" }).click();

    await expect(dialog).not.toBeVisible();
    await expect(page.getByText("E2E Test Project").first()).toBeVisible();
  });

  test("TC-02 | Project card navigates to project detail", async ({ page }) => {
    const p = await createProject("Link Test Project", "Link Client");
    projectId = p.id;

    await page.goto("/");
    // Target the anchor link that wraps the card
    const cardLink = page.locator(`a[href="/projects/${p.id}"]`).first();
    await expect(cardLink).toBeVisible({ timeout: 10_000 });
    await Promise.all([
      page.waitForURL(`**/projects/${p.id}`),
      cardLink.click(),
    ]);
    await expect(page.url()).toContain(`/projects/${p.id}`);
  });

  test("TC-03 | Project detail page loads with title and tabs", async ({ page }) => {
    const p = await createProject("Detail Project", "Detail Client");
    projectId = p.id;

    await page.goto(`/projects/${p.id}`);
    await expect(page.getByRole("heading", { name: "Detail Project" })).toBeVisible();
    await expect(page.getByText("Detail Client")).toBeVisible();
    await expect(page.getByRole("tab", { name: "Team" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Positions" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Documents" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "AI Analysis" })).toBeVisible();
  });

  test("TC-04 | Project page has Timeline tab (coming soon)", async ({ page }) => {
    const p = await createProject("Timeline Project", "Timeline Client");
    projectId = p.id;
    await page.goto(`/projects/${p.id}`);
    await expect(page.getByRole("tab", { name: "Timeline" })).toBeVisible();
    await page.getByRole("tab", { name: "Timeline" }).click();
    await expect(page.getByText(/timeline/i).first()).toBeVisible();
  });

  test("TC-05 | Back arrow on project page navigates to dashboard", async ({ page }) => {
    const p = await createProject("Back Nav Project", "Nav Client");
    projectId = p.id;

    await page.goto(`/projects/${p.id}`);
    // Back button has ArrowLeft icon — class includes "lucide-arrow-left"
    const backBtn = page.locator("button:has(.lucide-arrow-left)").first();
    await Promise.all([
      page.waitForURL("http://localhost:3000/"),
      backBtn.click(),
    ]);
    await expect(page.url()).toMatch(/localhost:3000\/?$/);
  });

  test.afterEach(async () => {
    if (projectId) {
      await deleteProject(projectId).catch(() => {});
      projectId = 0;
    }
  });
});
