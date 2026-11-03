---
name: lgc-brand-ui
description: Identyfikacja wizualna Let's Go Cuts przełożona na Qt — tokeny kolorów, QSS generowany z tokenów, kontrast, fonty (Oswald, Lato, Barlow Condensed, cyfry tabelaryczne), logo z mastera SVG, motyw cięcia, ruch i ograniczanie ruchu, ikona aplikacji oraz presety marki w wideo (podpis LGC, miniatura YT). Użyj przy każdej zmianie wyglądu GUI albo presetów marki.
---

# Marka LGC w Qt

Źródło: `docs/brand/the_cut_v2.pdf` („THE CUT – Strategia wizualna V2”).
**Stan: w repo brak PDF-a i mastera logo.** Wartości poniżej pochodzą z briefu; przed etapem 3
potwierdź je z PDF-em. Bez mastera SVG nie rysuj logo, tylko poproś o plik.

Zasada nadrzędna: to narzędzie robocze, marka ma podpisywać, nie przeszkadzać.

## Tokeny (jedno źródło: `app/ui/theme.py`, etap 3)

| token | hex | użycie |
|---|---|---|
| `frame_black` | `#0C0C0D` | tło okna |
| `paper_white` | `#F3F0E8` | tekst główny, jasne powierzchnie |
| `cut_red` | `#C70006` | **tylko akcent**: główny przycisk, pasek postępu, aktywna zakładka; nigdy tło sekcji |
| `cut_red_light` | `#EC4A4E` | mały czerwony tekst na ciemnym, obrys focusu na panelach |
| `text_muted` | `#B2AFA7` | tekst pomocniczy na ciemnym |
| `line` | `#777773` | linie, obrysy, duże formy (nie mały tekst) |
| `ink_secondary` | `#62615C` | mały tekst na jasnym tle |
| `surface_panel` | `#1A1A1A` | panele i grupy (jak karty w PDF) — propozycja |
| `surface_raised` | `#242425` | pola edycji, hover listy — propozycja |
| `border_subtle` | `#2C2C2D` | obrys paneli (panel vs tło okna to tylko 1,12:1) — propozycja |
| `text_disabled` | `#6E6D68` | nieaktywne — propozycja |
| `cut_red_hover` / `cut_red_pressed` | `#D6141A` / `#A80005` | stany głównego przycisku — propozycja |

QSS powstaje z tokenów w `theme.py`; nigdzie indziej nie ma literałów hex (sprawdzenie:
`grep -rn "#[0-9A-Fa-f]\{6\}" app --include=*.py` poza `theme.py` ma być puste).
QSS nie obsługuje `letter-spacing` ani funkcji OpenType: rozstrzał i cyfry tabelaryczne ustawiaj
w `QFont` w kodzie.

## Kontrast (WCAG 2.x, policzone)

| para | kontrast | wniosek |
|---|---|---|
| paper_white na frame_black | 17,17:1 | tekst główny OK |
| paper_white na surface_panel | 15,28:1 | OK |
| text_muted na frame_black / panel / raised | 8,92 / 7,94 / 7,08 | tekst pomocniczy OK |
| line na frame_black / panel | 4,35 / 3,87 | obrysy OK (≥ 3:1), mały tekst nie |
| **cut_red na frame_black** | **3,19:1** | tylko duże elementy i grafika, nie mały tekst |
| **cut_red na surface_panel** | **2,84:1** | **za mało** dla elementu interfejsu (< 3:1) |
| cut_red_light na frame_black / panel / raised | 5,27 / 4,69 / 4,18 | mały czerwony tekst OK na czerni i panelu, nie na raised |
| paper_white na cut_red (tekst przycisku) | 5,37:1 | OK |
| paper_white na cut_red_hover / pressed | 4,64 / 6,91 | OK |
| ink_secondary na paper_white | 5,45:1 | OK |
| text_disabled na panel | 3,36:1 | czytelne, wyraźnie nieaktywne |

Reguły wynikające z tabeli:
- elementy w `cut_red` (główny przycisk, pasek postępu, znacznik aktywnej zakładki) stoją na
  `frame_black`, nie na panelu;
- **focus**: obrys 2 px `cut_red_light` (na panelu 4,69:1); na `frame_black` może być `cut_red`;
- pasek postępu: obrys 1 px `line`, wypełnienie `cut_red`, obok procent cyframi tabelarycznymi
  (informacja nie tylko kolorem);
