/**
 * E2E — Module 3: Positions & Pipeline
 * "New Position" button opens "Create New Position" dialog.
 * JD upload is required — Create Position button is disabled without a JD.
 */
import { test, expect } from "@playwright/test";
import { createProject, deleteProject, createPosition } from "./helpers";
import path from "path";
import fs from "fs";
import os from "os";

let projectId: number;

test.beforeAll(async () => {
  const p = await createProject("Positions E2E", "Pos Client");
  projectId = p.id;
});

test.afterAll(async () => {
  await deleteProject(projectId).catch(() => {});
});

function makeTempFile(name: string, content: string): string {
  const filePath = path.join(os.tmpdir(), name);
  fs.writeFileSync(filePath, content);
  return filePath;
}

test("TC-13 | Positions tab shows 'New Position' button", async ({ page }) => {
  await page.goto(`/projects/${projectId}`);
  await page.getByRole("tab", { name: "Positions" }).click();
  await expect(page.getByRole("button", { name: "New Position" })).toBeVisible();
});

test("TC-14 | New Position dialog opens with correct title", async ({ page }) => {
  await page.goto(`/projects/${projectId}`);
  await page.getByRole("tab", { name: "Positions" }).click();
  await page.getByRole("button", { name: "New Position" }).click();

  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(page.getByText("Create New Position")).toBeVisible();

  // Close dialog
  await page.keyboard.press("Escape");
});

test("TC-15 | Create Position with JD file", async ({ page }) => {
  const jdPath = makeTempFile("jd_e2e.txt",
    "Position: Frontend Engineer\nRequirements: React, TypeScript, CSS\nLevel: Mid"
  );

  await page.goto(`/projects/${projectId}`);
  await page.getByRole("tab", { name: "Positions" }).click();
  await page.getByRole("button", { name: "New Position" }).click();

  const dialog = page.getByRole("dialog");
  await dialog.getByPlaceholder(/Senior Backend Engineer/i).fill("Frontend Engineer E2E");

  // Set file via hidden input
  const fileInput = dialog.locator('input[type="file"]').first();
  await fileInput.setInputFiles(jdPath);

  // Button should become enabled after file selected
  const createBtn = dialog.getByRole("button", { name: "Create Position" });
  await expect(createBtn).toBeEnabled({ timeout: 5_000 });
  await createBtn.click();

  await expect(dialog).not.toBeVisible();
  await expect(page.getByText("Frontend Engineer E2E")).toBeVisible({ timeout: 10_000 });
});

test("TC-16 | Create Position button enabled when title is provided", async ({ page }) => {
  // canCreate = !!title || !!file || !!jdDocId — title alone is sufficient
  await page.goto(`/projects/${projectId}`);
  await page.getByRole("tab", { name: "Positions" }).click();
  await page.getByRole("button", { name: "New Position" }).click();

  const dialog = page.getByRole("dialog");
  await dialog.getByPlaceholder(/Senior Backend Engineer/i).fill("Title Only Position");

  await expect(dialog.getByRole("button", { name: "Create Position" })).toBeEnabled({ timeout: 3_000 });
  await page.keyboard.press("Escape");
});

test("TC-17 | Position card navigates to position detail", async ({ page }) => {
  const pos = await createPosition(projectId, "Nav Position E2E");

  await page.goto(`/projects/${projectId}`);
  await page.getByRole("tab", { name: "Positions" }).click();
  await expect(page.getByText("Nav Position E2E")).toBeVisible({ timeout: 10_000 });

  // Position card links to /positions/{id}
  const posLink = page.locator(`a[href="/positions/${pos.id}"]`).first();
  if (await posLink.isVisible({ timeout: 3_000 }).catch(() => false)) {
    await Promise.all([
      page.waitForURL(`**/positions/${pos.id}`),
      posLink.click(),
    ]);
  } else {
    // Fallback: click on the card text
    await Promise.all([
      page.waitForURL(`**/positions/${pos.id}`),
      page.getByText("Nav Position E2E").first().click(),
    ]);
  }
  await expect(page.url()).toContain(`/positions/${pos.id}`);
});

test("TC-18 | Position detail shows Add Candidate button", async ({ page }) => {
  const pos = await createPosition(projectId, "Detail Pos E2E");
  await page.goto(`/positions/${pos.id}`);

  await expect(page.getByText("Detail Pos E2E")).toBeVisible();
  await expect(page.getByRole("button", { name: /Add Candidate/i })).toBeVisible();
});

// ── Pipeline ──────────────────────────────────────────────────────────────────

test("TC-20 | Pipeline page loads", async ({ page }) => {
  await page.goto("/pipeline");
  await expect(page).toHaveURL(/\/pipeline/);
  await expect(page.getByText(/pipeline/i).first()).toBeVisible();
});

test("TC-21 | Pipeline shows open positions", async ({ page }) => {
  const pos = await createPosition(projectId, "Pipeline Visible E2E");

  await page.goto("/pipeline");
  await expect(page.getByText("Pipeline Visible E2E")).toBeVisible({ timeout: 10_000 });
});

test("TC-22 | Closed positions not shown in pipeline", async ({ page }) => {
  const pos = await createPosition(projectId, "Closed Pipeline E2E");
  await fetch(`http://localhost:8000/api/positions/${pos.id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: "closed" }),
  });

  await page.goto("/pipeline");
  await expect(page.getByText("Closed Pipeline E2E")).not.toBeVisible();
});
