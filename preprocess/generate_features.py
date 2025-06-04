import random
import ast
import json
import re
from my_logger import get_logger

# GENERATE FROM NEEDS
filter_templates = {
    'phone': {
        'Nhu cầu sử dụng': lambda v, product_name: f"Điện thoại {product_name} đặc biệt phù hợp với các nhu cầu như {v} – đáp ứng linh hoạt mọi mục đích sử dụng hằng ngày lẫn chuyên sâu.",
    },
    'laptop': {
        'Nhu cầu sử dụng': lambda v, product_name: f"Laptop {product_name} lý tưởng cho các nhu cầu như {v}.",
    },
    'tablet': {
        'Nhu cầu sử dụng': lambda v, product_name: f"Máy tính bảng {product_name} phù hợp với nhiều nhu cầu sử dụng như {v}.",
    },
    'monitor': {
        'Nhu cầu sử dụng': lambda v, product_name: f"{product_name} được thiết kế để đáp ứng tốt các nhu cầu như {v}.",
    },
}

COMMON_USAGE_NEEDS = {
    'phone': [
        'Chơi game', 'Điện thoại gập', 'Chụp ảnh đẹp', 'Livestream',
        'Dung lượng lớn', 'Pin trâu', 'Cấu hình cao', 'Điện thoại AI'
    ],
    'laptop': [
        'Văn phòng', 'Gaming', 'Mỏng nhẹ',
        'Đồ họa - kỹ thuật', 'Sinh viên', 'Cảm ứng', 'Laptop AI'
    ],
    'tablet': [
        'Máy tính bảng AI', 'Cho trẻ em', 'Chơi game', 'Học tập - văn phòng', 
        'Đồ họa - Sáng tạo', 'Máy đọc sách'
    ],
    'monitor': [
        'Gaming', 'Văn phòng', 'Đồ họa', 'Màn hình lập trình', 'Màn hình di động'
    ]
}

PHONE_NEED_DESCRIPTIONS = {
    'Chơi game': "Với cấu hình mạnh mẽ, {product_name} mang đến trải nghiệm chơi game mượt mà, ổn định.",
    'Chụp ảnh đẹp': "Camera chất lượng cao giúp {product_name} ghi lại từng khoảnh khắc sắc nét, sống động.",
    'Livestream': "{product_name} hỗ trợ livestream với chất lượng hình ảnh và âm thanh ấn tượng.",
    'Dung lượng lớn': "Bộ nhớ dung lượng cao giúp {product_name} lưu trữ dữ liệu thoải mái.",
    'Pin trâu': "Viên pin dung lượng lớn trên {product_name} giúp sử dụng suốt ngày dài.",
    'Cấu hình cao': "{product_name} được trang bị cấu hình mạnh mẽ, xử lý đa nhiệm nhanh chóng.",
    'Điện thoại AI': "{product_name} tích hợp công nghệ AI hiện đại, nâng cao trải nghiệm người dùng.",
}

LAPTOP_NEED_DESCRIPTIONS = {
    'Văn phòng': "{product_name} là trợ thủ đắc lực cho các công việc văn phòng nhờ hiệu năng ổn định.",
    'Gaming': "Với hiệu suất cao và hệ thống tản nhiệt tốt, {product_name} là lựa chọn lý tưởng cho game thủ.",
    'Mỏng nhẹ': "{product_name} có thiết kế mỏng nhẹ, dễ dàng mang theo khi di chuyển.",
    'Đồ họa - kỹ thuật': "{product_name} phù hợp cho thiết kế đồ họa với màn hình chất lượng cao và card đồ họa mạnh mẽ.",
    'Sinh viên': "{product_name} đáp ứng tốt nhu cầu học tập và giải trí cơ bản của sinh viên.",
    'Cảm ứng': "Với màn hình cảm ứng tiện lợi, {product_name} giúp bạn thao tác nhanh chóng và linh hoạt hơn.",
    'Laptop AI': "{product_name} tích hợp AI để tối ưu hiệu năng và tiết kiệm điện năng khi sử dụng.",
}

TABLET_NEED_DESCRIPTIONS = {
    'Máy tính bảng AI': "{product_name} sử dụng công nghệ AI nhằm tối ưu hóa hiệu suất và hỗ trợ người dùng thông minh hơn.",
    'Cho trẻ em': "{product_name} được thiết kế với giao diện thân thiện và tính năng an toàn cho trẻ em.",
    'Chơi game': "Cấu hình ổn định cùng màn hình lớn giúp {product_name} chơi game mượt mà, hình ảnh sắc nét.",
    'Học tập - văn phòng': "{product_name} phù hợp cho nhu cầu học tập và công việc văn phòng cơ bản.",
    'Đồ họa - Sáng tạo': "Màn hình sắc nét và bút cảm ứng hỗ trợ sáng tạo nội dung dễ dàng trên {product_name}.",
    'Máy đọc sách': "Với màn hình dịu mắt và thời lượng pin lâu, {product_name} là bạn đồng hành lý tưởng để đọc sách.",
}

