<#
 .SYNOPSIS
   Konwersja wideo do różnych formatów na Windows
   - Jeśli -Preset nie podano ⇒ otwiera GUI (Out-GridView) z wyborem.
   - Obsługuje wiele plików; 1 plik → wynik obok źródła, >1 plik → podfolder.
   - Parametr -Debug włącza pełny log (convert_debug.log).
#>

param(
  [string]$Preset,
  [switch]$Debug,
  [string[]]$Files
)

Add-Type -AssemblyName System.Windows.Forms

if (-not $Files) { $Files = $args }
if (-not $Files) {
  [System.Windows.Forms.MessageBox]::Show("Nie podano plików.","Convert") ; exit
}

# ---------- wybór GUI ----------
if (-not $Preset) {
  $options = @(
    'MP4 H.264 (CRF 18, AAC)'
    'MP4 H.265 / HEVC (CRF 23, AAC)'
    'DNxHD 1080p (120 Mb/s)'
    'DNxHR HQ 4K (185 Mb/s)'
    'ProRes 422 HQ'
    'Cineform Q4 (10-bit)'
    'Klatki PNG (lossless)'
    'Klatki JPEG (Q2/90%)'
    'Klatki EXR (16-bit half)'
    'Ostatnia klatka PNG'
    'Eksport klatek + WAV'
    'Anuluj'
  )
  $choice = $options | Out-GridView -Title "Wybierz kodek" -OutputMode Single
  if ($choice -eq 'Anuluj' -or -not $choice) { exit }
  switch -Wildcard ($choice) {
    'MP4 H.264*'       { $Preset = 'h264'        }
    'MP4 H.265*'       { $Preset = 'h265'        }
    'DNxHD*'           { $Preset = 'dnxhd'       }
    'DNxHR*'           { $Preset = 'dnxhr'       }
    'ProRes*'          { $Preset = 'prores'      }
    'Cineform*'        { $Preset = 'cineform'    }
    'Klatki PNG*'      { $Preset = 'frames_png'  }
    'Klatki JPEG*'     { $Preset = 'frames_jpg'  }
    'Klatki EXR*'      { $Preset = 'frames_exr'  }
    'Ostatnia klatka*' { $Preset = 'last_frame'  }
    'Eksport klatek*'  { $Preset = 'frames_wav'  }
  }
}

# ---------- dla frames_wav: wybór formatu klatek ----------
$FramesWavFormat = 'png'
if ($Preset -eq 'frames_wav') {
  $fmtOptions = @('PNG','JPG','EXR')
  $fmtChoice = $fmtOptions | Out-GridView -Title "Format klatek" -OutputMode Single
  if (-not $fmtChoice) { exit }
  $FramesWavFormat = $fmtChoice.ToLower()
}

Write-Host "Preset: $Preset" -ForegroundColor Cyan
if ($Debug) { $VerbosePreference = 'Continue' }

