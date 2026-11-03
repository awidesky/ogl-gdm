<#
.SYNOPSIS
    Bulk smoke test for an ogl-gdm artifact on Windows.

.DESCRIPTION
    Runs the tutorial executables from inside their own directory (assets load
    relative to it), and reports whether they ran.

    Interactive (the default): no timeout and no kill - the script waits until you
    close each window (Esc), then moves on to the next one, with the executable's
    output straight in this console. This is the mode for actually using the
    tutorials, and for reading what the gdm probe at the payload root prints about
    this machine.

    Every executable runs, all of them: four source directories hold two or three
    (tutorial09_vbo_indexing, misc05_picking, t16, t18) and they are separate
    demos, not duplicates of each other - misc05_picking alone covers glReadPixels
    picking, custom ray-box intersection and Bullet physics.

    Whatever ships in the payload is picked up automatically - an executable at
    the root (gdm's gdm_example_1_HelloWindow prints the GL/GLSL and GPU info of
    the machine it runs on) needs no entry anywhere.

    A downloaded artifact carries the "Mark of the Web", which blocks the
    executables; the script removes it. Optionally it also adds a Windows
    Defender exclusion, because unsigned executables are scanned on every launch
    (that needs an elevated shell, and is skipped with a warning if it fails).

.PARAMETER List
    Only print the executables that would run.

.PARAMETER Timed
    Opt out of the interactive default. Let each executable run for the given
    number of seconds, kill it, and capture its output in a log: a quick pass
    over the whole set for when nobody is watching. Surviving there proves each
    starts, finds its assets and loads its libraries, but not that it renders.

.PARAMETER DefenderBypass
    Add an exclusion for the payload directory to Windows Defender.

.EXAMPLE
    .\smoke-test.ps1
.EXAMPLE
    .\smoke-test.ps1 -DefenderBypass
.EXAMPLE
    .\smoke-test.ps1 -Timed 3
#>
[CmdletBinding()]
param(
    [switch]$List,
    [int]$Timed = 0,          # 0 = interactive (wait for the window to close)
    [switch]$DefenderBypass
)

$ErrorActionPreference = 'Stop'
if ($Timed -lt 1) {
    throw '-Timed needs a number of seconds, for example: -Timed 5.'
}
$interactive = ($Timed -eq 0)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $here

# 1. let a downloaded copy run.
#    Remove the Mark of the Web: without it Windows refuses, or prompts for, each
#    file that came out of an archive.
Get-ChildItem -LiteralPath $here -Recurse -File -Force |
    Unblock-File -ErrorAction SilentlyContinue

if ($DefenderBypass) {
    try {
        Add-MpPreference -ExclusionPath $here -ErrorAction Stop
        Write-Host "Defender exclusion added for $here"
    }
    catch {
        Write-Warning "Could not add a Defender exclusion (run in an elevated PowerShell): $($_.Exception.Message)"
    }
}

# 2. the executables: every executable inside a tutorial directory, plus one
#    shipped beside them at the payload root (gdm_example_1_HelloWindow, once the
#    gdm examples are built and packaged, prints the machine's GL/GLSL info).
#    The payload layout needs no list of names to keep in sync with the build.
$found = Get-ChildItem -LiteralPath $here -Recurse -Filter *.exe -File |
    Where-Object { $_.FullName -notlike "$here\lib\*" } |
    Sort-Object FullName

if (-not $found) {
    Write-Host "No executables found under $here (wrong directory?)"
    exit 2
}

# every executable: a directory with two or three of them holds separate
# demos (misc05_picking covers picking via three different techniques)
$executables = $found

if ($interactive) {
    Write-Host "smoke test: $(@($executables).Count) executables, close each window to move on"
} else {
    Write-Host "smoke test: $(@($executables).Count) executables, ${Timed}s each"
}
Write-Host "root: $here"

$scratch = Join-Path $env:TEMP "ogl-gdm-smoke"
$null = New-Item -ItemType Directory -Path $scratch -Force

$passed = 0
$failed = 0
foreach ($exe in $executables) {
    if ($List) {
        Write-Host "  $($exe.FullName)"
        continue
    }

    # a separator per executable, so the log can be read - or split at - the
    # boundary between runs
    Write-Host ""
    Write-Host "========== $($exe.Name) =========="
    $log = Join-Path $scratch "$($exe.BaseName).log"
    $arguments = @{
        FilePath         = $exe.FullName
        WorkingDirectory = $exe.DirectoryName
        PassThru         = $true
    }
    if ($interactive) {
        # no timeout and no kill: wait until the window is closed (Esc), with the
        # executable writing straight to this console
        $process = Start-Process @arguments -Wait
        if ($process.ExitCode -eq 0) {
            $passed++
            Write-Host "PASS  $($exe.Name) (closed)"
        }
        else {
            $failed++
            Write-Host "FAIL  $($exe.Name) (exit $($process.ExitCode))"
        }
        continue
    }

    try {
        $process = Start-Process @arguments -RedirectStandardOutput $log `
            -RedirectStandardError "$log.err"
    }
    catch {
        # a GUI subsystem executable does not accept redirected handles
        $process = Start-Process @arguments
    }

    Start-Sleep -Seconds $Timed

    if (-not $process.HasExited) {
        # kill the tree: these executables do not spawn helpers, but be sure
        try {
            taskkill /PID $process.Id /T /F 2>&1 | Out-Null
        }
        catch {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
        $passed++
        Write-Host "PASS  $($exe.Name)"
    }
    else {
        # A clean exit is a pass - the tutorials normally loop until you close
        # them, so exiting at all is unusual, but exiting *successfully* is not
        # a failure of the artifact.
        if ($process.ExitCode -eq 0) {
            $passed++
            Write-Host "PASS  $($exe.Name) (exited cleanly)"
        }
        else {
            $status = $process.ExitCode
            $failed++
            Write-Host "FAIL  $($exe.Name) (exit $status)"
            foreach ($stream in @("$log.err", $log)) {
                if (Test-Path -LiteralPath $stream) {
                    $content = Get-Content -LiteralPath $stream -Raw -ErrorAction SilentlyContinue
                    if ($content -and $content.Trim()) {
                        $content -split "`r?`n" |
                            Select-Object -First 8 |
                            ForEach-Object { Write-Host "      $_" }
                        break
                    }
                }
            }
        }
    }
}

if ($List) { exit 0 }

Write-Host ''
Write-Host "$passed passed, $failed failed"
if ($failed -ne 0) { exit 1 }
