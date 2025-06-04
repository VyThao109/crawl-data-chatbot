import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from collections import defaultdict
from my_logger import get_logger
def crawl_products_on_current_page(driver, logger, category, max_products=None):
    while True:
        try:
            view_more = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn-show-more"))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", view_more)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", view_more)
            time.sleep(2)
        except:
            break

    product_data = []
    try:
        products = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.product-item"))
        )
        logger.info(f"Tổng số sản phẩm cho nhu cầu {category}: {len(products)}")
        for product in products:
            try:
                url = product.find_element(By.CSS_SELECTOR, "a").get_attribute("href")
                name = product.find_element(By.CSS_SELECTOR, "div.product__name h3").text.strip()

                if name and url:
                    product_data.append({"name": name, "url": url})
            except Exception as e:
                print("Lỗi khi lấy sản phẩm:", e)
                continue

            if max_products and len(product_data) >= max_products:
                break

    except Exception as e:
        print("Lỗi khi lấy danh sách sản phẩm:", e)

    return product_data

def crawl_needs_filter(url, driver, max_needs=5):
    logger = get_logger()
    try:
        driver.get(url)
        time.sleep(3)

        # Lấy danh mục
        category_wrapper = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.categories-content-wrapper.is-flex"))
        )
        category_links = category_wrapper.find_elements(By.CSS_SELECTOR, "a")

        categories = []
        for link in category_links[:max_needs]:  # bỏ enumerate nếu không dùng index
            url = link.get_attribute("href")
            name = link.text.strip()
            if url and url != "javascript:void(0)":
                categories.append({"url": url, "name": name})
                logger.info(f"Đã thêm nhu cầu {name}")

        # Dict để tránh trùng sản phẩm
        product_map = defaultdict(lambda: {"name": "", "url": "", "needs": set()})

        for category in categories:
            logger.info(f"Đang thu thập dữ liệu cho nhu cầu {category['name']}")
            try:
                driver.get(category["url"])
                time.sleep(3)

                products = crawl_products_on_current_page(driver, logger, category['name'])

                for product in products:
                    key = (product["name"], product["url"])
                    product_map[key]["name"] = product["name"]
                    product_map[key]["url"] = product["url"]
                    product_map[key]["needs"].add(category["name"])  # add nhu cầu

                logger.info(f"Đã thu thập dữ liệu {len(products)} sản phẩm từ {category['name']}")

            except Exception as e:
                logger.info(f"Lỗi khi crawl {category['name']}: {e}")
                continue

        # Chuyển về list và ghi file
        final_products = []
        for data in product_map.values():
            final_products.append({
                "name": data["name"],
                "url": data["url"],
                "needs": list(data["needs"])
            })

        df = pd.DataFrame(final_products)
        return df

    except Exception as e:
        print(f"Lỗi nghiêm trọng: {e}")

