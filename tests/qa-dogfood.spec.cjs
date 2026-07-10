import { expect, test } from "@playwright/test";

test("local QA fixture supports navigation, form interaction, and console checks", async ({ page }) => {
  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.goto("http://127.0.0.1:4173");
  await expect(page.getByRole("heading", { name: "Codex QA Dogfood" })).toBeVisible();
  await page.getByLabel("Name").fill("Codex");
  await page.getByRole("button", { name: "Submit" }).click();
  await expect(page.getByText("Submitted")).toBeVisible();
  expect(consoleErrors).toEqual([]);
});
