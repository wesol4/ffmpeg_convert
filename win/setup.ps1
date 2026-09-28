param(
    [ValidateSet('', 'install', 'launch', 'audio', 'remove-menu', 'diagnose')]
    [string]$Action = '',
    [switch]$SmokeTest
)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUNBUFFERED = '1'

function Find-Python {
    $checks = @(
        @{ Exe = 'py'; Prefix = @('-3.12') },
        @{ Exe = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"; Prefix = @() },
        @{ Exe = 'python'; Prefix = @() }
    )
    foreach ($check in $checks) {
        if (-not (Get-Command $check.Exe -ErrorAction SilentlyContinue)) { continue }
        try {
            $exe = $check.Exe
            $prefix = $check.Prefix
            $result = & $exe @prefix -c "import sys,struct; sys.exit(1) if sys.version_info[:2]!=(3,12) or struct.calcsize('P')!=8 else print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $result) { return ([string](@($result)[-1])).Trim() }
        } catch { continue }
    }
    return $null
}

# Worker process: all blocking operations happen outside the UI process.
if ($Action) {
    try {
        [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
        $OutputEncoding = [Console]::OutputEncoding
        $python = Find-Python
        if (-not $python -and $Action -eq 'install') {
            if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
                throw 'Brak Python 3.12 i winget. Zainstaluj App Installer ze sklepu Microsoft lub Python 3.12 x64 z python.org.'
            }
            Write-Output 'Instalowanie Python 3.12 (moze potrwac kilka minut)...'
            & winget install --id Python.Python.3.12 --exact --source winget --scope user --architecture x64 --silent --accept-source-agreements --accept-package-agreements --disable-interactivity
            if ($LASTEXITCODE -ne 0) { throw 'Instalacja Python nie powiodla sie. Sprawdz komunikaty powyzej.' }
            $python = Find-Python
        }
        if (-not $python) { throw 'Nie znaleziono Python 3.12 64-bit. Kliknij Zainstaluj / aktualizuj.' }
        & $python (Join-Path $PSScriptRoot 'setup.py') --action $Action
        exit $LASTEXITCODE
    } catch {
        [Console]::Error.WriteLine($_.Exception.Message)
        exit 1
    }
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
$form = New-Object System.Windows.Forms.Form
$form.Text = 'FFmpeg Convert — instalator'
$form.Size = New-Object System.Drawing.Size(820, 680)
$form.MinimumSize = New-Object System.Drawing.Size(680, 560)
$form.StartPosition = 'CenterScreen'
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)
$form.BackColor = [System.Drawing.Color]::FromArgb(245, 247, 250)
$form.AutoScaleMode = 'Dpi'
$layout = New-Object System.Windows.Forms.TableLayoutPanel
$layout.Dock = 'Fill'
$layout.Padding = New-Object System.Windows.Forms.Padding(24)
$layout.ColumnCount = 1
$layout.RowCount = 7
foreach ($height in @(42, 64, 112, 42, 12)) {
    $layout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle('Absolute', $height))) | Out-Null
}
$layout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle('Percent', 100))) | Out-Null
$layout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle('Absolute', 36))) | Out-Null
$form.Controls.Add($layout)

$title = New-Object System.Windows.Forms.Label
$title.Text = 'FFmpeg Convert'
$title.Font = New-Object System.Drawing.Font('Segoe UI', 20, [System.Drawing.FontStyle]::Bold)
$title.Dock = 'Fill'
$layout.Controls.Add($title, 0, 0)
$intro = New-Object System.Windows.Forms.Label
$intro.Text = "Zainstaluj lub zaktualizuj aplikację dla swojego konta.`nFolder: $env:LOCALAPPDATA\FFmpegConvert"
$intro.Dock = 'Fill'
$layout.Controls.Add($intro, 0, 1)

