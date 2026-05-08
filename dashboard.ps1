Write-Host '====================================================' -ForegroundColor Cyan
Write-Host '  Game News Collection - System Dashboard' -ForegroundColor Cyan
Write-Host ('  ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')) -ForegroundColor Cyan
Write-Host '====================================================' -ForegroundColor Cyan

# ===== 1. Cron Sync =====
Write-Host ''
Write-Host '=== 1. Cron Git Sync (WSL, /5min) ===' -ForegroundColor Yellow
$cronLog = 'C:\Users\q1138\game-news-daily\github-sync.log'
if (Test-Path $cronLog) {
    $entries = Get-Content $cronLog | Select-Object -Last 15
    if ($entries) {
        Write-Host '  Last 15 entries (newest at bottom):'
        foreach ($e in $entries) {
            if ($e -match 'FAIL') { Write-Host ('  ' + $e) -ForegroundColor Red }
            elseif ($e -match 'PULL|OK') { Write-Host ('  ' + $e) -ForegroundColor Green }
            elseif ($e -match 'SYNC') { Write-Host ('  ' + $e) -ForegroundColor Gray }
            else { Write-Host ('  ' + $e) }
        }
    } else {
        Write-Host '  No sync activity yet'
    }
} else {
    Write-Host '  No sync activity yet'
}

# ===== 2. Task Scheduler Status =====
Write-Host ''
Write-Host '=== 2. Scheduled Task ===' -ForegroundColor Yellow
$task = Get-ScheduledTask -TaskName 'DailyNewsOpenCLI' -ErrorAction SilentlyContinue
if ($task) {
    $info = Get-ScheduledTaskInfo -TaskName 'DailyNewsOpenCLI'
    Write-Host ('  State:         ' + $task.State)
    Write-Host ('  WakeToRun:     ' + $task.Settings.WakeToRun)
    Write-Host ('  Trigger:       ' + $task.Triggers[0].StartBoundary)
    Write-Host ('  Last Run:      ' + $info.LastRunTime)
    Write-Host ('  Next Run:      ' + $info.NextRunTime)
    Write-Host ('  Missed Runs:   ' + $info.NumberOfMissedRuns)
    $r = $info.LastTaskResult
    Write-Host ('  Last Result:   ' + $r)
    if ($r -eq 0) { Write-Host '    -> SUCCESS' -ForegroundColor Green }
    elseif ($r -eq 267009) { Write-Host '    -> Starting (queued, not completed)' -ForegroundColor Yellow }
    elseif ($r -eq 2147942402) { Write-Host '    -> FILE_NOT_FOUND' -ForegroundColor Red }
    elseif ($r -eq 2147946720) { Write-Host '    -> Still running or locked' -ForegroundColor Yellow }
    else { Write-Host ('    -> 0x{0:X}' -f $r) }
} else {
    Write-Host '  [FATAL] Task NOT FOUND!' -ForegroundColor Red
}

# ===== 3. Recent Events =====
Write-Host ''
Write-Host '=== 3. Recent Task Events (last 24h) ===' -ForegroundColor Yellow
$events = Get-WinEvent -LogName 'Microsoft-Windows-TaskScheduler/Operational' -MaxEvents 500 -ErrorAction SilentlyContinue |
    Where-Object { $_.TimeCreated -gt (Get-Date).AddDays(-1) -and $_.Message -match 'DailyNewsOpenCLI' } |
    Select-Object -First 15
if ($events) {
    foreach ($e in $events) {
        $tag = '   '
        if ($e.Id -eq 201) { $tag = '[OK] ' }
        elseif ($e.Id -eq 101) { $tag = '[FAIL]' }
        elseif ($e.Id -eq 203) { $tag = '[FAIL]' }
        elseif ($e.Id -eq 200) { $tag = '[RUN] ' }
        elseif ($e.Id -eq 129) { $tag = '[PROC]' }
        elseif ($e.Id -eq 107) { $tag = '[TRIG]' }
        Write-Host ('  {0} {1}  ID={2}' -f $tag, $e.TimeCreated.ToString('HH:mm:ss'), $e.Id)
    }
} else {
    Write-Host '  No events found'
}

