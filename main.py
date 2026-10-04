import argparse
from pathlib import Path

import yaml
from playwright.sync_api import Page, sync_playwright

DESIGNS = ["Elegant", "Modern", "Classic", "Casual"]
LAYOUT_CSS = Path(__file__).with_name("layout.css").read_text()
LAYOUT_JS = Path(__file__).with_name("layout.js").read_text()


class MenuConfigError(Exception):
    pass


def settle(page: Page):
    page.wait_for_load_state("networkidle")


def click_continue(page: Page):
    page.get_by_role("button", name="Continue").click()
    settle(page)


def fill_optional(page: Page, selector: str, config: dict, key: str):
    value = config.get(key, "").strip()
    if not value:
        return
    page.locator(selector).fill(value)
    settle(page)


def choose_design(config: dict, page: Page):
    if "design" not in config:
        raise MenuConfigError("design key not found")
    if config["design"] not in DESIGNS:
        raise MenuConfigError(f"invalid design, choose from {DESIGNS}")
    design = config["design"]
    card = page.locator("div.template-option").filter(has_text=design)
    card.locator("div[wire\\:click^='selectTemplate']").click()
    settle(page)
    click_continue(page)


def add_restaurant_details(config: dict, page: Page):
    if "restaurant" not in config:
        raise MenuConfigError("restaurant key not found")
    restaurant = config["restaurant"]
    if not restaurant.get("name"):
        raise MenuConfigError("restaurant name is required")
    page.locator("#restaurantName").fill(restaurant["name"])
    settle(page)
    fill_optional(page, "#tagline", restaurant, "tagline")
    fill_optional(page, "#address", restaurant, "address")
    fill_optional(page, "#phone", restaurant, "phone")
    fill_optional(page, "#footerNote", restaurant, "footer")
    if restaurant.get("logo"):
        page.locator('input[type="file"]').set_input_files(restaurant["logo"])
        settle(page)
    click_continue(page)


def section_title(key: str) -> str:
    return key.replace("_", " ").title()


def parse_groups(config: dict) -> list[dict]:
    """Top-level sections, each a list of items or a mapping of sub-sections to lists of items.

    Returns [{"title", "page_per_subsection", "subsections": [{"title": str | None, "items": list}]}],
    where a None sub-section title means the items sit directly under the top-level section.
    """
    sections = config.get("sections")
    if not sections:
        raise MenuConfigError("sections key not found or empty")
    page_per_subsection = config.get("page_per_subsection", [])
    unknown = set(page_per_subsection) - set(sections)
    if unknown:
        raise MenuConfigError(f"page_per_subsection names unknown sections: {sorted(unknown)}")
    groups = []
    for key, value in sections.items():
        if isinstance(value, dict):
            if not value:
                raise MenuConfigError(f"section '{key}' has no sub-sections")
            subsections = [{"title": section_title(k), "items": v} for k, v in value.items()]
        else:
            subsections = [{"title": None, "items": value}]
        groups.append({
            "title": section_title(key),
            "page_per_subsection": key in page_per_subsection,
            "subsections": subsections,
        })
    return groups


def add_menu_sections(groups: list[dict], page: Page):
    flat = [(sub["title"] or group["title"], sub["items"]) for group in groups for sub in group["subsections"]]
    for s, (title, items) in enumerate(flat):
        if not items:
            raise MenuConfigError(f"section '{title}' has no items")
        if s > 0:
            page.get_by_role("button", name="+ Add Section").click()
            settle(page)
        page.locator(f'[wire\\:model\\.lazy="sections.{s}.name"]').fill(title)
        settle(page)
        for i, item in enumerate(items):
            if not item.get("item_name"):
                raise MenuConfigError(f"item {i} in section '{title}' has no item_name")
            if i > 0:
                page.locator(f'[wire\\:click="addItem({s})"]').click()
                settle(page)
            prefix = f"sections.{s}.items.{i}"
            page.locator(f'[wire\\:model\\.lazy="{prefix}.name"]').fill(item["item_name"])
            settle(page)
            fill_optional(page, f'[wire\\:model\\.lazy="{prefix}.price"]', item, "item_price")
            fill_optional(page, f'[wire\\:model\\.lazy="{prefix}.description"]', item, "item_description")
    click_continue(page)


IFRAME_READY = """
(name) => {
    const frame = document.querySelector('#pdf-iframe');
    if (!frame) return false;
    const src = frame.getAttribute('src');
    if (!src || src.endsWith('/0')) return false;
    const doc = frame.contentDocument;
    if (!doc || doc.readyState !== 'complete') return false;
    if (!doc.URL.endsWith(src)) return false;
    return doc.body.innerText.toUpperCase().includes(name.toUpperCase());
}
"""


def download_menu_pdf(config: dict, groups: list[dict], page: Page, output: str):
    page.get_by_role("button", name="Generate Menu").click()
    settle(page)
    page.wait_for_function(IFRAME_READY, arg=config["restaurant"]["name"])
    frame = next(f for f in page.frames if "/menu/render/" in f.url)
    frame.add_style_tag(content=LAYOUT_CSS)
    layout = [
        {
            "title": g["title"],
            "pagePerSubsection": g["page_per_subsection"],
            "subsections": [sub["title"] for sub in g["subsections"]],
        }
        for g in groups
    ]
    pages = frame.evaluate(LAYOUT_JS, layout)
    print(f"Laid out {pages} pages")
    with page.expect_download() as download_info:
        page.get_by_role("button", name="Download PDF").click()
    download = download_info.value
    download.save_as(output)


def main():
    parser = argparse.ArgumentParser(description="Build a menu PDF with staticfast from a YAML config")
    parser.add_argument("config", nargs="?", default="menu.yaml")
    parser.add_argument("-o", "--output", default="menu.pdf")
    args = parser.parse_args()
    with open(args.config) as file:
        config = yaml.safe_load(file)
    groups = parse_groups(config)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://staticfast.com/free-restaurant-menu-maker")
        settle(page)
        choose_design(config, page)
        add_restaurant_details(config, page)
        add_menu_sections(groups, page)
        download_menu_pdf(config, groups, page, args.output)
        print(f"Saved {args.output}")
        context.close()
        browser.close()


if __name__ == "__main__":
    main()