MONITOR_NEED_DESCRIPTIONS = {
    'Gaming': "{product_name} có tần số quét cao và độ trễ thấp, mang đến trải nghiệm game mượt mà.",
    'Văn phòng': "{product_name} giúp làm việc hiệu quả với màn hình lớn, chống chói và tiết kiệm năng lượng.",
    'Đồ họa': "Màn hình {product_name} có độ phân giải cao, màu sắc chuẩn xác – lý tưởng cho công việc thiết kế.",
    'Màn hình lập trình': "{product_name} phù hợp cho lập trình viên với tỷ lệ hiển thị tối ưu và chế độ chống mỏi mắt.",
    'Màn hình di động': "{product_name} nhỏ gọn, dễ dàng mang theo và kết nối linh hoạt với nhiều thiết bị.",
}

def generate_needs_description(usage_needs: list, product_type: str, product_name: str) -> list:
    descriptions = []

    category = product_type.strip().lower()
    usage_needs_cleaned = [x.strip() for x in usage_needs if x.strip()]
    if not usage_needs_cleaned:
        return []

    # Lấy dict mô tả nhu cầu tương ứng category
    need_descriptions_map = {
        'phone': PHONE_NEED_DESCRIPTIONS,
        'laptop': LAPTOP_NEED_DESCRIPTIONS,
        'tablet': TABLET_NEED_DESCRIPTIONS,
        'monitor': MONITOR_NEED_DESCRIPTIONS,
    }

    descriptions_dict = need_descriptions_map.get(category, {})

    # Tạo map lowercase key -> original key
    lowercase_to_key = {k.lower(): k for k in descriptions_dict.keys()}

    matched = []
    unmatched = []

    for need in usage_needs_cleaned:
        need_lower = need.lower()
        if need_lower in lowercase_to_key:
            matched.append(lowercase_to_key[need_lower])
        else:
            unmatched.append(need)

    # Thêm mô tả cho từng nhu cầu đã matched
    for need_key in matched:
        descriptions.append(descriptions_dict[need_key].format(product_name=product_name))

    # Gom các nhu cầu không có mô tả riêng, viết mô tả tổng quát
    if unmatched:
        v = ', '.join(unmatched)
        fallback_template = filter_templates.get(category, {}).get('Nhu cầu sử dụng')
        if fallback_template:
            descriptions.append(fallback_template(v, product_name))

    return descriptions

# GENERATE FROM PRICES
def generate_price_features(prices_by_source, product_type, product_name):
    # Từ điển ánh xạ product_type với tên gọi tiếng Việt
    product_type_dict = {
        'phone': 'điện thoại',
        'laptop': 'laptop',
        'tablet': 'máy tính bảng',
        'monitor': 'màn hình',
        'pc': 'máy tính'
    }
    
    # Từ điển ánh xạ tên nguồn web
    source_name_dict = {
        'cellphones': 'Cellphones',
        'fptshop': 'FPTShop',
        'tgdd': "Thế giới di động"
    }

    # Lấy tên loại sản phẩm
    product_type_name = product_type_dict.get(product_type, 'sản phẩm')

    features = []

    # Duyệt từng nguồn (cellphones, fptshop,...)
    for source_key, prices in prices_by_source.items():
        if not prices:
            continue

        # Lấy tên nguồn tiếng Việt
        source_name = source_name_dict.get(source_key, source_key.capitalize())

        # Nếu prices là string (JSON dạng chuỗi), chuyển thành object
        if isinstance(prices, str):
            try:
                prices = ast.literal_eval(prices)
            except Exception:
                continue
        
        for price_info in prices:
            color = price_info.get('color', 'Mặc định')
            price = price_info.get('price', 0)

            if price == 0:
                feature_text = f"Không thể tìm thấy thông tin giá công khai của {product_type_name} {product_name} tại {source_name}. Bạn có thể liên hệ trực tiếp với cửa hàng để biết giá cụ thể."
            else:
                if color.lower() == 'default':  # Nếu color là 'default' (không phân biệt hoa thường)
                    feature_text = f"{product_type_name.capitalize()} {product_name} tại {source_name} có giá là {price:,} VND."
                else:
                    feature_text = f"{product_type_name.capitalize()} {product_name} tại {source_name} màu {color} có giá là {price:,} VND."

            features.append(feature_text.lower())

    return features

