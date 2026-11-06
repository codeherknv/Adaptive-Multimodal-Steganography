import puppeteer from 'puppeteer-core';
import path from 'path';
import fs from 'fs';

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const SAMPLE_DIR = 'C:\\Users\\91701\\OneDrive\\Desktop\\Adaptive Steganography\\scratch\\sample_triad';
const OUT_DIR = 'C:\\Users\\91701\\OneDrive\\Desktop\\Adaptive Steganography\\scratch';
const ARTIFACT_DIR = 'C:\\Users\\91701\\.gemini\\antigravity-cli\\brain\\c624d88c-4faa-4af8-9929-66471fb6be86';

const imgFile = path.join(SAMPLE_DIR, 'sample_cover.png');
const audFile = path.join(SAMPLE_DIR, 'sample_cover.wav');
const vidFile = path.join(SAMPLE_DIR, 'sample_cover.avi');

async function run() {
  console.log('Launching Chrome from:', CHROME_PATH);
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1400,1200'],
    defaultViewport: { width: 1400, height: 1200 },
  });

  const page = await browser.newPage();
  console.log('Navigating to http://localhost:5173/...');
  await page.goto('http://localhost:5173/', { waitUntil: 'networkidle0' });

  // 1. Upload files in Step 1
  console.log('Uploading carrier files...');
  const fileInputs = await page.$$('input[type="file"]');
  console.log(`Found ${fileInputs.length} file inputs on initial page`);

  if (fileInputs.length >= 3) {
    await fileInputs[0].uploadFile(imgFile);
    await fileInputs[1].uploadFile(audFile);
    await fileInputs[2].uploadFile(vidFile);
    console.log('Uploaded image, audio, video carriers.');
  }

  // 2. Set message text
  console.log('Entering secret message...');
  const msgSelector = 'textarea#multimodal-msg';
  await page.waitForSelector(msgSelector);
  await page.focus(msgSelector);
  await page.keyboard.type('Classified Multimodal Payload for Live Cross-Strategy Benchmark Verification (AES-256-GCM)');

  // 3. Click the Portfolio (Markowitz) strategy card to show its novel badge and lambda slider
  console.log('Selecting Portfolio (Markowitz) card...');
  const buttons = await page.$$('button');
  for (const btn of buttons) {
    const text = await page.evaluate(el => el.textContent, btn);
    if (text && text.includes('Portfolio (Markowitz)')) {
      await btn.click();
      console.log('Clicked Portfolio card');
      break;
    }
  }

  // Wait a moment for re-render and slider reveal
  await new Promise(r => setTimeout(r, 1000));

  // Take Screenshot 1: Expanded 8-card grid
  const shot1Path = path.join(OUT_DIR, 'expanded_8card_grid.png');
  await page.screenshot({ path: shot1Path, fullPage: false });
  console.log('Screenshot 1 captured:', shot1Path);

  // Copy to artifacts dir
  fs.copyFileSync(shot1Path, path.join(ARTIFACT_DIR, 'expanded_8card_grid.png'));

  // 4. Click "Compare All 8 Strategies" button
  console.log('Navigating to Strategy Comparison...');
  const compareButtons = await page.$$('button');
  for (const btn of compareButtons) {
    const text = await page.evaluate(el => el.textContent, btn);
    if (text && text.includes('Compare All 8 Strategies')) {
      await btn.click();
      console.log('Clicked "Compare All 8 Strategies" button');
      break;
    }
  }

  // Wait for the comparison API call to finish and render the table
  console.log('Waiting for live strategy comparison table...');
  await page.waitForSelector('table', { timeout: 15000 });
  await new Promise(r => setTimeout(r, 2000));

  // Scroll table into view
  await page.evaluate(() => {
    const el = document.querySelector('table');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  });

  await new Promise(r => setTimeout(r, 1000));

  // Take Screenshot 2: Comparison table & chart
  const shot2Path = path.join(OUT_DIR, 'strategy_comparison_table.png');
  await page.screenshot({ path: shot2Path, fullPage: false });
  console.log('Screenshot 2 captured:', shot2Path);

  // Copy to artifacts dir
  fs.copyFileSync(shot2Path, path.join(ARTIFACT_DIR, 'strategy_comparison_table.png'));

  // Full page view
  const shot3Path = path.join(OUT_DIR, 'full_comparison_view.png');
  await page.screenshot({ path: shot3Path, fullPage: true });
  fs.copyFileSync(shot3Path, path.join(ARTIFACT_DIR, 'full_comparison_view.png'));
  console.log('Full page screenshot captured:', shot3Path);

  await browser.close();
  console.log('All screenshots captured successfully!');
}

run().catch(err => {
  console.error('Error during screenshot capture:', err);
  process.exit(1);
});
