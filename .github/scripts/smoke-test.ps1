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
    number of seconds and then kill it: a quick pass over the whole set for when
    nobody is watching. Its output still appears in this console. Surviving there
    proves each starts, finds its assets and loads its libraries, but not that it
    renders.

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
# PowerShell 7.4 can turn a native command's non-zero exit into a terminating
# error; we want the real code from $LASTEXITCODE instead
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}
# only a value that was actually passed is checked: absent means interactive,
# whose sentinel is the same 0
if ($PSBoundParameters.ContainsKey('Timed') -and $Timed -lt 1) {
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

$passed = 0
$failed = 0
foreach ($exe in $executables) {
    if ($List) {
        Write-Host "  $($exe.FullName)"
        continue
    }

    # a separator per executable, so the console can be read - or split at - the
    # boundary between runs
    Write-Host ""
    Write-Host "========== $($exe.Name) =========="
    if ($interactive) {
        # no timeout and no kill: run it in the foreground with the call
        # operator, so it inherits this console and its output appears inline,
        # and wait until its window is closed (Esc). Start-Process would detach
        # it from the console, which is why nothing was printed before.
        Push-Location -LiteralPath $exe.DirectoryName
        try {
            $LASTEXITCODE = 0        # clear a stale code before the run
            & $exe.FullName
            $code = $LASTEXITCODE
        }
        catch {
            $code = 1
            Write-Host "      $($_.Exception.Message)"
        }
        finally {
            Pop-Location
        }
        if ($null -eq $code) { $code = 0 }
        if ($code -eq 0) {
            $passed++
            Write-Host "PASS  $($exe.Name) (closed)"
        }
        else {
            $failed++
            Write-Host "FAIL  $($exe.Name) (exit $code)"
        }
        continue
    }

    # timed: same console output, but killed after a few seconds. The .NET API
    # is used instead of Start-Process because UseShellExecute = $false is what
    # makes the child share this console (Start-Process would give it a new
    # window, or none at all when it redirects).
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $exe.FullName
    $startInfo.WorkingDirectory = $exe.DirectoryName
    $startInfo.UseShellExecute = $false
    try {
        $process = [System.Diagnostics.Process]::Start($startInfo)
    }
    catch {
        # one executable that cannot even start must not stop the whole run
        $failed++
        Write-Host "FAIL  $($exe.Name) (could not start: $($_.Exception.Message))"
        continue
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
            $failed++
            Write-Host "FAIL  $($exe.Name) (exit $($process.ExitCode))"
        }
    }
}

if ($List) { exit 0 }

Write-Host ''
Write-Host "$passed passed, $failed failed"
if ($failed -ne 0) { exit 1 }
