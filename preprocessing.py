import pandas as pd
import ast
import re
import unicodedata

# === Brand + Rule Definitions ===
phone_brands = ["apple", "samsung", "xiaomi", "oppo", "realme", "tecno", "vivo", "infinix", "nokia", "nubia", "nothing phone", "masstel", "sony", "itel"]
phone_rules = {
    "iphone": "apple", "iphone (apple)": "apple", "redmi": "xiaomi",
    "iqoo": "vivo", "moto": "motorola", "red": "nubia", "zenfone": "asus",
    "xperia": "sony", "black": lambda parts: "xiaomi" if len(parts) > 1 and parts[1] == "shark" else "black"
}

laptop_brands = ["mac", "asus", "lenovo", "dell", "hp", "acer", "lg", "huawei", "msi", "gigabyte", "vaio", "masstel", "apple", "microsoft", "itel", "avita"]
laptop_rules = {"macbook": "mac", "probook": "hp"}

tablet_brands = ["apple", "samsung", "xiaomi", "huawei", "lenovo", "nokia", "teclast", "kindle", "boox", "remarkable"]
tablet_rules = {"ipad": "apple"}
tablet_phrases = ["máy tính bảng", "máy đọc sách"]

monitor_brands = ["asus", "samsung", "dell", "lg", "msi", "acer", "xiaomi", "viewsonic", "philips", "aoc", "dahua"]
monitor_phrases = ["màn hình cong gaming", "màn hình cong", "màn hình lập trình", "màn hình gaming", "màn hình", "giá treo màn hình", "giá treo màn hình máy tính"]

pc_brands = ["asus", "msi"]
pc_phrases = ["pc"]

cut_patterns = [
    r"\| chính hãng.*", r" chính hãng.*", r"- nhập khẩu.*", r"- chỉ có tại.*",
    r"- đã kích hoạt.*", r"- đkh online.*", r"- cũ.*", r"- kèm.*", r" kèm.*",
    r"\(bản không quảng cáo\).*"
]
cut_regex = "|".join(cut_patterns)

# === Cleaning and Utility Functions ===
def clean_name_column(series):
    series = series.str.lower().str.strip()
    series = series.str.replace(cut_regex, "", regex=True).str.strip()
    series = series.str.replace(r'[^\w\s\-/+\.]', '', regex=True)
    return series

def clean_display_name_column(series):
    original_series = series.copy()
    lower_series = series.str.lower().str.strip()
    cleaned_series = lower_series.str.replace(cut_regex, "", regex=True).str.strip()

    restored_series = []
    for original, cleaned in zip(original_series, cleaned_series):
        start = original.lower().find(cleaned)
        if start != -1:
            restored = original[start:start + len(cleaned)].strip()
            restored_series.append(restored)
        else:
            restored_series.append(cleaned)
    return pd.Series(restored_series, index=series.index)

def parse_dict_string(text):
    try:
        return ast.literal_eval(text)
    except:
        return {}

def clean_text(text):
    if isinstance(text, str):
        return unicodedata.normalize("NFKC", text).strip().replace("\n", ", ").replace("  ", " ")
    return text

def clean_specs_column(series):
    return series.fillna("").apply(
        lambda x: {
            clean_text(k): clean_text(v) for k, v in parse_dict_string(x).items()
        } if isinstance(x, str) else {}
    )

def parse_list_string(text):
    try:
        return ast.literal_eval(text)
    except:
        return []

def clean_feature_list(lst):
    return [
        unicodedata.normalize("NFKC", item).strip().replace("\n", " ").replace("  ", " ")
        for item in lst if isinstance(item, str)
    ]

def clean_features_column(series):
    return series.fillna("").apply(
        lambda x: clean_feature_list(parse_list_string(x)) if isinstance(x, str) else []
    )

def update_brand(row, valid_brands=None, extra_rules=None, key_phrase_list=None):
    brand = row.get("brand", "unknown")
    name = str(row.get("name", "")).lower()

    if brand != "unknown":
        return brand

    try:
        spec = ast.literal_eval(row.get("specifications", "{}"))
        brand_from_spec = spec.get("Hãng sản xuất", "").strip().lower()
        if brand_from_spec and brand_from_spec not in ["hãng khác", "hang khac", "other", "unknown"]:
            return brand_from_spec
    except:
        pass

    if valid_brands:
        for b in valid_brands:
            if b in name:
                return b

    name_parts = name.split()
    if name_parts and extra_rules:
        first_word = name_parts[0]
        mapped = extra_rules.get(first_word)
        if isinstance(mapped, str):
            return mapped
        elif callable(mapped):
            return mapped(name_parts)

    if name_parts and key_phrase_list:
        for phrase in key_phrase_list:
            if phrase in name:
                after_phrase = name.split(phrase, 1)[1].strip()
                after_parts = after_phrase.split()
                if after_parts:
                    if after_parts[0] == "ipad":
                        return "apple"
                    return after_parts[0]

    return name_parts[0] if name_parts else "unknown"

def process_product_df(df, df_filtered=None, brand_list=None, brand_rules=None, key_phrase_list=None):
    df["display_name"] = clean_display_name_column(df["name"])
    df["name"] = clean_name_column(df["name"])
    df["specifications"] = clean_specs_column(df["specifications"])
    if "features" in df.columns:
        df["features"] = clean_features_column(df["features"])

    if brand_list is not None:
        df["brand"] = df["brand"].str.lower().str.strip()
        df["brand"] = df["brand"].apply(lambda x: x if x in brand_list else "unknown")

    if brand_list is not None or brand_rules is not None:
        df["brand"] = df.apply(lambda row: update_brand(row, brand_list, brand_rules, key_phrase_list), axis=1)

    if df_filtered is not None:
        df = pd.merge(df, df_filtered[["url", "filters"]], on="url", how="left")

    return df

# === Main Logic ===
def load_and_process(shop_name, category, brand_list, brand_rules=None, key_phrases=None):
    base_path = f"data/{shop_name}"
    raw_df = pd.read_csv(f"{base_path}/{category}.csv", encoding="utf-8").drop_duplicates().reset_index(drop=True)
    filtered_df = pd.read_csv(f"{base_path}/filtered/{category}.csv", encoding="utf-8")

    return process_product_df(raw_df, filtered_df, brand_list, brand_rules, key_phrases)

def main():
    categories = {
        "phone": (phone_brands, phone_rules, None),
        "laptop": (laptop_brands, laptop_rules, None),
        "tablet": (tablet_brands, tablet_rules, tablet_phrases),
        "monitor": (monitor_brands, None, monitor_phrases),
        "pc": (pc_brands, None, pc_phrases),
    }

    shops = ["cellphones", "fpt", "tgdd"]
    all_processed = {}

    for shop in shops:
        all_processed[shop] = {}
        for cat, (brands, rules, phrases) in categories.items():
            print(f"Processing {shop} - {cat}...")
            df = load_and_process(shop, cat, brands, rules, phrases)
            all_processed[shop][cat] = df
            print(f"{shop} - {cat}: {df.shape[0]} rows, brands: {df['brand'].nunique()} unique")

if __name__ == "__main__":
    main()
