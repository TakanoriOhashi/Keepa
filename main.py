from __future__ import annotations

"""
Shopee向け仕入れ機会発掘ツール（完全無料版）
価格.com を使って Amazon・楽天・ビックカメラの価格差を自動検出する

【条件】
  - Amazon価格 > 楽天 or ビックカメラ の場合のみ表示
  - 対象: Amazon価格 1万円以上の商品

使い方:
    python main.py
    python main.py --category camera --min-price 15000
    python main.py --category smartphone --min-diff 1000 --pages 3
    python main.py --keyword "ゲーミングヘッドセット"
"""
import argparse
import csv
import sys
import time
from datetime import datetime

from kakaku_scraper import KakakuScraper, KakakuProduct, CATEGORY_IDS


def parse_args():
    parser = argparse.ArgumentParser(
        description="価格.com経由 Amazon vs 楽天・ビックカメラ価格比較ツール"
    )
    parser.add_argument(
        "--category", default="all",
        help=f"カテゴリ。選択肢: {', '.join(CATEGORY_IDS.keys())} (デフォルト: all)"
    )
    parser.add_argument(
        "--keyword", default="",
        help="検索キーワード（例: 'ゲーミングマウス'）"
    )
    parser.add_argument(
        "--min-price", type=int, default=5000,
        help="最低Amazon価格（円）（デフォルト: 5000）"
    )
    parser.add_argument(
        "--max-price", type=int, default=13000,
        help="最高Amazon価格（円）（デフォルト: 13000）"
    )
    parser.add_argument(
        "--min-diff", type=int, default=500,
        help="検出する最低差額（円）（デフォルト: 500）"
    )
    parser.add_argument(
        "--pages", type=int, default=3,
        help="取得ページ数（1ページ約50件）（デフォルト: 3）"
    )
    parser.add_argument(
        "--interval", type=float, default=2.0,
        help="リクエスト間隔（秒）（デフォルト: 2.0）"
    )
    parser.add_argument(
        "--output", default="",
        help="出力CSVファイル名（デフォルト: 自動生成）"
    )
    return parser.parse_args()


def run(args):
    scraper = KakakuScraper(request_interval=args.interval)

    # Step 1: 商品一覧を取得
    all_products: list[KakakuProduct] = []
    print(f"[検索] カテゴリ={args.category}, キーワード='{args.keyword}', "
          f"価格{args.min_price:,}円以上, {args.pages}ページ")

    for page in range(1, args.pages + 1):
        print(f"  ページ {page}/{args.pages} 取得中...", end=" ", flush=True)
        products = scraper.search_products(
            category=args.category,
            min_price=args.min_price,
            max_price=args.max_price,
            page=page,
            keyword=args.keyword,
        )
        print(f"{len(products)} 件")
        all_products.extend(products)
        if len(products) == 0:
            break  # 結果なし

    if not all_products:
        print("商品が見つかりませんでした。キーワードやカテゴリを変えて試してください。")
        sys.exit(0)

    # 重複除去（同じ kakaku_id）
    seen = set()
    unique_products = []
    for p in all_products:
        key = p.kakaku_id or p.kakaku_url
        if key and key not in seen:
            seen.add(key)
            unique_products.append(p)

    print(f"\n合計 {len(unique_products)} 件。ショップ別価格を取得中...\n")

    # Step 2: 各商品のショップ別価格を取得して比較
    opportunities: list[KakakuProduct] = []
    total = len(unique_products)

    for i, product in enumerate(unique_products, 1):
        # プログレスバー
        bar_len = 30
        filled = int(bar_len * i / total)
        bar = "#" * filled + "-" * (bar_len - filled)
        print(f"\r  [{bar}] {i}/{total}  ", end="", flush=True)

        scraper.get_shop_prices(product)

        # Amazonに価格がなければスキップ（Amazonで売っていない商品）
        if product.amazon_price is None:
            continue

        # Amazon価格が指定範囲外はスキップ
        if product.amazon_price < args.min_price:
            continue
        if args.max_price > 0 and product.amazon_price > args.max_price:
            continue

        # 仕入れ機会判定
        if product.is_opportunity(args.min_diff):
            opportunities.append(product)
            print(
                f"\n  [発見!] {product.title[:40]}\n"
                f"          Amazon:{product.amazon_price:,}円 → "
                f"{product.best_source}:{product.best_source_price:,}円 "
                f"(差額 {product.max_savings:,}円 / {product.savings_rate}%)"
            )

    print(f"\n\n完了。{len(unique_products)} 件チェック → 仕入れ機会 {len(opportunities)} 件発見")

    return opportunities


def save_csv(opportunities: list[KakakuProduct], output_path: str):
    if not opportunities:
        print("仕入れ機会が見つかりませんでした。")
        return

    # 節約額の大きい順にソート
    opportunities.sort(key=lambda x: x.max_savings or 0, reverse=True)

    rows = [o.to_dict() for o in opportunities]
    fieldnames = list(rows[0].keys())

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"結果を保存: {output_path}")


def print_top10(opportunities: list[KakakuProduct]):
    if not opportunities:
        return

    sorted_ops = sorted(opportunities, key=lambda x: x.max_savings or 0, reverse=True)
    print("\n" + "=" * 65)
    print("  仕入れ機会 TOP10（節約額順）")
    print("=" * 65)

    for i, op in enumerate(sorted_ops[:10], 1):
        print(
            f"{i:2}. {op.title[:48]}\n"
            f"     Amazon: {op.amazon_price:>8,}円  "
            f"{op.best_source}: {op.best_source_price:>8,}円  "
            f"差額: {op.max_savings:>6,}円 ({op.savings_rate}%)\n"
            f"     {op.kakaku_url}"
        )


def main():
    args = parse_args()
    opportunities = run(args)

    output_path = args.output or f"opportunities_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    save_csv(opportunities, output_path)
    print_top10(opportunities)


if __name__ == "__main__":
    main()
