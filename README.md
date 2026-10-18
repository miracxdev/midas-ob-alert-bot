# 📈 Midas PO3 / CISD Alert Bot

**Midas "En Çok Artan" kripto listesini takip eden ve listedeki coinlerde PO3 modeline göre yeni bir +CISD oluştuğu anda telefona ve bilgisayara bildirim gönderen bot.**

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey)
![Telegram](https://img.shields.io/badge/bildirim-Telegram%20%2B%20macOS-26A5E4?logo=telegram&logoColor=white)
![Tests](https://img.shields.io/badge/testler-pytest-0A9EDC?logo=pytest&logoColor=white)

> ⚠️ **Bu bir bildirim aracıdır, yatırım tavsiyesi değildir.** Bot hiçbir borsada emir açmaz, hiçbir hesaba erişmez, sadece herkese açık fiyat verisini okur ve bildirim gönderir.

---

## İçindekiler

- [Ne işe yarar?](#ne-işe-yarar)
- [Özellikler](#özellikler)
- [Nasıl çalışır?](#nasıl-çalışır)
- [Bildirim örnekleri](#bildirim-örnekleri)
- [Kurulum](#kurulum)
- [Çalıştırma ve durdurma](#çalıştırma-ve-durdurma)
- [Telegram komutları](#telegram-komutları)
- [Ayarlar](#ayarlar)
- [PO3 / CISD mantığı](#po3--cisd-mantığı)
- [Proje yapısı](#proje-yapısı)
- [Geliştirme ve test](#geliştirme-ve-test)
- [Sorun giderme](#sorun-giderme)
- [Lisans ve teşekkür](#lisans-ve-teşekkür)

---

## Ne işe yarar?

Gün içinde en çok yükselen coinler genelde güçlü hareketin içindedir. Bu bot:

1. [Midas'ın "En Çok Artan" kripto listesini](https://www.getmidas.com/canli-kripto/en-cok-artan) düzenli olarak alır,
2. her coinin borsadaki **USDT paritesini** bulur,
3. bu coinlerin **5 dakikalık grafiğini** sürekli tarar,
4. TradingView'deki **PO3 Model [CantoLab]** indikatörünün C2 + CISD kurulumuyla **yeni bir +CISD** oluştuğu anda
5. **Telegram** (telefon + masaüstü) ve **macOS** bildirimi gönderir. Bildirimde CISD seviyesi, C2 dibi, fiyat ve tek tıkla açılan **TradingView grafik linki** bulunur.

Böylece 20 coinin grafiğini tek tek izlemek yerine, sadece sinyal geldiğinde grafiğe bakmanız yeterli olur.

## Özellikler

- 🔄 **Canlı liste:** Midas listesi 16:25'te alınır ve tarama boyunca **her saat** yenilenir. Listeye yeni giren coin otomatik olarak taramaya eklenir.
- ⏱️ **Mum kapanışına hizalı tarama:** Her 5 dakikalık mum kapandıktan ~10 saniye sonra tüm coinler taranır.
- 🧠 **PO3 / CISD modeli:** 5 dakikalık grafik 1 saatlik mumlarla eşlenir. C2 mumu önceki saatin dibini süpürüp 5 dakikalıkta CISD seviyesinin üstünde kapanış gelince sinyal verilir. Sadece kapanmış mumlar kullanılır, sinyal sonradan kaybolmaz (repaint yok). İsteğe bağlı olarak LuxAlgo Order Block motoruna da geçilebilir.
- 🏦 **6 borsa desteği:** Binance → OKX → Bybit → Gate → KuCoin → MEXC sırasıyla parite aranır. API anahtarı gerekmez.
- 🔔 **Çoklu bildirim kanalı:** Telegram, macOS ve isteğe bağlı [ntfy](https://ntfy.sh).
- 🚫 **Tekrar yok:** Aynı sinyal asla iki kez gönderilmez (SQLite). Listeye geç giren coinlerin eski sinyalleri bildirilmez.
- 🤖 **Telegram'dan kontrol:** `/durum`, `/bugun`, `/liste`, `/durdur`, `/baslat` gibi komutlar.
- 🛡️ **Dayanıklı:** Borsa hatasında yeniden dener, gönderilemeyen bildirimi kuyruğa alır, art arda hata olursa tek bir uyarı yollar, çökerse kendini yeniden başlatır.
- 💸 **Ücretsiz:** Hiçbir ücretli servis kullanmaz.

## Nasıl çalışır?

```mermaid
flowchart LR
    A[Midas<br/>En Çok Artan<br/>ilk 20 coin] -->|16:25 + her saat| B[Parite eşleme<br/>Binance → OKX → ...]
    B --> C[(SQLite<br/>izleme listesi)]
    C -->|her 5 dk| D[OHLCV çek<br/>ccxt]
    D --> E[PO3: 1h C2 süpürme<br/>+ 5m CISD]
    E -->|yeni +CISD?| F{Daha önce<br/>gönderildi mi?}
    F -->|hayır| G[📱 Telegram<br/>💻 macOS]
```

### Günlük akış (İstanbul saati)

| Saat | Ne olur |
|---|---|
| **16:25** | Midas listesinin ilk 20 coini alınır, borsa paritelerine eşlenir ve tam liste gönderilir. |
| **16:30** | Tarama başlar. Liste alınamadıysa hatırlatma gelir. |
| **Her 5 dakikada** (16:35:10, 16:40:10 …) | Güncel listedeki tüm coinler taranır. Yeni +CISD varsa bildirim gönderilir. |
| **17:25, 18:25 … 23:25** | Liste yeniden alınır. Değiştiyse eklenen/çıkan coinler bildirilir, değişmediyse mesaj gelmez. |
| **23:59** | Tarama durur. Bot açık kalır, ertesi gün 16:25'te yeniden başlar. |

Hafta sonu dahil her gün çalışır. Bot 16:25'ten sonra açılırsa listeyi hemen alır.

## Bildirim örnekleri

**Yeni +CISD sinyali:**
```
🟢 +CISD — XYZ/USDT (5m)
CISD seviyesi: 0.4189
C2 dibi: 0.4123
Fiyat: 0.4231
Mum: 17:45 (İST)
Borsa: Binance
📈 https://www.tradingview.com/chart/?symbol=BINANCE:XYZUSDT&interval=5
```

| Alan | Anlamı |
|---|---|
| CISD seviyesi | Grafikteki mavi +CISD çizgisinin fiyatı |
| C2 dibi | 1 saatlik C2 mumunun önceki saatin dibini süpürdüğü en düşük nokta (grafikteki c2 etiketi) |
| Fiyat | CISD'yi onaylayan 5 dakikalık mumun kapanışı |
| Mum | Onay mumunun kapanış saati |
| 📈 | Grafiği TradingView'de 5 dakikalık olarak açar |

**Saatlik liste değişikliği:**
```
🔄 Midas listesi güncellendi
➕ Eklenen: ABC (BINANCE:ABCUSDT)
➖ Çıkan: DEF
```

## Kurulum

Gereken: **Python 3.11+** ve bir **Telegram** hesabı.

### 1. Projeyi indirin ve kurun

```bash
git clone https://github.com/miracxdev/midas-ob-alert-bot.git ~/development/midas-ob-alert-bot
cd ~/development/midas-ob-alert-bot

RT="$HOME/Library/Application Support/obbot"
python3 -m venv "$RT/venv"
ln -sfn "$RT/venv" .venv
.venv/bin/pip install -e '.[dev]'
cp .env.example .env
```

> 💡 **Proje klasörünü Masaüstü veya Belgeler'e koymayın.** Bu klasörler iCloud ile senkronize olabilir. iCloud dosyaları buluta taşıdığında arka plandaki bot onları okuyamaz ve çöker. Sanal ortam, veritabanı ve loglar bu yüzden `~/Library/Application Support/obbot/` altında tutulur (`OBBOT_HOME` ile değiştirilebilir).

### 2. Telegram botunu bağlayın

1. Telegram'da **@BotFather** → `/newbot` → isim verin → verilen token'ı `.env` dosyasına yazın: `TELEGRAM_BOT_TOKEN=...`
2. Yeni botunuza herhangi bir mesaj atın (ör. `merhaba`).
3. Tarayıcıda `https://api.telegram.org/bot<TOKEN>/getUpdates` adresini açın. `"chat":{"id":123456789` kısmındaki sayıyı `.env` dosyasına yazın: `TELEGRAM_CHAT_ID=123456789`
4. Deneyin: `.venv/bin/python scripts/test_notify.py` telefona ve Mac'e örnek bir bildirim gönderir.

> 🔒 `.env` dosyası `.gitignore` içindedir ve GitHub'a gönderilmez. Token'ınızı asla `.env.example` dosyasına yazmayın. Bot yalnızca `.env`'deki `TELEGRAM_CHAT_ID`'den gelen komutlara cevap verir.

### 3. macOS bildirimleri

Varsayılan olarak `osascript` kullanılır. Bildirim gelmiyorsa: **Sistem Ayarları → Bildirimler → Script Editor** bölümünden bildirimleri açın. Bildirime tıklayınca grafiğin açılmasını isterseniz `brew install terminal-notifier` kurun, bot onu otomatik kullanır.

## Çalıştırma ve durdurma

### Elle çalıştırma

```bash
.venv/bin/python -m obbot.main            # botu başlat (Ctrl+C ile durdur)
.venv/bin/python -m obbot.main --check    # sadece ayarları kontrol et
```

### Arka planda sürekli çalıştırma (önerilen)

Mac açıldığında otomatik başlar, çökerse kendini yeniden başlatır:

```bash
./scripts/install_launchd.sh              # kur ve başlat
./scripts/install_launchd.sh uninstall    # kaldır
```

| İşlem | Komut |
|---|---|
| Taramayı duraklat / devam ettir | Telegram'dan `/durdur` / `/baslat` |
| Botu tamamen kapat | `launchctl bootout gui/$(id -u)/com.obbot.midas` |
| Botu tekrar aç | `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.obbot.midas.plist` |
| Çalışıyor mu? | `launchctl print gui/$(id -u)/com.obbot.midas \| grep "state ="` |

Loglar: `~/Library/Application Support/obbot/logs/`

> 💤 **Mac uyurken tarama yapılmaz.** Tarama saatlerinde Mac'i uyanık tutmak için Sistem Ayarları → Pil → Seçenekler → "Güç adaptörüne bağlıyken otomatik uyumayı engelle" ayarını açın. 7/24 çalıştırmak için küçük bir VPS veya Raspberry Pi kullanabilirsiniz: [deploy/obbot.service](deploy/obbot.service).

## Telegram komutları

| Komut | İşlev |
|---|---|
| `/bugun` | Bugünün izleme listesi ve eşlenen pariteler |
| `/durum` | Son tarama zamanı, hata sayısı, tarama penceresi |
| `/yenile` | Listeyi Midas'tan hemen yeniden çek |
| `/liste XYZ ABC ...` | Bugünün listesini elle ayarla (saatlik yenileme bu listeye dokunmaz) |
| `/test` | Deneme bildirimi |
| `/durdur` / `/baslat` | Taramayı duraklat / devam ettir |

## Ayarlar

Tüm ayarlar [config.yaml](config.yaml) dosyasındadır. Değişiklikten sonra botu yeniden başlatın.

| Ayar | Değer | Açıklama |
|---|---|---|
| `watchlist.refresh_at` | `16:25` | Listenin ilk alındığı saat |
| `watchlist.top_n` | `20` | Listenin ilk kaç coini izlenir |
| `watchlist.hourly_refresh` | `true` | Tarama boyunca listeyi her saat yenile |
| `watchlist.max_change_pct` | `null` | Ör. `500` → %500'den fazla artan (hatalı veri olabilecek) coinleri atla |
| `scan_window` | `16:30–23:59` | Tarama penceresi. Gece yarısını aşabilir: `{start: "16:30", end: "04:00"}` |
| `days` | her gün | Ör. `[mon, tue, wed, thu, fri]` |
| `timeframes` | `["5m"]` | Ör. `["5m", "15m"]`; her biri ayrı sinyal üretir |
| `max_signal_age_bars` | `3` | Bundan eski mumlarda oluşan sinyaller bildirilmez |
| `ob.engine` | `po3` | `po3` = PO3 C2 + CISD, `custom` = LuxAlgo Order Block, `default` = basit swing/BOS OB |
| `ob.direction` | `bullish` | `bullish` (+CISD), `bearish` (-CISD) veya `both` |
| `ob.events` | `[cisd]` | PO3 için `cisd`. OB motorları için `ob_formed`, `ob_retest` |
| `ob.params.htf` | `1h` | PO3 üst zaman dilimi (indikatördeki Alignment: Auto → 5m ↔ 1h) |
| `ob.params.swing_len` | `10` | OB motorları: LuxAlgo'daki **Swing Lookback** |
| `ob.params.use_body` | `true` | OB motorları: LuxAlgo'daki **Use Candle Body** |
| `notifiers` | `[telegram, macos]` | `ntfy` de eklenebilir (`.env` → `NTFY_TOPIC`) |

Midas'taki bir sembol borsada farklı adla geçiyorsa [data/symbol_aliases.yaml](data/symbol_aliases.yaml) dosyasına ekleyin (ör. `"1000PEPE": "PEPE"`).

## PO3 / CISD mantığı

Bot, TradingView'deki **PO3 Model [CantoLab]** indikatörünün C2 + CISD kurulumunu yeniden üretir ([src/obbot/ob/po3.py](src/obbot/ob/po3.py)). İndikatör kapalı kaynaklı olduğu için kod, yazarın açıklaması ve gerçek grafiklerle karşılaştırılarak yazıldı. İndikatör ayarları: **Bias: Bullish, Alignment: Auto** (5m grafik ↔ 1h üst zaman dilimi).

1. **C1 ve C2:** Her 1 saatlik mum, bir öncekiyle (C1) karşılaştırılır. C2 mumu C1'in **dibinin altına inerse** manipülasyon (süpürme) oluşmuş demektir. Bu nokta grafikte **c2** etiketiyle gösterilir.
2. **CISD seviyesi:** C2'deki en düşük 5 dakikalık mumdan geriye doğru, dibe giden **ardışık düşüş mumlarının ilkinin açılışı**. Dip mumu yeşilse ondan önceki düşüş dizisi alınır.
3. **+CISD:** C2 sürerken bir 5 dakikalık mum bu seviyenin **üstünde kapanırsa** teslimat yönü değişmiş (Change in State of Delivery) sayılır ve **bildirim gönderilir**.
4. **Geçersizlik:** C2 içinde daha düşük bir dip oluşursa önceki kurulum geçersiz olur (grafikte xc2 / xCISD) ve seviye yeniden hesaplanır. Her kurulum en fazla bir kez sinyal verir.

-CISD (bearish) bunun simetriğidir; `ob.direction: both` ile açılabilir.

**Doğrulama:** Gerçek grafiklerden alınan iki örnek testlerde birebir tutuyor:

| Örnek | TradingView | Bot |
|---|---|---|
| BINANCE:BTCUSDT 5m, 17.10 | c2: 20:00, +CISD çizgisi ≈ 81,258 | c2: 20:00, seviye 81,258.80, sinyal 20:10 |
| BINANCE:QUSDT.P 5m, 18.10 | xc2: 10:20, xCISD çizgisi ≈ 0.1287 | c2: 10:20, seviye 0.128737, sinyal 10:30 |

> 📌 Kapalı kaynaklı bir indikatörün yeniden yapımı olduğu için bazı köşe durumlarda TradingView'den farklı sonuç verebilir. Fark görürseniz coin, saat ve ekran görüntüsüyle bildirin.

### LuxAlgo Order Block motoru (alternatif)

`ob.engine: custom` yapılırsa bot, **LuxAlgo ICT Concepts** indikatörünün Order Block mantığıyla çalışır ([indicator/ob.pine](indicator/ob.pine) → [src/obbot/ob/custom.py](src/obbot/ob/custom.py)). Kapanış son swing high'ın üstüne çıktığında, swing ile kırılım arasındaki en düşük gövdeli mum OB olur. Bu durumda `ob.events: [ob_formed]` kullanın.

### TradingView ile karşılaştırma

```bash
.venv/bin/python scripts/backtest_ob.py BINANCE:BTCUSDT 5m           # son 300 mumdaki sinyaller
.venv/bin/python scripts/run_once.py --midas --hours 6               # Midas listesiyle tek tarama
```

Çıktıdaki c2 saatlerini ve CISD seviyelerini TradingView'de aynı zaman diliminde, indikatörün **History** ayarını artırarak karşılaştırın.

## Proje yapısı

```
midas-ob-alert-bot/
├── config.yaml              # tüm ayarlar
├── .env.example             # Telegram token / chat id şablonu
├── indicator/ob.pine        # LuxAlgo ICT Concepts (Pine Script kaynağı)
├── data/symbol_aliases.yaml # Midas sembolü → borsa sembolü eşlemeleri
├── deploy/                  # macOS launchd ve Linux systemd dosyaları
├── scripts/                 # kurulum, test ve hata ayıklama scriptleri
├── src/obbot/
│   ├── main.py              # giriş noktası: zamanlayıcı + Telegram komutları
│   ├── scheduler.py         # 16:25 liste, saatlik yenileme, 5 dk tarama
│   ├── scanner.py           # tarama, eski sinyal filtresi, tekrar kontrolü
│   ├── watchlist.py         # liste alma, değişiklik tespiti
│   ├── sources/             # Midas web kaynağı, dosya kaynağı
│   ├── markets/             # parite eşleme (resolver) ve OHLCV (ccxt)
│   ├── ob/                  # po3.py (PO3 / CISD), custom.py (LuxAlgo OB), default.py
│   ├── notify/              # Telegram, macOS, ntfy
│   ├── bot/commands.py      # /durum, /bugun, /liste ...
│   └── db.py                # SQLite: liste, gönderilen sinyaller, tarama kayıtları
└── tests/                   # pytest testleri
```

## Geliştirme ve test

```bash
.venv/bin/pytest            # tüm testler
.venv/bin/ruff check src    # lint
.venv/bin/python scripts/test_notify.py   # örnek bildirim gönder
```

Testler sinyal algoritmalarını gerçek grafik verisi ve elle kurulmuş mum senaryolarıyla, zamanlayıcıyı ise saati taklit eden (`freezegun`) entegrasyon testleriyle doğrular.

## Sorun giderme

| Sorun | Çözüm |
|---|---|
| Hiç bildirim gelmiyor | `/durum` ile botun çalıştığını kontrol edin. Sinyal ancak yeni +CISD oluştuğunda gelir; bazı saatlerde hiç çıkmayabilir. |
| Telegram cevap vermiyor | `.env` içinde `TELEGRAM_CHAT_ID` dolu mu? Botu yeniden başlatın. |
| Mac bildirimi gelmiyor | Sistem Ayarları → Bildirimler → Script Editor açık mı? Odak modu kapalı mı? |
| Liste gelmedi | Midas sayfasının yapısı değişmiş olabilir. Loglara bakın; geçici çözüm `/liste XYZ ABC`. |
| "parite bulunamadı" | Coin 6 borsanın hiçbirinde USDT/USD paritesine sahip değil ya da adı farklı → `symbol_aliases.yaml`. |
| Bot sürekli çöküyor | Proje iCloud ile senkronize bir klasörde olabilir. `~/development/` gibi bir yere taşıyıp `install_launchd.sh`'ı yeniden çalıştırın. |
| Art arda hata uyarısı | Genelde internet ya da borsa kaynaklıdır, kendiliğinden düzelir. |

## Lisans ve teşekkür

- **PO3 / CISD modeli:** *PO3 Model [CantoLab]* indikatöründen esinlenen bağımsız bir yeniden yapımdır; CantoLab'ın kodu kullanılmamıştır (indikatör kapalı kaynaklıdır). Kavramlar ICT ve MXMM'nin Power of Three anlatımına dayanır.
- **Order Block algoritması:** [indicator/ob.pine](indicator/ob.pine) dosyası ve onun Python portu [src/obbot/ob/custom.py](src/obbot/ob/custom.py), **© LuxAlgo** tarafından [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) lisansıyla yayımlanan *ICT Concepts [LuxAlgo]* indikatörüne dayanır. Bu dosyalar aynı lisansla, **ticari olmayan** kullanım için paylaşılmıştır.
- **Liste kaynağı:** Midas'ın herkese açık [En Çok Artan](https://www.getmidas.com/canli-kripto/en-cok-artan) sayfası. Bu proje Midas ile bağlantılı değildir.
- **Fiyat verisi:** [ccxt](https://github.com/ccxt/ccxt) üzerinden borsaların herkese açık API'leri.

> Bu yazılım yalnızca bilgilendirme amaçlıdır. Kripto para yatırımları yüksek risk içerir; verilen sinyaller alım-satım tavsiyesi değildir.
