import pandas as pd
import time
import re
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, WebDriverException
import urllib3
from bs4 import BeautifulSoup
import json
from my_logger import get_logger


def setup_driver():
    options = Options()
    is_github_actions = os.getenv('GITHUB_ACTIONS') == 'true'

    if is_github_actions:
        # GitHub Actions specific options
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--enable-unsafe-swiftshader')
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--disable-background-timer-throttling')
        options.add_argument('--disable-backgrounding-occluded-windows')
        options.add_argument('--disable-renderer-backgrounding')
        options.add_argument('--disable-features=TranslateUI,VizDisplayCompositor')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-default-apps')
        options.add_argument('--disable-sync')
        options.add_argument('--disable-background-networking')
        options.add_argument('--memory-pressure-off')
        options.add_argument('--single-process')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--virtual-time-budget=60000')
        options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        chromedriver_path = '/usr/local/bin/chromedriver'
        service = Service(executable_path=chromedriver_path)
        driver = webdriver.Chrome(service=service, options=options)

    else:
        # Local development
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-web-security')
        options.add_argument('--enable-unsafe-swiftshader') 
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        driver = webdriver.Chrome(options=options)

    return driver



def crawl_product_list(driver, logger, category_url): 
    try:
        driver.get(category_url)
    except (TimeoutException, WebDriverException, urllib3.exceptions.HTTPError) as e:
        logger.warning(f"Timeout khi truy cập URL: {category_url} - {e}")
        return []

    while True:
        try:
            # Click nút "Xem thêm"
            view_more_button = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "div.view-more a"))
            )
            driver.execute_script("arguments[0].click();", view_more_button)  # Click using JavaScript
            time.sleep(2)

            show_more_btn_text = view_more_button.text.strip()
            print(f"Còn: {show_more_btn_text}")
        except TimeoutException:
            print("Không tìm thấy nút 'Xem thêm' (Timeout).")
            break
        except Exception as e:
            logger.warning(f"Lỗi khi click nút 'Xem thêm': {e}")
            break

    # Lấy danh sách tất cả sản phẩm sau khi đã load hết
    products = []
    try:
        product_items = driver.find_elements(By.CSS_SELECTOR, "ul.listproduct li.item")
    except Exception as e:
        logger.error(f"Lỗi khi tìm danh sách sản phẩm: {e}")
        return []

    i = 1
    for item in product_items:
        try:
            # Lấy URL sản phẩm
            first_a = item.find_element(By.TAG_NAME, "a")
            product_url = first_a.getAttribute("href")
            
            # Lấy tên sản phẩm
            h3_tag = item.find_element(By.TAG_NAME, "h3")
            product_name = h3_tag.text.strip()
            
            products.append({"name": product_name, "url": product_url})
            logger.debug(f"Appended {i} name: {product_name}, url: {product_url}")
            i += 1
        except Exception as e:
            logger.debug(f"Lỗi khi xử lý sản phẩm: {e}")
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
        return [{'color': 'default', 'price': 0.0}]

def crawl_selected_range(start_index, end_index, df_input, category, driver, logger, df_results=None):
    rows_to_crawl = df_input.iloc[start_index:end_index].copy()
    new_results = []

    for index, row in rows_to_crawl.iterrows():
        logger.debug(f"Thu thập dữ liệu sản phẩm ({index}/{len(df_input)}): {row['name']}")
        
        try:
            driver.get(row["url"])
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except TimeoutException as te:
            logger.warning(f"Timeout khi truy cập sản phẩm {row['name']} ({row['url']}): {te}")
            time.sleep(2)  # Nghỉ một chút tránh bị block
            continue
        except Exception:
            logger.warning(f"Timeout khi tải trang: {row['url']}")
            time.sleep(2)
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
        # Kiểm tra thiếu mục nào
        missing_fields = []
        if not brand_name:
            missing_fields.append("brand")
        if not specifications:
            missing_fields.append("specifications")
        if not prices:
            missing_fields.append("prices")
        if missing_fields:
            logger.warning(f"Thiếu {', '.join(missing_fields)} ở sản phẩm: {row['name']}")

        logger.info(f"Đã thu thập chi tiết sản phẩm {row['name']}")

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
        logger.info(f"Thu thập danh sách sản phẩm {category ['name']}")
        products = crawl_product_list(driver, logger, category ["url"])
        df_products = pd.DataFrame(products).drop_duplicates(subset=["url"], keep="last").reset_index(drop=True)
        detailed = crawl_selected_range(0, len(df_products), df_products, category ["name"], driver, logger)
        output_path = f"data/raw/tgdd/{category ['name_file']}.csv"
        detailed.to_csv(output_path, index=False)
        logger.info(f"Hoàn thành crawl dữ liệu cho danh mục {category ['name']}")

    driver.quit()
