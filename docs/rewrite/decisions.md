# Decyzje do podjęcia przed etapem 2

D1–D6 to decyzje z promptu. D7–D14 wynikły z audytu (`audit.md`) i blokują część punktów
`spec.md` oznaczonych `[? Dx]`. Przy każdej: opcje, koszty i rekomendacja.

## Podsumowanie rekomendacji

| # | decyzja | rekomendacja | kiedy ma znaczenie |
|---|---|---|---|
| D1 | framework Qt | **PySide6** (Essentials, przypięta wersja), przejście w etapie 3 | etap 3–4 |
| D2 | sposób przepisania | **moduł po module** (strangler) z testami charakteryzującymi | od razu |
| D3 | model zadań | **jedna kolejka**: kodowanie szeregowo, obrazy w puli; anulowanie; „ponów nieudane” zamiast wznawiania | etap 2 |
| D4 | konfiguracja | **domyślne w kodzie + opcjonalny `config.toml` użytkownika**; stan UI w QSettings | etap 2 |
| D5 | struktura pakietu | **`src/ffmpeg_convert/`**, entry pointy, `python -m ffmpeg_convert`, dane w katalogu użytkownika | etap 2 (pakiet), etap 4 (instalatory) |
| D6 | funkcje marki w wideo | **tak, etapowo**: podpis LGC + miniatura YT w v2.0, plansza końcowa po dostarczeniu assetów | etap 3 |
| D7 | nadpisywanie | **sufiks `_002`** dla nazw generowanych; błąd dla nazw podanych; `--overwrite` jawnie | etap 2 |
| D8 | polityka koloru | **reguła „dystrybucja vs montaż”** + odczyt przestrzeni z nagłówka EXR | etap 2 |
| D9 | fps NTSC | **mapowanie 23,976 → 24000/1001 itd.**, fps jako ułamek | etap 2 |
| D10 | DNxHD/DNxHR | **DNxHD: tabela bitrate + pasy; DNxHR: HQX 10-bit** | etap 2 |
| D11 | nieparzyste wymiary | **przycięcie 1 px** wszędzie, z wpisem w logu | etap 2 |
| D12 | ścieżki audio | **montażowe: wszystkie ścieżki; MP4: pierwsza** | etap 2 |
| D13 | licencja | **ustalić razem z D1** (PySide6 pozwala na dowolną) | przed release |
| D14 | zgodność CLI | **komendy i flagi bez zmian**; zmiany zachowania w `CHANGELOG.md` | etap 2 |

Najkrótsza odpowiedź, jaka mi wystarczy: „akceptuję wszystkie rekomendacje” albo lista numerów
z innym wyborem.

---

## D1. PyQt5 czy PySide6

**Kontekst.** Aplikacja używa PyQt5 5.15.11 (Qt 5.15). Wolna wersja Qt 5.15 nie dostaje
poprawek od maja 2023. PyQt5 jest na GPLv3 albo licencji komercyjnej, a repo nie ma pliku
licencji (D13). GUI to ok. 1300 linii, rdzeń nie zależy od Qt, więc decyzja dotyczy etapów 3–4.

Sprawdziłem w tym środowisku (Linux, Python 3.12):

| | PyQt5 5.15.11 | PySide6 6.12.0 (Essentials) |
|---|---|---|
| licencja | GPLv3 / komercyjna | LGPLv3 |
| Qt | 5.15 (bez poprawek OSS) | 6.12 (wspierane) |
| rozmiar instalacji (site-packages) | 202 MB | 246 MB |
| QtSvg (logo z mastera SVG) | jest | jest (w Essentials) |
| cyfry tabelaryczne (`tnum`) w Qt | brak API; trzeba „zamrozić” funkcję w pliku fontu (fonttools) | `QFont.setFeature(QFont.Tag("tnum"), 1)` działa (od Qt 6.7) |
| HiDPI 150% na Windows | trzeba włączać ręcznie, skalowanie ułamkowe słabsze | domyślnie, skalowanie ułamkowe |
| Linux: zależności systemowe | brak dodatkowych | **wymaga `libEGL.so.1`** (`libegl1`); w minimalnym kontenerze go brakowało; zwykłe pulpity go mają, w CI trzeba doinstalować |

