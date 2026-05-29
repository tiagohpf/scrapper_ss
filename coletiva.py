from playwright.sync_api import sync_playwright
from datetime import timedelta
import csv
import hashlib
import time


URL = "https://www.seg-social.pt/ptss/sef/lista-devedores/consulta-lista-devedores?dswid=7612"

CSV_FILE = "devedores_coletivos.csv"


# =========================================================
# Wait for AJAX requests
# =========================================================
def wait_for_ajax(page):
    # Wait to finish main overlay
    try:
        page.wait_for_selector("#frawPageBlocker_blocker", state="hidden", timeout=30000)
    except Exception:
        pass

    # Wait to finish second overlay
    try:
        page.wait_for_selector("#frawPageBlocker", state="hidden", timeout=30000)
    except Exception:
        pass

    page.wait_for_load_state("networkidle")
    time.sleep(1)

# =========================================================
# Generate table fingerprint
# =========================================================
def generate_table_fingerprint(page):

    table_rows = page.locator("table tbody tr")

    table_text = table_rows.all_inner_texts()

    raw_content = "|".join(table_text)

    return hashlib.md5(
        raw_content.encode("utf-8")
    ).hexdigest()


# =========================================================
# Extract table data
# =========================================================
def extract_table_data(page):

    table = page.locator("table")

    headers = table.locator(
        "thead tr th"
    ).all_inner_texts()

    table_rows = table.locator(
        "tbody tr"
    )

    rows = []

    for i in range(table_rows.count()):
        row = table_rows.nth(i)

        columns = row.locator(
            "td"
        ).all_inner_texts()

        columns = [column.strip() for column in columns]

        if columns:
            rows.append(columns)

    return headers, rows


# =========================================================
# Get entity type dropdown
# =========================================================
def get_entity_dropdown(page):

    selects = page.locator("select")

    for i in range(selects.count()):

        select = selects.nth(i)

        options = select.locator("option")

        option_texts = [
            options.nth(j).inner_text().strip()
            for j in range(options.count())
        ]

        if "Pessoas coletivas" in option_texts:
            return select

    return None


# =========================================================
# Get debt range dropdown
# =========================================================
def get_debt_range_dropdown(page):

    selects = page.locator("select")

    for i in range(selects.count()):

        select = selects.nth(i)

        options = select.locator("option")

        option_texts = [
            options.nth(j).inner_text().strip()
            for j in range(options.count())
        ]

        if any(
            "7500" in text or "1000000" in text
            for text in option_texts
        ):
            return select

    return None


# =========================================================
# Fetch debt ranges
# =========================================================
def get_debt_ranges(page):

    wait_for_ajax(page)

    dropdown = get_debt_range_dropdown(page)

    if dropdown is None:
        raise Exception("Debt range dropdown not found.")

    options = dropdown.locator("option")

    debt_ranges = []

    for i in range(options.count()):
        text = options.nth(i)\
            .inner_text()\
            .strip()

        if (text and "selecion" not in text.lower()):
            debt_ranges.append(text)

    debt_ranges = list(
        dict.fromkeys(debt_ranges)
    )

    return debt_ranges


# =========================================================
# Select corporate entities
# =========================================================
def select_corporate_entities(page):

    dropdown = get_entity_dropdown(page)

    if dropdown is None:
        raise Exception(
            "Corporate entity dropdown not found."
        )

    dropdown.select_option(
        label="Pessoas coletivas"
    )

    wait_for_ajax(page)


# =========================================================
# Select debt range
# =========================================================
def select_debt_range(page, debt_range):

    dropdown = get_debt_range_dropdown(page)

    if dropdown is None:
        raise Exception(
            "Debt range dropdown not found."
        )

    dropdown.select_option(
        label=debt_range
    )

    wait_for_ajax(page)


# =========================================================
# Click search
# =========================================================
def click_search(page):

    for attempt in range(5):

        try:

            wait_for_ajax(page)

            page.get_by_text(
                "Pesquisar"
            ).click(force=True)

            break

        except:

            time.sleep(2)

    wait_for_ajax(page)


