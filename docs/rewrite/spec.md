# Specyfikacja zachowania (kontrakt v2)

Opis zachowania ffmpeg_convert v0.7.0 jako kontrakt dla v2. W etapie 2 każdy punkt dostaje
test o tej samej nazwie (np. `test_VID_01`). Zachowanie, które w audycie okazało się błędem,
jest opisane tak, jak ma działać po naprawie, a obecny stan podaje linia „Obecnie”.

**Oznaczenia**

- `[=]` obecne zachowanie jest kontraktem, przenosimy 1:1;
- `[Δ Axx]` kontrakt zmienia obecne zachowanie, naprawa błędu z `audit.md`;
- `[? Dx]` kontrakt zależy od decyzji z `decisions.md`; wpisany jest wariant rekomendowany.

**Słownik:** *stem*: nazwa pliku bez rozszerzenia; *batch*: więcej niż jeden plik wejściowy;
*rdzeń*: presety + planowanie + runner, wspólne dla GUI i CLI.

Spis: [1. Wspólne](#1-wspólne-zasady-wsp) · [2. Wideo](#2-presety-wideo-vid) ·
[3. Obrazy](#3-obrazy-img) · [4. Split i flipbook](#4-split-spl-i-flipbook-flp) ·
[5. Sekwencje](#5-sekwencje-seq) · [6. Runner](#6-runner-run) · [7. CLI](#7-cli-cli) ·
[8. GUI](#8-gui-gui) · [9. Menu kontekstowe i instalatory](#9-menu-kontekstowe-i-instalatory-ctx) ·
[10. Separacja audio](#10-separacja-audio-aud) · [11. Logi i aktualizacje](#11-logi-log-i-aktualizacje-upd)

---

## 1. Wspólne zasady (WSP)

**WSP-01 [=] Rozpoznanie typu pliku**
- Given plik z rozszerzeniem (wielkość liter bez znaczenia)
- When rdzeń klasyfikuje wejście
- Then `.png .jpg .jpeg .exr .tif .tiff .webp` → obraz; `.mp4 .mov .mkv .avi .webm .m4v` →
  wideo; inne → pomijane (GUI i CLI logują pominięcie).

**WSP-02 [=] Wynik nigdy nie jest wejściem**
- Given ścieżka wyniku równa ścieżce dowolnego wejścia (klatki, audio, obrazu)
- When budowane są zadania
- Then dla obrazów zadanie jest pomijane; dla sekwencji i audio zgłaszany jest błąd przed startem.

**WSP-03 [Δ A02] [? D7] Brak cichego nadpisywania**
- Given plik lub folder wynikowy już istnieje
- When uruchamiam dowolny preset
- Then istniejący plik pozostaje nietknięty, a wynik dostaje pierwszą wolną nazwę z sufiksem
  `_002`, `_003`…; log podaje faktyczną nazwę. Nadpisanie tylko po jawnym `--overwrite` (CLI)
  albo potwierdzeniu w GUI.
- Obecnie: tylko MP4 sekwencji jest chroniony (błąd „już istnieje”), pozostałe presety używają `-y`.

**WSP-04 [=] Miejsce zapisu wideo**
- Given jeden plik wideo / kilka plików
- When preset wideo z sufiksem (np. `H264`)
- Then jeden plik: wynik obok źródła; batch: wynik w podfolderze `<folder źródła>/<sufiks>/`.
  Wyjątki: `last_frame` zawsze obok źródła, `frames` zawsze w `<stem>_FRAMES/`,
  `audio_separate` zawsze w `<stem>_AUDIO/`.

**WSP-05 [Δ A03] Kolizje nazw w batchu**
- Given batch, w którym dwa wejścia dają tę samą ścieżkę wyniku (`clip.mov` i `clip.mp4`,
  `a.png` i `a.jpg`)
- When planuję zadania
- Then żadne zadanie nie nadpisuje wyniku innego (sufiks wg WSP-03), a pliki pośrednie
  (np. logi 2-pass) są unikalne dla zadania.
- Obecnie: drugi wynik nadpisuje pierwszy, wspólny `passlog`.

**WSP-06 [=] Błąd jednego zadania nie przerywa batcha**
- Given batch z jednym wadliwym plikiem
- When uruchamiam
- Then pozostałe zadania się wykonują, log ma `OK:` / `BŁĄD:` dla każdego, wynik końcowy to
  `poprawne/wszystkie`.

**WSP-07 [Δ A07] Brak częściowych wyników**
- Given zadanie kończy się błędem albo zostaje anulowane
- When runner kończy zadanie
- Then w miejscu wyniku nie ma pliku częściowego ani pustego; foldery utworzone przez to zadanie
  i puste po błędzie są usuwane; ponowienie działa bez ręcznego sprzątania.
- Obecnie: zostaje plik częściowy lub 0 B; sekwencja przy ponowieniu zgłasza „już istnieje”.

**WSP-08 [Δ A18] Zasoby tymczasowe**
- Given zadanie potrzebuje plików tymczasowych (linki klatek, lista concat, logi 2-pass)
- When zadanie zostało zbudowane, ale nie uruchomione / zakończyło się / padło / zostało anulowane
- Then budowanie niczego nie tworzy na dysku; runner tworzy zasoby i usuwa wyłącznie te, które
  sam utworzył dla tego zadania, zawsze.
- Obecnie: sprzątanie po uruchomieniu działa, ale katalog `ffseq_*`, lista `ffflip_*` i folder
  proxy powstają już przy budowaniu.

**WSP-09 [=] Bez shella**
- Given dowolna komenda zewnętrzna
- When jest uruchamiana
- Then przekazywana jest lista argumentów bez shella; na Windows bez migania okna konsoli.

**WSP-10 [Δ A12] Znaki specjalne w nazwach**
- Given nazwy zawierające spację, `'`, `\`, `%`, `&`, polskie znaki
- When dowolny preset
- Then wynik ma oczekiwaną nazwę i powstaje poprawnie; nazwa z newline jest odrzucana z
  komunikatem przed startem (lista concat i GUI).
- Obecnie: `%` psuje eksport klatek i zmienia nazwy obrazów (`logo 100%d.png` → `logo 1001.jpg`).

**WSP-11 [Δ A04] [? D11] Wymiary niezgodne z subsamplingiem**
- Given źródło o nieparzystej szerokości lub wysokości (np. 1281×721)
- When kodek wymaga parzystych wymiarów (H.264/H.265 4:2:0, Cineform, DNxHR, 4:2:2)
- Then obraz jest przycinany o 1 px z prawej i/lub z dołu, a log o tym informuje; kodeki, które
  akceptują nieparzyste wymiary (ProRes), dostają wymiar oryginalny.
- Obecnie: działa tylko dla sekwencji PNG/TIFF/EXR z konwersją koloru; wideo i sekwencje JPG
  kończą się błędem.

**WSP-12 [=] Zachowana liczba klatek i fps**
- Given wideo o N klatkach i fps F (w tym 24000/1001)
- When preset wideo→wideo
- Then wynik ma N klatek i `r_frame_rate` = F; długość ścieżki wideo jest równa źródłowej.

**WSP-13 [Δ A05] Postęp w trakcie zadania**
- Given zadanie o znanej długości (wideo, sekwencja)
- When koduje
- Then postęp rośnie w trakcie zadania (wiele wartości pośrednich, monotonicznie), 2-pass liczy
  oba przebiegi; zadania bez długości zgłaszają postęp po każdej komendzie.
- Obecnie: tylko 1.0 po zakończeniu komendy.

**WSP-14 [Δ A06] [? D3] Anulowanie**
- Given trwa zadanie lub kolejka
- When użytkownik przerywa (GUI „Przerwij”, CLI Ctrl+C)
- Then bieżący proces ffmpeg kończy się w ciągu ~2 s, częściowy wynik jest usuwany (WSP-07),
  kolejne zadania nie startują, log podaje, co zostało ukończone.
- Obecnie: brak anulowania.

---

## 2. Presety wideo (VID)

Wspólne Given dla VID-01…VID-12: jeden plik `X.mov` z obrazem 1920×1080 i dźwiękiem, enkoder CPU.

**VID-01 [=] MP4 H.264 (CRF 18)**, id `h264`
- When preset `h264`
- Then `X_H264.mp4`; `libx264 -crf 18 -preset slow -pix_fmt yuv420p`; AAC 192 kb/s.

**VID-02 [=] MP4 H.264, kontrola rozmiaru, tryb CRF**, id `h264size`, `size_mode=crf`
- When CRF = c (zakres 18–32, domyślnie 23)
- Then `X_H264.mp4`; `libx264 -crf c` (lub odpowiednik GPU wg VID-14); AAC 192 kb/s; etykieta
  zawiera `CRF c`.

**VID-03 [Δ A16] MP4 H.264, kontrola rozmiaru, docelowy MB**, `size_mode=size`
- When cel = T MB (1 MB = 10^6 B, zakres 1–100000)
- Then CPU libx264 w 2 przebiegach (enkoder GPU ignorowany); bitrate wideo = (T × 8000 kb ×
  (1 − narzut)) / długość − bitrate audio (128 kb/s, gdy jest audio; 0, gdy brak); pass 2 bez
  audio, gdy źródło go nie ma; logi 2-pass usunięte. Wynik nie przekracza T dla klipów ≥ 3 s
  na typowym materiale; gdy cel jest nieosiągalny albo obcięty przez limit bitrate, log to mówi;
  po kodowaniu log podaje rzeczywisty rozmiar.
- Brak długości źródła → jeden przebieg CRF (domyślne CRF z konfiguracji) z powodem w etykiecie.
- Obecnie: mnożnik 8192, cel przekraczany na krótkich klipach, limit 25 Mb/s nadpisuje cel po cichu.

**VID-04 [=] MP4 H.264 20 Mb/s (limit, 2 przebiegi)**, id `h264_20m`
- When preset `h264_20m`
- Then `X_H264_20M.mp4`; CPU 2-pass, `-b:v = -maxrate = 20000 − 4000 − audio` kb/s,
  `-bufsize 4000k`, audio AAC 128 kb/s albo `-an`; każde przesuwne okno 1 s ≤ 20 Mb/s.
  Limit pochodzi z konfiguracji.

**VID-05 [=] MP4 H.265 / HEVC (CRF 23)**, id `h265`
- Then `X_HEVC.mp4`; `libx265 -crf 23 -preset medium -pix_fmt yuv420p`; AAC 192 kb/s.

**VID-06 [Δ A17] [? D10] DNxHD 1080p**, id `dnxhd`
- Then `X_DNxHD.mov`; DNxHD 1920×1080 `yuv422p`, bitrate z tabeli Avid dla fps źródła
  (115 Mb/s przy 23,976/24, 120 przy 25, 145 przy 29,97…), skalowanie z zachowaniem proporcji
  i czarnymi pasami; fps spoza tabeli → błąd przed startem z listą obsługiwanych; PCM s16le.
- Obecnie: zawsze `scale=1920:1080` (rozciąga pion i 4:3) i 120 Mb/s.

**VID-07 [Δ A01] [? D10] DNxHR HQ**, id `dnxhr`
- Then `X_DNxHR.mov`; DNxHR HQ 8-bit `yuv422p` w rozdzielczości źródła (wariant rekomendowany);
  PCM s16le; plik powstaje dla źródeł 8- i 10-bitowych.
- Obecnie: zawsze błąd (`dnxhr_hq` + `yuv422p10le`).

**VID-08 [=] ProRes 422 HQ**, id `prores`
- Then `X_PR.mov`; `prores_ks -profile:v 3 -pix_fmt yuv422p10le`; PCM s16le.

**VID-09 [Δ A14] ProRes HQ → Nuke**, id `prores_nuke`
- Then `X_NUKE.mov`; jak VID-08 + tagi `bt709/bt709/bt709`, PCM s24le 48 kHz. Tagi zgadzają
  się z faktyczną macierzą: źródło RGB lub otagowane inaczej jest konwertowane do 709 przed
  zapisem.
- Obecnie: tagi bez konwersji; źródło RGB ma w środku macierz 601.

**VID-10 [=] Cineform Q4 (10-bit)**, id `cineform`
- Then `X_CF.mov`; `cfhd -quality 4 -pix_fmt yuv422p10le`; PCM s16le.

**VID-11 [=] Ostatnia klatka PNG**, id `last_frame`
- Then `X_last.png` obok źródła (także w batchu); ostatnia klatka z ostatniej sekundy
  (`-sseof -1 -update 1`); nieotagowane wideo YUV o wysokości ≥ 720 dekodowane macierzą 709.

**VID-12 [Δ A08 A09 A12] Eksport klatek (+ WAV)**, id `frames`
- When format `png|jpg|exr`, WAV włączony (domyślnie)
- Then folder `X_FRAMES/` z klatkami `X_0001.<fmt>`… w liczbie równej liczbie klatek źródła
  (`-fps_mode passthrough`); WAV `X.wav` (PCM s24le) tylko, gdy źródło ma audio, inaczej log
  „brak audio, pomijam WAV” i zadanie OK; istniejący folder → nowy folder z sufiksem
  (`X_FRAMES_002`), nigdy mieszanie klatek; nieotagowane HD dekodowane macierzą 709.
- Obecnie: brak audio = błąd zadania; istniejący folder dostaje nowe klatki obok starych; `%` w
  nazwie psuje wzorzec.

**VID-13 [=] Separacja audio**, id `audio_separate`: patrz sekcja 10.

**VID-14 [=] Enkodery GPU**
- Given enkoder `nvenc|qsv|amf`
- When preset `h264`, `h265` albo `h264size` w trybie CRF
- Then NVENC: `h264_nvenc/hevc_nvenc -preset p4 -tune hq -rc vbr -cq <q> -b:v 0 -pix_fmt yuv420p`;
  QSV: `h264_qsv/hevc_qsv -preset veryslow -look_ahead 0 -global_quality <q>`; AMF:
  `h264_amf/hevc_amf -quality quality -rc cqp -qp_i <q> -qp_p <q> -b:v 0 -pix_fmt yuv420p`;
  `<q>` to CRF presetu; etykieta zawiera `[NVENC]` itp. ProRes/DNx/Cineform/`h264_20m`/tryb MB
  ignorują enkoder.

**VID-15 [Δ A20] Lista dostępnych enkoderów**
- Given ffmpeg i karta graficzna
- When GUI lub CLI pokazuje enkodery
- Then CPU jest zawsze; GPU tylko, gdy ffmpeg ma enkoder **i** próbne kodowanie 1 klatki się
  udaje; wynik jest liczony raz na sesję, w tle.
- Obecnie: tylko sprawdzenie kompilacji, 8 wywołań przy starcie.

**VID-16 [? D12] Strumienie**
- Given źródło z kilkoma ścieżkami audio
- When preset montażowy (ProRes, DNx, Cineform, prores_nuke)
- Then zachowane są wszystkie ścieżki audio; MP4 (H.264/H.265) dostają pierwszą ścieżkę.
- Obecnie: zawsze jedna ścieżka (wybór domyślny ffmpeg).

**VID-17 [Δ A14] Kolor wideo → wideo**
- Given źródło YUV z tagami / bez tagów / źródło RGB
- When dowolny preset wideo
- Then otagowane: tagi przeniesione bez zmian i zgodne z danymi; nieotagowane YUV HD+:
  traktowane jak 709; RGB: konwersja do YUV macierzą 709 i tagi 709. Kolor wzorcowy po
  zdekodowaniu zgodnie z tagami różni się o ≤ 3 na kanał.

**VID-18 [=] Nieznany preset**
- When id spoza listy
- Then `ValueError` (rdzeń) albo błąd argparse (CLI).

---

## 3. Obrazy (IMG)

**IMG-01 [=] Kompresja domyślna**
- Given obraz `a.png`
- When kompresja z domyślnymi ustawieniami
- Then `compressed/a.jpg`; `-q:v 2 -vf format=yuvj420p`.

**IMG-02 [=] Jakość**
- When jakość Q2 / Q5 / Q10 / „bez kompresji”
- Then `-q:v` = 2 / 5 / 10 / 1.

**IMG-03 [=] Zachowaj oryginał**
- When tryb „zachowaj oryginał” (`keep`)
- Then kopia bajt w bajt z oryginalnym rozszerzeniem, w podfolderze lub z nową nazwą;
  skalowanie i konwersja koloru nieaktywne.

**IMG-04 [=] Zmiana nazwy**
- Given 3 obrazy w podanej kolejności, nazwa bazowa `render`
- Then `render_001.jpg`, `render_002.jpg`, `render_003.jpg` (numerowane tylko obrazy, w
  kolejności podania); puste pole = oryginalne nazwy.

**IMG-05 [=] Miejsce zapisu**
- When „obok oryginału”
- Then wynik w folderze źródła; gdy wynik == źródło (keep, ta sama nazwa i folder), zadanie
  jest pomijane.

**IMG-06 [=] Skalowanie**
- When skala p% (1–800, domyślnie 50; suwak przyciąga do 10/25/50/75/90/100)
- Then `scale=trunc(iw*p/100/2)*2:trunc(ih*p/100/2)*2` przed konwersją; 100% = bez skalowania.

**IMG-07 [=] EXR → JPG**
- Given obraz EXR
- When konwersja koloru włączona (domyślnie)
- Then ACES2065-1: LUT 3D AP0→sRGB (wbudowany lub własny), `format=rgb24`, tagi
  709/sRGB/pc; lin709: zscale linear→sRGB; brak zscale lub LUT → bez konwersji + ostrzeżenie w
  logu pliku; skala przed konwersją koloru. `--no-color` → bez konwersji.
  (Domyślna przestrzeń: decyzja D8.)

**IMG-08 [=] Dowolny obraz rastrowy**
- Given PNG / TIFF / WebP / JPG / EXR
- Then każdy jest przekodowywany do JPG (JPG też, z nową jakością).

**IMG-09 [=] Pliki nie-obrazy**: pomijane bez błędu.

**IMG-10 [Δ A03]**: kolizje nazw wg WSP-05 (`a.png` + `a.jpg` → `a.jpg`, `a_002.jpg`).

**IMG-11 [? D8] Przezroczystość**
- Given PNG z kanałem alfa
- Then przezroczystość jest spłaszczana na biało (rekomendacja) i log o tym informuje.
- Obecnie: zostaje kolor spod przezroczystości.

**IMG-12 [Δ A12]**: nazwy z `%` wg WSP-10.

---

## 4. Split (SPL) i flipbook (FLP)

**SPL-01 [=] Podział na siatkę**
- Given obraz W×H, siatka X×Y
- Then X·Y plików PNG `<stem>_<y>_<x>.png`; kafel `W//X × H//Y`, ostatnia kolumna/wiersz
  dostaje resztę pikseli.

**SPL-02 [=] Folder**
- Given CLI z jednym plikiem / z wieloma
- Then jeden plik: obok oryginału; wiele: podfolder `SplitGrid/`; `--beside` wymusza „obok”.

**SPL-03 [=] Walidacja**: X lub Y < 1 → błąd; pliki nie-obrazy pomijane; obraz bez
odczytanych wymiarów pomijany.

**SPL-04 [Δ A36]**: EXR jest konwertowany do sRGB tak jak w IMG-07.

**FLP-01 [=] Spritesheet**
- Given klatki (dowolna kolejność podania), siatka C×R
- Then sortowanie naturalne; `<stem sekwencji>_flipbook_<C>x<R>.png` obok pierwszej klatki;
  concat + `tile`; mniej klatek niż pól → puste pola.

**FLP-02 [=] Kafelek**: `--tile WxH` skaluje kafel, gdy różni się od wymiaru pierwszej klatki;
niepoprawny format `--tile` → komunikat i kod 1.

**FLP-03 [=] Nazwy**: `'` i `\` w ścieżkach działają; newline → błąd „nowej linii”.

**FLP-04 [Δ A27]**: więcej klatek niż C×R → ostrzeżenie z liczbą pominiętych klatek.

**FLP-05 [=]**: C lub R < 1 → błąd; pusta lista → błąd.

---

## 5. Sekwencje (SEQ)

### 5.1 Wykrywanie

**SEQ-D01 [=] Klatka numerowana**
- Given obraz, którego stem kończy się cyframi (`shot.1001.exr`, `render_0001.png`, `0001.png`)
- Then tożsamość = (prefiks, rozszerzenie bez wielkości liter, padding, numer).

**SEQ-D02 [=] Jedna klatka → cała sekwencja**
- Given wskazana jedna klatka ze środka sekwencji
- When CLI `seq` z jednym plikiem albo GUI z jedną klatką
- Then wykrywane są tylko klatki z tym samym prefiksem i rozszerzeniem, w tym samym
  (bezpośrednim) folderze; inne prefiksy, obrazy bez numeru i podfoldery o nazwach klatek są
  ignorowane.

**SEQ-D03 [=] Padding**: wskazanie z paddingiem dopasowuje tylko tę samą liczbę cyfr; przejście
`0999 → 1000` wykrywane z obu końców.

**SEQ-D04 [=]**: mniej niż 2 pasujące klatki → to nie jest sekwencja (zwykła konwersja obrazu).

**SEQ-D05 [=]**: powtórzony numer (np. `.png` i `.PNG`) → błąd „Powtarzające się numery klatek”.

**SEQ-D06 [=] Dziury**
- Given brak klatek 5 oraz 10–12
- Then komunikat „Brak klatek: 5, 10–12…” (do 8 pozycji), wideo zablokowane; GUI pokazuje
  powód i wyłącza przycisk; CLI kończy z kodem 2; brak alokacji całego zakresu przy ogromnym
  numerze (np. 999999999999).

**SEQ-D07 [=] Nazwa sekwencji**: prefiks bez końcowych `._- `; pusty prefiks → nazwa folderu.

**SEQ-D08 [=] GUI: najpierw podgląd, potem przełączenie**
- Given w GUI dodana jedna klatka sekwencji
- Then panel obrazów zostaje aktywny; widoczny komunikat „Wykryto sekwencję: <nazwa>, N klatek
  (first–last)” i przycisk „Utwórz wideo z całej sekwencji”; po kliknięciu panel sekwencji, po
  ponownym kliknięciu powrót do obrazów bez ponownego dodawania plików.

**SEQ-D09 [=]**: sekwencja zmieniona na dysku między wykryciem a startem → błąd „Sekwencja
zmieniła się na dysku. Dodaj klatkę ponownie.”

**SEQ-D10 [=]**: CLI `--selected-only` → tylko wskazane pliki, bez wykrywania.

**SEQ-D11 [=] Jawna lista klatek**: sortowanie naturalne; jeden folder, jedno rozszerzenie,
wszystkie istnieją i są obrazami, bez duplikatów; inaczej błąd przed startem.

**SEQ-D12 [Δ A10] Tryb folderów**
- Given folder(y) przekazane jako wejście
- Then jedno zadanie na folder; folder bez obrazów lub nieistniejący pomijany; kilka sekwencji →
  błąd „Kilka sekwencji w <folder>. Wybierz jedną klatkę zamiast folderu.”; dziura → błąd;
  sekwencja + luźne obrazy bez numeru → wideo tylko z sekwencji, luźne obrazy wymienione w logu;
  jedna numerowana klatka + luźne obrazy → błąd z prośbą o wybór plików.
- Obecnie: w ostatnim przypadku wszystkie obrazy folderu trafiają do wideo.

**SEQ-D13 [=]**: folder wyłącznie z obrazami bez numeracji → wideo ze wszystkich, sortowanie
naturalne.

### 5.2 Audio

**SEQ-A01 [=] Dopasowanie automatyczne**
- Given w folderze sekwencji `shot.####.png` są `shot.wav`, `muzyka.wav`
- When tryb audio „dopasuj”
- Then użyty `shot.wav`. Kandydaci: stem = nazwa sekwencji, potem stem = nazwa folderu;
  rozszerzenia `.wav .flac .mp3 .m4a .aac .ogg .aif .aiff` oraz `.mp4 .mov .mkv .webm`
  z dźwiękiem; plik musi mieć strumień audio (ffprobe); niepowiązane nazwy nigdy nie są używane.

**SEQ-A02 [=] Niejednoznaczność**: więcej niż jeden kandydat → błąd z listą nazw i prośbą o
wybór pliku albo wyłączenie audio.

**SEQ-A03 [=]**: plik wynikowy nigdy nie jest kandydatem audio.

**SEQ-A04 [=]**: plik o pasującej nazwie bez audio (uszkodzony, „not audio”) jest pomijany w
trybie auto; jawnie wskazany → błąd „nie zawiera dostępnego audio”.

**SEQ-A05 [=] Jawny plik**
- Given wskazany plik audio albo film z dźwiękiem
- Then użyta pierwsza ścieżka audio; obraz wyniku pochodzi wyłącznie z sekwencji (wymiar
  sekwencji, nie filmu).

**SEQ-A06 [=]**: tryb „bez dźwięku” → wynik bez ścieżki audio.

**SEQ-A07 [=] Długość**
- Given N klatek przy F fps i audio krótsze / dłuższe
- Then audio dopełnione ciszą / przycięte do N/F s; liczba klatek = N; długość wyniku ≈ N/F
  (±0,05 s).

**SEQ-A08 [=]**: audio == plik wynikowy → błąd.

**SEQ-A09 [=] Kodek audio**: MP4 → AAC 192 kb/s (tryb MB: 128 kb/s); MOV → PCM s16le.

**SEQ-A10 [=] GUI**: tryb auto pokazuje „Znaleziono: …” albo „Brak dopasowanego audio. Wskaż
plik lub utwórz film bez dźwięku.”; tryb „Wybierz plik…” bez pliku → błąd „Wskaż plik audio
lub wybierz tryb bez dźwięku.”

### 5.3 Wynik

**SEQ-O01 [=] Nazwa i miejsce**
- Jawna lista klatek → `<folder>/<nazwa folderu>.<ext>`.
- CLI, jedna klatka → `<folder>/<nazwa sekwencji>.<ext>`; `--mp4-in-parent` → folder nadrzędny;
  `--output` → podana ścieżka.
- GUI, jedna klatka → pole „Nazwa filmu” (domyślnie nazwa sekwencji), zapis w folderze
  sekwencji albo nadrzędnym.
- Tryb folderów → `<folder>/<nazwa folderu>.<ext>` albo `<nadrzędny>/<nazwa folderu>.<ext>`.

**SEQ-O02 [=]**: istniejący plik wynikowy → błąd przed startem, plik nietknięty
(sekwencja zostaje przy błędzie, a nie sufiksie, bo nazwę wybiera użytkownik).

**SEQ-O03 [=]**: wynik nie może być żadną z klatek.

**SEQ-O04 [=] GUI, walidacja nazwy**: pusta, `.`, `..`, zawierająca `/`, `\`, newline → błąd
„Podaj samą nazwę filmu, bez ścieżki.”

**SEQ-O05 [=] Miniatura**
- When miniatura włączona, szerokość W (64–1920, domyślnie 320)
- Then `<nadrzędny>/<nazwa>_thumb.jpg` z połowy nowego filmu (długość = N/F), szerokość W,
  wysokość parzysta; wymaga filmu (CLI `--thumb` przy `--no-mp4` → ostrzeżenie i pominięcie).
  W CLI `--thumb` działa w trybie folderów; w GUI w obu trybach. Istniejąca miniatura: WSP-03.

**SEQ-O06 [Δ A09 A28] Proxy**
- When warianty `jpg` (q2, 100%), `png16` (16-bit, 100%), `half` (q5, 50%), start S
  (domyślnie 1001, 0–100000)
- Then `<folder sekwencji>/<podfolder wariantu>/<nazwa sekwencji>.<SSSS>.<ext>`, numeracja od S,
  padding 4, liczba = N; EXR z konwersją koloru jak IMG-07; istniejący podfolder z klatkami →
  nowy podfolder z sufiksem.
- Obecnie: nazwa od folderu, nie od sekwencji; `-y` dopisuje nowe klatki do starych.

**SEQ-O07 [=]**: brak filmu i brak proxy → błąd „Wybierz utworzenie wideo lub przynajmniej
jeden wariant proxy.”; tylko proxy → bez filmu i bez miniatury.

### 5.4 Format, fps, rozmiar

**SEQ-F01 [=] H.264**: `libx264 -crf c -preset slow -pix_fmt yuv420p`, c domyślnie 23 (18–32)
[? D14]; enkoder GPU wg VID-14.

**SEQ-F02 [=] H.265**: `libx265 -crf 23 -preset medium -pix_fmt yuv420p`; GPU z CRF 23.

**SEQ-F03 [=] ProRes 422 HQ**: jak VID-08, enkoder ignorowany.

**SEQ-F04 [Δ A17]**: DNxHD jak VID-06, skala i konwersja koloru w jednym `-vf`.

**SEQ-F05 [Δ A16] Docelowy MB** (tylko H.264): CPU 2-pass, długość = N/F, zasady VID-03;
wybór enkodera nieaktywny.

**SEQ-F06 [Δ A13] [? D9] fps**
- Given fps 23,976 / 29,97 / 59,94 / 47,952 / 119,88
- Then wynik ma `r_frame_rate` 24000/1001 / 30000/1001 / 60000/1001 / 48000/1001 / 120000/1001;
  inne wartości dokładnie jak podane; fps ≤ 0, NaN, ∞ → błąd przed utworzeniem czegokolwiek.
- Obecnie: 23,976 → 2997/125.

**SEQ-F07 [=] Liczba klatek**: wynik ma dokładnie N klatek (demuxer image2 przez ponumerowane
linki; na Windows bez uprawnień do linków → kopie).

### 5.5 Kolor sekwencji

**SEQ-C01 [=] [? D8] PNG/TIFF → wideo**: RGB → YUV macierzą 709, zakres TV, tagi 709;
transfer w tagu wg D8 (obecnie `iec61966-2-1`). Kolor wzorcowy po dekodowaniu 709 ±3.

**SEQ-C02 [Δ A04]**: nieparzyste wymiary wg WSP-11 dla każdego formatu klatek.

**SEQ-C03 [? D8] JPG → wideo**: obecnie bez konwersji macierzy, wynik otagowany 601.
Rekomendacja: jak SEQ-C01 (709 dla HD+).

**SEQ-C04 [=] EXR → H.264/H.265**: ACES2065-1 (LUT AP0→sRGB, bez RRT, clip) albo lin709
(zscale); własny LUT; tagi 709/sRGB; brak zscale lub LUT → bez konwersji + ostrzeżenie.

**SEQ-C05 [? D8] EXR → ProRes/DNxHD**: obecnie surowe wartości liniowe bez tagów.

**SEQ-C06 [=]**: `--no-color` → bez konwersji EXR.

---

## 6. Runner (RUN)

**RUN-01 [=]**: komendy zadania wykonywane po kolei; pierwsza błędna przerywa zadanie.

**RUN-02 [=]**: komenda kopiowania kopiuje plik z metadanymi; z WSP-03 nie nadpisuje.

**RUN-03 [=]**: folder wynikowy tworzony przed startem (rekurencyjnie).

**RUN-04 [=]**: zasoby tymczasowe zadania usuwane zawsze, także po błędzie (pliki i katalogi).

**RUN-05 [=] Komunikat błędu**: nazwa narzędzia, kod wyjścia i istotne linie stderr
[Δ A39: przyczyna, nie tylko ostatnie 5 linii]; log UI `BŁĄD: <etykieta>` + powód;
`OK:  <etykieta>`; wpis w pliku logu.

**RUN-06 [=]**: zwraca liczbę poprawnych zadań; zdarzenie „zadanie i z n ukończone” po każdym;
postęp łączny 0–1 przez wszystkie zadania.

**RUN-07 [=]**: linie `progress_fraction=<0..1>` z workerów (separacja audio) są postępem.

**RUN-08 [=]**: niepoprawne bajty w stderr nie przerywają konwersji (zamiana znaków).

**RUN-09 [Δ A05]**: WSP-13. **RUN-10 [Δ A06]**: WSP-14. **RUN-11 [Δ A07]**: WSP-07.

---

## 7. CLI (CLI)

Wywołanie: `python app/cli.py …` (v2: `ffmpeg-convert …` oraz `python -m ffmpeg_convert …`, D5).
Każda komenda konfiguruje dzienny plik logu.

**CLI-00 [=] [? D14] Kody wyjścia i wyjście**
- Wszystkie zadania OK → 0; brak zadań → 1 („Brak zadań do wykonania…”); część zadań nieudana,
  błąd walidacji (`ValueError`/`OSError` → `Błąd: …` na stderr) albo błąd argumentów → 2.
- Brakujący plik wejściowy → `Pomijam (nie istnieje): <ścieżka>` na stderr, reszta działa.
- Na stdout: `OK:  …` / `BŁĄD: …`, `[i/n]`, na końcu `=== Gotowe: ok/n ===`.
- Rekomendacja D14: rozdzielić kody (2 = błąd użycia, 3 = część zadań nieudana).

**CLI-01 [=] `video`**
```
video --preset {h264,h264size,h264_20m,h265,dnxhd,dnxhr,prores,prores_nuke,cineform,
                last_frame,frames,audio_separate}
      [--crf N] [--target-mb MB] [--frames-format {png,jpg,exr}] [--no-wav]
      [--encoder {cpu,nvenc,qsv,amf}] FILE...
```
- `--crf` (domyślnie 23) dotyczy tylko `h264size`; `--target-mb` włącza tryb MB dla `h264size`;
  `--no-wav` dotyczy `frames`; `--encoder` dotyczy `h264`, `h265`, `h264size` w trybie CRF.
- [Δ] opcja podana do presetu, który jej nie używa → ostrzeżenie na stderr (obecnie ciche ignorowanie).

**CLI-02 [=] `image`**
```
image [--quality {1,2,5,10,keep}] [--name NAZWA] [--beside] [--scale PCT] [--no-color]
      [--exr-colorspace {aces2065,lin709}] [--aces-lut PLIK] FILE...
```
- Domyślnie `--quality 2`, podfolder `compressed`; zachowanie wg sekcji 3.

**CLI-03 [=] `seq`**
```
seq [--fps F] [--audio PLIK | --no-audio] [--selected-only] [--output PLIK]
    [--format {h264,h265,prores,dnxhd}] [--encoder {cpu,nvenc,qsv,amf}]
    [--target-mb MB] [--crf N] [--no-color] [--mp4-in-parent] [--thumb W] [--no-mp4]
    [--proxy {jpg,png16,half}]... [--proxy-start N]
    [--exr-colorspace {aces2065,lin709}] [--aces-lut PLIK] PATH...
```
- Domyślnie: fps 24, format h264, CRF 23, audio auto, proxy brak, start 1001, miniatura wyłączona.
- PATH to klatki **albo** foldery; mieszanie → błąd „Wybierz foldery albo pliki klatek…”;
  foldery + `--output` → błąd; brakująca ścieżka → błąd „Brakuje wybranych klatek lub folderów.”
- Jedna klatka bez `--selected-only` → wykrycie sekwencji, wypisanie
  `Wykryto N klatek: first–last`, dziura → błąd (SEQ-D06).
- `--thumb` z `--no-mp4` → ostrzeżenie i pominięcie miniatury.

**CLI-04 [=] `split`**: `split --cols X --rows Y [--beside] FILE...` (sekcja 4).

**CLI-05 [=] `flipbook`**: `flipbook --cols C --rows R [--tile WxH] FILE...` (sekcja 4).

**CLI-06 [=] `gui`**: `gui [FILE...]` otwiera GUI z wczytanymi plikami.

**CLI-07 [=] `audio-setup`**: instaluje runtime separacji audio; 0 = gotowe, 1 = błąd z komunikatem.

**CLI-08 [=] `update`**: wypisuje wynik sprawdzenia wersji; zawsze kod 0; nic nie pobiera.

---

## 8. GUI (GUI)

**GUI-01 [=] Start**
- Given aplikacja uruchomiona bez plików
- Then okno „FFmpeg Convert” mieści się na ekranie; pusta lista z podpowiedzią „Przeciągnij i
  upuść pliki tutaj (obrazy, wideo lub foldery sekwencji)”; „Konwertuj” nieaktywny.

**GUI-02 [=] Dodawanie**: przeciągnij i upuść, „Dodaj pliki…”, „Dodaj foldery…” (wybór wielu
folderów), argumenty z CLI/menu kontekstowego.

**GUI-03 [=] Jeden typ na listę**
- Given lista zawiera obrazy
- When dodaję wideo / plik nieobsługiwany / nieistniejący / duplikat
- Then wideo pominięte z logiem „inny typ niż reszta listy — wyczyść listę, by zmienić tryb”;
  nieobsługiwany i niedostępny pominięte z logiem; duplikat ignorowany. Folder = tryb sekwencji
  (foldery tylko z folderami).

**GUI-04 [=] Panel obrazów**: jakość (Q2 domyślnie, Q5, Q10, bez kompresji, zachowaj oryginał),
nazwa bazowa z podglądem na żywo (≤ 4 pozycje albo 3 pierwsze + „… (jeszcze N plików) …” +
ostatnia), miejsce zapisu (podfolder `compressed` domyślnie / obok), skalowanie (wyłączone przy
„zachowaj oryginał”), przestrzeń EXR.

**GUI-05 [=] Wykryta sekwencja**: SEQ-D08, SEQ-D06.

**GUI-06 [=] Panel wideo**: presety w kolejności `h264, h264size, h264_20m, h265, dnxhd, dnxhr,
prores, prores_nuke, cineform, last_frame, frames, audio_separate`, pierwszy zaznaczony;
opcje widoczne tylko dla swojego presetu (klatki: format + WAV; `h264size`: CRF / MB; enkoder:
`h264`, `h265`, `h264size`, nieaktywny w trybie MB; opis separacji audio).

**GUI-07 [=] Panel sekwencji**: fps (0,001–240, 3 miejsca), kodek, podsumowanie
„N klatek · s · pierwsza … ostatnia” (tryb jednej sekwencji), nazwa filmu, audio
(dopasuj / bez / plik + Przeglądaj… + podpowiedź), enkoder, kontrola rozmiaru (tylko H.264),
„Utwórz film z klatek” + miejsce (folder sekwencji / nadrzędny), miniatura (domyślnie włączona,
320 px), proxy (domyślnie wyłączone) + klatka startowa, przestrzeń EXR, LUT ACES.
[Δ, etap 3] Liczba klatek, długość, audio i przycisk akcji widoczne razem, bez przewijania.

**GUI-08 [=] Konwersja**: pliki usunięte z dysku są pomijane z logiem i znikają z listy; błąd
budowania → „Błąd przygotowania zadań: …”; brak zadań → komunikat; w trakcie panele i przyciski
nieaktywne, pasek 0–100; na końcu „=== Ukończono poprawnie: ok/n ===” i odblokowanie.
[Δ A11] Planowanie i probe w tle, okno reaguje. [Δ A32] Log nie kasuje komunikatów sprzed startu.

**GUI-09 [Δ A06] W trakcie pracy**: dodawanie i czyszczenie zablokowane z komunikatem;
„Przerwij” zatrzymuje pracę (WSP-14); zamknięcie okna pyta, czy przerwać.
Obecnie: zamknięcie jest blokowane, nie ma przerwania.

**GUI-10 [=] Aktualizacje**: Pomoc → „Sprawdź aktualizacje…” w tle, wynik w oknie dialogowym,
bez pobierania.

**GUI-11 [Δ A21] Okno i klawiatura**: zmiana rozmiaru, minimalizacja i Snap działają; każdy
element osiągalny klawiaturą (Tab, skróty), widoczny focus, etykiety powiązane z polami.

**GUI-12 [=]**: „Wyczyść listę” zeruje listę, tryb, log, przycisk sekwencji i panel.

**GUI-13 [=]**: nazwy plików wyświetlane jako zwykły tekst (bez interpretacji HTML).

**GUI-14 [Δ A26]**: po konwersji przycisk sekwencji z dziurami pozostaje nieaktywny.

---

## 9. Menu kontekstowe i instalatory (CTX)

### 9.1 Linux (Nemo)

**CTX-L01 [=] Instalacja `linux/install.sh`**: sprawdza `ffmpeg`, `zenity`, PyQt5 i instaluje
brakujące przez `apt`; linkuje skrypty `*.sh` do `~/.local/bin`; kopiuje akcje do
`~/.local/share/nemo/actions` z podstawieniem ścieżek; tworzy wpis menu „FFmpeg Convert”;
restartuje Nemo. [? D1/D5: środowisko i polecenia zmienią się wraz z pakietem.]

**CTX-L02 [=] „Konwertuj wideo (FFmpeg)”**: rozszerzenia wideo (obie wielkości liter) → GUI z
zaznaczonymi plikami.

**CTX-L03 [=] „Kompresuj / zmień nazwę obrazów”**: png, jpg, jpeg, exr, tif, tiff, webp → GUI.

**CTX-L04 [=] „Konwertuj wideo z klatek (FFmpeg GUI)”**: png, jpg, jpeg, tif, tiff, exr → GUI;
jedna klatka uruchamia wykrywanie sekwencji (SEQ-D08).

**CTX-L05 [=] „Split Image (Grid)”**: png, jpg, jpeg, webp, tif, tiff → terminal → Zenity
(X, Y liczby ≥ 1, inaczej komunikat błędu) → CLI `split` → „Split zakończony!”.

**CTX-L06 [=] „Make Flipbook (Spritesheet)”**: png, jpg, jpeg, tif, tiff, exr → terminal →
Zenity z podpowiedzią: liczba klatek, wymiar pierwszej klatki, auto-siatka (kolumny z 8/16/32/64
z najmniejszą liczbą pustych pól) → CLI `flipbook` → „Flipbook gotowy!”; puste pola = wartości auto.

**CTX-L07 [=]**: wpis menu aplikacji uruchamia GUI z plikami (`%F`).

**CTX-L08 [Δ A24]**: ścieżka instalacji ze spacją lub znakami `&`/`|` działa; akcja dla folderów
sekwencji (jak w Windows); jest deinstalacja.

### 9.2 Windows

**CTX-W01 [=] Start instalatora**: `setup.vbs` uruchamia `setup.ps1` bez konsoli; `setup.bat`
uruchamia `setup.vbs`; `setup.ps1` działa bezpośrednio, gdy Windows Script Host jest zablokowany;
polityka wykonywania tylko dla procesu.

**CTX-W02 [=] Zainstaluj / aktualizuj**: Python 3.12 x64 (`py -3.12`, `%LOCALAPPDATA%\Programs\
Python\Python312`, `python`; filtr aliasu Sklepu), brak → `winget Python.Python.3.12 --scope user`;
`ffmpeg`/`ffprobe` z PATH odświeżonego z rejestru i `WinGet\Links`, brak → `winget Gyan.FFmpeg
--scope user`; venv `%LOCALAPPDATA%\FFmpegConvert\.venv` z PyQt5; aplikacja kopiowana przez staging
(kompilacja plików), stara wersja przywracana przy błędzie; `windows-tools.json` z pełnymi
ścieżkami narzędzi; menu kontekstowe; skrót w menu Start.

**CTX-W03 [=] Menu kontekstowe**: „FFmpeg Convert...” w `HKCU\Software\Classes\
SystemFileAssociations\.<ext>\shell\FFmpegConvert` dla mp4, mov, mkv, avi, webm, m4v, png, jpg,
jpeg, exr, tif, tiff, webp oraz `Directory\shell\FFmpegConvert`; `MultiSelectModel=Single`;
polecenie `"<venv>\pythonw.exe" "<app>\launch.py" "%1"` (oba w cudzysłowach).

**CTX-W04 [=]**: stare wpisy `KonwertujWideo`/`KonwertujObraz` wskazujące `scripts\app\gui.py`
są usuwane; stary folder `%USERPROFILE%\scripts\app` zostaje.

**CTX-W05 [=] Pozostałe akcje**: „Uruchom aplikację”; „Zainstaluj separację audio” (CLI
`audio-setup`); „Usuń menu kontekstowe” (tylko klucze, aplikacja i model zostają);
„Sprawdź instalację” (interpreter, narzędzia, PyQt5); każda wymaga instalacji, inaczej
„Najpierw kliknij Zainstaluj / aktualizuj.”

**CTX-W06 [=]**: błąd startu GUI z menu → okno komunikatu ze ścieżką logu.

**CTX-W07 [=]**: aktualizacja zachowuje lokalny model audio. [? D5: migracja lokalizacji.]

**CTX-W08 [=] Okno instalatora**: przyciski nieaktywne w trakcie, wskaźnik pracy, szczegóły
(ostatnie 100 000 znaków), „Kopiuj szczegóły”, zamknięcie zablokowane w trakcie, komunikat
końcowy sukces/błąd.

**CTX-W09 [=]**: `setup.py` poza Windows / nie 3.12 / nie 64-bit → komunikat i kod 1.

---

## 10. Separacja audio (AUD)

**AUD-01 [=]**: preset `audio_separate` (GUI i CLI `video`) uruchamia ten sam worker konsolowym
Pythonem, bez importu bibliotek ML w GUI/CLI.

**AUD-02 [=] Sprawdzenie wejścia przed instalacją**: brak pliku albo brak ścieżki audio → błąd,
nic nie jest instalowane ani tworzone.

**AUD-03 [=] Runtime**: venv z torch 2.6.0 CPU, torchaudio 2.6.0, eluate 0.0.3; model z Zenodo;
SHA-256 sprawdzane przed wczytaniem; marker wersji; równoległa instalacja → błąd z informacją o
locku; nieudane pobranie nie publikuje modelu; `--checkpoint` = lokalna kopia modelu.
[? D5: lokalizacja runtime; Δ A22: hashe pakietów, wykrywanie martwego locka.]

**AUD-04 [=] Wynik**: `<stem>_AUDIO/` (kolejne `_002`, `_003`, bez nadpisywania) z
`speech.wav`, `music.wav`, `sfx.wav`, `background_no_dialogue.wav` (48 kHz / 24 bit, stereo),
`video_without_dialogue.mkv` (obraz kopiowany, tylko gdy źródło ma obraz), `report.json`
(model, czas, 0 kredytów).

**AUD-05 [=]**: przetwarzana jest pierwsza ścieżka audio.

**AUD-06 [=]**: błąd → usuwany tylko własny folder wyniku; wcześniejsze wyniki nietknięte.

**AUD-07 [=]**: postęp przez `progress_fraction` (RUN-07).

**AUD-08 [=]**: media nie opuszczają komputera; po instalacji działa offline.

---

## 11. Logi (LOG) i aktualizacje (UPD)

**LOG-01 [=]**: dzienny plik `YYYY-MM-DD.log` w `ffmpeg_convert/logs` pod `XDG_CACHE_HOME`
(Linux), `~/Library/Caches` (macOS), `%LOCALAPPDATA%` (Windows); ponowna konfiguracja nie
dubluje wpisów; bez konfiguracji biblioteka nic nie zapisuje.

**UPD-01 [=]**: sprawdzenie `releases/latest` w GitHub; porównanie wersji numerycznie
(`v1.2.3` → 1.2.3); komunikaty: nowa wersja / aktualna / „Nie udało się sprawdzić aktualizacji
(brak sieci, rate-limit GitHub lub brak opublikowanego release'u).”; bez automatycznego pobierania.