**Opcje**

- **A. Zostać przy PyQt5.** Zero migracji. Koszt: Qt bez poprawek, `tnum` przez przerobiony
  plik fontu, słabsze 150%, GPL.
- **B. PySide6.** Koszt: migracja GUI (zmiany API: `exec`, `Signal`, `QAction` w `QtGui`, pełne
  nazwy enumów), +44 MB, `libegl1` w CI. Zysk: wspierane Qt, LGPL, `tnum` i HiDPI bez obejść.
  Na etap 3 i tak przepisujemy GUI, więc koszt migracji jest w dużej części już ponoszony.
- **C. PyQt6.** Te same zalety Qt6, ale GPL. Brak przewagi nad B.
- **D. Warstwa zgodności (qtpy).** Dwie ścieżki do testowania. Nie warto dla jednej aplikacji.

**Wpływ na instalatory i Nemo.** Windows: instalator już tworzy venv, więc zmienia się tylko
pakiet (`PySide6-Essentials==6.12.*` zamiast `PyQt5==5.15.11`); aktualizacja tworzy venv od
nowa. Linux: dziś akcje Nemo używają systemowego `python3` i `python3-pyqt5` z apt.
Z PySide6 rekomenduję venv jak na Windows (`~/.local/share/ffmpeg_convert/venv`), a akcje Nemo
wywołują program z venv (D5). `apt` instaluje wtedy tylko `ffmpeg`, `zenity`, `python3-venv`,
`libegl1`.

**Rekomendacja: B**, przejście razem z nowym GUI w etapie 3. Etap 2 (rdzeń) jest niezależny od Qt.

## D2. Big-bang czy moduł po module

- **A. Big-bang:** nowy kod obok, przełączenie naraz. Szybciej się pisze, ale porównanie
  „stara/nowa” jest możliwe dopiero na końcu, a regresje wychodzą hurtem.
- **B. Moduł po module (strangler):** najpierw testy charakteryzujące ze `spec.md` na
  obecnym kodzie (punkty `[Δ]` jako `xfail` z odnośnikiem do audytu), potem nowe moduły w
  `src/ffmpeg_convert/` w kolejności: probe → model zadań i planowanie ścieżek → receptury →
  runner → sekwencje → CLI. Stare `app/presets` przez chwilę delegują do nowego rdzenia, więc
  GUI działa przez cały czas. `app/` znika w etapie 4, gdy jego część `spec.md` przechodzi.
  Koszt: krótkotrwałe adaptery i podwójne importy.

**Rekomendacja: B** (zgodnie z Twoją preferencją). Małe commity per moduł.

**Gałąź.** Prompt mówi `rewrite/v2`, ale ta sesja może pushować tylko do
`claude/new-session-hw35j9`. Pracuję tam; gałąź `rewrite/v2` mogę utworzyć, jeśli wyraźnie
na to pozwolisz.

## D3. Model zadań

| opcja | opis | koszt |
|---|---|---|
| A | jedna kolejka szeregowa (jak dziś) + anulowanie | najprościej; batch obrazów wolny |
| **B** | jedna kolejka; kodowanie wideo szeregowo, lekkie zadania (obrazy, split, probe) w puli `min(4, CPU/2)` | trochę więcej kodu w schedulerze |
| C | pełna równoległość | x264/x265 już używają wszystkich rdzeni, GPU ma limit sesji; zysk niewielki, ryzyko przeciążenia |

- **Anulowanie:** token anulowania w runnerze, `terminate()` procesu, po 2 s `kill()`,
  usunięcie `*.part` (WSP-07, WSP-14).
