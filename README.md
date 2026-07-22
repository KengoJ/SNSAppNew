- Font Awesomeアイコン導入
- 文字化けしていた画面文言の修正

### Ajax化

- 投稿の非同期送信
- 投稿の非同期削除
- 投稿検索の非同期化
- ユーザー検索の非同期化
- Toast通知
- 削除確認モーダル
- ローディング表示

### SNS機能の追加

- 投稿へのいいね
- 投稿への返信
- 通知機能
- 通知バッジ
- 通知画面を開いた時の既読処理
- DM送信のAjax化
- プロフィール / ポートフォリオページ
- 自己紹介、スキル、ポートフォリオURLの登録

### DB・保守性の改善

- 新機能用のDBモデル追加
  - `EntryLike`
  - `EntryReply`
  - `Notification`
- ユーザー情報へのプロフィール項目追加
- 既存DBに対する軽いスキーマ更新処理
- DBパスの安定化
- サンプルデータの追加

## 工夫した点

- 既存の掲示板アプリの構造を活かしながら、SNSらしい機能を段階的に追加しました。
- Python側の変更は必要な機能追加に絞り、UIや操作性の改善はテンプレート、CSS、JavaScriptを中心に行いました。
- Ajax化により、投稿・削除・検索・DM送信の操作で画面遷移を減らし、使いやすさを改善しました。
- 通知、いいね、返信、DMを組み合わせることで、単なる掲示板ではなく「ユーザー同士の交流があるアプリ」に近づけました。
- ポートフォリオページを追加し、ユーザーごとの自己紹介やスキルを表示できるようにしました。

## 起動方法

```bash
pip install -r requirements.txt
python run.py
```

起動後、ブラウザで以下にアクセスします。

```txt
http://127.0.0.1:5000/
```

## サンプルログインユーザー

DBには動作確認用のサンプルユーザーを追加しています。

| ユーザーID | パスワード |
|---|---|
| `sample_akira` | `password123` |
| `sample_mika` | `password123` |
| `sample_ren` | `password123` |
| `sample_yui` | `password123` |

## ディレクトリ構成

```txt
SNSApp-master/
├── main/
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css
│   │   ├── js/
│   │   │   └── app.js
│   │   └── imgs/
│   ├── templates/
│   │   ├── layout.html
│   │   ├── bbs.html
│   │   ├── thread.html
│   │   ├── profile.html
│   │   ├── notifications.html
│   │   ├── chat.html
│   │   ├── login.html
│   │   └── signup.html
│   ├── __init__.py
│   ├── config.py
│   ├── models.py
│   ├── views.py
│   └── First.db
├── run.py
├── requirements.txt
├── Procfile
├── runtime.txt
└── README.md
```

## 今後改善したい点

- CSRF対策の導入
- パスワード再設定機能の安全性向上
- DBマイグレーション管理の導入
- 投稿画像アップロード
- 通知のリアルタイム化
- テストコードの追加
- デプロイ環境での動作確認

## 補足

このプロジェクトは、自分で作成した掲示板アプリをベースに、AI支援を受けながら段階的に改修したものです。AIが生成したコードをそのまま使うのではなく、既存アプリの構造に合わせて機能を取り込み、動作確認や修正を行いながらポートフォリオとして見せられる形に整えました。