- mały tekst nigdy w `cut_red` ani `line`.

## Typografia

Pliki TTF/OTF w `assets/fonts/`, licencje OFL w `assets/fonts/LICENSES/` (Qt nie ładuje WOFF2).
Ładowanie: `QFontDatabase.addApplicationFont(path)`; gdy się nie uda: systemowy sans, wpis w logu.

| krój | gdzie | ustawienia |
|---|---|---|
| Oswald | tytuł okna i sekcji, wersaliki, oszczędnie | 18–22 px |
| Lato Regular / Bold | treść, opisy, log | 13 px |
| Barlow Condensed 500 | etykiety w wersalikach; timecode, FPS, liczba klatek, rozmiary | 11–12 px, `setLetterSpacing(QFont.AbsoluteSpacing, 1.6–2.5)`, `setFeature(QFont.Tag("tnum"), 1)` |

`QFont.setFeature` istnieje od Qt 6.7 (PySide6, D1). W PyQt5 cyfr tabelarycznych nie da się
włączyć z kodu.

## Logo i motyw cięcia

- **Wyłącznie master SVG** (proponowana ścieżka `assets/brand/lgc_logo.svg`), render przez
  `QSvgRenderer` / `QSvgWidget`. Nie przerysowuj liter ani cięcia, nie zmieniaj kolorów.
- W nagłówku albo w „O programie”: wysokość ≥ 64 px, pole ochronne = 1/6 wysokości znaku z
  każdej strony, tylko na ciemnym tle, bez dodatkowych ukośnych cięć obok.
- Ukośne cięcie jako motyw: najwyżej jeden subtelny element (separator albo stan aktywny).
- Podgląd miniatur i kadrów bez żadnych filtrów, nakładek i tintów: kolor filmu pozostaje
  własnością filmu.
- Ikona aplikacji z mastera: Windows `.ico` (16, 24, 32, 48, 64, 128, 256), Linux `.png` 256 i `.svg`.

## Ruch

- Animacje 160–240 ms, ease-out; bez migania, glitchu i pulsowania.
- Ograniczanie ruchu: Windows `SystemParametersInfoW(SPI_GETCLIENTAREAANIMATION)`;
  GNOME/Cinnamon `gsettings get org.gnome.desktop.interface enable-animations`; ustawienie w
  aplikacji i zmienna `FFCONVERT_REDUCE_MOTION=1`. Gdy ruch ograniczony: czas animacji 0.

## Presety marki w wideo (D6: v2.0 podpis i miniatura, v2.1 plansza)

Grafikę renderuj w Qt (QtSvg + fonty marki) do tymczasowego PNG, nakładaj w ffmpeg
(`overlay`); nie zależy to od `librsvg` ani `drawtext` w buildzie ffmpeg. Presety są opcjonalne,
w grupie „Marka LGC”.

**LGC podpis: propozycja do potwierdzenia z PDF** (H = wysokość kadru):

| proporcje | wysokość logo | margines od góry i prawej | „AI GENERATED” (lewy dół) |
|---|---|---|---|
| 16:9 | 6% H | 5% H | Barlow Condensed 500, 2,2% H, margines 5% H |
| 9:16 | 3,5% H | 6% H (nad interfejsem platform) | 1,6% H, od dołu 14% H |
| 4:5 | 5% H | 4,5% H | 2% H, margines 4,5% H |
| 1:1 | 6% H | 5% H | 2,2% H, margines 5% H |

Tekst „AI GENERATED” w `paper_white`, wersaliki, rozstrzał 0,15 em. Wszystko w safe area,
skala stała dla danych proporcji, niezależna od rozdzielczości.

**Miniatura YouTube**: 1280×720 JPG z wybranej klatki, bez filtrów; logo tylko wg reguł podpisu.

**Plansza końcowa (v2.1)**: logo, „Od niemożliwej wizji do gotowego filmu.”, letsgocuts.com,
hello@letsgocuts.com, sting 1,2 s i stop-klatka. Wymaga pliku dźwięku stingu i układu z PDF-a.

## Weryfikacja

Zrzuty stanów okna (skill `gui-change`) obejrzane przed opisem; kontrast nowych par policz przed
dodaniem tokenu; test offscreen ładuje fonty i sprawdza, czy rodzina się zarejestrowała.