# ===== 4. Collection Output =====
Write-Host ''
Write-Host '=== 4. Collection Output ===' -ForegroundColor Yellow
$pendingFile = 'C:\Users\q1138\game-news-daily\output\.cache\opencli-pending.json'
$seenFile = 'C:\Users\q1138\game-news-daily\output\.cache\seen_items.json'
foreach ($f in @($pendingFile, $seenFile)) {
    if (Test-Path $f) {
        $item = Get-Item $f
        Write-Host ('  {0}: {1} bytes, {2}' -f $item.Name, $item.Length, $item.LastWriteTime)
    } else {
        Write-Host ('  {0}: NOT FOUND' -f (Split-Path $f -Leaf))
    }
}

# ===== 5. OpenCLI =====
Write-Host ''
Write-Host '=== 5. OpenCLI Status ===' -ForegroundColor Yellow
$result = & opencli doctor 2>&1
$result | Select-Object -First 6 | ForEach-Object { Write-Host '  ' $_ }

# ===== 6. Wake Events =====
Write-Host ''
Write-Host '=== 6. Power/Wake Events ===' -ForegroundColor Yellow
$wakeEvents = Get-WinEvent -FilterHashtable @{LogName='System';Id=1,42,107} -MaxEvents 10 -ErrorAction SilentlyContinue |
    Where-Object { $_.TimeCreated -gt (Get-Date).AddDays(-1) }
if ($wakeEvents) {
    $wakeEvents | Select-Object -First 5 | ForEach-Object {
        Write-Host ('  [{0}] {1}' -f $_.TimeCreated.ToString('HH:mm:ss'), $_.Message.Substring(0, [Math]::Min(100, $_.Message.Length)))
    }
} else {
    Write-Host '  No wake/sleep events today'
}

# ===== 7. Task-run.bat check =====
Write-Host ''
Write-Host '=== 7. Config Check ===' -ForegroundColor Yellow
$trb = 'C:\Users\q1138\game-news-daily\task-run.bat'
if (Test-Path $trb) {
    Write-Host '  task-run.bat: EXISTS'
    $content = Get-Content $trb -Raw
    if ($content -match 'SetSuspendState') { Write-Host '  Auto-sleep:   ENABLED' -ForegroundColor Green; $sleepOk = $true }
    else { Write-Host '  Auto-sleep:   MISSING' -ForegroundColor Red; $sleepOk = $false }
    if ($content -match 'git pull origin') { Write-Host '  Pre-pull:     ENABLED' -ForegroundColor Green }
    else { Write-Host '  Pre-pull:     MISSING' -ForegroundColor Yellow }
    if ($content -match 'Chrome') { Write-Host '  Chrome start: ENABLED' -ForegroundColor Green }
} else {
    Write-Host '  task-run.bat: MISSING!' -ForegroundColor Red
}

# ===== Summary =====
Write-Host ''
Write-Host '====================================================' -ForegroundColor Cyan
$t = Get-ScheduledTask -TaskName 'DailyNewsOpenCLI' -ErrorAction SilentlyContinue
$stat = if ($t -and $t.State -eq 'Ready') { 'TASK=READY' } else { 'TASK=MISSING' }
$wake = if ($t -and $t.Settings.WakeToRun) { 'WAKE=ON' } else { 'WAKE=OFF' }
$pend = if (Test-Path $pendingFile) { 'PENDING=YES' } else { 'PENDING=NO' }
$sleep = if ($sleepOk) { 'SLEEP=ON' } else { 'SLEEP=OFF' }
$pull = if ($content -match 'git pull origin') { 'PULL=ON' } else { 'PULL=OFF' }
Write-Host ('  ' + $stat + ' | ' + $wake + ' | ' + $pend + ' | ' + $sleep + ' | ' + $pull) -ForegroundColor Green
Write-Host '====================================================' -ForegroundColor Cyan
Write-Host ''
Read-Host 'Press Enter to close'