- **Kolejka w GUI:** można dodać kolejną partię w trakcie pracy; każda partia ma zamrożone
  ustawienia z chwili dodania.
- **Wznawianie:** bez wznawiania w środku pliku (ffmpeg tego nie umożliwia sensownie).
  Zamiast tego „Ponów nieudane” po zakończeniu i brak częściowych plików. Kolejka nie
  przetrwa zamknięcia aplikacji.

**Rekomendacja: B** z powyższymi zasadami.

## D4. Konfiguracja

- **A. Tylko `CONFIG` w kodzie (jak dziś).** Zmiana = edycja kodu, brak presetów użytkownika.
- **B. Domyślne w kodzie + opcjonalny `config.toml`** w katalogu konfiguracji użytkownika
  (`%APPDATA%\FFmpegConvert\config.toml`, `~/.config/ffmpeg_convert/config.toml`), czytany
  przez `tomllib` (stdlib), walidowany schematem dataclass (nieznany klucz → błąd z nazwą
  klucza). Presety użytkownika jako `[[preset]]`, które dziedziczą po wbudowanej recepturze
  i zmieniają tylko wybrane pola (CRF, preset kodera, bitrate audio, sufiks, skala).
- **C. JSON / QSettings dla wszystkiego.** Wygodne dla GUI, nieczytelne do ręcznej edycji.

Stan interfejsu (ostatnie wybory, rozmiar okna) trzymam w QSettings, więc aplikacja nie musi
zapisywać TOML-a i nie potrzebuje dodatkowej biblioteki.

**Otwarte pytanie:** czy preset użytkownika może zawierać surowe argumenty ffmpeg
(`extra_args`)? Elastyczne, ale wyłącza walidację i gwarancje z `spec.md`. Rekomenduję **nie**
w v2.0.

**Rekomendacja: B** bez `extra_args`.

## D5. Struktura pakietu

**Rekomendacja:**

```
src/ffmpeg_convert/
  __main__.py        # python -m ffmpeg_convert  → CLI
  cli.py
  core/              # probe, model Job, planowanie ścieżek, polityki (nadpisywanie, kolizje)
  recipes/           # czyste funkcje: parametry → lista argumentów
  sequences.py
  runner.py
  config.py
  audio/             # separacja (worker + runtime)
  gui/               # etap 3
  data/              # LUT, fonty, logo (importlib.resources)
```

- `pyproject.toml`: `[project.scripts] ffmpeg-convert`, `[project.gui-scripts] ffmpeg-convert-gui`
  (na Windows `.exe` bez konsoli), wersja z jednego miejsca.
- Instalacja przez `pip install .` do venv na obu systemach; w repo `pip install -e .`.
- **Katalogi danych poza kodem:** runtime audio, konfiguracja, logi w katalogach użytkownika.
  Dziś runtime audio leży obok kodu (`.audio-runtime/`), co w `site-packages` nie zadziała.
- **Migracja:** instalator przenosi `%LOCALAPPDATA%\FFmpegConvert\.audio-runtime` (lub
  `<repo>/.audio-runtime` na Linuxie) do nowego katalogu przez `rename` na tym samym dysku,
  bez ponownego pobierania kilku GB. Rejestr i akcje Nemo dostają nowe polecenie
  (`ffmpeg-convert-gui.exe "%1"` / `ffmpeg-convert-gui %F`). Przez jedną wersję zostaje cienki
  `app/cli.py` i `app/gui.py` przekierowujący do nowego pakietu, żeby stare wpisy menu nie padły.

Koszt: uruchomienie z repo wymaga `pip install -e .`; `python app/gui.py` przestaje być
głównym sposobem.

## D6. Funkcje z brand booka w wyjściu wideo

Ograniczenia: brak PDF-a i mastera SVG w repo; ffmpeg z winget (Gyan) nie czyta SVG, a
`drawtext` zależy od buildu. Dlatego rekomenduję renderowanie grafik marki w Qt (QtSvg +
dołączone fonty) do tymczasowego PNG i nakładanie go w ffmpeg (`overlay`). Typografia jest
wtedy identyczna z UI i nie zależy od buildu ffmpeg.

