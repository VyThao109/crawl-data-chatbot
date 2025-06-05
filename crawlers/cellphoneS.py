import pandas as pd
import time
import re
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup, Tag
import json
from .filter_cellphoneS import crawl_needs_filter
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

# ======= Crawl danh sách sản phẩm =======
def crawl_product_list(driver, logger, category_url):
    logger.info(f"Truy cập trang danh mục: {category_url}")
    driver.get(category_url)
    stable_count = 0
    prev_count = 0

    while True:
        try:
            view_more_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "div.cps-block-content_btn-showmore a"))
            )
            driver.execute_script("arguments[0].click();", view_more_button)
            time.sleep(2)

            items = driver.find_elements(By.CSS_SELECTOR, "div.product-info-container.product-item")
            current_count = len(items)
            print(f"Số sản phẩm hiện tại: {current_count}")

            if current_count == prev_count:
                stable_count += 1
            else:
                stable_count = 0

            if stable_count >= 3:
                print("Số lượng sản phẩm ổn định, dừng tải thêm")
                break

            prev_count = current_count

        except Exception as e:
            logger.warning(f"Không còn nút xem thêm hoặc lỗi xảy ra: {e}")
            break

    items = driver.find_elements(By.CSS_SELECTOR, "div.product-info-container.product-item")
    
    products = []
    for i, item in enumerate(items):
        try:
            product_url = item.find_element(By.TAG_NAME, "a").get_attribute("href")
            product_name = item.find_element(By.CSS_SELECTOR, "div.product__name h3").text.strip()
            products.append({"name": product_name, "url": product_url})
            logger.debug(f"Thêm sản phẩm {i}: {product_name} - {product_url}")
        except Exception as e:
            logger.debug(f"Bỏ qua sản phẩm do lỗi: {e}")
            continue
    logger.info(f"Tổng sản phẩm thu thập được: {len(products)}")
    return products


# ======= Các hàm phụ trợ lấy thông tin =======
def get_brand(driver):
    try:
        tags = driver.find_elements(By.XPATH, '//script[@type="application/ld+json"]')
        for tag in tags:
            try:
                data = json.loads(tag.get_attribute("innerHTML"))
                if isinstance(data, dict) and data.get("@type") == "Product":
                    return data.get("brand", {}).get("name", "").strip()
                if isinstance(data, list):
                    for item in data:
                        if item.get("@type") == "Product":
                            return item.get("brand", {}).get("name", "").strip()
            except:
                continue
    except:
        pass
    return None

def get_nuxt_data(driver):
    try:
        return driver.execute_script("return window.__NUXT__;")
    except:
        return None

def clean_value(raw_value):
    if not isinstance(raw_value, str): return raw_value
    raw_value = re.sub(r"\(Path: x=\d+, y=\d+\)", "", raw_value).strip()
    soup = BeautifulSoup(raw_value, "html.parser")
    links = [a.get_text(strip=True) for a in soup.find_all("a")]
    text = soup.get_text("\n").strip().split("\n")
    if len(links) > 1: return links
    return text if len(text) > 1 else text[0] if text else ""

def extract_specifications(nuxt_data):
    try:
        specs = nuxt_data["state"]["product"]["productData"]["specification"]["full_by_group"]
        return {item["label"]: clean_value(item["value"]) for group in specs for item in group["value"]}
    except:
        return {}

def parse_price(price_text):
    cleaned = re.sub(r"[^\d]", "", price_text)
    return int(cleaned) if cleaned.isdigit() else None

def scrape_prices(driver, nuxt_data):
    prices = []
    try:
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME, "box-product-variants")))
        items = driver.find_elements(By.CSS_SELECTOR, "ul.list-variants > li")
        for item in items:
            try:
                name = item.find_element(By.CSS_SELECTOR, "strong.item-variant-name").text.strip()
                price = parse_price(item.find_element(By.CSS_SELECTOR, "span.item-variant-price").text.strip())
                if name and price:
                    prices.append({"color": name, "price": price})
            except:
                continue
    except:
        try:
            price = nuxt_data["state"]["product"]["productData"]["filterable"]["special_price"]
            prices.append({"color": "default", "price": price})
        except:
            return []
    return prices

def scrape_features(driver, nuxt_data, logger=None):
    features = []

    # --- Phần 1: Lấy từ DOM ---
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "v2Gallery"))
        )
        v2_gallery = driver.find_element(By.ID, "v2Gallery")
        desktop_div = v2_gallery.find_element(By.CSS_SELECTOR, "div.desktop")
        li_elements = desktop_div.find_elements(By.CSS_SELECTOR, "ul > li")

        for li in li_elements:
            raw_html = li.get_attribute("outerHTML")
            text = BeautifulSoup(raw_html, "html.parser").get_text(separator=" ").strip()
            clean_text = ' '.join(text.split())
            if clean_text:
                features.append(clean_text)

    except Exception as e:
        msg = f"Lỗi khi lấy features từ DOM: {e}"
        print(msg) if not logger else logger.warning(msg)

    # --- Phần 2: Lấy từ nuxt_data ---
    try:
        if nuxt_data and "data" in nuxt_data and nuxt_data["data"]:
            html_content = nuxt_data["data"][0].get("pageInfo", {}).get("content", "")
            if html_content:
                soup = BeautifulSoup(html_content, "html.parser")

                content_source = soup.find("blockquote")
                if not content_source and soup.body:
                    for child in soup.body.descendants:
                        if isinstance(child, Tag) and child.name == "p":
                            content_source = child
                            break

                if content_source:
                    raw_text = content_source.get_text(separator=" ").strip()
                    clean_text = ' '.join(raw_text.split())

                    # Tách thành câu
                    sentences = re.split(r'(?<=[.!?])\s+', clean_text)
                    for sentence in sentences:
                        if sentence.strip():
                            features.append(sentence.strip())
    except Exception as e:
        msg = f"Lỗi khi lấy features từ nuxt_data: {e}"
        print(msg) if not logger else logger.warning(msg)

    return features


