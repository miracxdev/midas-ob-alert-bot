# Midas Yükselenler → Order Block Bildirim Botu

> **Bu dosya Claude Code için bir proje şartnamesidir (spec).**
> Proje klasörüne `CLAUDE.md` (veya `SPEC.md`) olarak koy, Claude Code'u o klasörde aç ve en alttaki **"Claude Code'a verilecek başlangıç komutu"** bölümündeki metni yapıştır.

---

## 1. Amaç (tek cümle)

Her gün Midas Kripto'daki **"Yükselenler"** listesinde çıkan coinleri al, her birinin **USDT paritesini** (yoksa USD) bul, **16:30'dan (İstanbul saati) sonra** grafiği periyodik tara ve kullandığım **Order Block (OB)** indikatörü yeni bir OB verdiği anda **telefonuma ve bilgisayarıma bildirim** gönder; bildirimde TradingView grafik linki olsun.

## 2. Akış (yüksek seviye)

```
16:25  ┌──────────────────────────┐
       │ 1. Midas "Yükselenler"   │  → ["XYZ", "ABC", "DEF", ...]
       │    listesini al          │
       └────────────┬─────────────┘
                    ▼
       ┌──────────────────────────┐
       │ 2. Sembol → parite eşle  │  XYZ → BINANCE:XYZUSDT (yoksa OKX/Bybit/Gate…)
       └────────────┬─────────────┘
                    ▼
16:30– ┌──────────────────────────┐
23:59  │ 3. Her mum kapanışında   │  OHLCV çek (ccxt) → OB algoritması
       │    OB taraması           │  (Pine Script mantığının Python portu)
       └────────────┬─────────────┘
                    ▼
       ┌──────────────────────────┐
       │ 4. Yeni OB? → tekrar     │  SQLite ile aynı sinyali iki kez atma
       │    kontrolü              │
       └────────────┬─────────────┘
                    ▼
       ┌──────────────────────────┐
       │ 5. Bildirim              │  Telegram (telefon+PC) + macOS bildirimi
       └──────────────────────────┘
```

## 3. Temel mimari kararı: OB'yi nerede hesaplıyoruz?

TradingView'in, bir indikatörün sinyalini dışarıdan okumaya yarayan **resmi bir API'si yok.** İki yol var:

| | **Yol A — Python portu (ÖNERİLEN)** | **Yol B — TradingView alarmları + webhook** |
|---|---|---|
| Nasıl | Pine OB mantığı Python'a çevrilir, OHLCV borsadan (ccxt) çekilir | Her coin için TradingView'de alarm kurulur, webhook bota düşer |
| Her gün değişen coin listesi | Otomatik, sınırsız | Her gün alarmları elle (ya da kırılgan tarayıcı otomasyonuyla) yeniden kurmak gerekir |
| Ücret | Ücretsiz | Webhook ve çoklu alarm için ücretli TradingView planı gerekir; plan başına alarm limiti var |
| Doğruluk | Port, TV'deki indikatörle karşılaştırılarak doğrulanmalı | İndikatörün birebir kendisi |
| Sağlamlık | Yüksek | TV arayüzü değişince otomasyon bozulur; kullanım şartları açısından riskli |

**Karar: Yol A ana mimari.** TradingView yalnızca bildirimdeki "grafiği aç" linki için kullanılır. Yol B, Bölüm 12'de opsiyonel ek olarak tarif edilmiştir.

## 4. Teknoloji ve araçlar

| Amaç | Araç | Not |
|---|---|---|
| Dil | Python 3.11+ | |
| Paket yönetimi | `uv` (veya `pip` + `venv`) | |
| Borsa verisi (OHLCV) | `ccxt` | Public endpoint, API key gerekmez. Öncelik: Binance → OKX → Bybit → Gate → KuCoin → MEXC |
| Veri işleme | `pandas`, `numpy` | |
| Midas listesi (web varsa) | `playwright` (Chromium) | Bkz. Bölüm 5 |
| Midas listesi (ekran görüntüsü) | Telegram bot + OCR (`pytesseract`) veya Claude API vision (`anthropic`) | En güvenilir yedek yol |
| Zamanlama | `APScheduler` (uygulama içi) + macOS `launchd` (uygulamayı ayakta tutmak için) | Saat dilimi: `Europe/Istanbul` |
| Bildirim — telefon & PC | Telegram Bot API (`python-telegram-bot` veya düz `httpx`) | Telegram masaüstü uygulaması PC'de de bildirim gösterir |
| Bildirim — alternatif | `ntfy.sh` (HTTP POST, iOS/Android/Desktop uygulaması var) | Telegram istemezsen |
| Bildirim — macOS yerel | `terminal-notifier` (brew) veya `osascript -e 'display notification ...'` | Sesli uyarı da eklenebilir |
| Kalıcı durum | `sqlite3` (stdlib) | Günlük liste, gönderilen sinyaller |
| Konfig | `config.yaml` + `.env` (`pydantic-settings`) | Token'lar `.env`'de, git'e girmez |
| Log | `loguru` | `logs/` klasörüne günlük rotasyon |
| Test | `pytest` | OB algoritması için sabit veriyle birim test |
| Lint/format | `ruff` | |

