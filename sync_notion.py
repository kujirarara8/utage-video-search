#!/usr/bin/env python3
"""
Notion DBから動画データを取得し、data.jsonに書き出すスクリプト
GitHub Actionsから定期実行される。
"""
import os
import json
import sys
import urllib.request
import urllib.error

NOTION_TOKEN = os.environ.get('NOTION_TOKEN')
DATABASE_ID = os.environ.get('NOTION_DATABASE_ID', '349690fe3fa4805abf07d4b0c0a806c0')
NOTION_VERSION = '2022-06-28'
OUTPUT_FILE = 'data.json'

# カテゴリの並び順（このサイト上での表示順）
CATEGORY_ORDER = [
    'マインド',
    'ショップ設計基礎',
    '戦略',
    'マルシェ',
    '商品撮影',
    'インスタ',
    'minne・creema',
    'LP・告知動画',
]


def fetch_database_pages():
    """Notion DB の全ページを取得（ページネーション対応）"""
    url = f'https://api.notion.com/v1/databases/{DATABASE_ID}/query'
    headers = {
        'Authorization': f'Bearer {NOTION_TOKEN}',
        'Notion-Version': NOTION_VERSION,
        'Content-Type': 'application/json',
    }

    all_pages = []
    next_cursor = None

    while True:
        body = {'page_size': 100}
        if next_cursor:
            body['start_cursor'] = next_cursor

        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode('utf-8'),
            headers=headers,
            method='POST',
        )

        try:
            with urllib.request.urlopen(req) as res:
                data = json.loads(res.read())
        except urllib.error.HTTPError as e:
            print(f'❌ Notion APIエラー: {e.code} {e.reason}')
            print(e.read().decode('utf-8'))
            sys.exit(1)

        all_pages.extend(data['results'])

        if not data.get('has_more'):
            break
        next_cursor = data.get('next_cursor')

    return all_pages


def extract_text(prop):
    """title / rich_text 系プロパティから文字列を取り出す"""
    if not prop:
        return ''
    if prop.get('type') == 'title':
        items = prop.get('title', [])
    elif prop.get('type') == 'rich_text':
        items = prop.get('rich_text', [])
    else:
        return ''
    return ''.join(item.get('plain_text', '') for item in items).strip()


def extract_select(prop):
    """select プロパティの値を取り出す"""
    if not prop or prop.get('type') != 'select':
        return ''
    sel = prop.get('select')
    return sel['name'] if sel else ''


def extract_multi_select(prop):
    """multi_select プロパティの値を配列で取り出す"""
    if not prop or prop.get('type') != 'multi_select':
        return []
    return [item['name'] for item in prop.get('multi_select', [])]


def extract_url(prop):
    """url プロパティを取り出す"""
    if not prop or prop.get('type') != 'url':
        return ''
    return prop.get('url') or ''


def transform(pages):
    """Notionレスポンスをサイト用JSONに変換"""
    videos = []
    for page in pages:
        props = page.get('properties', {})
        title = extract_text(props.get('動画タイトル'))
        if not title:
            continue
        videos.append({
            'title': title,
            'category': extract_select(props.get('カテゴリ')),
            'keywords': extract_multi_select(props.get('キーワード')),
            'summary': extract_text(props.get('概要')),
            'url': extract_url(props.get('動画リンク')),
        })

    # カテゴリの順 → タイトルの順 でソート
    def sort_key(v):
        cat = v.get('category', '')
        cat_idx = CATEGORY_ORDER.index(cat) if cat in CATEGORY_ORDER else 999
        return (cat_idx, v['title'])

    videos.sort(key=sort_key)
    return videos


def main():
    if not NOTION_TOKEN:
        print('❌ NOTION_TOKEN が設定されていません')
        sys.exit(1)

    print(f'📥 Notion DB から取得開始: {DATABASE_ID}')
    pages = fetch_database_pages()
    print(f'  取得ページ数: {len(pages)}')

    videos = transform(pages)
    print(f'  有効な動画: {len(videos)}件')

    # カテゴリ別集計
    cat_count = {}
    for v in videos:
        c = v['category'] or '(未分類)'
        cat_count[c] = cat_count.get(c, 0) + 1
    for c, n in sorted(cat_count.items(), key=lambda x: -x[1]):
        print(f'    {c}: {n}件')

    # 保存（既存と同じなら更新不要）
    new_json = json.dumps(videos, ensure_ascii=False, indent=2)
    try:
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            old_json = f.read()
        if old_json == new_json:
            print('✓ 変更なし（書き込みスキップ）')
            return
    except FileNotFoundError:
        pass

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(new_json)
    print(f'✓ {OUTPUT_FILE} を更新')


if __name__ == '__main__':
    main()
