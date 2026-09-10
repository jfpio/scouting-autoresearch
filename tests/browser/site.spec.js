import { test, expect } from '@playwright/test';
const base = '/scouting-autoresearch';
const mapURL = locale => `${base}/semantic-map/${locale}/`;
const engine = page => page.frames().find(f => /\/engine\.html/.test(f.url()));
const noOverflow = async page => expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);

for (const locale of ['pl', 'en']) {
  for (const theme of ['light', 'dark']) {
    for (const width of [360, 390, 768, 1440]) {
      test(`map ${locale} ${theme} ${width}px: usable list and working renderer`, async ({ page }, testInfo) => {
        const errors = [];
        page.on('pageerror', e => errors.push(e.message));
        await page.setViewportSize({ width, height: 900 });
        await page.addInitScript(theme => localStorage.setItem('starlight-theme', theme), theme);
        await page.goto(mapURL(locale));
        await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
        await noOverflow(page);
        await expect(page.locator('[data-map-list-item]')).toHaveCount(914);
        await expect(page.locator('[data-map-relation]')).toHaveCount(0);
        if (width < 768) {
          await expect(page.locator('body')).toHaveAttribute('data-view', 'list');
          await expect(page.locator('#map-engine')).not.toHaveAttribute('src', /engine/);
        }
        if (locale === 'pl' && theme === 'light' && [390,1440].includes(width)) {
          if (width === 1440) await expect(page.locator('#map-engine')).toHaveAttribute('data-state','ready');
          await page.screenshot({path:testInfo.outputPath(`map-${width}.png`)});
        }
        await page.locator('#map-search').fill('bsh-037');
        await expect(page.locator('#result-count')).toHaveText(/1 \/ 914/);
        await page.locator('[data-view-button=map]').click();
        await expect(page.locator('#map-engine')).toHaveAttribute('data-state', 'ready');
        const frame = engine(page);
        await expect(frame.locator('html')).toHaveAttribute('data-visible-points', '1');
        await expect(frame.locator('html')).toHaveAttribute('data-theme', theme);
        await expect(page.locator('#map-status')).toBeHidden();
        await page.locator('[data-view-button=list]').click();
        await expect(page.locator('[data-map-list-item]:visible')).toHaveCount(1);
        await expect(page.locator('[data-map-list-item]:visible a')).toHaveAttribute('href', new RegExp(`/${locale === 'en' ? 'en/' : ''}activities/bsh-037/`));
        if (width < 768) await page.locator('#open-panel').click();
        await page.locator('#region').selectOption('top-01');
        await expect(page.locator('#download')).toHaveAttribute('href', 'downloads/top/top-01.txt');
        const response = await page.request.get(`${mapURL(locale)}downloads/top/top-01.txt`);
        expect(response.ok()).toBe(true);
        expect(await response.text()).toContain('public-domain');
        if (width < 768) {
          await page.keyboard.press('Escape');
          await expect(page.locator('#open-panel')).toBeFocused();
        }
        await page.locator('#clear').click();
        await expect(page.locator('#result-count')).toHaveText(/914 \/ 914/);
        await page.locator('#map-search').fill('zzzz-no-such-game');
        await expect(page.locator('#empty')).toBeVisible();
        await expect(frame.locator('html')).toHaveAttribute('data-visible-points', '0');
        await noOverflow(page);
        expect(errors).toEqual([]);
      });
    }
  }
}

