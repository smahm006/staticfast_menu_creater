// Runs inside the staticfast render iframe before the PDF capture. staticfast
// renders one flat list of sections into a single tall page; this regroups them
// into top-level sections with optional sub-sections and lays them out on
// fixed letter-size pages. Every top-level section starts on a new page, as
// does every sub-section of a group with pagePerSubsection; other sub-sections
// flow on. Content that runs long continues on the next page without repeating
// its title. The document height is an exact number of pages, so the capture
// has no blank tail.
//
// groups: [{title, pagePerSubsection, subsections: [{title | null, qr: [{code, src} | null]}]}],
// in the same order the sections were submitted. A null sub-section title means
// the items belong directly to the top-level section. qr holds, per item, the
// item code and its QR image, shown to the right of the item text.
async (groups) => {
    await document.fonts.ready;

    const sections = [...document.querySelectorAll('.menu-body > .section')];
    const expected = groups.reduce((n, g) => n + g.subsections.length, 0);
    if (sections.length !== expected) {
        throw new Error(`expected ${expected} rendered sections, found ${sections.length}`);
    }
    const header = document.querySelector('.header');
    const footer = document.querySelector('.footer');

    const withQr = (item, qr) => {
        if (!qr) return item;
        const text = document.createElement('div');
        text.className = 'item-text';
        text.append(...item.childNodes);
        const block = document.createElement('div');
        block.className = 'item-qr';
        const img = Object.assign(document.createElement('img'), {src: qr.src, alt: qr.code});
        block.append(img, Object.assign(document.createElement('div'), {className: 'item-code', textContent: qr.code}));
        item.classList.add('has-qr');
        item.append(text, block);
        return item;
    };
    // One block per description line instead of white-space: pre-line, which
    // html2canvas draws over itself when a line wraps.
    const splitLines = (item) => {
        const desc = item.querySelector('.item-desc');
        if (!desc) return item;
        const lines = desc.textContent.split('\n').map((l) => l.trim()).filter(Boolean);
        desc.replaceChildren(...lines.map((l) => Object.assign(document.createElement('div'), {textContent: l})));
        return item;
    };
    const titled = (className, text) => {
        const el = document.createElement('div');
        el.className = className;
        el.append(Object.assign(document.createElement('span'), {textContent: text}));
        return el;
    };

    document.body.replaceChildren();
    let frame, grid;

    const overflows = () => frame.scrollHeight > frame.clientHeight;
    const newPage = () => {
        const page = document.createElement('div');
        page.className = 'sm-page';
        frame = document.createElement('div');
        frame.className = 'menu-frame sm-frame';
        page.append(frame);
        document.body.append(page);
    };
    // Headings plus an item grid, appended to the current page.
    const openBlock = (headings) => {
        grid = document.createElement('div');
        grid.className = 'sm-grid';
        frame.append(...headings, grid);
        return [...headings, grid];
    };

    groups.forEach((group, g) => {
        group.subsections.forEach(({title: subtitle, qr}, s) => {
            const headings = [];
            if (g === 0 && s === 0 && header) headings.push(header);
            if (s === 0) headings.push(titled('section-title', group.title));
            if (subtitle) headings.push(titled('sm-sub-title', subtitle));
            if (s === 0 || group.pagePerSubsection) newPage();
            let startsPage = frame.childElementCount === 0;
            let block = openBlock(headings);
            const items = [...sections.shift().querySelectorAll('.item')];
            if (items.length !== qr.length) {
                throw new Error(`section ${subtitle || group.title}: expected ${qr.length} items, found ${items.length}`);
            }
            for (const item of items.map((el, i) => withQr(splitLines(el), qr[i]))) {
                grid.append(item);
                if (!overflows()) continue;
                const first = grid.children.length === 1;
                if (first && startsPage) {
                    throw new Error(`item does not fit on a page: ${item.textContent.trim()}`);
                }
                // A heading never sits alone at the foot of a page: move it with its first item.
                if (first) block.forEach((el) => el.remove());
                else item.remove();
                newPage();
                block = openBlock(first ? headings : []);
                startsPage = true;
                grid.append(item);
                if (overflows()) {
                    throw new Error(`item does not fit on a page: ${item.textContent.trim()}`);
                }
            }
        });
    });
    if (footer) {
        frame.append(footer);
        if (overflows()) {
            newPage();
            frame.append(footer);
        }
    }
    return document.querySelectorAll('.sm-page').length;
}