$buttons = New-Object System.Windows.Forms.TableLayoutPanel
$buttons.Dock = 'Fill'
$buttons.ColumnCount = 2
$buttons.RowCount = 3
$buttons.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle('Percent', 50))) | Out-Null
$buttons.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle('Percent', 50))) | Out-Null
$layout.Controls.Add($buttons, 0, 2)
$definitions = @(
    @('Zainstaluj / aktualizuj', 'install'),
    @('Uruchom aplikację', 'launch'),
    @('Zainstaluj separację audio', 'audio'),
    @('Sprawdź instalację', 'diagnose'),
    @('Usuń menu kontekstowe', 'remove-menu')
)
$script:actionButtons = @()
for ($index = 0; $index -lt $definitions.Count; $index++) {
    $button = New-Object System.Windows.Forms.Button
    $button.Text = $definitions[$index][0]
    $button.Tag = $definitions[$index][1]
    $button.Dock = 'Fill'
    $button.Margin = New-Object System.Windows.Forms.Padding(0, 0, 8, 6)
    $button.Add_Click({ param($sender, $eventArgs) Start-Task ([string]$sender.Tag) })
    $buttons.Controls.Add($button, ($index % 2), [int][Math]::Floor($index / 2))
    $script:actionButtons += $button
}
$script:actionButtons[0].BackColor = [System.Drawing.Color]::FromArgb(28, 85, 153)
$script:actionButtons[0].ForeColor = [System.Drawing.Color]::White
$script:actionButtons[0].FlatStyle = 'Flat'
$status = New-Object System.Windows.Forms.Label
$status.Text = 'Gotowe do instalacji. Separacja audio jest opcjonalna i zajmuje kilka GB.'
$status.Dock = 'Fill'
$status.TextAlign = 'MiddleLeft'
$layout.Controls.Add($status, 0, 3)
$progress = New-Object System.Windows.Forms.ProgressBar
$progress.Dock = 'Fill'
$progress.Style = 'Marquee'
$progress.MarqueeAnimationSpeed = 0
$layout.Controls.Add($progress, 0, 4)
$log = New-Object System.Windows.Forms.TextBox
$log.Multiline = $true
$log.ReadOnly = $true
$log.ScrollBars = 'Both'
$log.WordWrap = $false
$log.Dock = 'Fill'
$log.BackColor = [System.Drawing.Color]::White
$log.Font = New-Object System.Drawing.Font('Consolas', 9)
$log.AccessibleName = 'Szczegóły instalacji i błędy'
$layout.Controls.Add($log, 0, 5)
$footer = New-Object System.Windows.Forms.FlowLayoutPanel
$footer.Dock = 'Fill'
$footer.FlowDirection = 'RightToLeft'
$close = New-Object System.Windows.Forms.Button
$close.Text = 'Zamknij'
$close.AutoSize = $true
$close.Add_Click({ $form.Close() })
$copy = New-Object System.Windows.Forms.Button
$copy.Text = 'Kopiuj szczegóły'
$copy.AutoSize = $true
$copy.Add_Click({ if ($log.Text) { [System.Windows.Forms.Clipboard]::SetText($log.Text) } })
$footer.Controls.Add($close)
$footer.Controls.Add($copy)
$layout.Controls.Add($footer, 0, 6)

$script:worker = $null
$script:logRoot = Join-Path ([IO.Path]::GetTempPath()) ('ffmpeg-setup-' + [Guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($script:logRoot) | Out-Null
$script:stdoutFile = ''
$script:stderrFile = ''
function Start-Task([string]$task) {
    if ($script:worker -and -not $script:worker.HasExited) { return }
    $stamp = [Guid]::NewGuid().ToString('N')
    $script:stdoutFile = Join-Path $script:logRoot ($stamp + '.out.txt')
    $script:stderrFile = Join-Path $script:logRoot ($stamp + '.err.txt')
    $log.Clear()
    $status.Text = 'Praca w toku… Szczegóły pojawią się poniżej.'
    foreach ($button in $script:actionButtons) { $button.Enabled = $false }
    $close.Enabled = $false
    $progress.MarqueeAnimationSpeed = 30
    try {
        $arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $PSCommandPath + '" -Action ' + $task
        $script:worker = Start-Process -FilePath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -ArgumentList $arguments -WindowStyle Hidden -RedirectStandardOutput $script:stdoutFile -RedirectStandardError $script:stderrFile -PassThru
        $null = $script:worker.Handle
    } catch {
        $script:worker = $null
        $status.Text = 'Nie można rozpocząć operacji. Szczegóły poniżej.'
        $log.Text = $_.Exception.Message
        foreach ($button in $script:actionButtons) { $button.Enabled = $true }
        $close.Enabled = $true
        $progress.MarqueeAnimationSpeed = 0
    }
}
$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 300
$timer.Add_Tick({
    if (-not $script:worker) { return }
    try {
        $text = ''
        foreach ($file in @($script:stdoutFile, $script:stderrFile)) {
            if (Test-Path -LiteralPath $file) { $text += [IO.File]::ReadAllText($file) + "`r`n" }
        }
        if ($text.Length -gt 100000) { $text = $text.Substring($text.Length - 100000) }
        if ($log.Text -ne $text) {
            $log.Text = $text
            $log.SelectionStart = $log.TextLength
            $log.ScrollToCaret()
        }
    } catch { } # A log may be briefly locked while the worker is writing.
    if ($script:worker.HasExited) {
        $code = $script:worker.ExitCode
        $script:worker.Dispose()
        $script:worker = $null
        $progress.MarqueeAnimationSpeed = 0
        foreach ($button in $script:actionButtons) { $button.Enabled = $true }
        $close.Enabled = $true
        if ($code -eq 0) { $status.Text = 'Gotowe. Operacja zakończona poprawnie.' }
        else { $status.Text = 'Operacja nie powiodła się. Sprawdź szczegóły i spróbuj ponownie.' }
    }
})
$form.Add_FormClosing({
    param($sender, $eventArgs)
    if ($script:worker -and -not $script:worker.HasExited) {
        $eventArgs.Cancel = $true
        $status.Text = 'Poczekaj na zakończenie bieżącej operacji przed zamknięciem okna.'
    }
})
$timer.Start()
if ($SmokeTest) {
    $smokeTimer = New-Object System.Windows.Forms.Timer
    $smokeTimer.Interval = 500
    $smokeTimer.Add_Tick({ $smokeTimer.Stop(); $form.Close() })
    $smokeTimer.Start()
}
try { [System.Windows.Forms.Application]::Run($form) }
finally { $timer.Dispose(); $form.Dispose() }
