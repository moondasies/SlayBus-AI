// End-to-end user test: drives a real browser through the whole teacher journey.
//
// Needs: agent on :8000 (LLM_PROVIDER=fake or gemini, DEV_AUTH=true) and the
// frontend on :3000 (NEXT_PUBLIC_DEV_AUTH=true). Then:
//   SAMPLE_PDF=/path/to/book.pdf node e2e/user-journey.mjs
// Screenshots go to $SHOTS_DIR (default ./e2e/screenshots).

import { mkdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { chromium, devices } from "playwright";

const BASE = process.env.BASE_URL || "http://localhost:3000";
const PDF = process.env.SAMPLE_PDF;
const SHOTS = process.env.SHOTS_DIR || "e2e/screenshots";
const AI_TIMEOUT = Number(process.env.AI_TIMEOUT_MS || 180000); // real Gemini is slower than the fake
if (!PDF) throw new Error("Set SAMPLE_PDF to a textbook PDF (agent/scripts/make_sample_textbook.py makes one)");
mkdirSync(SHOTS, { recursive: true });

const run = Date.now().toString(36);
const results = [];
const problems = [];
let allowErrors = null; // regex of errors a step triggers on purpose

async function step(name, fn) {
  const t = Date.now();
  try {
    await fn();
    results.push(`✅ ${name} (${((Date.now() - t) / 1000).toFixed(1)}s)`);
  } catch (e) {
    results.push(`❌ ${name}: ${e.message.split("\n")[0]}`);
    throw e;
  }
}

function expect(cond, msg) {
  if (!cond) throw new Error(msg);
}

function watch(page, label) {
  const report = (msg) => !(allowErrors && allowErrors.test(msg)) && problems.push(`[${label}] ${msg}`);
  page.on("console", (m) => m.type() === "error" && report(`console: ${m.text()}`));
  page.on("pageerror", (e) => report(`page error: ${e.message}`));
  page.on("response", (r) => r.status() >= 400 && report(`HTTP ${r.status()} ${r.request().method()} ${r.url()}`));
}

const shot = (page, name) => page.screenshot({ path: join(SHOTS, `${name}.png`), fullPage: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 }, acceptDownloads: true });
const page = await ctx.newPage();
watch(page, "teacher");
let paperUrl = "";