# ---------- funkcje enkodowania ----------
function Encode-H264 { param($In,$Out)
  ffmpeg -hide_banner -y -i "$In" `
    -c:v libx264 -crf 18 -preset slow `
    -pix_fmt yuv420p `
    -c:a aac -b:a 192k "$Out"
}
function Encode-H265 { param($In,$Out)
  ffmpeg -hide_banner -y -i "$In" `
    -c:v libx265 -crf 23 -preset medium `
    -pix_fmt yuv420p `
    -c:a aac -b:a 192k "$Out"
}
function Encode-DNxHD { param($In,$Out)
  ffmpeg -hide_banner -y -i "$In" `
    -vf scale=1920:1080 `
    -c:v dnxhd -b:v 120M -pix_fmt yuv422p `
    -c:a pcm_s16le "$Out"
}
function Encode-DNxHR { param($In,$Out)
  ffmpeg -hide_banner -y -i "$In" `
    -c:v dnxhd -profile:v dnxhr_hq -pix_fmt yuv422p10le `
    -c:a pcm_s16le "$Out"
}
function Encode-ProRes { param($In,$Out)
  ffmpeg -hide_banner -y -i "$In" `
    -c:v prores_ks -profile:v 3 -pix_fmt yuv422p10le `
    -c:a pcm_s16le "$Out"
}
function Encode-Cine { param($In,$Out)
  ffmpeg -hide_banner -y -i "$In" `
    -c:v cfhd -quality 4 -pix_fmt yuv422p10le `
    -c:a pcm_s16le "$Out"
}
function Encode-FramesPNG { param($In,$OutDir,$Base)
  New-Item "$OutDir" -ItemType Directory -EA 0 | Out-Null
  ffmpeg -hide_banner -y -i "$In" `
    -fps_mode passthrough `
    "$OutDir\${Base}_%04d.png"
}
function Encode-FramesJPG { param($In,$OutDir,$Base)
  New-Item "$OutDir" -ItemType Directory -EA 0 | Out-Null
  ffmpeg -hide_banner -y -i "$In" `
    -fps_mode passthrough -q:v 2 `
    "$OutDir\${Base}_%04d.jpg"
}
function Encode-FramesEXR { param($In,$OutDir,$Base)
  New-Item "$OutDir" -ItemType Directory -EA 0 | Out-Null
  ffmpeg -hide_banner -y -i "$In" `
    -fps_mode passthrough -pix_fmt rgba64le `
    "$OutDir\${Base}_%04d.exr"
}
function Encode-LastFrame { param($In,$Out)
  ffmpeg -hide_banner -y -sseof -1 -i "$In" -update 1 "$Out"
}
function Encode-FramesWav { param($In,$OutDir,$Base,$Fmt)
  New-Item "$OutDir" -ItemType Directory -EA 0 | Out-Null
  ffmpeg -hide_banner -y -i "$In" `
    -fps_mode passthrough `
    "$OutDir\${Base}_%04d.$Fmt"
  ffmpeg -hide_banner -y -i "$In" `
    -vn -c:a pcm_s24le `
    "$OutDir\${Base}.wav"
}

# ---------- pętla po plikach ----------
foreach ($f in $Files) {
  if (-not (Test-Path "$f")) { Write-Warning "$f nie istnieje" ; continue }
  $dir  = Split-Path "$f"
  $base = [System.IO.Path]::GetFileNameWithoutExtension("$f")

  # — klatki: zawsze własny podfolder
  if ($Preset -in 'frames_png','frames_jpg','frames_exr') {
    $framesDir = Join-Path $dir "${base}_FRAMES"
    Write-Host "`n$f  →  $framesDir\" -ForegroundColor Yellow
    try {
      switch ($Preset) {
        'frames_png' { Encode-FramesPNG $f $framesDir $base }
        'frames_jpg' { Encode-FramesJPG $f $framesDir $base }
        'frames_exr' { Encode-FramesEXR $f $framesDir $base }
      }
    } catch {
      Write-Error "Błąd FFmpeg: $_"
      if ($Debug) { $_ | Out-File (Join-Path $dir 'convert_debug.log') -Append }
    }
    continue
  }

  if ($Preset -eq 'last_frame') {
    $outFile = Join-Path $dir "${base}_last.png"
    Write-Host "`n$f  →  $outFile" -ForegroundColor Yellow
    try { Encode-LastFrame $f $outFile }
    catch {
      Write-Error "Błąd FFmpeg: $_"
      if ($Debug) { $_ | Out-File (Join-Path $dir 'convert_debug.log') -Append }
    }
    continue
  }

  if ($Preset -eq 'frames_wav') {
    $framesDir = Join-Path $dir "${base}_FRAMES"
    Write-Host "`n$f  →  $framesDir\" -ForegroundColor Yellow
    try { Encode-FramesWav $f $framesDir $base $FramesWavFormat }
    catch {
      Write-Error "Błąd FFmpeg: $_"
      if ($Debug) { $_ | Out-File (Join-Path $dir 'convert_debug.log') -Append }
    }
    continue
  }

  # — pojedynczy vs batch
  if ($Files.Count -gt 1) {
    $outDir = Join-Path $dir $Preset.ToUpper()
    New-Item "$outDir" -ItemType Directory -EA 0 | Out-Null
  } else {
    $outDir = $dir
  }

  $suffix = switch ($Preset) {
    'h264'    { '_H264'  }
    'h265'    { '_HEVC'  }
    'dnxhd'   { '_DNxHD' }
    'dnxhr'   { '_DNxHR' }
    'prores'  { '_PR'    }
    'cineform'{ '_CF'    }
  }
  $ext = switch ($Preset) {
    'h264'  { 'mp4' }
    'h265'  { 'mp4' }
    default { 'mov' }
  }
  $outFile = Join-Path $outDir "$base$suffix.$ext"

  Write-Host "`n$f  →  $outFile" -ForegroundColor Yellow
  try {
    switch ($Preset) {
      'h264'    { Encode-H264   $f $outFile }
      'h265'    { Encode-H265   $f $outFile }
      'dnxhd'   { Encode-DNxHD  $f $outFile }
      'dnxhr'   { Encode-DNxHR  $f $outFile }
      'prores'  { Encode-ProRes $f $outFile }
      'cineform'{ Encode-Cine   $f $outFile }
    }
  } catch {
    Write-Error "Błąd FFmpeg: $_"
    if ($Debug) { $_ | Out-File (Join-Path $dir 'convert_debug.log') -Append }
  }
}

[System.Windows.Forms.MessageBox]::Show("Gotowe!","Convert")
