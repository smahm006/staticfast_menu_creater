// Runs inside the staticfast render iframe before the PDF capture. staticfast
// renders one flat list of sections into a single tall page; this regroups them
// into top-level sections with optional sub-sections and lays them out on
// fixed letter-size pages. Every top-level section starts on a new page, as
// does every sub-section of a group with pagePerSubsection; other sub-sections
// flow on. Content that runs long continues on the next page without repeating
// its title. The document height is an exact number of pages, so the capture
// has no blank tail.
//
// groups: [{title, pagePerSubsection, subsections: [title | null, ...]}], in the same order the
// sections were submitted. A null sub-section title means the items belong
// directly to the top-level section.
async (groups) => {
    await document.fonts.ready;

    const sections = [...document.querySelectorAll('.menu-body > .section')];
    const expected = groups.reduce((n, g) => n + g.subsections.length, 0);
    if (sections.length !== expected) {
        throw new Error(`expected ${expected} rendered sections, found ${sections.length}`);
    }
    const header = document.querySelector('.header');
    const footer = document.querySelector('.footer');

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
        group.subsections.forEach((subtitle, s) => {
            const headings = [];
            if (g === 0 && s === 0 && header) headings.push(header);
            if (s === 0) headings.push(titled('section-title', group.title));
            if (subtitle) headings.push(titled('sm-sub-title', subtitle));
            if (s === 0 || group.pagePerSubsection) newPage();
            let startsPage = frame.childElementCount === 0;
            let block = openBlock(headings);
            for (const item of sections.shift().querySelectorAll('.item')) {
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
