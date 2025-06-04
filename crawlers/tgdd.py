import pandas as pd
import time
import re
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import json
from my_logger import get_logger
# ======= Setup driver =======
def setup_driver(logger):
    """Initialize Chrome driver with proper configuration"""
    options = webdriver.ChromeOptions()
    
    # Essential options for GitHub Actions
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-web-security')
    options.add_argument('--disable-features=VizDisplayCompositor')
    options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    # Version compatibility handling
    try:
        # Try with explicit chromedriver path
        service = webdriver.ChromeService('/usr/local/bin/chromedriver')
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        print(f"Failed to initialize Chrome with custom service: {e}")
        # Fallback to default
        try:
            driver = webdriver.Chrome(options=options)
            return driver
        except Exception as e2:
            print(f"Failed to initialize Chrome with default service: {e2}")
            raise e2


def crawl_product_list(driver, logger, category_url): 
    driver.get(category_url)
    while True:
        try:
            # Click nút "Xem thêm"
            view_more_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "div.view-more a"))
            )
            driver.execute_script("arguments[0].click();", view_more_button)  # Click using JavaScript
            time.sleep(2)  

            show_more_btn_text = view_more_button.text.strip()
            print(f"Còn: {show_more_btn_text}")
        except:
            print("No more 'View More' button found.")
            break 

    # Lấy danh sách tất cả sản phẩm sau khi đã load hết
    product_items = driver.find_elements(By.CSS_SELECTOR, "ul.listproduct li.item")
    products = []
    i = 1
    for item in product_items:
        try:
            # Lấy URL sản phẩm
            first_a = item.find_element(By.TAG_NAME, "a")
            product_url = first_a.get_attribute("href")
            
            # Lấy tên sản phẩm
            h3_tag = item.find_element(By.TAG_NAME, "h3")
            product_name = h3_tag.text.strip()
            
            products.append({"name": product_name, "url": product_url})
            logger.debug(f"Appended {i} name: {product_name}, url: {product_url}")
            i = i + 1

        except:
            continue
    return products

def extract_json_product_gtm(driver):
    try:
        input_elem = driver.find_element(By.ID, "jsonProductGTM")
        json_data = json.loads(input_elem.get_attribute("value"))
        return json_data
    except Exception as e:
        print(f"Lỗi khi extract jsonProductGTM: {e}")
        return {}
    
def get_brand(driver):
    data = extract_json_product_gtm(driver)
    brand_info = data.get("brand", {})
    brand_name = ""

    if isinstance(brand_info, dict):
        brand_name = brand_info.get("name", "")
        if isinstance(brand_name, list):
            brand_name = ", ".join(brand_name)

    return brand_name.strip() if brand_name else None

def clean_html_value(value):
    """Loại bỏ thẻ HTML và chỉ lấy text"""
    if not value:
        return ""
    soup = BeautifulSoup(value, "html.parser")
    return soup.get_text(separator=" ", strip=True)

def get_specs(driver):
    data = extract_json_product_gtm(driver)
    specs_list = data.get("additionalProperty", [])
    specs = {}

    for spec in specs_list:
        name = spec.get("name")
        value = clean_html_value(spec.get("value", ""))
        if name and value:
            specs[name] = value

    return specs