# =========================================================
# Ensure 50 results per page
# =========================================================
def ensure_50_results_per_page(page):

    selects = page.locator("select")

    for i in range(selects.count()):

        select = selects.nth(i)

        options = select.locator("option")

        option_texts = [
            options.nth(j).inner_text().strip()
            for j in range(options.count())
        ]

        if (
            "10" in option_texts
            and
            "25" in option_texts
            and
            "50" in option_texts
        ):

            current_value = select.input_value()

            if current_value != "50":

                print(
                    "⚠ Results per page reset to 10. "
                    "Restoring 50..."
                )

                try:

                    select.select_option("50")

                    wait_for_ajax(page)

                except Exception as error:

                    print(error)

            return


# =========================================================
# Go to next page
# =========================================================
def go_to_next_page(page):

    next_button = page.locator(
        "a[aria-label='Next Page'], "
        "a.ui-paginator-next, "
        ".ui-paginator-next"
    )

    if next_button.count() == 0:
        return False

    classes = (
        next_button.first.get_attribute(
            "class"
        ) or ""
    )

    if "disabled" in classes:
        return False

    for attempt in range(5):

        try:
            wait_for_ajax(page)
            next_button.first.click(force=True)
            break
        except:
            time.sleep(2)

    wait_for_ajax(page)

    return True


# =========================================================
# Initialize CSV
# =========================================================
def initialize_csv(headers):
    with open(
        CSV_FILE,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.writer(file)

        writer.writerow([
            *headers,
            "Tipo Entidade",
            "EscalãoDívida"
        ])


# =========================================================
# Append rows to CSV
# =========================================================
def append_rows_to_csv(rows,debt_range):
    with open(
        CSV_FILE,
        "a",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.writer(file)

        for row in rows:

            writer.writerow([
                *row,
                "Pessoa Coletiva",
                debt_range
            ])


# =========================================================
# Fetch initial debt ranges
# =========================================================
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)

    page = browser.new_page()
    page.goto(URL, timeout=120000)

    wait_for_ajax(page)

    select_corporate_entities(page)

    click_search(page)

    headers, _ = extract_table_data(page)

    initialize_csv(headers)

    debt_ranges = get_debt_ranges(page)

    browser.close()

print(f"Debt Ranges Found: {debt_ranges}")


# =========================================================
# Main scraping loop
# =========================================================
total_start_time = time.time()

for debt_range in debt_ranges:

    range_start_time = time.time()

    print("\n" + "=" * 60)
    print(f"DEBT RANGE: {debt_range}")
    print("=" * 60)

    with sync_playwright() as playwright:

        browser = playwright.chromium.launch(headless=True)

        page = browser.new_page()
        page.goto(URL, timeout=120000)

        wait_for_ajax(page)

        select_corporate_entities(page)

        click_search(page)

        select_debt_range(page, debt_range)

        click_search(page)

        page_number = 1

        fingerprints = set()

        while True:
            page_start_time = time.time()

            ensure_50_results_per_page(page)

            headers, rows = extract_table_data(page)

            fingerprint = generate_table_fingerprint(page)

            # Prevent infinite AJAX loops
            if fingerprint in fingerprints:
                print("⚠ Duplicate page detected. Stopping pagination.")
                break

            fingerprints.add(fingerprint)

            append_rows_to_csv(rows, debt_range)

            page_runtime = time.time() - page_start_time

            print(
                f"[{debt_range}] "
                f"Page {page_number} "
                f"-> {len(rows)} rows "
                f"({page_runtime:.2f}s)"
            )

            success = go_to_next_page(page)

            if not success:
                print("Reached last page.")
                break

            page_number += 1

        range_runtime = time.time() - range_start_time

        print(
            f"\n✅ Debt range completed in "
            f"{timedelta(seconds=int(range_runtime))}"
        )

        current_index = debt_ranges.index(debt_range) + 1

        average_runtime = (
            (time.time() - total_start_time)
            / current_index
        )

        remaining_ranges = (
            len(debt_ranges) - current_index
        )


        browser.close()


total_runtime = time.time() - total_start_time

print("\n✅ Scraping completed successfully.")

print(
    f"⏱ Total runtime: "
    f"{timedelta(seconds=int(total_runtime))}"
)

print(f"CSV exported: {CSV_FILE}")