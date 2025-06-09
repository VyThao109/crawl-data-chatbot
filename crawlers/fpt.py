from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service
import pandas as pd
import time
import time
import os
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
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-web-security')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        driver = webdriver.Chrome(options=options)

    return driver



def crawl_products_on_current_page(driver, logger, max_products=None):
    while True:
        try:
            view_more_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.Button_root__LQsbl.Button_btnSmall__aXxTy.Button_whitePrimary__nkoMI.Button_btnIconRight__4VSUO.border.border-iconDividerOnWhite.px-4.py-2"))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", view_more_button)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", view_more_button)
            time.sleep(2)
            show_more_btn_text = view_more_button.text.strip()
            print(f"Còn: {show_more_btn_text}")
        except Exception as e:
            print("Không còn sản phẩm để tải thêm hoặc có lỗi")
            break

    product_data = []
    try:
        container = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.grid.grid-cols-2.gap-2.md\\:grid-cols-4"))
        )
        products = container.find_elements(By.CSS_SELECTOR, "div.group.flex.h-full.flex-col.justify-between.ProductCard_brandCard__VQQT8.ProductCard_cardDefault__km9c5")
        logger.info(f"Tổng số sản phẩm trong danh sách {len(products)}")
        for product in products:
            try:
                url_element = product.find_element(By.CSS_SELECTOR, "a")
                url = url_element.get_attribute("href")
                name_element = product.find_element(By.CSS_SELECTOR, "h3.ProductCard_cardTitle__HlwIo")
                name = name_element.text.strip()
                if url and name:
                    product_data.append({
                        "name": name,
                        "url": url,
                    })
            except Exception as e:
                logger.error(f"Lỗi khi lấy thông tin sản phẩm: {str(e)}")
                continue

            if max_products and len(product_data) >= max_products:
                break
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách sản phẩm: {str(e)}")

    return product_data

def get_colors_and_prices(driver, logger):
    prices = []
    try:
        color_buttons = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "button.Selection_button__vX7ZX.Selection_horizontalContainer__r4oCB"))
        )

        for btn in color_buttons:
            try:
                color_name = btn.text.strip()
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                time.sleep(1)
                btn.click()
                time.sleep(4)

                price_element = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, "span.text-black-opacity-100.h4-bold"))
                )
                price_text = price_element.text.replace(".", "").replace("₫", "").strip()
                price = int(price_text) if price_text.isdigit() else None

                if price is not None:
                    prices.append({
                        "color": color_name,
                        "price": price
                    })
            except Exception as e:
                logger.error(f"Không lấy được giá cho màu {btn.text.strip()}: {str(e)}")
                continue
    except Exception as e:
        logger.error(f"Không tìm thấy màu hoặc giá:  {str(e)}")
    return prices

def get_specifications(driver, logger):
    specs = {}
    try:
        # Click the "Xem cấu hình chi tiết" button to open the modal
        spec_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.Button_root__LQsbl.Button_btnMedium___hdAA.Button_redSecondary___XGMX.h-8.w-\\[182px\\]"))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", spec_button)
        time.sleep(3)
        spec_button.click()


        # Wait for modal to load
        modal_rows = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.flex.gap-2.border-b.border-dashed.border-b-iconDividerOnWhite.py-1\\.5"))
        )

        for row in modal_rows:
            try:
                # Extract key
                key_element = row.find_element(By.CSS_SELECTOR, "div.w-2\\/5.text-textOnWhiteSecondary.b2-regular")
                key = key_element.text.strip()

                # Try both value types
                value_elements = row.find_elements(By.CSS_SELECTOR,
                    "div.flex.flex-1.flex-col.py-0\\.5, span.flex-1.text-textOnWhitePrimary.b2-regular"
                )

                values = [v.text.strip() for v in value_elements if v.text.strip()]

                if len(values) == 1:
                    specs[key] = values[0]
                elif len(values) > 1:
                    specs[key] = values
            except Exception as e:
                logger.error(f"Lỗi đọc dòng thông số kỹ thuật: {str(e)}")
                continue
    except Exception as e:
        logger.error(f"Không thể mở modal cấu hình hoặc lấy dữ liệu: {type(e).__name__} - {str(e)}")
    return specs

def extract_phone_brand(phone_name):
    # Danh sách các thương hiệu phổ biến
    brands = [
        "Samsung", "Xiaomi", "OPPO", "Realme", "Honor", "Vivo", "Nubia",
        "Tecno", "ZTE", "Inoi", "Benco", "Viettel", "iPhone", "Apple", "Masstel", "Nokia", "Mobell", "Itel", "TCL"
    ]

    # Nếu bắt đầu bằng "iPhone", trả về "Apple"
    if phone_name.startswith("iPhone"):
        return "Apple"

    # Kiểm tra xem tên có bắt đầu bằng thương hiệu nào không
    for brand in brands:
        if phone_name.startswith(brand):
            return brand

    # Mặc định nếu không khớp gì
    return "Unknown"

def extract_monitor_brand(product_name):
    brands = [
        "LG", "Samsung", "MSI", "Acer", "Viewsonic", "Asus", "Gigabyte", "Xiaomi",
        "Lenovo", "Dell", "Edra", "AOC", "Apple"
    ]

    # Trường hợp đặc biệt: sản phẩm Apple nhưng không chứa từ "Apple" rõ ràng
    if "Studio Display" in product_name or "Pro Display XDR" in product_name:
        return "Apple"

    for brand in brands:
        if brand.lower() in product_name.lower():
            return brand

    return "Unknown"

