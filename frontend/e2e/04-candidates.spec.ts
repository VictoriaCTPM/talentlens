/**
 * E2E — Module 4: Candidates
 * - Candidate name in position table is a <Link href="/candidates/{id}">
 * - Add Candidate dialog: placeholder "Jane Smith" for name, button disabled until name filled
 * - Submit button text: "Add Candidate" (same as dialog title — use role="button" exact)
 */
import { test, expect } from "@playwright/test";
import { createProject, deleteProject, createPosition, createCandidate } from "./helpers";
import path from "path";
import fs from "fs";
import os from "os";

let projectId: number;
let positionId: number;

test.beforeAll(async () => {
  const p = await createProject("Candidates E2E", "Cand Client");
  projectId = p.id;
  const pos = await createPosition(projectId, "E2E Engineer Role");
  positionId = pos.id;
});

test.afterAll(async () => {
  await deleteProject(projectId).catch(() => {});
});

function makeTempFile(name: string, content: string): string {
  const filePath = path.join(os.tmpdir(), name);
  fs.writeFileSync(filePath, content);
  return filePath;
}

test("TC-23 | Add candidate with resume upload via UI", async ({ page }) => {
  // The Add Candidate dialog requires a resume file (upload mode) or existing doc selection.
  // Default mode is "existing"; with no docs available button is disabled until file uploaded.
  const resumePath = makeTempFile("cand_tc23.txt",
    "Name: John Doe\nSkills: JavaScript, TypeScript\nExperience: 2 years"
  );

  await page.goto(`/positions/${positionId}`);
  await page.getByRole("button", { name: /Add Candidate/i }).click();

  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();

  // Switch to "Upload resume" mode
  await dialog.getByText(/Upload/i).first().click();
  await dialog.getByPlaceholder("Jane Smith").fill("John Doe UI");

  // Upload file
  const fileInput = dialog.locator('input[type="file"]').first();
  await fileInput.setInputFiles(resumePath);

  const submitBtn = dialog.getByRole("button", { name: "Add Candidate" });
  await expect(submitBtn).toBeEnabled({ timeout: 5_000 });
  await submitBtn.click();

  await expect(dialog).not.toBeVisible();
  await expect(page.getByText("John Doe UI")).toBeVisible({ timeout: 10_000 });
});

test("TC-24 | Add second candidate with different resume", async ({ page }) => {
  const resumePath = makeTempFile("jane_resume.txt",
    "Name: Jane Smith\nSkills: Python, Django, PostgreSQL\nExperience: 4 years"
  );

  await page.goto(`/positions/${positionId}`);
  await page.getByRole("button", { name: /Add Candidate/i }).click();

  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();

  await dialog.getByText(/Upload/i).first().click();
  await dialog.getByPlaceholder("Jane Smith").fill("Jane Smith UI");

  const fileInput = dialog.locator('input[type="file"]').first();
  await fileInput.setInputFiles(resumePath);

  const submitBtn = dialog.getByRole("button", { name: "Add Candidate" });
  await expect(submitBtn).toBeEnabled({ timeout: 5_000 });
  await submitBtn.click();

  await expect(dialog).not.toBeVisible();
  await expect(page.getByText("Jane Smith UI")).toBeVisible({ timeout: 10_000 });
});

test("TC-25 | Candidate name is a link to profile", async ({ page }) => {
  const cand = await createCandidate(positionId, "Link Profile Cand");

  await page.goto(`/positions/${positionId}`);
  // Candidate name is a <Link href="/candidates/{id}">
  const candLink = page.locator(`a[href="/candidates/${cand.id}"]`).first();
  await expect(candLink).toBeVisible({ timeout: 10_000 });

  await Promise.all([
    page.waitForURL(`**/candidates/${cand.id}`),
    candLink.click(),
  ]);
  await expect(page.url()).toContain(`/candidates/${cand.id}`);
  await expect(page.getByText("Link Profile Cand").first()).toBeVisible();
});

