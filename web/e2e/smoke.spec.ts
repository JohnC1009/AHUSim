// M3 gate: build the §6.1 unit from a blank project and reach a summer-design result.
import { expect, test, type Page } from "@playwright/test";

async function add(page: Page, slots: string[], label: string) {
  for (const s of slots) await page.getByTestId(s).click();
  await page.locator(".palette li", { hasText: label }).first().click();
}

test("build the §6.1 unit from blank and get a summer-design result", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));

  await page.goto("/projects");
  await page.getByLabel("New project name").fill("Smoke test");
  await page.getByRole("button", { name: "Create project" }).click();
  await page.getByLabel("New unit name").fill("AHU-1");
  await page.getByRole("button", { name: "New blank unit" }).click();

  // Supply: oa, erw1.supply, mix1, flt1, hc1, cc1, hc2, sf1. Return: ra, rf1, mix1, erw1.exhaust, ef1.
  await add(page, ["slot-supply-1"], "Fan");
  await add(page, ["slot-supply-1", "slot-return-1"], "Mixing box");
  await add(page, ["slot-return-1"], "Fan");
  await add(page, ["slot-supply-1", "slot-return-3"], "Energy wheel");
  await add(page, ["slot-return-4"], "Fan");
  await add(page, ["slot-supply-3"], "Filter");
  await add(page, ["slot-supply-4"], "Heating coil (HW)");
  await add(page, ["slot-supply-5"], "Cooling coil (CHW)");
  await add(page, ["slot-supply-6"], "Heating coil (HW)");
  for (const id of ["erw1", "mix1", "flt1", "hc1", "cc1", "hc2", "sf1", "rf1", "ef1"]) {
    await expect(page.getByTestId(`node-${id}`)).toBeVisible();
  }

  await page.locator(".react-flow__pane").click({ position: { x: 5, y: 5 } });
  await page.getByLabel("Altitude", { exact: true }).fill("33");
  await page.getByLabel("Minimum OA", { exact: true }).fill("3000");
  await page.getByLabel("Pressurization bias", { exact: true }).fill("200");
  await page.getByRole("button", { name: "+ Sensor" }).click();
  await page.getByLabel("Sensor id").fill("SAT");
  await page.getByLabel("SAT location").selectOption("after:sf1");

  await page.getByRole("link", { name: "Sequence" }).click();
  await page.getByRole("button", { name: "+ Loop" }).click();
  await page.getByLabel("Loop sensor").selectOption("SAT");
  await page.getByLabel("Stage 1 actuator").selectOption("cc1.valve");
  await page.getByRole("button", { name: "+ Mode" }).click();
  await page.getByLabel("Run loop loop1").check();

  await page.getByRole("link", { name: "Conditions" }).click();
  await page.getByRole("button", { name: "+ Condition" }).click();
  await page.getByLabel("Condition id").fill("summer_design");

  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("unsaved")).toBeHidden();
  await page.reload();
  await page.getByRole("link", { name: "Unit", exact: true }).click();
  await expect(page.getByTestId("node-cc1")).toBeVisible(); // the unit came back from the database
  await expect(page.getByText("v2")).toBeVisible();
  await page.getByRole("combobox", { name: "Condition", exact: true }).selectOption("summer_design");
  await page.getByRole("button", { name: "Run", exact: true }).click();

  const sat = page.getByRole("row", { name: /after sf1/ });
  await expect(sat).toBeVisible({ timeout: 20_000 });
  const db = Number((await sat.locator("td").nth(1).innerText()).trim());
  expect(db).toBeGreaterThan(56);
  expect(db).toBeLessThan(59.5); // ~57.8 °F: the coil cannot make 55 °F after fan heat
  await expect(page.locator(".failure-strip")).toContainText("cannot hold SAT at 55.0 °F");
  await expect(page.locator(".failure-strip")).toContainText("mix1.ra");
  await expect(page.getByRole("img", { name: "Psychrometric chart" })).toBeVisible();
  expect(errors).toEqual([]);
});
