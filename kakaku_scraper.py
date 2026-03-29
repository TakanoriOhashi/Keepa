from __future__ import annotations

"""
価格.com スクレイパー

search.kakaku.com のキーワード検索を使って商品を取得し、
各商品の価格比較ページから Amazon・楽天・ビックカメラの価格を抽出する。

検索URL: https://search.kakaku.com/{keyword}/?Price_from=5000&Price_to=13000&p=1
価格比較: https://kakaku.com/item/{id}/pricecomparison/
"""
import re
import time
import requests
from bs4 import BeautifulSoup
from typing import Optional
from dataclasses import dataclass, field
import urllib.parse

KAKAKU_BASE        = "https://kakaku.com"
KAKAKU_SEARCH_BASE = "https://search.kakaku.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
}

# ショップ名判定（小文字で部分一致）
AMAZON_KEYWORDS    = ["amazon"]
RAKUTEN_KEYWORDS   = ["楽天", "rakuten"]
BICCAMERA_KEYWORDS = ["ビックカメラ", "biccamera"]

# カテゴリ → 検索キーワード
CATEGORY_KEYWORDS = {
    "all":        None,          # DEFAULT_KEYWORDS をループ
    "camera":     "デジタルカメラ",
    "mirrorless": "ミラーレス一眼",
    "smartphone": "スマートフォン",
    "pc":         "ノートパソコン",
    "tablet":     "タブレット",
    "audio":      "ワイヤレスイヤホン",
    "headphone":  "ヘッドホン",
    "tv":         "液晶テレビ",
    "game":       "ゲーム機",
    "watch":      "スマートウォッチ",
    "beauty":     "美顔器",
}

# "all" のときに順番に検索するキーワード群
DEFAULT_KEYWORDS = [
    # オーディオ・イヤホン
    "ワイヤレスイヤホン",
    "ヘッドホン",
    "Bluetoothスピーカー",
    "ネックスピーカー",
    # カメラ・映像
    "デジタルカメラ",
    "ミラーレス一眼",
    "アクションカメラ",
    "ドライブレコーダー",
    "ウェブカメラ",
    # スマホ・ウェアラブル
    "スマートフォン",
    "スマートウォッチ",
    "スマートバンド",
    "ワイヤレス充電器",
    # PC・周辺機器
    "ノートパソコン",
    "タブレット",
    "ゲーミングマウス",
    "ゲーミングキーボード",
    "外付けSSD",
    "モバイルバッテリー",
    # ゲーム
    "ゲームコントローラー",
    "携帯ゲーム機",
    # 生活家電
    "電動歯ブラシ",
    "電気シェーバー",
    "ロボット掃除機",
    "空気清浄機",
    "美顔器",
    # その他
    "ポータブル電源",
    "電子書籍リーダー",
]

# main.py から参照
CATEGORY_IDS = {k: k for k in CATEGORY_KEYWORDS}


@dataclass
class KakakuProduct:
    """価格.comから取得した商品情報"""
    kakaku_id: str = ""
    title: str = ""
    kakaku_url: str = ""
    image_url: str = ""
    lowest_price: Optional[int] = None
    lowest_shop: str = ""

    amazon_price: Optional[int] = None
    rakuten_price: Optional[int] = None
    biccamera_price: Optional[int] = None
    shop_prices: list = field(default_factory=list)

    rakuten_diff: Optional[int] = None
    biccamera_diff: Optional[int] = None
    best_source: str = ""
    best_source_price: Optional[int] = None
    max_savings: Optional[int] = None
    savings_rate: Optional[float] = None

    def calculate_diffs(self):
        if self.amazon_price is None:
            return
        if self.rakuten_price is not None:
            self.rakuten_diff = self.amazon_price - self.rakuten_price
        if self.biccamera_price is not None:
            self.biccamera_diff = self.amazon_price - self.biccamera_price

        candidates = []
        if self.rakuten_diff and self.rakuten_diff > 0:
            candidates.append(("楽天", self.rakuten_price, self.rakuten_diff))
        if self.biccamera_diff and self.biccamera_diff > 0:
            candidates.append(("ビックカメラ", self.biccamera_price, self.biccamera_diff))

        if candidates:
            best = max(candidates, key=lambda x: x[2])
            self.best_source      = best[0]
            self.best_source_price = best[1]
            self.max_savings      = best[2]
            self.savings_rate     = round(self.max_savings / self.amazon_price * 100, 1)

    def is_opportunity(self, min_diff: int = 500) -> bool:
        return self.max_savings is not None and self.max_savings >= min_diff

    def to_dict(self) -> dict:
        return {
            "商品名": self.title,
            "Amazon価格(円)": self.amazon_price or "",
            "楽天最安値(円)": self.rakuten_price or "",
            "楽天差額(円)": self.rakuten_diff if (self.rakuten_diff and self.rakuten_diff > 0) else "",
            "ビックカメラ価格(円)": self.biccamera_price or "",
            "ビックカメラ差額(円)": self.biccamera_diff if (self.biccamera_diff and self.biccamera_diff > 0) else "",
            "最安仕入先": self.best_source,
            "最安仕入価格(円)": self.best_source_price or "",
            "最大節約額(円)": self.max_savings or "",
            "節約率(%)": self.savings_rate or "",
            "価格.com URL": self.kakaku_url,
        }