test("TC-26 | Candidate profile shows status selector", async ({ page }) => {
  const cand = await createCandidate(positionId, "Status Selector Cand");
  await page.goto(`/candidates/${cand.id}`);
  await expect(page.getByRole("combobox").first()).toBeVisible();
});

test("TC-27 | Change candidate status to Screening", async ({ page }) => {
  const cand = await createCandidate(positionId, "Status Change Cand");
  await page.goto(`/candidates/${cand.id}`);

  await page.getByRole("combobox").first().click();
  await page.getByRole("option", { name: "Screening" }).click();

  await expect(page.getByText("Screening").first()).toBeVisible({ timeout: 5_000 });
});

test("TC-28 | Status change recorded and timeline appears after reload", async ({ page }) => {
  const cand = await createCandidate(positionId, "Timeline Cand");
  await page.goto(`/candidates/${cand.id}`);

  await page.getByRole("combobox").first().click();
  await page.getByRole("option", { name: "Screening" }).click();
  await new Promise((r) => setTimeout(r, 500));

  // Reload to get fresh timeline data
  await page.reload();
  await expect(page.getByText(/Activity Timeline/i)).toBeVisible({ timeout: 8_000 });
  await expect(page.getByText(/status changed/i)).toBeVisible({ timeout: 5_000 });
});

test("TC-29 | Edit recruiter notes inline", async ({ page }) => {
  const cand = await createCandidate(positionId, "Notes Cand");
  await page.goto(`/candidates/${cand.id}`);

  await page.getByText(/click to add notes/i).first().click();
  const textarea = page.locator("textarea").first();
  await textarea.fill("Good TypeScript skills, strong communicator");
  await textarea.blur();

  await expect(page.getByText("Good TypeScript skills, strong communicator")).toBeVisible({ timeout: 5_000 });
});

test("TC-30 | Rejection reason card appears when status = Rejected", async ({ page }) => {
  const cand = await createCandidate(positionId, "Reject Me Cand");
  await page.goto(`/candidates/${cand.id}`);

  await page.getByRole("combobox").first().click();
  await page.getByRole("option", { name: "Rejected" }).click();

  await expect(page.getByText(/Rejection Reason/i)).toBeVisible({ timeout: 5_000 });
});

test("TC-31 | AI score button disabled when no resume", async ({ page }) => {
  const cand = await createCandidate(positionId, "No Resume AI Cand");
  await page.goto(`/candidates/${cand.id}`);
  await expect(page.getByRole("button", { name: /re-analyze/i })).toBeDisabled();
});

test("TC-32 | Margin calculator saves rates", async ({ page }) => {
  const cand = await createCandidate(positionId, "Margin Cand");
  await page.goto(`/candidates/${cand.id}`);

  await page.locator('input[placeholder="0"]').first().fill("5000");
  await page.getByRole("button", { name: "Save Rates" }).click();

  await expect(
    page.getByText(/margin|missing.*rate/i).first()
  ).toBeVisible({ timeout: 8_000 });
});

test("TC-33 | Delete candidate via trash icon", async ({ page }) => {
  const cand = await createCandidate(positionId, "Delete Me Cand");

  await page.goto(`/positions/${positionId}`);
  await expect(page.getByText("Delete Me Cand")).toBeVisible({ timeout: 10_000 });

  // Find the specific row for this candidate and click its trash icon
  // Candidate name is a <Link>, its parent <td> is the name cell
  const candidateLink = page.locator(`a[href="/candidates/${cand.id}"]`);
  const candidateRow = candidateLink.locator("../.."); // a → td → tr
  await candidateRow.locator('[title="Remove candidate"]').click();

  await new Promise((r) => setTimeout(r, 1_500));
  await page.reload();
  await expect(page.getByText("Delete Me Cand")).not.toBeVisible({ timeout: 10_000 });
});

test("TC-34 | Non-existent candidate shows error state", async ({ page }) => {
  await page.goto("/candidates/999999");
  await expect(page.getByText(/not found|go back/i).first()).toBeVisible({ timeout: 8_000 });
});