| opcja | zakres | uwagi |
|---|---|---|
| A | nic | narzędzie zostaje czysto techniczne |
| **B** | „LGC podpis” (logo w prawym górnym rogu + opcjonalnie „AI GENERATED” w lewym dolnym, skala i marginesy w % wysokości dla 16:9, 9:16, 4:5, 1:1) + miniatura YouTube 1280×720 z wybranej klatki | potrzebny tylko master SVG |
| C | B + „Plansza końcowa” (logo, hasło, adres www i e-mail, 1,2 s sting, stop-klatka) | potrzebne: plik dźwięku stingu, definicja animacji/układu z PDF-a |

- Presety marki są opcjonalne, w osobnej grupie „Marka LGC”; żaden zwykły preset nie dodaje
  logo.
- Podgląd kadru w GUI zawsze bez filtrów.

**Rekomendacja: B w v2.0, C w v2.1** po dostarczeniu assetów stingu. Wartości skal i marginesów
zaproponuję w skillu `lgc-brand-ui` po otrzymaniu PDF-a.

## D7. Polityka nadpisywania (A02, A03, A09)

- **A.** Błąd, gdy wynik istnieje (dziś tylko sekwencje). Bezpieczne, ale batch staje na
  drugim uruchomieniu.
- **B.** Automatyczny sufiks `_002`, `_003` (dziś separacja audio). Nic nie ginie, ale mogą
  narastać kopie.
- **C.** Pytanie w GUI przy każdym konflikcie. Uciążliwe w batchu.

**Rekomendacja:** B dla nazw generowanych (wideo, obrazy, foldery klatek i proxy), A dla nazw
wpisanych przez użytkownika (nazwa filmu sekwencji, `--output`). Nadpisanie tylko jawnie:
`--overwrite` w CLI, przełącznik w GUI (domyślnie wyłączony). Zmiana zachowania CLI → wpis w
`CHANGELOG.md`.

## D8. Polityka koloru (A14, A15, A30, A36)

| pytanie | opcje | rekomendacja |
|---|---|---|
| a) tag transferu dla źródeł RGB/sRGB → wideo | `iec61966-2-1` (dziś sekwencje) / `bt709` (dziś prores_nuke) | **dystrybucja (MP4) → `iec61966-2-1`** (bez przesunięcia gammy w aplikacjach Apple i przeglądarkach); **montaż (ProRes/DNx/Cineform) → `bt709`** (oczekiwane przez NLE i Nuke) |
| b) sekwencje JPG | bez konwersji, tag 601 (dziś) / jak PNG: macierz 709 | **jak PNG** dla HD i większych |
| c) domyślna przestrzeń EXR | zawsze ACES2065-1 (dziś) / zawsze lin709 / z nagłówka | **odczyt atrybutu `chromaticities` z nagłówka EXR** (AP0 → ACES, Rec.709 → lin709); brak atrybutu → ACES2065-1 jak dziś, z widocznym komunikatem |
| d) EXR → ProRes/DNxHD | surowe wartości liniowe bez tagów (dziś) / transformacja do Rec.709 display jak MP4 | **transformacja jak MP4** + tagi; surowe wartości tylko przez `--no-color` |
| e) PNG z alfą → JPG | kolor spod przezroczystości (dziś) / białe tło / czarne tło | **białe tło**, wpis w logu |
| f) źródła RGB w presetach wideo | jak dziś (601, brak tagów) / konwersja 709 + tagi | **konwersja 709 + tagi** (VID-17) |

Szczegóły trafią do skilla `color-pipeline`.

## D9. fps NTSC (A13)

- **A.** Bez zmian: `23.976` dosłownie (wynik 2997/125).
- **B.** Mapowanie 23,976 / 29,97 / 59,94 / 47,952 / 119,88 na 24000/1001, 30000/1001…;
  fps przechowywany jako ułamek; w GUI lista typowych wartości + pole własne.