try {
  await step("Landing page loads with tagline", async () => {
    await page.goto(BASE);
    await page.getByText("Powered by your syllabus.").first().waitFor();
    await shot(page, "01-landing");
    await page.getByRole("link", { name: "Start free" }).click();
    await page.waitForURL(/\/login/);
  });

  await step("Log in (dev mode) as a new teacher", async () => {
    await page.getByLabel("Email").fill(`asha.${run}@school.in`);
    await shot(page, "02-login");
    await page.getByRole("button", { name: "Continue" }).click();
    await page.waitForURL(/\/onboarding/);
  });

  await step("Onboarding", async () => {
    await page.getByLabel("Your name").fill("Asha Sharma");
    await page.getByLabel(/School/).fill("Green Valley School");
    await page.getByLabel("Board").selectOption("CBSE");
    await page.getByRole("group", { name: "Classes" }).getByRole("button", { name: "7", exact: true }).click();
    await page.getByRole("group", { name: "Subjects" }).getByRole("button", { name: "Science", exact: true }).click();
    await shot(page, "03-onboarding");
    await page.getByRole("button", { name: "Continue to dashboard" }).click();
    await page.waitForURL(/\/dashboard/);
    await page.getByText("Namaste, Asha").waitFor();
    await page.getByText("Upload your first textbook").waitFor();
    await shot(page, "04-dashboard-empty");
  });

  await step("Upload a textbook PDF", async () => {
    await page.getByRole("link", { name: /Upload book/ }).first().click();
    await page.waitForURL(/\/books\/new/);
    await page.getByTestId("file-input").setInputFiles(PDF);
    await page.getByLabel("Book title").fill("Science Explorer");
    await page.getByLabel("Class").fill("7");
    await shot(page, "05-upload");
    await page.getByRole("button", { name: "Upload & process" }).click();
    await page.waitForURL(/\/books\/[0-9a-f-]{36}$/);
  });

  await step("Book is processed and chapters are listed", async () => {
    await page.getByText(/Ready\. \d+ chapters found/).waitFor({ timeout: AI_TIMEOUT });
    const chapters = await page.locator("ol li").count();
    expect(chapters >= 2, `expected chapters, got ${chapters}`);
    await shot(page, "06-book-ready");
  });

  await step("Create a 50-mark paper across all chapters", async () => {
    await page.getByRole("link", { name: "Create paper" }).last().click();
    await page.waitForURL(/\/papers\/new/);
    await page.getByRole("button", { name: "Select all" }).waitFor();
    await page.getByRole("button", { name: "Select all" }).click();
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByLabel(/Title/).fill(`Periodic Test ${run}`);
    await shot(page, "07-paper-type");
    await page.getByRole("button", { name: "Next" }).click();
    const total = await page.getByTestId("total-marks").innerText();
    expect(total.includes("50") && total.includes("29 questions"), `blueprint total was "${total}"`);
    await shot(page, "08-blueprint");
    // the form must block an invalid difficulty mix
    await page.getByLabel("easy (%)").fill("90");
    await page.getByText(/must be 100%/).waitFor();
    expect(await page.getByRole("button", { name: "Next" }).isDisabled(), "Next should be disabled when mix != 100");
    await page.getByLabel("easy (%)").fill("30");
    await page.getByRole("button", { name: "Next" }).click();
    await shot(page, "09-review");
    await page.getByRole("button", { name: "Generate paper" }).click();
    await page.waitForURL(/\/papers\/[0-9a-f-]{36}$/);
    paperUrl = page.url();
  });

  await step("Paper is generated with every question traceable to a page", async () => {
    await page.getByTestId("paper-summary").waitFor({ timeout: AI_TIMEOUT });
    const summary = await page.getByTestId("paper-summary").innerText();
    const cards = page.getByTestId("question-card");
    const n = await cards.count();
    expect(n >= 25, `expected ~29 questions, got ${n} (${summary})`);
    const withSource = await page.locator("[data-testid=question-card] button[title='Show the textbook passage']").count();
    expect(withSource === n, `only ${withSource}/${n} questions show a source page`);
    await shot(page, "10-editor");
  });

  await step("Show source passage", async () => {
    await page.getByTitle("Show the textbook passage").first().click();
    await page.getByRole("dialog", { name: "From your textbook" }).getByText(/PDF page \d+/).first().waitFor();
    await shot(page, "11-source");
    await page.keyboard.press("Escape");
  });

  await step("Edit a question", async () => {
    const card = page.getByTestId("question-card").nth(10);
    await card.getByRole("button", { name: "Edit" }).click();
    await card.getByLabel("Question").fill("What is the full form of the blank in this edited question ______?");
    await card.getByLabel("Answer").fill("Edited answer");
    await card.getByRole("button", { name: "Save" }).click();
    await card.getByText("edited question").waitFor();
  });

  await step("Invalid MCQ edit is rejected with a clear message", async () => {
    allowErrors = /422/;
    const card = page.getByTestId("question-card").first();
    await card.getByRole("button", { name: "Edit" }).click();
    await card.getByLabel("Option b", { exact: true }).fill(await card.getByLabel("Option a", { exact: true }).inputValue());
    await card.getByRole("button", { name: "Save" }).click();
    await card.getByText(/distinct/).waitFor();
    await shot(page, "12-mcq-validation");
    await card.getByRole("button", { name: "Cancel" }).click();
    allowErrors = null;
  });

  await step("Regenerate one question", async () => {
    const card = page.getByTestId("question-card").nth(20);
    const before = await card.getByTestId("question-text").innerText();
    await card.getByRole("button", { name: "Regenerate" }).click();
    await page.getByRole("dialog").getByLabel("Difficulty").selectOption("hard");
    await page.getByRole("dialog").getByRole("button", { name: "Regenerate" }).click();
    await page.getByText(/regenerated/).waitFor({ timeout: AI_TIMEOUT });
    const after = await card.getByTestId("question-text").innerText();
    expect(before !== after, "question text did not change");
  });

  await step("Reorder questions", async () => {
    const first = await page.getByTestId("question-text").nth(0).innerText();
    await page.getByTestId("question-card").nth(1).getByRole("button", { name: "Move up" }).click();
    await page.waitForTimeout(500);
    const nowSecond = await page.getByTestId("question-text").nth(1).innerText();
    expect(first === nowSecond, "move up did not swap questions");
    await page.reload();
    await page.getByTestId("paper-summary").waitFor();
    expect((await page.getByTestId("question-text").nth(1).innerText()) === first, "order was not saved");
  });

  await step("Delete a question, then add it back from the bank", async () => {
    const n = await page.getByTestId("question-card").count();
    page.once("dialog", (d) => d.accept());
    await page.getByTestId("question-card").last().getByRole("button", { name: "Delete" }).click();
    await page.waitForFunction((c) => document.querySelectorAll("[data-testid=question-card]").length === c - 1, n);
    await page.getByRole("button", { name: "Add from bank" }).last().click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: "Add" }).first().click();
    await page.waitForFunction((c) => document.querySelectorAll("[data-testid=question-card]").length === c, n);
  });

  await step("Preview and download PDF + DOCX (with answer key)", async () => {
    await page.getByRole("tab", { name: /preview/ }).click();
    await page.getByTestId("paper-preview").waitFor();
    await shot(page, "13-preview");
    for (const fmt of ["PDF", "DOCX"]) {
      const [dl] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: fmt }).click()]);
      const path = join(SHOTS, `paper.${fmt.toLowerCase()}`);
      await dl.saveAs(path);
      expect(statSync(path).size > 2000, `${fmt} file too small`);
      if (fmt === "PDF") expect(readFileSync(path).subarray(0, 4).toString() === "%PDF", "not a PDF");
    }
    await page.getByLabel("Answer key").uncheck();
    const [dl] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "PDF" }).click()]);
    expect(!dl.suggestedFilename().includes("with-answers"), "answer key toggle ignored");
  });

  await step("Question bank search and filter", async () => {
    await page.getByRole("link", { name: "Question bank" }).first().click();
    await page.getByTestId("bank-total").waitFor();
    await page.getByLabel("Question type").selectOption("mcq");
    await page.waitForTimeout(600);
    const total = await page.getByTestId("bank-total").innerText();
    expect(/^\d+ question/.test(total), `bank total: ${total}`);
    await shot(page, "14-bank");
  });

  await step("Dashboard lists the book and the paper", async () => {
    await page.getByRole("link", { name: "Dashboard" }).first().click();
    await page.getByText(`Periodic Test ${run}`).waitFor();
    await shot(page, "15-dashboard");
  });

  await step("Privacy: another teacher cannot see this paper", async () => {
    allowErrors = /404/;
    const other = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const p2 = await other.newPage();
    watch(p2, "other-teacher");
    await p2.goto(`${BASE}/login`);
    await p2.getByLabel("Email").fill(`ravi.${run}@school.in`);
    await p2.getByRole("button", { name: "Continue" }).click();
    await p2.waitForURL(/\/onboarding/);
    await p2.getByLabel("Your name").fill("Ravi");
    await p2.getByRole("button", { name: "Continue to dashboard" }).click();
    await p2.getByText("Upload your first textbook").waitFor();
    await p2.goto(paperUrl);
    await p2.getByText("Paper not found").waitFor();
    await other.close();
    allowErrors = null;
  });

  await step("Mobile layout (iPhone 13)", async () => {
    const m = await browser.newContext({ ...devices["iPhone 13"] });
    const mp = await m.newPage();
    watch(mp, "mobile");
    await mp.goto(BASE);
    await mp.evaluate((s) => localStorage.setItem("slaybus.devSession", s), await page.evaluate(() => localStorage.getItem("slaybus.devSession")));
    await mp.goto(paperUrl);
    await mp.getByTestId("paper-summary").waitFor();
    const overflow = await mp.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    expect(!overflow, "page scrolls sideways on mobile");
    await mp.screenshot({ path: join(SHOTS, "16-mobile-editor.png") });
    await m.close();
  });

  await step("Log out", async () => {
    await page.getByRole("button", { name: "Log out" }).click();
    await page.waitForURL(/\/login/);
  });
} catch {
  await shot(page, "zz-failure").catch(() => {});
} finally {
  await browser.close();
  console.log("\nSLAYBUS user journey\n" + results.join("\n"));
  if (problems.length) console.log("\nProblems seen in the browser:\n" + [...new Set(problems)].join("\n"));
  const failed = results.some((r) => r.startsWith("❌")) || problems.length > 0;
  console.log(failed ? "\nRESULT: FAIL" : "\nRESULT: PASS");
  process.exit(failed ? 1 : 0);
}