def scrape_faq_answers(driver):
    answers = []
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CLASS_NAME, "block-breadcrumbs"))
        )

        scripts = driver.find_elements(By.CSS_SELECTOR, 'script[type="application/ld+json"]')
        for script in scripts:
            try:
                data = json.loads(script.get_attribute('innerText'))

                if data.get('@type') == 'FAQPage' and 'mainEntity' in data:
                    for item in data['mainEntity']:
                        answer_html = item.get('acceptedAnswer', [{}])[0].get('text', '')
                        raw_text = BeautifulSoup(answer_html, 'html.parser').get_text(separator=" ").strip()
                        answer_text = ' '.join(raw_text.split()) 
                        if answer_text:
                            answers.append(answer_text)
                    break
            except Exception:
                continue

    except Exception:
        pass

    return answers

def get_image_urls(driver):
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.swiper-slide a.spotlight")))
        return [a.get_attribute("href") for a in driver.find_elements(By.CSS_SELECTOR, "div.swiper-slide a.spotlight") if a.get_attribute("href").startswith("https://")]
    except:
        return []
    
def crawl_selected_range(start, end, df_input, category, driver, logger):
    results = []
    logger.info(f"Bắt đầu lấy dữ liệu chi tiết sản phẩm từ {start} đến {end} cho danh mục: {category}")
    
    for index, row in df_input.iloc[start:end].iterrows():
        logger.info(f"Thu thập dữ liệu sản phẩm {index}: {row['name']}")
        try:
            driver.get(row["url"])
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except TimeoutException as te:
            logger.warning(f"Timeout khi truy cập sản phẩm {row['name']} ({row['url']}): {te}")
            time.sleep(2)  # Nghỉ một chút tránh bị block
            continue
        except Exception as e:
            logger.warning(f"Lỗi khác khi truy cập sản phẩm {row['name']} ({row['url']}): {e}")
            time.sleep(2)
            continue

        try:
            # Các hàm lấy thông tin chi tiết
            brand_name = get_brand(driver)
            nuxt_data = get_nuxt_data(driver)
            specifications = extract_specifications(nuxt_data) if nuxt_data else {}
            prices = scrape_prices(driver, nuxt_data)
            features = scrape_features(driver, nuxt_data)
            faq_answers = scrape_faq_answers(driver)
            image_links = get_image_urls(driver)

            result = {
                "name": row["name"],
                "url": row["url"],
                "category": category,
                "brand": brand_name,
                "specifications": specifications,
                "prices": prices,
                "image_links": image_links,
                "features": features + faq_answers if (features or faq_answers) else []
            }
            results.append(result)
            logger.debug(f"Đã thu thập chi tiết sản phẩm {row['name']}")
        except Exception as e:
            logger.error(f"Lỗi khi xử lý dữ liệu sản phẩm {row['name']}: {e}")
            time.sleep(2)
            continue

    logger.info(f"Hoàn tất crawl chi tiết {len(results)} sản phẩm cho danh mục {category}")
    return results

# ======= main =======
categories = [
    {"name": "điện thoại", "url": "https://cellphones.com.vn/mobile.html", "name_file": "phone", "max_needs": 8},
    {"name": "máy tính bảng", "url": "https://cellphones.com.vn/tablet.html", "name_file": "tablet", "max_needs": 6},
    {"name": "laptop", "url": "https://cellphones.com.vn/laptop.html", "name_file": "laptop", "max_needs": 7},
    {"name": "màn hình", "url": "https://cellphones.com.vn/man-hinh.html", "name_file": "monitor", "max_needs": 6},
    {"name": "pc", "url": "https://cellphones.com.vn/may-tinh-de-ban.html", "name_file": "pc", "max_needs": 4}
]

def crawl():
    logger = get_logger()
    logger.info("Khởi tạo trình duyệt và bắt đầu quá trình crawl")
    driver = setup_driver(logger)

    for category in categories:
        logger.info(f"Xử lý danh mục: {category['name']}")

        logger.info(f"Thu thập nhu cầu sử dụng cho danh mục: {category['name']}")

        filter_products = crawl_needs_filter(category["url"], driver, category["max_needs"])
        df_filter = pd.DataFrame(filter_products)

        products = crawl_product_list(driver, logger, category["url"])
        df_products = pd.DataFrame(products).drop_duplicates(subset=["url"], keep="last").reset_index(drop=True)
        detailed = crawl_selected_range(0, len(df_products), df_products, category["name"], driver, logger)
        df_detailed = pd.DataFrame(detailed)

        if not df_filter.empty:
            df_detailed = pd.merge(df_detailed, df_filter[["url", "needs"]], on="url", how="left")
        else:
            df_detailed["needs"] = None

        output_path = f"data/raw/cellphones/{category['name_file']}.csv"
        df_detailed.to_csv(output_path, index=False)
        logger.info(f"Hoàn thành lưu dữ liệu danh mục {category['name']} vào {output_path}")

    driver.quit()
    logger.info("Đóng trình duyệt, kết thúc chương trình")


if __name__ == "__main__":
    crawl()