def get_prices(driver):
    try:
        time.sleep(2)
        # Tìm tất cả thẻ <a> màu sắc
        color_elements = driver.find_elements(By.CSS_SELECTOR, 'div.box03.color.group.desk a')

        # Nếu tìm thấy màu sắc
        if color_elements:
            result = []
            color_links = [(a.text.strip(), a.get_attribute('href')) for a in color_elements]

            for color_name, href in color_links:
                driver.get(href)
                time.sleep(2)

                # Dùng regex trên page source để lấy giá
                html = driver.page_source
                match = re.search(r'window\.gtmViewItemV2\s*=\s*function\s*\(obj\)\s*{(.*?)};', html, re.DOTALL)
                if match:
                    item_match = re.search(r'item_variant:\s*"([^"]+)",\s*price:\s*([\d.]+)', match.group(1))
                    if item_match:
                        variant = item_match.group(1)
                        price = float(item_match.group(2))
                        if price != 0.0: 
                            result.append({"color": variant, "price": price})
                        else:
                            json_data = extract_json_product_gtm(driver)
                            price_from_gtm = json_data.get("offers", {}).get("price", 0.0)
                            result.append({"color": variant, "price": price_from_gtm})
            return result
        
        gtm_data = driver.execute_script("return window.gtmViewItemV2 || window.gtmAddToCartAll;")
        if gtm_data:
            items = gtm_data[0]['items'] if isinstance(gtm_data, list) else gtm_data['items']
            result = []
            for item in items:
                color = item.get('item_variant', 'default')
                price = item.get('price', 0.0)
                result.append({'color': color, 'price': price})
            return result
        
        json_data = extract_json_product_gtm(driver)
        price = json_data.get("offers", {}).get("price", 0.0)
        return [{"color": "default", "price": float(price)}]

    
    except Exception as e:
        print(f"Lỗi khi lấy giá sản phẩm: {e}")
        return [{'color': 'default', 'price': 0.0}]

def crawl_selected_range(start_index, end_index, df_input, category, driver, logger, df_results=None):
    rows_to_crawl = df_input.iloc[start_index:end_index].copy()
    new_results = []

    for index, row in rows_to_crawl.iterrows():
        logger.debug(f"Đang crawl ({index}/{len(df_input)}): {row['name']}")
        
        try:
            driver.get(row["url"])
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except Exception:
            logger.warning(f"Timeout khi tải trang: {row['url']}")
            continue

        brand_name = get_brand(driver)
        specifications = get_specs(driver)
        prices = get_prices(driver)

        new_results.append({
            "name": row["name"],
            "url": row["url"],
            "category": category,
            "brand": brand_name,
            "specifications": specifications,
            "prices": prices,
        })

    new_df = pd.DataFrame(new_results)

    if df_results is None or df_results.empty:
        df_results = new_df
    else:
        df_results = pd.concat([df_results, new_df]) \
                       .drop_duplicates(subset=["url"], keep="last") \
                       .reset_index(drop=True)

    logger.info(f"Đã cập nhật {len(new_results)} dòng vào DataFrame. Tổng số dòng: {len(df_results)}")
    return df_results

# ======= main =======
categories = [
    {"name": "điện thoại", "url": "https://www.thegioididong.com/dtdd", "name_file": "phone"},
    {"name": "máy tính bảng", "url": "https://www.thegioididong.com/may-tinh-bang", "name_file": "tablet"},
    {"name": "laptop", "url": "https://www.thegioididong.com/laptop", "name_file": "laptop"},
    {"name": "màn hình", "url": "https://www.thegioididong.com/man-hinh-may-tinh", "name_file": "monitor"},
    {"name": "pc", "url": "https://www.thegioididong.com/may-tinh-de-ban", "name_file": "pc"}
]

def crawl():
    logger = get_logger()
    logger.info("Khởi tạo trình duyệt và bắt đầu quá trình crawl")
    driver = setup_driver()

    for category in categories:
        logger.info(f"Đang lấy danh sách sản phẩm cho: {category ['name']}")
        products = crawl_product_list(driver, logger, category ["url"])
        df_products = pd.DataFrame(products).drop_duplicates(subset=["url"], keep="last").reset_index(drop=True)
        detailed = crawl_selected_range(0, len(df_products), df_products, category ["name"], driver, logger)
        output_path = f"data/raw/tgdd/{category ['name_file']}.csv"
        detailed.to_csv(output_path, index=False)
        logger.info(f"Hoàn thành crawl dữ liệu cho danh mục {category ['name']}")

    driver.quit()