## 5. Midas "Yükselenler" listesini alma

Midas'ın herkese açık bir API'si olduğu bilinmiyor. **Claude Code, Faz 0'da aşağıdakileri sırayla araştırıp hangisinin çalıştığını raporlamalı.** Kod bir *adapter* deseniyle yazılır; hangi kaynak çalışıyorsa o kullanılır, diğerleri yedek kalır.

```python
class GainersSource(Protocol):
    name: str
    def fetch(self) -> list[str]: ...   # ["XYZ", "ABC", ...] — yalnızca base sembol
```

| Öncelik | Adapter | Açıklama |
|---|---|---|
| 1 | `MidasWebSource` | Midas'ın web arayüzünde kripto "Yükselenler" sayfası varsa Playwright ile aç, oturum çerezini `storage_state.json` olarak sakla (ilk girişi kullanıcı elle yapar), tabloyu oku. Sayfa arka planda bir JSON endpoint'ine istek atıyorsa (DevTools → Network) doğrudan o endpoint'i kullan. |
| 2 | `TelegramScreenshotSource` | Kullanıcı Midas uygulamasında Yükselenler ekranının görüntüsünü bota gönderir → bot görselden sembolleri çıkarır (Claude vision veya Tesseract) → listeyi onay için geri yazar. Günde 1 ekran görüntüsü, %100 çalışır. |
| 3 | `TelegramManualSource` | `/liste XYZ ABC DEF` komutu ile elle liste. |
| 4 | `FileSource` | `data/gainers_today.txt` dosyasından oku (her satıra bir sembol). |
| 5 | `ExchangeProxySource` (yedek) | Midas'a ulaşılamazsa: Binance 24s en çok yükselenler ∩ `data/midas_listed.txt` (Midas'ta listelenen coinler). Midas listesiyle birebir aynı olmaz; bildirimde "(proxy)" etiketi göster. |

Kurallar:
- Liste her gün **16:25**'te çekilir (konfigüre edilebilir). Elle/ekran görüntüsüyle gelen liste o gün için bunun yerine geçer.
- Listenin ilk **N** coini alınır (varsayılan `top_n: 10`).
- Sembol normalizasyonu: büyük harf, `TRY`/`USDT` son eklerini at, Midas'a özgü isimleri `data/symbol_aliases.yaml` ile eşle (ör. `"BTTC": "BTTC"`, `"1000PEPE": "PEPE"` gibi).
- Midas'ın kullanım şartlarına uy; scraping yasaksa Adapter 2/3'ü kullan.

## 6. Sembol → parite eşleme

```python
@dataclass
class Market:
    base: str            # "XYZ"
    quote: str           # "USDT" | "USD"
    exchange: str        # "binance"
    ccxt_symbol: str     # "XYZ/USDT"
    tv_symbol: str       # "BINANCE:XYZUSDT"
    tv_url: str          # "https://www.tradingview.com/chart/?symbol=BINANCE:XYZUSDT"
```