# GENERATE FROM BRAND
def generate_brand_description(brand, product_name, product_type):
    if not brand:
        return "Không có thông tin về thương hiệu."
    
    # Từ điển ánh xạ product_type với tên gọi tương ứng
    product_type_dict = {
        'phone': 'điện thoại',
        'laptop': 'laptop',
        'tablet': 'máy tính bảng',
        'monitor': 'màn hình',
        'pc': 'máy tính'
    }
    # Lấy tên sản phẩm từ từ điển, mặc định là 'sản phẩm' nếu không có trong từ điển
    product_type_name = product_type_dict.get(product_type, 'sản phẩm')

    # Định nghĩa các mẫu câu
    templates = [
        f"{product_type_name} {product_name} đến từ thương hiệu {brand}.",
        f"{brand} là nhà sản xuất của {product_type_name} {product_name}.",
        f"sản phẩm {product_type_name} {product_name} được sản xuất bởi hãng {brand}.",
        f"đây là {product_type_name} {product_name} thuộc thương hiệu {brand}.",
        f"{brand} mang đến chất lượng cho {product_type_name} {product_name}.",
        f"thương hiệu {brand} đã thiết kế và sản xuất {product_type_name} {product_name}."
    ]
    
    return random.choice(templates).lower()

# GENERATE FROM SPECS
def generate_spec_description(specs, product_name, product_type):
    if not specs:
        return []

    product_type_dict = {
        'phone': 'điện thoại',
        'laptop': 'laptop',
        'tablet': 'máy tính bảng',
        'monitor': 'màn hình',
        'pc': 'máy tính'
    }

    product_type_name = product_type_dict.get(product_type, 'sản phẩm')
    descriptions = []

    for key, value in specs.items():
        if isinstance(value, list):
            value_str = ", ".join(str(v).strip() for v in value)
        else:
            value_str = str(value).lower().strip()

        sentence = f"{key.lower()} của {product_type_name} {product_name} là {value_str}.".lower()
        descriptions.append(sentence)

    return descriptions

def parse_json_field(value):
    if isinstance(value, str):
        try:
            return json.loads(value.replace("'", '"'))  # xử lý khi chuỗi dùng dấu nháy đơn
        except json.JSONDecodeError:
            return {}
    return value if value else {}

def parse_price_list(value):
    if isinstance(value, str):
        try:
            return json.loads(value.replace("'", '"'))
        except json.JSONDecodeError:
            return {}
    return value if value else {}


def remove_unwanted_words(product_name):
    for word in ['điện thoại', 'máy tính bảng', 'laptop']:
        product_name = re.sub(r'\b' + re.escape(word) + r'\b', '', product_name, flags=re.IGNORECASE).strip()
    return product_name

def generated_features_df(df, product_type):
    logger = get_logger()
    
    df['features'] = df['features'].apply(lambda x: x if isinstance(x, list) else [])  # Đảm bảo rằng 'features' là danh sách

    for i, row in df.iterrows():
        # product_name = row['name'].strip() 
        product_name = remove_unwanted_words(row['name']) 
        
        # Lấy các features cũ (nếu có)
        combined_features = row['features']

        # Mô tả từ needs (nhu cầu sử dụng)
        needs = parse_json_field(row.get('needs'))
        if isinstance(needs, list):
            filter_descs = generate_needs_description(needs, product_type, product_name=product_name)
            combined_features.extend(filter_descs)  # Thêm vào danh sách các features cũ
        
        # Mô tả thương hiệu
        brand_desc = generate_brand_description(row['brand'], product_name=product_name, product_type=product_type)
        combined_features.append(brand_desc)
        
        # Mô tả thông số kỹ thuật
        specs = parse_json_field(row.get('specifications'))
        if isinstance(specs, dict):
            spec_desc = generate_spec_description(specs, product_name=product_name, product_type=product_type)  # Sử dụng 'specs' đã là dictionary
            combined_features.extend(spec_desc)
       
        # Mô tả giá sản phẩm
        prices = parse_price_list(row.get('prices'))
        if isinstance(prices, dict):
            price_features = generate_price_features(prices, product_name=product_name, product_type=product_type)
            combined_features.extend(price_features)

        # Cập nhật lại cột 'features' với các features đã bổ sung
        df.at[i, 'features'] = combined_features
        logger.info(f"Tổng số features cho {product_name}: {len(combined_features)}")
        
                
    # Chuyển đổi các giá trị trong cột 'features' thành chuỗi
    df['features'] = df['features'].apply(lambda x: str(x).lower())

    return df