test('map selection opens details and zoom controls change the view', async ({ page }) => {
  await page.setViewportSize({width:1440,height:1000});
  await page.goto(mapURL('pl'));
  await expect(page.locator('#map-engine')).toHaveAttribute('data-state','ready');
  await page.locator('#map-search').fill('bsh-037');
  const frame = engine(page);
  await expect(frame.locator('html')).toHaveAttribute('data-visible-points','1');
  const startZoom = await frame.evaluate(() => window.datamap.deckgl.viewManager.getViewState().zoom);
  await page.locator('[data-map-action=zoom-in]').click();
  await expect.poll(() => frame.evaluate(() => window.datamap.deckgl.viewManager.getViewState().zoom)).toBeGreaterThan(startZoom);
  await page.locator('[data-map-action=reset]').click();
  const position = await frame.evaluate(() => {
    const d = window.datamap;
    const i = d.metaData.activity_id.indexOf('bsh-037');
    return d.deckgl.viewManager.getViewports()[0].project([d.pointData.x[i],d.pointData.y[i]]);
  });
  await frame.locator('canvas').click({position:{x:position[0],y:position[1]}});
  await expect(page.locator('#detail-link')).toHaveAttribute('href', `${base}/activities/bsh-037/`);
});

for (const failure of ['missing-data', 'webgl']) {
  test(`${failure}: recover to list and retry`, async ({ page }) => {
    await page.setViewportSize({width:390,height:844});
    if (failure === 'missing-data') await page.route('**/map_point_data_0.zip', route => route.fulfill({status:404,body:'missing'}));
    else await page.addInitScript(() => {
      const original = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function(kind, ...args) {
        return String(kind).includes('webgl') ? null : original.call(this,kind,...args);
      };
    });
    await page.goto(mapURL('pl'));
    await page.locator('[data-view-button=map]').click();
    await expect(page.locator('#map-engine')).toHaveAttribute('data-state','error');
    await expect(page.locator('#recovery')).toBeVisible();
    await page.locator('#fallback-list').click();
    await page.locator('#map-search').fill('bsh-037');
    await expect(page.locator('[data-map-list-item]:visible')).toHaveCount(1);
    if (failure === 'missing-data') {
      await page.unroute('**/map_point_data_0.zip');
      await page.locator('[data-view-button=map]').click();
      await page.locator('#retry').click();
      await expect(page.locator('#map-engine')).toHaveAttribute('data-state','ready');
    }
  });
}

test('slow renderer exits loading after 30 seconds', async ({ page }) => {
  await page.setViewportSize({width:390,height:844});
  await page.route('**/engine.html?*', route => route.fulfill({contentType:'text/html',body:'<!doctype html><title>Pending</title>'}));
  await page.goto(mapURL('en'));
  await page.clock.install();
  await page.locator('[data-view-button=map]').click();
  await page.clock.fastForward(31000);
  await expect(page.locator('#map-engine')).toHaveAttribute('data-state','error');
  await page.locator('#fallback-list').click();
  await expect(page.locator('[data-map-list-item]:visible')).toHaveCount(914);
});

test('mobile site navigation, filters, history and single titles', async ({ page }) => {
  await page.setViewportSize({width:390,height:844});
  await page.goto(`${base}/all/?query=Seton`);
  await expect(page.locator('h1')).toHaveCount(1);
  const initial = await page.locator('[data-count]').textContent();
  await expect(page.locator('.filter-grid')).toBeHidden();
  await page.locator('[data-toggle-filters]').click();
  await page.locator('[data-filter-menu=year] summary').click();
  await page.locator('input[data-filter=year][value="1911"]').check();
  await expect(page).toHaveURL(/year=1911/);
  await page.keyboard.press('Escape');
  await expect(page.locator('[data-toggle-filters]')).toBeFocused();
  await expect(page.locator('[data-selected-filters]')).toBeVisible();
  await page.locator('[data-clear]').click();
  await expect(page.locator('[data-count]')).not.toHaveText(initial);
  await page.locator('.menu-toggle').click();
  await expect(page.locator('.primary-tabs')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('.menu-toggle')).toBeFocused();
  await page.goto(`${base}/games/?query=bledny`);
  await page.goto(`${base}/sources/`);
  await page.goBack();
  await expect(page.locator('[data-query]')).toHaveValue('bledny');
  for (const route of ['', 'games/', 'trials/', 'courses/', 'sources/', 'authors/', 'about/', 'activities/bsh-037/', 'map/', 'en/map/']) {
    await page.goto(`${base}/${route}`);
    await expect(page.locator('h1')).toHaveCount(1);
    await noOverflow(page);
  }
});
