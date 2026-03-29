# Shopee向け仕入れ機会発掘ツール

価格.com を使って **Amazon・楽天・ビックカメラの価格差** を自動検出し、Shopeeで利益が取れる商品を見つけるツールです。

## 仕組み

```
価格.com を検索
    ↓
各商品のショップ別価格を取得（Amazon・楽天・ビックカメラ）
    ↓
Amazon > 楽天 or ビックカメラ の差額が大きい商品を抽出
    ↓
結果をCSVで出力
```

**表示される商品の条件（重要）**
- Amazon価格 が 楽天 or ビックカメラ より高い場合のみ表示
- Amazonが一番安い商品は除外（Shopeeへの出品ツールの仕様上、仕入れ先を変えるメリットがないため）

---

## セットアップ

### 1. Python のインストール確認

```bash
python --version
# Python 3.9 以上推奨
```

### 2. ライブラリのインストール

```bash
pip install -r requirements.txt
```

インストールされるライブラリ:

| ライブラリ | 用途 |
|---|---|
| requests | HTTP通信 |
| beautifulsoup4 | HTMLの解析 |
| lxml | HTMLパーサー（高速） |

**APIキーは不要です。完全無料で動きます。**

---

## 使い方

### 基本実行（デフォルト設定）

```bash
python main.py
```

デフォルト設定:
- 対象価格: **5,000円〜13,000円**
- 最低差額: 500円以上
- 取得ページ数: 2ページ（約60件）
- カテゴリ: 全カテゴリ

---

### よく使うオプション

#### カテゴリを絞る

```bash
python main.py --category camera
python main.py --category smartphone
python main.py --category game
```

利用可能なカテゴリ一覧:

| キー | 説明 |
|---|---|
| `all` | 全カテゴリ（デフォルト） |
| `camera` | カメラ・ビデオカメラ |
| `pc` | パソコン・周辺機器 |
| `smartphone` | スマートフォン |
| `audio` | オーディオ機器 |
| `tv` | テレビ |
| `game` | TVゲーム |
| `appliance` | 家電 |
| `watch` | 腕時計 |
| `beauty` | 美容・健康 |

#### キーワードで検索

```bash
python main.py --keyword "ゲーミングヘッドセット"
python main.py --keyword "ワイヤレスイヤホン"
```

#### 価格帯を変える

```bash
# 8,000円〜20,000円に変更
python main.py --min-price 8000 --max-price 20000
```

#### 差額の閾値を上げる（より大きな差額だけ表示）

```bash
python main.py --min-diff 1000
```

#### 取得ページ数を増やす（より多くの商品を検索）

```bash
python main.py --pages 5
```

1ページ約30件なので、5ページ = 約150件チェック

#### 出力ファイル名を指定

```bash
python main.py --output result_camera.csv
```

指定しない場合は `opportunities_20260328_123456.csv` のように自動生成されます。

---

### 組み合わせ例

```bash
# カメラカテゴリ、差額1,000円以上、5ページ分
python main.py --category camera --min-diff 1000 --pages 5

# キーワード検索、価格帯を広げる
python main.py --keyword "スマートウォッチ" --min-price 5000 --max-price 30000

# ゲームカテゴリ、結果をファイル名指定で保存
python main.py --category game --output game_result.csv
```

---

## 出力CSVの見方

実行後に `opportunities_YYYYMMDD_HHMMSS.csv` が生成されます。
Excelで開く場合は文字化けしないよう **UTF-8（BOM付き）** で保存されています。

| 列名 | 説明 |
|---|---|
| 商品名 | 商品のタイトル |
| Amazon価格(円) | Amazon.co.jp の現在価格 |
| 楽天最安値(円) | 楽天市場の最安値 |
| 楽天差額(円) | Amazon - 楽天（正の値 = 楽天が安い） |
| ビックカメラ価格(円) | ビックカメラの価格 |
| ビックカメラ差額(円) | Amazon - ビックカメラ |
| 最安仕入先 | 楽天 or ビックカメラ（どちらが安いか） |
| 最安仕入価格(円) | 仕入れ先の価格 |
| 最大節約額(円) | Amazon価格との差額 |
| 節約率(%) | 節約額 ÷ Amazon価格 × 100 |
| 価格.com URL | 価格.com の商品ページURL |

---

## 注意事項

- 価格.com のスクレイピングを行うため、**過度な実行は避けてください**（デフォルト2秒間隔）
- 取得する価格はリアルタイムではなく、価格.com の更新タイミングに依存します
- ビックカメラ・楽天が価格.com に出品していない商品は価格が取得できません
- 実際の仕入れ前に必ず各サイトで価格を確認してください

---

## ファイル構成

```
Keepa/
├── main.py              # メインスクリプト（ここを実行する）
├── kakaku_scraper.py    # 価格.comスクレイパー
├── requirements.txt     # 依存ライブラリ
└── README.md            # このファイル
```
