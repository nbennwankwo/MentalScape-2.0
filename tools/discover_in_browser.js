// List every MHSDS Monthly Statistics download card, from a normal browser.
//
// NHS England's pages challenge cloud servers, so the GitHub Actions runner
// cannot read them (docs/adr/0011). This script does the reading part from a
// browser session instead. It mirrors parse_series_page and parse_release_page
// in src/mentalscape/ingest/nhs_pages.py and only extracts what is on the page.
// Classification stays in Python.
//
// Use it by opening the series page in a browser, pasting this into the
// developer console, and keeping the mhsds_cards.json file it saves. Then run
//   uv run python -m mentalscape.ingest.mhsds classify --cards mhsds_cards.json
(async () => {
  const series = '/data-and-information/publications/statistical/mental-health-services-monthly-statistics';
  const firstYear = 2022;
  const clean = (text) => (text || '').replace(/\s+/g, ' ').trim();
  const pages = new Map();
  for (const a of document.querySelectorAll('a[href][title]')) {
    const href = new URL(a.getAttribute('href'), location.origin);
    const title = clean(a.getAttribute('title'));
    if (title.startsWith('Mental Health Services Monthly Statistics') && href.pathname.startsWith(series + '/')) {
      const years = (title.match(/\b20\d\d\b/g) || []).map(Number);
      if (!years.length || Math.max(...years) >= firstYear) pages.set(href.href, title);
    }
  }
  const cards = [];
  for (const [pageUrl, listedTitle] of pages) {
    const response = await fetch(pageUrl);
    if (!response.ok) continue;
    const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
    const h1 = doc.querySelector('h1');
    for (const card of doc.querySelectorAll('div.nhsd-m-download-card')) {
      const link = card.querySelector('a[href]');
      if (!link) continue;
      const url = new URL(link.getAttribute('href'), location.origin);
      if (url.host !== 'files.digital.nhs.uk') continue;
      cards.push({
        page_url: pageUrl,
        page_title: h1 ? clean(h1.textContent) : listedTitle,
        card_title: clean((card.querySelector('p') || link).textContent),
        source_url: link.getAttribute('href'),
        original_filename: decodeURIComponent(url.pathname.split('/').pop()),
        file_type: clean((card.querySelector('.nhsd-a-tag--meta') || {}).textContent).toLowerCase(),
        size_text: clean((card.querySelector('.nhsd-a-tag--meta-light') || {}).textContent),
      });
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  const payload = {collected_at_utc: new Date().toISOString(), pages: pages.size, cards};
  const blob = new Blob([JSON.stringify(payload, null, 1)], {type: 'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'mhsds_cards.json';
  document.body.appendChild(a);
  a.click();
  return {pages: pages.size, cards: cards.length};
})();
