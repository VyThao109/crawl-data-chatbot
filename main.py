import os
import ast
import datetime
import re
import json
import pandas as pd
import numpy as np
import firebase_admin
from firebase_admin import credentials, firestore

from my_logger import init_logger, get_logger
from crawlers import cellphoneS, fpt, tgdd
from preprocess import clean_data, merge_data, generate_features

# Lấy chuỗi JSON từ biến môi trường (được inject bởi GitHub Action)
firebase_creds = os.environ.get("FIREBASE_CREDENTIALS")

# Chuyển chuỗi JSON thành dict
cred_dict = json.loads(firebase_creds)

# Khởi tạo credential từ dict
cred = credentials.Certificate(cred_dict)

# Khởi tạo Firebase app và client
firebase_admin.initialize_app(cred)
db = firestore.client()

def load_raw_data(source_dir: str):
    """Đọc toàn bộ csv trong thư mục theo cấu trúc `data/raw/<source>/<category>.csv`"""
    result = {}
    for category_file in os.listdir(source_dir):
        if category_file.endswith('.csv'):
            category_name = category_file.replace('.csv', '')
            path = os.path.join(source_dir, category_file)
            df = pd.read_csv(path, encoding='utf-8').drop_duplicates().reset_index(drop=True)
            result[category_name] = df
    return result


def is_value_na(v):
    if isinstance(v, (list, tuple, np.ndarray, pd.Series)):
        # Nếu v là mảng, kiểm tra xem tất cả phần tử có NaN không (hoặc ít nhất một NaN)
        # Ở đây giả sử bạn muốn nếu tất cả là NaN thì đổi thành None
        return all(pd.isna(x) for x in v)
    else:
        return pd.isna(v)

def upload_df_to_firestore(df: pd.DataFrame, collection_name: str, logger=None):
    for idx, row in df.iterrows():
        data_dict = row.to_dict()
        for k, v in data_dict.items():
            if is_value_na(v):
                data_dict[k] = None
        try:
            doc_ref = db.collection(collection_name).document(str(idx))
            doc_ref.set(data_dict)
            if logger:
                logger.info(f"Uploaded doc {idx} to collection '{collection_name}'")
        except Exception as e:
            if logger:
                logger.error(f"Error uploading doc {idx} to Firestore: {e}")

# Cột cần convert (ví dụ: "features")
list_like_columns = ["features", "image_links", "needs"]

def parse_prices_column(prices_dict):
    try:
        if not isinstance(prices_dict, dict):
            return prices_dict  # bỏ qua nếu không đúng định dạng dict

        parsed = {}
        for key, val in prices_dict.items():
            if isinstance(val, str) and val.strip().startswith("["):
                try:
                    parsed[key] = ast.literal_eval(val)
                except:
                    parsed[key] = []  # nếu lỗi parse thì để rỗng
            else:
                parsed[key] = val
        return parsed
    except Exception as e:
        print("Lỗi khi parse:", e)
        return None
    
def main():
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)

    now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'{now}.log')

    init_logger(log_file)
    logger = get_logger()

    logger.info("== BẮT ĐẦU TOÀN BỘ QUÁ TRÌNH CRAWL ==")

    logger.info(">>> Bắt đầu crawl từ FPT")
    fpt.crawl()

    logger.info(">>> Bắt đầu crawl từ Thế Giới Di Động")
    tgdd.crawl()

    logger.info(">>> Bắt đầu crawl từ CellphoneS")
    cellphoneS.crawl()

    logger.info("== HOÀN TẤT TOÀN BỘ QUÁ TRÌNH CRAWL ==")
    logger.info("== BẮT ĐẦU QUÁ TRÌNH XỬ LÝ DỮ LIỆU ==")

    # Danh sách nguồn và loại sản phẩm
    sources = ["cellphones", "fpt", "tgdd"]
    categories = ["phone", "laptop", "tablet", "monitor", "pc"]

    # Load raw data
    raw_data = {}
    for source in sources:
        raw_data[source] = {}
        for cat in categories:
            path = f"data/raw/{source}/{cat}.csv"
            df = pd.read_csv(path, encoding="utf-8").drop_duplicates().reset_index(drop=True)
            raw_data[source][cat] = df

    # Clean dữ liệu
    for source in sources:
        for cat in categories:
            df = raw_data[source][cat]
            if source == "cellphones" and cat == "monitor":
                df = df[~df['name'].str.lower().str.startswith("giá treo màn hình")]
            if source == "cellphones" and cat == "pc":
                df["display_name"] = df["name"]
            
            clean_args = {
                "brand_list": getattr(clean_data, f"{cat}_brands", None),
                "brand_rules": getattr(clean_data, f"{cat}_rules", None),
                "key_phrase_list": getattr(clean_data, f"{cat}_phrases", None)
            }
            # Loại bỏ đối số None để tránh lỗi trong hàm
            clean_args = {k: v for k, v in clean_args.items() if v is not None}
            raw_data[source][cat] = clean_data.clean_product_df(df, **clean_args)
            logger.info(f"Hoàn thiện làm sạch dữ liệu danh mục {cat} nguồn {source}")

    # Merge dữ liệu
    merged_data = {}
    for cat in categories:
        merged_data[cat] = merge_data.merge_product_df(
            raw_data["cellphones"][cat],
            raw_data["fpt"][cat],
            raw_data["tgdd"][cat],
            category=cat
        )
        logger.info(f"Hoàn thiện gộp dữ liệu danh mục {cat}")

    generated_data = {}
    for cat in categories:
        generated_data[cat] = generate_features.generated_features_df(
            merged_data[cat],
            product_type=cat
        )
        logger.info(f"Hoàn thiện sinh thêm features dữ liệu danh mục {cat}")

    for cat in categories:
        df = generated_data[cat]

        # Convert các cột dạng list string thành list
        for col in list_like_columns:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) and x.startswith("[") else x)

        # Convert cột prices thành dict chuẩn
        if "prices" in df.columns:
            df["prices"] = df["prices"].apply(parse_prices_column)

    output_dir = "data/preprocessed"
    os.makedirs(output_dir, exist_ok=True)
    for cat in categories:
        output_path = f"{output_dir}/{cat}.csv"
        upload_df_to_firestore(generated_data[cat], cat, logger)
        merged_data[cat].to_csv(output_path, index=False, encoding="utf-8")
    logger.info("== HOÀN THÀNH QUÁ TRÌNH XỬ LÝ DỮ LIỆU ==")


if __name__ == '__main__':
    main()
