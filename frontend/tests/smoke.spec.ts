import { expect, test } from "@playwright/test";

const PAGES = [
  ["/", "Dashboard"],
  ["/icp", "ICP"],
  ["/sender", "Sender"],
  ["/leads", "Leads"],
  ["/tam", "TAM"],
  ["/feed", "Signal Feed"],
  ["/compose", "AI Composer"],
  ["/sequences", "Sequences"],
  ["/analytics", "Analytics"],
] as const;

for (const [path, heading] of PAGES) {
  test(`renders ${path}`, async ({ page }) => {
    await page.goto(path);
    await expect(
      page.getByRole("heading", { name: new RegExp(heading, "i") }),
    ).toBeVisible();
  });
}