class KakakuScraper:
    def __init__(self, request_interval: float = 2.0):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.interval = request_interval
        self._last_request = 0.0

    def _get(self, url: str, params: dict = None) -> Optional[BeautifulSoup]:
        elapsed = time.time() - self._last_request
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self._last_request = time.time()

        try:
            resp = self.session.get(url, params=params, timeout=20)
            resp.raise_for_status()
            # search.kakaku.com は UTF-8、kakaku.com は Shift-JIS
            resp.encoding = resp.apparent_encoding
            return BeautifulSoup(resp.text, "lxml")
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return None  # 404は正常な「結果なし」として扱う
            print(f"\n[価格.com] HTTPエラー ({url}): {e}")
            return None
        except requests.RequestException as e:
            print(f"\n[価格.com] リクエストエラー ({url}): {e}")
            return None

    # ------------------------------------------------------------------ #
    #  商品一覧取得
    # ------------------------------------------------------------------ #
    def search_products(
        self,
        category: str = "all",
        min_price: int = 5000,
        max_price: int = 13000,
        page: int = 1,
        keyword: str = "",
    ) -> list[KakakuProduct]:
        """
        商品一覧を取得する（価格比較なし）

        キーワード指定 > カテゴリキーワード > all(複数キーワード) の順で使う
        """
        if keyword:
            return self._fetch(keyword, min_price, max_price, page)

        if category == "all":
            results = []
            for kw in DEFAULT_KEYWORDS:
                products = self._fetch(kw, min_price, max_price, page)
                results.extend(products)
            return results

        kw = CATEGORY_KEYWORDS.get(category, category)
        return self._fetch(kw, min_price, max_price, page)

    def _fetch(
        self, keyword: str, min_price: int, max_price: int, page: int
    ) -> list[KakakuProduct]:
        """search.kakaku.com でキーワード検索して商品リストを返す"""
        encoded = urllib.parse.quote(keyword)
        url = f"{KAKAKU_SEARCH_BASE}/{encoded}/"
        params: dict = {"Price_from": min_price, "p": page}
        if max_price > 0:
            params["Price_to"] = max_price

        soup = self._get(url, params=params)
        if soup is None:
            return []
        return self._parse_result_list(soup)

    def _parse_result_list(self, soup: BeautifulSoup) -> list[KakakuProduct]:
        products = []
        for item in soup.select("div.p-resultItem"):
            product = self._parse_result_item(item)
            if product:
                products.append(product)
        return products

    def _parse_result_item(self, item_el) -> Optional[KakakuProduct]:
        # 価格.com上に独自ページがある商品のみ対象（/item/{id}/ URLを持つもの）
        link = None
        for a in item_el.select("a[href]"):
            href = a.get("href", "")
            if re.search(r"/item/[JK]\d+/", href):
                link = a
                break

        if not link:
            return None

        title = link.get_text(strip=True)
        href  = link.get("href", "")
        url = href if href.startswith("http") else KAKAKU_BASE + href

        m = re.search(r"/item/([JK]\d+)/", url)
        kakaku_id = m.group(1) if m else ""

        price_el    = item_el.select_one("em.p-item_priceNum")
        lowest_price = _parse_price(price_el.get_text()) if price_el else None

        img       = item_el.select_one("img.p-item_visual_entity") or item_el.select_one("img")
        image_url = img.get("src", "") if img else ""

        return KakakuProduct(
            kakaku_id=kakaku_id,
            title=title,
            kakaku_url=url,
            image_url=image_url,
            lowest_price=lowest_price,
        )

    # ------------------------------------------------------------------ #
    #  ショップ別価格取得
    # ------------------------------------------------------------------ #
    def get_shop_prices(self, product: KakakuProduct) -> KakakuProduct:
        """価格比較ページから Amazon・楽天・ビックカメラの価格をセット"""
        if not product.kakaku_url:
            return product

        price_url = product.kakaku_url.rstrip("/") + "/pricecomparison/"
        soup = self._get(price_url)
        if soup is None:
            return product

        self._extract_shop_prices(soup, product)
        product.calculate_diffs()
        return product

    def _extract_shop_prices(self, soup: BeautifulSoup, product: KakakuProduct):
        shop_prices = []

        for row in soup.select("li.p-priceList_item"):
            shop_el  = row.select_one("a.p-priceList_shopName")
            price_el = row.select_one("p.p-priceList_price")
            if not shop_el or not price_el:
                continue

            shop_name = shop_el.get_text(strip=True)
            price     = _parse_price(price_el.get_text())
            if price is None:
                continue

            shop_prices.append((shop_name, price))
            shop_lower = shop_name.lower()

            if any(k in shop_lower for k in AMAZON_KEYWORDS):
                if product.amazon_price is None or price < product.amazon_price:
                    product.amazon_price = price

            elif any(k in shop_lower for k in RAKUTEN_KEYWORDS):
                if product.rakuten_price is None or price < product.rakuten_price:
                    product.rakuten_price = price

            elif any(k in shop_name for k in BICCAMERA_KEYWORDS):
                if product.biccamera_price is None or price < product.biccamera_price:
                    product.biccamera_price = price

        product.shop_prices = shop_prices
        if shop_prices:
            cheapest           = min(shop_prices, key=lambda x: x[1])
            product.lowest_price = cheapest[1]
            product.lowest_shop  = cheapest[0]


def _parse_price(text: str) -> Optional[int]:
    """'22,989~' や '¥12,800' などから数値を抽出"""
    # '~' より前だけ使う
    text = text.split("~")[0]
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return None
    price = int(digits)
    if price < 100 or price > 10_000_000:
        return None
    return price
