import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  // Capture console messages
  page.on('console', msg => console.log(`BROWSER CONSOLE: ${msg.type()} - ${msg.text()}`));
  page.on('pageerror', error => console.log(`BROWSER ERROR: ${error}`));
  
  await page.goto('http://localhost:3000/chat');
  await page.waitForLoadState('networkidle');
  
  console.log("Typing message...");
  await page.fill('textarea', 'Hello AI!');
  
  console.log("Pressing Enter...");
  await page.keyboard.press('Enter');
  
  console.log("Waiting 3 seconds...");
  await page.waitForTimeout(3000);
  
  console.log("Test finished.");
  await browser.close();
})();
