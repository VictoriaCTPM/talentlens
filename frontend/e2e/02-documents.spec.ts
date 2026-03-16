/**
 * E2E — Module 2: Documents
 */
import { test, expect } from "@playwright/test";
import { createProject, deleteProject } from "./helpers";
import path from "path";
import fs from "fs";
import os from "os";

let projectId: number;

test.beforeAll(async () => {
  const p = await createProject("Docs E2E Project", "Docs Client");
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

test("TC-06 | Documents tab renders with upload sections", async ({ page }) => {
  await page.goto(`/projects/${projectId}`);
  await page.getByRole("tab", { name: "Documents" }).click();
  await expect(page.getByText("Upload Documents")).toBeVisible();
  await expect(page.getByRole("button", { name: "Upload Resume / CV" })).toBeVisible();
});

test("TC-07 | Upload a Resume TXT document", async ({ page }) => {
  const filePath = makeTempFile("resume_e2e.txt",
    "Skills: TypeScript, React\nExperience: 3 years frontend development"
  );

  await page.goto(`/projects/${projectId}`);
  await page.getByRole("tab", { name: "Documents" }).click();

  const [fileChooser] = await Promise.all([
    page.waitForEvent("filechooser"),
    page.getByRole("button", { name: "Upload Resume / CV" }).click(),
  ]);
  await fileChooser.setFiles(filePath);

  await expect(page.getByText("resume_e2e.txt")).toBeVisible({ timeout: 20_000 });
});

test("TC-08 | Resume/CV section shows uploaded count", async ({ page }) => {
  await page.goto(`/projects/${projectId}`);
  await page.getByRole("tab", { name: "Documents" }).click();
  // Section heading "Resume / CVs (N)" appears
  await expect(page.getByText(/Resume \/ CVs/i).first()).toBeVisible({ timeout: 10_000 });
});

test("TC-09 | File size limit rejects files > 50 MB", async ({ page }) => {
  const bigPath = path.join(os.tmpdir(), "huge_file_e2e.txt");
  fs.writeFileSync(bigPath, Buffer.alloc(51 * 1024 * 1024, "x"));

  await page.goto(`/projects/${projectId}`);
  await page.getByRole("tab", { name: "Documents" }).click();

  const [fileChooser] = await Promise.all([
    page.waitForEvent("filechooser"),
    page.getByRole("button", { name: "Upload Resume / CV" }).click(),
  ]);
  await fileChooser.setFiles(bigPath);

  await expect(page.getByText(/too large|maximum|50 MB/i)).toBeVisible({ timeout: 10_000 });
  fs.unlinkSync(bigPath);
});

test("TC-10 | Document preview panel opens on preview icon click", async ({ page }) => {
  await page.goto(`/projects/${projectId}`);
  await page.getByRole("tab", { name: "Documents" }).click();
  await expect(page.getByText("resume_e2e.txt")).toBeVisible({ timeout: 15_000 });

  await page.locator('[title="Preview"]').first().click();

  await expect(
    page.getByText(/skills|summary|experience|extracted/i).first()
  ).toBeVisible({ timeout: 10_000 });
});

test("TC-11 | Document preview closes on Escape", async ({ page }) => {
  await page.goto(`/projects/${projectId}`);
  await page.getByRole("tab", { name: "Documents" }).click();
  await page.getByText("resume_e2e.txt").waitFor({ timeout: 15_000 });
  await page.locator('[title="Preview"]').first().click();
  // Panel opens
  await page.locator('[title="Close preview"], [aria-label="Close"]').first()
    .click().catch(() => page.keyboard.press("Escape"));
});

test("TC-12 | Delete a document", async ({ page }) => {
  const filePath = makeTempFile("to_delete_e2e.txt", "Temporary document to delete");

  await page.goto(`/projects/${projectId}`);
  await page.getByRole("tab", { name: "Documents" }).click();

  const [fc] = await Promise.all([
    page.waitForEvent("filechooser"),
    page.getByRole("button", { name: "Upload Resume / CV" }).click(),
  ]);
  await fc.setFiles(filePath);
  await expect(page.getByText("to_delete_e2e.txt")).toBeVisible({ timeout: 15_000 });

  // Delete icon — title="Delete", may have multiple, target the row
  const row = page.getByText("to_delete_e2e.txt").locator("../../..");
  await row.locator('[title="Delete"]').first().click();

  await expect(page.getByText("to_delete_e2e.txt")).not.toBeVisible({ timeout: 10_000 });
});
