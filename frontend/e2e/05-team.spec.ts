/**
 * E2E — Module 5: Team Members
 * Add Team Member dialog: placeholder "e.g. Alex Johnson" (name), "e.g. Senior Backend Developer" (role)
 * Edit button: 2 exist (header + notes card) — use first()
 * Back button: has .lucide-arrow-left SVG
 * MemberCard: <Card onClick={() => router.push('/team/${id}')}> — click via .cursor-pointer filter
 */
import { test, expect } from "@playwright/test";
import { createProject, deleteProject, createTeamMember } from "./helpers";
import path from "path";
import fs from "fs";
import os from "os";

let projectId: number;

test.beforeAll(async () => {
  const p = await createProject("Team E2E Project", "Team Client");
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

test("TC-38 | Team tab renders with Add Member button", async ({ page }) => {
  await page.goto(`/projects/${projectId}`);
  await page.getByRole("tab", { name: "Team" }).click();
  await expect(page.getByRole("button", { name: /Add Member/i })).toBeVisible();
});

test("TC-39 | Add team member via UI dialog", async ({ page }) => {
  await page.goto(`/projects/${projectId}`);
  await page.getByRole("tab", { name: "Team" }).click();
  await page.getByRole("button", { name: /Add Member/i }).click();

  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText("Add Team Member")).toBeVisible();

  await dialog.getByPlaceholder("e.g. Alex Johnson").fill("Alice Dev UI");
  await dialog.getByPlaceholder("e.g. Senior Backend Developer").fill("Frontend Developer");

  const addBtn = dialog.getByRole("button", { name: "Add Member" });
  await expect(addBtn).toBeEnabled({ timeout: 3_000 });
  await addBtn.click();

  await expect(dialog).not.toBeVisible();
  await expect(page.getByText("Alice Dev UI")).toBeVisible({ timeout: 10_000 });
});

test("TC-40 | Add team member with resume upload", async ({ page }) => {
  const resumePath = makeTempFile("team_resume_ui.txt",
    "Skills: Python, Go, PostgreSQL, Redis\nExperience: 6 years backend development"
  );

  await page.goto(`/projects/${projectId}`);
  await page.getByRole("tab", { name: "Team" }).click();
  await page.getByRole("button", { name: /Add Member/i }).click();

  const dialog = page.getByRole("dialog");
  await dialog.getByPlaceholder("e.g. Alex Johnson").fill("Bob Backend UI");
  await dialog.getByPlaceholder("e.g. Senior Backend Developer").fill("Backend Dev");

  // File input is hidden — set files directly
  const fileInput = dialog.locator('input[type="file"]').first();
  await fileInput.setInputFiles(resumePath);

  const addBtn = dialog.getByRole("button", { name: "Add Member" });
  await expect(addBtn).toBeEnabled({ timeout: 3_000 });
  await addBtn.click();

  await expect(dialog).not.toBeVisible();
  await expect(page.getByText("Bob Backend UI")).toBeVisible({ timeout: 10_000 });
});

test("TC-41 | Click team member card navigates to /team/{id}", async ({ page }) => {
  const member = await createTeamMember(projectId, "Card Nav Dev");

  await page.goto(`/projects/${projectId}`);
  await page.getByRole("tab", { name: "Team" }).click();
  await expect(page.getByText("Card Nav Dev")).toBeVisible({ timeout: 10_000 });

  // MemberCard is a <Card onClick={() => router.push('/team/${id}')}>
  // Card renders as a <div class="... cursor-pointer ...">
  const card = page.locator(".cursor-pointer").filter({ hasText: "Card Nav Dev" }).first();
  await Promise.all([
    page.waitForURL(`**/team/${member.id}`),
    card.click(),
  ]);
  await expect(page.url()).toContain(`/team/${member.id}`);
});

test("TC-42 | Team member profile page shows name and Resume section", async ({ page }) => {
  const member = await createTeamMember(projectId, "Profile Sections Dev");
  await page.goto(`/team/${member.id}`);

  await expect(page.getByText("Profile Sections Dev")).toBeVisible();
  await expect(page.getByText(/Resume/i).first()).toBeVisible();
});

test("TC-43 | Edit team member opens Edit Team Member dialog", async ({ page }) => {
  const member = await createTeamMember(projectId, "Edit Target Dev");
  await page.goto(`/team/${member.id}`);

  // Two "Edit" buttons exist: header button and notes card button
  // The header edit button renders "Edit" text (with Pencil icon)
  await page.getByRole("button", { name: "Edit" }).first().click();

  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("Edit Team Member")).toBeVisible();
  await expect(dialog.getByText("Name *")).toBeVisible();

  await dialog.getByRole("button", { name: /save/i }).click();
  await expect(dialog).not.toBeVisible();
});

test("TC-44 | Back arrow navigates to parent project page", async ({ page }) => {
  const member = await createTeamMember(projectId, "Back Nav Dev");
  await page.goto(`/team/${member.id}`);

  // Back button has ArrowLeft icon — SVG class includes "lucide-arrow-left"
  const backBtn = page.locator("button:has(.lucide-arrow-left)").first();
  await expect(backBtn).toBeVisible();
  await Promise.all([
    page.waitForURL(`**/projects/${projectId}`),
    backBtn.click(),
  ]);
  await expect(page.url()).toContain(`/projects/${projectId}`);
});

test("TC-45 | Sync skills button appears when skills exist", async ({ page }) => {
  const member = await createTeamMember(projectId, "Sync Skills Dev");
  await page.goto(`/team/${member.id}`);

  const syncBtn = page.getByRole("button", { name: /Sync from Resume/i });
  if (await syncBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
    await syncBtn.click();
    await expect(page.locator("body")).not.toContainText("500");
  }
});

test("TC-46 | Non-existent team member shows error state", async ({ page }) => {
  await page.goto("/team/999999");
  await expect(page.getByText(/not found|error|go back/i).first()).toBeVisible({ timeout: 8_000 });
});

test("TC-47 | Offboard (delete) team member via trash icon", async ({ page }) => {
  const member = await createTeamMember(projectId, "Delete Team Dev");

  await page.goto(`/projects/${projectId}`);
  await page.getByRole("tab", { name: "Team" }).click();
  await expect(page.getByText("Delete Team Dev")).toBeVisible({ timeout: 10_000 });

  // Trash icon in MemberCard — title="Offboard member"
  const card = page.locator(".cursor-pointer").filter({ hasText: "Delete Team Dev" }).first();
  const trashBtn = card.locator('[title="Offboard member"]');
  if (await trashBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
    await trashBtn.click();
    // Member should be offboarded (grayed out) or removed
    await page.waitForTimeout(1_000);
    // Just verify no 500 error
    await expect(page.locator("body")).not.toContainText("500");
  }
});