def extract_tablet_brand(product_name):
    brands = [
        "Samsung", "Lenovo", "Apple", "iPad", "Xiaomi", "Masstel", "Vivo",
        "Nokia", "Oppo", "Mobell", "Realme", "TCL", "Huawei", "Honor"
    ]

    # Nếu bắt đầu bằng iPad thì quy về Apple
    if product_name.startswith("iPad"):
        return "Apple"

    for brand in brands:
        if brand.lower() in product_name.lower():
            return "Apple" if brand == "iPad" else brand

    return "Unknown"

def extract_laptop_brand(product_name):
    brands = [
        "Asus", "HP", "Dell", "Lenovo", "Acer", "MSI", "Apple", "MacBook",
        "LG", "Gigabyte", "Huawei", "Samsung", "Microsoft", "Avita", "Razer", "Masstel", "VAIO"
    ]

    # Trường hợp đặc biệt: MacBook → Apple
    if product_name.startswith("MacBook"):
        return "Apple"

    for brand in brands:
        if brand.lower() in product_name.lower():
            return "Apple" if brand == "MacBook" else brand

    return "Unknown"

def extract_pc_brand(product_name):
    brands = ["E-Power", "Apple", "Asus", "Lenovo"]

    # Trường hợp đặc biệt: MacBook → Apple
    if product_name.startswith("Mac") | product_name.startswith("iMac"):
        return "Apple"

    for brand in brands:
        if brand.lower() in product_name.lower():
            return "Apple" if brand == "MacBook" else brand

    return "Unknown"

def extract_brand(product_name, category):
    if category == "điện thoại":
        return extract_phone_brand(product_name)
    elif category == "màn hình":
        return extract_monitor_brand(product_name)
    elif category == "máy tính bảng":
        return extract_tablet_brand(product_name)
    elif category == "laptop":
        return extract_laptop_brand(product_name)
    elif category == "pc":
        return extract_pc_brand(product_name)
    else:
        return "Unknown"




categories = [
    {"name": "điện thoại", "url": "https://fptshop.com.vn/dien-thoai", "name_file": "phone.csv"},
    {"name": "máy tính bảng", "url": "https://fptshop.com.vn/may-tinh-bang", "name_file": "tablet.csv"},
    {"name": "laptop", "url": "https://fptshop.com.vn/may-tinh-xach-tay", "name_file": "laptop.csv"},
    {"name": "màn hình", "url": "https://fptshop.com.vn/man-hinh", "name_file": "monitor.csv"},
    {"name": "pc", "url": "https://fptshop.com.vn/may-tinh-de-ban", "name_file": "pc.csv"}
]

def crawl():
    output_dir = "data/raw/fpt/"
    os.makedirs(output_dir, exist_ok=True)
    logger = get_logger()
    logger.info("Khởi tạo trình duyệt và bắt đầu quá trình crawl")
    driver = setup_driver()

    try:
        for category in categories:
            category_name = category["name"]
            url = category['url']
            filename = category['name_file']

            if not url or not filename:
                logger.info(f"Không tìm thấy URL hoặc tên file cho danh mục {category_name}")
                continue

            logger.info(f"Crawling danh mục: {category_name} - URL: {url}")

            try:
                driver.get(url)
                time.sleep(3)
            except TimeoutException as te:
                logger.warning(f"Timeout khi truy cập trang danh mục {category_name}: {te}")
                continue
            except WebDriverException as wde:
                logger.warning(f"Lỗi trình duyệt khi mở trang danh mục {category_name}: {wde}")
                continue
            except Exception as e:
                logger.warning(f"Lỗi không xác định khi mở trang danh mục {category_name}: {e}")
                continue

            products = crawl_products_on_current_page(driver, logger)
            all_data = []

            for index, product in enumerate(products):
                logger.info(f"Đang crawl ({index + 1}/{len(products)}): {product['name']}")
                product_url = product["url"]

                try:
                    driver.get(product_url)
                    time.sleep(3)
                except TimeoutException as te:
                    logger.warning(f"Timeout khi truy cập sản phẩm: {product_url}: {te}")
                    continue
                except WebDriverException as wde:
                    logger.warning(f"Lỗi trình duyệt khi mở sản phẩm: {product_url}: {wde}")
                    continue
                except Exception as e:
                    logger.warning(f"Lỗi không xác định khi mở sản phẩm: {product_url}: {e}")
                    continue

                try:
                    prices = get_colors_and_prices(driver, logger)
                    specs = get_specifications(driver, logger)
                    brand = extract_brand(product["name"], category_name)

                    data_entry = {
                        "name": product["name"],
                        "url": product_url,
                        "brand": brand,
                        "prices": prices,
                        "specifications": specs,
                    }
                    all_data.append(data_entry)

                except Exception as e:
                    logger.error(f"Lỗi khi xử lý dữ liệu sản phẩm {product['name']}: {e}")
                    continue

            out_path = os.path.join(output_dir, filename)
            df = pd.DataFrame(all_data)
            df.to_csv(out_path, index=False)
            logger.info(f"Đã lưu dữ liệu danh mục {category_name} vào {out_path}")

    except Exception as e:
        logger.error(f"Lỗi tổng quát trong quá trình crawl: {str(e)}")

    finally:
        driver.quit()

