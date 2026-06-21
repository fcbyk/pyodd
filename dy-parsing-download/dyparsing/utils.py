# ==============================================================================
# Copyright (C) 2021 Evil0ctal
#
# This file is part of the Douyin_TikTok_Download_API project.
#
# This project is licensed under the Apache License 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================


import re
import sys
import random
import secrets
import datetime

from typing import Union, List

# 生成一个 16 字节的随机字节串
seed_bytes = secrets.token_bytes(16)
seed_int = int.from_bytes(seed_bytes, "big")
random.seed(seed_int)


def gen_random_str(randomlength: int) -> str:
    """
    根据传入长度产生随机字符串
    """
    base_str = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-"
    return "".join(random.choice(base_str) for _ in range(randomlength))


def get_timestamp(unit: str = "milli"):
    """
    根据给定的单位获取当前时间
    """
    now = datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)
    if unit == "milli":
        return int(now.total_seconds() * 1000)
    elif unit == "sec":
        return int(now.total_seconds())
    elif unit == "min":
        return int(now.total_seconds() / 60)
    else:
        raise ValueError("Unsupported time unit")


def extract_valid_urls(inputs: Union[str, List[str]]) -> Union[str, List[str], None]:
    """从输入中提取有效的URL"""
    url_pattern = re.compile(r"https?://\S+")

    if isinstance(inputs, str):
        match = url_pattern.search(inputs)
        return match.group(0) if match else None

    elif isinstance(inputs, list):
        valid_urls = []
        for input_str in inputs:
            matches = url_pattern.findall(input_str)
            if matches:
                valid_urls.extend(matches)
        return valid_urls


def split_filename(text: str, os_limit: dict) -> str:
    """
    根据操作系统的字符限制分割文件名
    """
    os_name = sys.platform
    filename_length_limit = os_limit.get(os_name, 200)

    chinese_length = sum(1 for char in text if "\u4e00" <= char <= "\u9fff") * 3
    english_length = sum(1 for char in text if char.isalpha())
    num_underscores = text.count("_")

    total_length = chinese_length + english_length + num_underscores

    if total_length > filename_length_limit:
        split_index = min(total_length, filename_length_limit) // 2 - 6
        split_text = text[:split_index] + "......" + text[-split_index:]
        return split_text
    else:
        return text
