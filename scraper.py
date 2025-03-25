import time
import random
import pandas as pd
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import ElementClickInterceptedException
from supabase import create_client
import socket

SUPABASE_URL = "https://agxcrwewxkmjwlrxeigz.supabase.co"
SUPABASE_KEY = "YOUR_SUPABASE_KEY"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

EDGE_DRIVER_PATH = r"C:\Users\jakramel\Downloads\edgedriver_win64\msedgedriver.exe"
BASE_URL = "https://www.janado.de/collections/apple-iphones"

def init_driver():
    options = webdriver.EdgeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    service = Service(EDGE_DRIVER_PATH)
    driver = webdriver.Edge(service=service, options=options)
    driver.implicitly_wait(10)
    return driver

def random_delay(min_sec=2, max_sec=5):
    time.sleep(random.uniform(min_sec, max_sec))

def safe_click(driver, element):
    try:
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable(element)).click()
    except:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", element)

def get_product_links(driver):
    product_links = []
    while True:
        WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "product-item a")))
        links = driver.find_elements(By.CSS_SELECTOR, "product-item a")
        product_links.extend([link.get_attribute("href") for link in links if link.get_attribute("href")])

        try:
            next_button = driver.find_element(By.CSS_SELECTOR, "#facet-main > page-pagination button[aria-label='Nächste Seite']")
            if "disabled" in next_button.get_attribute("class"):
                break
            safe_click(driver, next_button)
            random_delay()
        except:
            break

    return list(set(product_links))

def scrape_variants(driver, product_url):
    scraped = []
    try:
        driver.get(product_url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.product__title")))

        product_name = driver.find_element(By.CSS_SELECTOR, "h1.product__title").text.strip()

        color_buttons = driver.find_elements(By.CSS_SELECTOR,
            "div.product-form__variantsWrapper product-variants > div:nth-child(1) .color-swatch")
        capacity_selector = driver.find_element(By.CSS_SELECTOR,
            "div.product-form__variantsWrapper product-variants > div:nth-child(2) .select-wrapper > button")
        condition_selector = driver.find_element(By.CSS_SELECTOR,
            "div.product-form__variantsWrapper product-variants > div:nth-child(3) .select-wrapper > button")

        colors = [btn.get_attribute("aria-label") for btn in color_buttons]

        for color_button in color_buttons:
            color_name = color_button.get_attribute("aria-label")
            safe_click(driver, color_button)
            random_delay()

            safe_click(driver, capacity_selector)
            capacities = driver.find_elements(By.CSS_SELECTOR,
                "div.product-form__variantsWrapper product-variants > div:nth-child(2) ul > li")
            for cap in capacities:
                cap_text = cap.text.strip()
                safe_click(driver, cap)
                random_delay()

                safe_click(driver, condition_selector)
                conditions = driver.find_elements(By.CSS_SELECTOR,
                    "div.product-form__variantsWrapper product-variants > div:nth-child(3) ul > li")
                for cond in conditions:
                    cond_text = cond.text.strip()
                    safe_click(driver, cond)
                    random_delay()

                    try:
                        price = driver.find_element(By.CSS_SELECTOR, ".price__current").text.replace("€", "").replace(",", ".").strip()
                        price = float(price)
                    except:
                        price = None

                    scraped.append({
                        "item_name": product_name,
                        "storage_capacity": cap_text,
                        "color": color_name,
                        "condition": cond_text,
                        "price": price,
                        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "product_url": product_url
                    })

    except Exception as e:
        print(f"❌ Error scraping product variants: {e}")

    return scraped

def scrape_janado():
    driver = init_driver()
    driver.get(BASE_URL)
    random_delay()
    
    all_data = []

    product_urls = get_product_links(driver)
    print(f"🔍 Found {len(product_urls)} products.")

    for index, url in enumerate(product_urls[:5]):  # TEST MODE: limit to 5
        print(f"➡ Scraping {index + 1}: {url}")
        product_data = scrape_variants(driver, url)
        all_data.extend(product_data)

    driver.quit()

    df = pd.DataFrame(all_data)
    print(df.head(10))
    df.to_csv("janado_scrape_result.csv", index=False)
    print("📁 CSV saved: janado_scrape_result.csv")

    send_to_supabase(all_data)

def send_to_supabase(data):
    if not data:
        print("❌ No data to insert into Supabase.")
        return

    batch_size = 999
    for i in range(0, len(data), batch_size):
        batch = data[i:i+batch_size]
        for attempt in range(3):
            try:
                supabase.table("janado").insert(batch).execute()
                print(f"✅ Batch {i//batch_size + 1} inserted.")
                break
            except Exception as e:
                print(f"⚠️ Retry {attempt+1} for batch {i//batch_size + 1}: {e}")
                time.sleep(5)

# ✅ RUN
if __name__ == "__main__":
    scrape_janado()

