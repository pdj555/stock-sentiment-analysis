const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const path = require('path');

test.use({ browserName: 'chromium' });


function startServer() {
  return new Promise((resolve, reject) => {
    const serverPath = path.join(__dirname, 'ui_browser_server.py');
    const python = process.env.PYTHON || 'python3';
    const server = spawn(python, [serverPath], {
      cwd: path.join(__dirname, '..'),
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    let stderr = '';
    const timeout = setTimeout(() => {
      server.kill('SIGTERM');
      reject(new Error(`Timed out waiting for UI browser fixture server.\n${stderr}`));
    }, 10000);

    server.stdout.on('data', (chunk) => {
      const line = chunk.toString().trim();
      if (!line.startsWith('http://')) {
        return;
      }
      clearTimeout(timeout);
      resolve({ server, url: line });
    });

    server.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });

    server.on('exit', (code) => {
      clearTimeout(timeout);
      if (code === 0 || code === null) {
        return;
      }
      reject(new Error(`UI browser fixture server exited with code ${code}.\n${stderr}`));
    });
  });
}


async function stopServer(server) {
  if (!server || server.exitCode !== null) {
    return;
  }
  await new Promise((resolve) => {
    server.once('exit', resolve);
    server.kill('SIGTERM');
  });
}


test('local UI happy path renders analyzed result', async ({ page }) => {
  test.setTimeout(30000);
  const { server, url } = await startServer();

  try {
    await page.goto(url);
    await page.fill('#ticker', 'tsla');
    await page.click('#submit-button');

    await expect(page.locator('.summary-grid')).toBeVisible();
    await expect(page.locator('#summary')).toContainText('TSLA');
    await expect(page.locator('#summary')).toContainText('buy');
    await expect(page.locator('#status-line')).toContainText('Google News RSS');
    await expect(page.locator('#status-line')).toContainText('3-day lookback');
    await expect(page.locator('#status-line')).toContainText('1 of 18 articles analyzed');
    await expect(page.locator('.article-title')).toContainText('Example article for TSLA');
    await expect(page.locator('.article-reason')).toContainText('Demand outlook improved.');
    await expect(page.locator('.badge')).toHaveText('positive');
    await expect(page.locator('#submit-button')).toBeEnabled();
  } finally {
    await stopServer(server);
  }
});
