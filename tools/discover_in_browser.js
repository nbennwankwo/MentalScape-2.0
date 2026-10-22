// List every download card of an NHS England statistical series, from a normal browser.
//
// NHS England's pages challenge cloud servers, so the GitHub Actions runner
// cannot read them (docs/adr/0011). This script does the reading part from a
// browser session instead. It mirrors parse_series_page and parse_release_page
// in src/mentalscape/ingest/nhs_pages.py and only extracts what is on the page.
// Classification stays in Python.
//
// Use it by opening one of the series pages below in a browser, pasting this
// into the developer console, and keeping the JSON file it saves. Then run the
// classify command named for that series, for example
//   uv run python -m mentalscape.ingest.mhsds classify --cards mhsds_cards.json
//   uv run python -m mentalscape.ingest.talking_therapies classify --cards talking_therapies_cards.json
//
// Setting window.MENTALSCAPE_NO_DOWNLOAD = true before running keeps the result
// in window.MENTALSCAPE_CARDS instead of saving a file.
(async () => {
  const root = '/data-and-information/publications/statistical/';
  const SERIES = {
    mhsds: {
      file: 'mhsds_cards.json',
      lists: [{path: root + 'mental-health-services-monthly-statistics', title: 'Mental Health Services Monthly Statistics'}],
    },
    talking_therapies: {
      file: 'talking_therapies_cards.json',
      // The publication was renamed from IAPT in May 2023, and the older
      // releases stay on their own series page.
      lists: [
        {path: root + 'nhs-talking-therapies-monthly-statistics-including-employment-advisors', title: 'NHS Talking Therapies Monthly Statistics'},
        {path: root + 'psychological-therapies-report-on-the-use-of-iapt-services', title: 'Psychological Therapies'},
      ],
    },
  };
  const firstYear = 2022;
  const clean = (text) => (text || '').replace(/\s+/g, ' ').trim();
  const here = location.pathname.replace(/\/$/, '');
  const key = Object.keys(SERIES).find((k) => SERIES[k].lists.some((l) => l.path === here));
  if (!key) throw new Error('Open one of the series pages listed in this script first.');

  const pages = new Map();
  for (const list of SERIES[key].lists) {
    const doc = list.path === here ? document : new DOMParser().parseFromString(await (await fetch(list.path)).text(), 'text/html');
    for (const a of doc.querySelectorAll('a[href][title]')) {
      const href = new URL(a.getAttribute('href'), location.origin);
      const title = clean(a.getAttribute('title'));
      if (title.startsWith(list.title) && href.pathname.startsWith(list.path + '/')) {
        const years = (title.match(/\b20\d\d\b/g) || []).map(Number);
        if (!years.length || Math.max(...years) >= firstYear) pages.set(href.href, title);
      }
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

  const payload = {series: key, collected_at_utc: new Date().toISOString(), pages: pages.size, cards};
  window.MENTALSCAPE_CARDS = payload;
  if (!window.MENTALSCAPE_NO_DOWNLOAD) {
    const blob = new Blob([JSON.stringify(payload, null, 1)], {type: 'application/json'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = SERIES[key].file;
    document.body.appendChild(a);
    a.click();
  }
  return {series: key, pages: pages.size, cards: cards.length};
})();