Algoritma:
1. `config.exchanges` sırasıyla dolaş (`binance, okx, bybit, gate, kucoin, mexc`).
2. Her borsada `load_markets()` (günde bir kez, cache'le) → önce `BASE/USDT` spot, yoksa `BASE/USD`.
3. İlk bulunan kazanır. Hiçbirinde yoksa logla ve Telegram'a "XYZ için USDT paritesi bulunamadı" bilgisini gönder.
4. TradingView prefix eşlemesi: `binance→BINANCE, okx→OKX, bybit→BYBIT, gate→GATEIO, kucoin→KUCOIN, mexc→MEXC`.
5. Yeterli geçmiş veri yoksa (yeni listelenmiş coin, `< min_bars`) atla ve bildir.

## 7. Order Block algoritması

### 7.1 Kullanıcının kendi indikatörü (öncelikli)
- Kullandığım OB indikatörünün Pine kaynağı `indicator/ob.pine` dosyasına konacak.
- Claude Code bu dosyayı **satır satır** Python'a port edecek (`ob/custom.py`), aynı girdiler (`input.*`) `config.yaml` → `ob.params` altında olacak.
- Pine fonksiyon karşılıkları: `ta.pivothigh/pivotlow` → kaydırmalı pencere, `ta.crossover` → `(a > b) & (a.shift() <= b.shift())`, `ta.atr` → Wilder RMA, `var` değişkenler → döngü içi durum, `barstate.isconfirmed` → yalnızca kapanmış mumlar.
- **Parite doğrulaması zorunlu:** Aynı coin + aynı zaman dilimi için son 300 mumda Python'un bulduğu OB'ler ile TradingView'de görünenler karşılaştırılır (Bölüm 11).

### 7.2 Varsayılan OB mantığı (Pine kaynağı gelene kadar)
Swing + yapı kırılımı (BOS) tabanlı, yaygın kullanılan tanım:

```
Girdiler: swing_len = 5, tf = "15m", use_body = False

1. Swing high/low: pivot bar, solundaki ve sağındaki swing_len barın en yükseği/en düşüğü.
   (Pivot ancak swing_len bar sonra onaylanır → repaint yok.)

2. Bullish OB:
   - Kapanış, son kırılmamış swing high'ın ÜSTÜNDE kapanırsa (BOS yukarı):
   - Swing high barı ile kırılım barı arasındaki son DÜŞÜŞ mumu (close < open) bulunur
     (aralıkta en düşük low'a sahip düşüş mumu).
   - OB bölgesi = o mumun [low, high] (use_body=True ise [min(o,c), max(o,c)]).
   - Sinyal zamanı = kırılım mumunun KAPANIŞI.

3. Bearish OB: simetriği (swing low altında kapanış, son YÜKSELİŞ mumu).

4. Mitigasyon: fiyat bölgeyi tamamen geçerek kapatırsa OB geçersiz sayılır.
```

### 7.3 Sinyal türleri (config ile seçilir)

| Event | Açıklama | Varsayılan |
|---|---|---|
| `ob_formed` | Yeni OB oluştu (indikatörün "OB verdiği an") | **açık** |
| `ob_retest` | Fiyat aktif bir OB bölgesine geri girdi | kapalı |
| `direction` | `bullish`, `bearish` veya `both` | `bullish` |

### 7.4 Kurallar
- **Sadece kapanmış mumlar** kullanılır (ccxt'nin döndürdüğü son mum açıksa at).
- Bir mumda oluşan OB yalnızca o mumun kapanışından sonraki ilk taramada bildirilir; "16:30'dan önce oluşmuş OB'ler" bildirilmez.
- Çoklu zaman dilimi desteklenir (`timeframes: ["15m", "1h"]`), her biri ayrı sinyal.

Arayüz:

```python
@dataclass
class OBSignal:
    market: Market
    timeframe: str
    kind: Literal["ob_formed", "ob_retest"]
    direction: Literal["bullish", "bearish"]
    zone_low: float
    zone_high: float
    candle_time: datetime        # OB'yi doğuran mumun kapanışı (UTC)
    price: float                 # son kapanış

    @property
    def key(self) -> str:        # tekrar kontrolü için
        return f"{self.market.tv_symbol}|{self.timeframe}|{self.kind}|{self.direction}|{self.candle_time.isoformat()}"

def detect(df: pd.DataFrame, params: OBParams) -> list[OBSignal]: ...
```

## 8. Zamanlama

- Saat dilimi her yerde `Europe/Istanbul`; DB'de UTC sakla.
- **16:25** → `refresh_watchlist` (liste + parite eşleme). Liste gelmemişse 16:30'da Telegram'dan hatırlatma: "Bugünün Yükselenler ekran görüntüsünü gönder."
- **16:30 – 23:59** → tarama penceresi (`scan_window: {start: "16:30", end: "23:59"}`, kriptolar 7/24 olduğu için bitiş saati ayarlanabilir; `"04:00"` gibi gece yarısını aşan değerler de desteklensin).
- Tarama tetikleyicisi **mum kapanışlarına hizalı**: 15m için her `:00, :15, :30, :45` + 10 saniye gecikme (borsanın mumu kapatması için). `1h` için her saat başı + 10 sn.
- Pencere dışında tarama yapılmaz, ama uygulama ayakta kalır.
- Hafta sonu dahil her gün çalışır (`days: [mon..sun]` ile değiştirilebilir).

macOS'ta sürekli çalıştırma — `launchd` (`~/Library/LaunchAgents/com.obbot.midas.plist`):
- `RunAtLoad=true`, `KeepAlive=true`, `StandardOutPath/StandardErrorPath` → `logs/`.
- Mac uykuya geçerse tarama durur: kullanıcıya `caffeinate` veya Enerji ayarı notu düşülsün, alternatif olarak küçük bir VPS / Raspberry Pi'ye `systemd` ile deploy talimatı da yazılsın.

## 9. Bildirimler

```python
class Notifier(Protocol):
    def send(self, signal: OBSignal) -> None: ...
    def send_text(self, text: str) -> None: ...
```

Uygulamalar: `TelegramNotifier` (varsayılan), `NtfyNotifier`, `MacOSNotifier`. Birden fazlası aynı anda aktif olabilir (`notifiers: [telegram, macos]`).

**Telegram kurulumu (README'de adım adım yazılmalı):**
1. Telegram'da `@BotFather` → `/newbot` → token'ı al → `.env` → `TELEGRAM_BOT_TOKEN=...`
2. Bota bir mesaj at → `https://api.telegram.org/bot<TOKEN>/getUpdates` ile `chat_id`'yi bul → `.env` → `TELEGRAM_CHAT_ID=...`
3. Telefon + Mac'teki Telegram uygulamasında bildirimleri aç.

**Mesaj formatı (sade, düz metin):**

```
🟢 BULLISH OB — XYZ/USDT (15m)
Bölge: 0.4123 – 0.4189
Fiyat: 0.4231
Mum: 17:45 (İST)
Borsa: Binance
📈 https://www.tradingview.com/chart/?symbol=BINANCE:XYZUSDT&interval=15
```

Bearish için 🔴. Aynı coinde 10 dakika içinde birden fazla sinyal olursa tek mesajda birleştir.

**Bot komutları:**

| Komut | İşlev |
|---|---|
| `/liste XYZ ABC ...` | Bugünün listesini elle ayarla |
| (fotoğraf) | Midas ekran görüntüsünden listeyi çıkar, onay iste |
| `/bugun` | Bugünün izleme listesi ve eşlenen pariteler |
| `/durum` | Son tarama zamanı, hata sayısı, aktif pencere |
| `/test` | Deneme bildirimi |
| `/durdur` / `/baslat` | Taramayı duraklat/devam ettir |

Bot yalnızca `.env`'deki `TELEGRAM_CHAT_ID`'den gelen mesajlara cevap verir.

## 10. Proje yapısı

```
midas-ob-bot/
├── CLAUDE.md                  # bu dosya
├── README.md                  # kurulum + kullanım (Claude Code yazar)
├── pyproject.toml
├── .env.example               # TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ANTHROPIC_API_KEY(ops.), NTFY_TOPIC(ops.)
├── config.yaml
├── indicator/
│   └── ob.pine                # kullanıcının OB indikatörü (kullanıcı koyar)
├── data/
│   ├── symbol_aliases.yaml
│   ├── midas_listed.txt       # proxy kaynağı için (opsiyonel)
│   └── bot.db                 # SQLite (otomatik oluşur, git'e girmez)
├── logs/
├── src/obbot/
│   ├── __init__.py
│   ├── main.py                # giriş noktası: scheduler + telegram polling
│   ├── config.py              # pydantic-settings
│   ├── models.py              # Market, OBSignal, OBParams
│   ├── db.py                  # watchlist, signals, runs tabloları
│   ├── scheduler.py           # 16:25 refresh, mum-hizalı tarama, pencere kontrolü
│   ├── sources/
│   │   ├── base.py            # GainersSource protokolü
│   │   ├── midas_web.py
│   │   ├── telegram_screenshot.py
│   │   ├── manual.py
│   │   ├── file.py
│   │   └── exchange_proxy.py
│   ├── markets/
│   │   ├── resolver.py        # sembol → Market
│   │   └── ohlcv.py           # ccxt ile OHLCV, retry, rate limit
│   ├── ob/
│   │   ├── default.py         # Bölüm 7.2
│   │   ├── custom.py          # ob.pine portu
│   │   └── pivots.py
│   ├── notify/
│   │   ├── base.py
│   │   ├── telegram.py
│   │   ├── ntfy.py
│   │   └── macos.py
│   └── bot/
│       └── commands.py        # /liste, /bugun, /durum ...
├── scripts/
│   ├── backtest_ob.py         # bir coin için geçmiş OB'leri listele (TV ile karşılaştırma)
│   ├── run_once.py            # tek tarama, pencere kontrolü olmadan (debug)
│   └── install_launchd.sh
├── deploy/
│   ├── com.obbot.midas.plist
│   └── obbot.service          # Linux/VPS için systemd
└── tests/
    ├── fixtures/              # sabit OHLCV CSV'leri
    ├── test_ob_default.py
    ├── test_resolver.py
    ├── test_window.py         # 16:30 penceresi, gece yarısı geçişi
    └── test_dedup.py
```

**SQLite şeması:**

```sql
CREATE TABLE watchlist (
  date TEXT, base TEXT, source TEXT, exchange TEXT, tv_symbol TEXT,
  PRIMARY KEY (date, base)
);
CREATE TABLE signals (
  key TEXT PRIMARY KEY, tv_symbol TEXT, timeframe TEXT, kind TEXT,
  direction TEXT, zone_low REAL, zone_high REAL, candle_time TEXT, sent_at TEXT
);
CREATE TABLE runs (
  started_at TEXT, finished_at TEXT, symbols INTEGER, signals INTEGER, errors TEXT
);
```

**`config.yaml` örneği:**

```yaml
timezone: Europe/Istanbul
watchlist:
  refresh_at: "16:25"
  top_n: 10
  sources: [midas_web, telegram_screenshot, manual, file, exchange_proxy]
scan_window: { start: "16:30", end: "23:59" }
days: [mon, tue, wed, thu, fri, sat, sun]
timeframes: ["15m"]
candle_close_delay_sec: 10
exchanges: [binance, okx, bybit, gate, kucoin, mexc]
quote_preference: [USDT, USD]
min_bars: 200
ob:
  engine: default          # default | custom
  direction: bullish       # bullish | bearish | both
  events: [ob_formed]      # ob_formed, ob_retest
  params: { swing_len: 5, use_body: false }
notifiers: [telegram, macos]
merge_window_min: 10
```

## 11. Geliştirme fazları (Claude Code bu sırayla ilerlesin)

Her fazın sonunda kısa bir rapor ver, kabul kriterini göster, sonra bir sonraki faza geç.

| Faz | İş | Kabul kriteri |
|---|---|---|
| **0 — Keşif** | Midas'a erişim yollarını araştır (web sayfası var mı, JSON endpoint var mı, giriş gerekli mi). Bulguları raporla. | Hangi `GainersSource`'un birincil olacağı netleşti |
| **1 — İskelet** | `pyproject`, config, `.env.example`, logging, SQLite, modeller | `python -m obbot.main --help` çalışıyor |
| **2 — Parite eşleme + OHLCV** | `resolver.py`, `ohlcv.py` (retry, rate limit, açık mumu atma) | `run_once.py --symbols BTC,PEPE,XYZFAKE` doğru Market'leri ve "bulunamadı"yı gösteriyor |
| **3 — OB motoru** | `default.py` + testler; `ob.pine` varsa `custom.py` portu | `pytest` yeşil; `backtest_ob.py BINANCE:BTCUSDT 15m` son 300 mumdaki OB'leri saat/bölge olarak listeliyor |
| **4 — TV ile parite kontrolü** | Kullanıcı 2–3 coin için TV'deki OB'lerle `backtest_ob.py` çıktısını karşılaştırır | Kullanıcı onayı; farklar giderildi |
| **5 — Bildirim** | Telegram + macOS notifier, mesaj formatı, birleştirme | `/test` telefona ve Mac'e düşüyor |
| **6 — Liste kaynakları** | Faz 0'da seçilen birincil kaynak + ekran görüntüsü + manuel | Günün listesi DB'ye yazılıyor, `/bugun` gösteriyor |
| **7 — Zamanlayıcı** | 16:25 refresh, 16:30–bitiş mum-hizalı tarama, dedup | `test_window.py` yeşil; saati taklit eden (freezegun) entegrasyon testi tek bildirim üretiyor |
| **8 — Çalıştırma** | `launchd` plist + kurulum scripti, `systemd` alternatifi, README | Mac yeniden başlasa da bot ayağa kalkıyor |
| **9 — (Ops.) Yol B** | TradingView webhook alıcısı (Bölüm 12) | — |

## 12. (Opsiyonel) Yol B — TradingView alarmları + webhook

İndikatörün birebir TradingView'deki halini kullanmak istersen:

1. Pine koduna `alert()` ekle (OB oluşan barda, `barstate.isconfirmed` ile), mesajı JSON yap:
   `{"symbol":"{{ticker}}","exchange":"{{exchange}}","tf":"{{interval}}","event":"ob_formed","dir":"bullish","price":{{close}}}`
2. Bot içinde küçük bir `FastAPI` endpoint'i: `POST /tv-webhook?secret=...` → aynı `Notifier`'a yolla. Gizli anahtar kontrolü zorunlu.
3. Webhook'un dışarıdan erişilebilmesi için `cloudflared tunnel` veya `ngrok`.
4. Kısıt: Webhook ve çok sayıda alarm ücretli plan ister; alarmlar sembol başına kurulduğu için her gün değişen liste elle güncellenmeli. TradingView arayüzünü tarayıcı otomasyonuyla sürmek kırılgandır ve platform şartlarıyla çelişebilir — **otomatik alarm kurma yapılmayacak.**
5. Saat filtresi: webhook bot tarafında da 16:30 penceresinden geçirilir.

## 13. Hata yönetimi ve dayanıklılık

- ccxt çağrılarında 3 deneme, üstel bekleme; `enableRateLimit=True`.
- Bir coinde hata diğerlerini durdurmaz; hata `runs.errors`'a yazılır.
- Art arda 3 tarama hatalıysa Telegram'a tek bir uyarı.
- Borsa erişilemezse sıradaki borsaya düş (resolver o gün için yeniden eşler).
- Telegram gönderimi başarısızsa kuyruğa al, sonraki taramada tekrar dene.
- Saat kayması: tüm zaman hesapları `zoneinfo` ile; sistem saatine güvenme, borsadan dönen mum zamanını esas al.

## 14. Güvenlik

- `.env`, `data/bot.db`, `storage_state.json` → `.gitignore`.
- Borsa API key'i **gerekmez** (sadece public veri); işlem açma yetkisi olan hiçbir anahtar kullanılmaz.
- Midas giriş bilgileri kodda/konfigte tutulmaz; Playwright oturumu kullanıcı tarafından elle açılır ve sadece çerez dosyası saklanır.
- Bot yalnızca yetkili `chat_id`'ye cevap verir.

## 15. Kapsam dışı

- Otomatik alım/satım emri.
- Midas hesabına herhangi bir yazma işlemi.
- TradingView hesabında otomatik alarm oluşturma.

> Not: Bu bir bildirim aracıdır, yatırım tavsiyesi üretmez.

---

## Claude Code'a verilecek başlangıç komutu

```
Bu klasördeki CLAUDE.md dosyası projenin tam şartnamesi. Önce tamamını oku.
Sonra Bölüm 11'deki fazları sırayla uygula. Faz 0'da Midas'a erişim yollarını
araştır ve bana rapor ver; hangi kaynağı birincil yapacağımızı birlikte seçelim.
indicator/ob.pine dosyası varsa Faz 3'te onu port et, yoksa Bölüm 7.2'deki
varsayılan mantığı kullan. Her fazın sonunda kabul kriterini göster ve onayımı bekle.
Tüm kullanıcıya dönük mesajlar ve README Türkçe olsun.
```

## Kullanıcının hazırlaması gerekenler (kontrol listesi)

- [ ] Kullandığın OB indikatörünün Pine kodu → `indicator/ob.pine` (kapalı kaynaksa indikatör adı + ayarlarının ekran görüntüsü)
- [ ] OB'yi hangi zaman diliminde izlediğin (15m, 1h …) ve sadece bullish mi, ikisi de mi
- [ ] Telegram bot token'ı ve chat_id
- [ ] Midas'a webden mi, sadece uygulamadan mı eriştiğin
- [ ] Taramanın bitiş saati (varsayılan 23:59)