**Rekomendacja: B.** Zmienia metadane wyniku (na właściwe); wpis w `CHANGELOG.md`.

## D10. DNxHD i DNxHR (A01, A17)

- **DNxHD 1080p:** (a) jak dziś, skala do 1920×1080 i 120 Mb/s; (b) skala z zachowaniem
  proporcji + pasy, bitrate z tabeli Avid wg fps, nieobsługiwany fps → błąd; (c) usunąć
  DNxHD na rzecz DNxHR. **Rekomendacja: b.**
- **DNxHR:** (a) HQ 8-bit (`dnxhr_hq`, `yuv422p`); (b) HQX 10-bit (`dnxhr_hqx`,
  `yuv422p10le`); (c) oba. Obecna receptura miesza HQ z 10-bitowym pix_fmt, więc intencja była
  raczej 10-bitowa. **Rekomendacja: b** i etykieta „DNxHR HQX (10-bit)”. Id `dnxhr` w CLI
  zostaje.

## D11. Nieparzyste wymiary (A04)

- **A. Przycięcie 1 px** z prawej/dołu (dziś w sekwencjach PNG). Bez resamplingu, strata
  niewidoczna.
- **B. Dopełnienie 1 px** czarnym pasem. Wszystkie piksele zostają, ale dochodzi sztuczna
  krawędź.
- **C. Skalowanie** do najbliższego parzystego. Resampling całego obrazu.

**Rekomendacja: A** dla wszystkich kodeków wymagających parzystych wymiarów, z wpisem w logu.

## D12. Ścieżki audio i strumienie (A19)

- **A.** Jak dziś: jedna ścieżka wybrana przez ffmpeg.
- **B.** Formaty montażowe (ProRes, DNx, Cineform, prores_nuke): wszystkie ścieżki audio;
  MP4: pierwsza ścieżka.
- **C.** Wszystkie ścieżki wszędzie (MP4 z wieloma ścieżkami bywa źle obsługiwane przez
  odtwarzacze i serwisy).

**Rekomendacja: B.** Napisy i strumienie danych pomijane jak dziś.

## D13. Licencja (A23)

Repo nie ma licencji, czyli formalnie „wszystkie prawa zastrzeżone”, a zależy od PyQt5 (GPLv3).
Opcje: GPLv3 (zgodne z PyQt5), licencja własna studia lub MIT (wymaga PySide6, LGPL).
Fonty OFL wymagają dołączenia ich licencji (już w planie: `assets/fonts/LICENSES`).
FFmpeg jest pobierany przez winget/apt, nie dystrybuowany z aplikacją.

**Rekomendacja:** wybrać razem z D1. Przy PySide6 dowolna licencja; to Twoja decyzja biznesowa.

## D14. Zgodność CLI i drobne zmiany zachowania

Rekomendacja: komendy i flagi bez zmian; poniższe zmiany opisane w `CHANGELOG.md`:

1. Brak cichego nadpisywania + nowa flaga `--overwrite` (D7).
2. Kody wyjścia: 0 = OK, 1 = brak zadań, 2 = błąd użycia lub walidacji, **3 = część zadań
   nieudana** (dziś 2 oznacza też to). Skrypty Nemo traktują każdy kod ≠ 0 tak samo.
3. Ostrzeżenie, gdy opcja nie dotyczy wybranego presetu (dziś ciche ignorowanie, np. `--crf`
   przy `h264`).
4. Domyślne CRF sekwencji H.264: zostawić 23 (dziś) czy wyrównać do 18 jak preset wideo
   H.264? **Rekomendacja: zostawić 23** (mniejsze pliki z klatek, zgodnie z obecnym GUI) i
   poprawić etykietę.
5. `--fps 23.976` → 24000/1001 (D9).
6. Nowy entry point `ffmpeg-convert`; `python app/cli.py` działa przez jedną wersję (D5).
