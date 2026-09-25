import yaml
from playwright.sync_api import Page, sync_playwright

DESIGNS = ["Elegant", "Modern", "Classic", "Casual"]


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


def add_menu_sections(config: dict, page: Page):
    sections = config.get("sections")
    if not sections:
        raise MenuConfigError("sections key not found or empty")
    for s, (key, items) in enumerate(sections.items()):
        if not items:
            raise MenuConfigError(f"section '{key}' has no items")
        if s > 0:
            page.get_by_role("button", name="+ Add Section").click()
            settle(page)
        page.locator(f'[wire\\:model\\.lazy="sections.{s}.name"]').fill(section_title(key))
        settle(page)
        for i, item in enumerate(items):
            if not item.get("item_name"):
                raise MenuConfigError(f"item {i} in section '{key}' has no item_name")
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


def download_menu_pdf(config: dict, page: Page):
    page.get_by_role("button", name="Generate Menu").click()
    settle(page)
    page.wait_for_function(IFRAME_READY, arg=config["restaurant"]["name"])
    frame = next(f for f in page.frames if "/menu/render/" in f.url)
    frame.add_style_tag(content=".item-desc { white-space: pre-line; }")
    with page.expect_download() as download_info:
        page.get_by_role("button", name="Download PDF").click()
    download = download_info.value
    download.save_as(download.suggested_filename)
    return download.suggested_filename


def main():
    with sync_playwright() as p:
        with open('menu.yaml', 'r') as file:
            config = yaml.safe_load(file)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://staticfast.com/free-restaurant-menu-maker")
        settle(page)
        choose_design(config, page)
        add_restaurant_details(config, page)
        add_menu_sections(config, page)
        path = download_menu_pdf(config, page)
        print(f"Saved {path}")
        context.close()
        browser.close()


if __name__ == "__main__":
    main()
