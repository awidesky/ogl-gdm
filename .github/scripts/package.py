#!/usr/bin/env python3
"""Verify the ogl-gdm tutorial build and package it into a runnable artifact.

The CI (see .github/workflows/ci.yml) builds every CMake target but never runs
them: the tutorials are interactive OpenGL programs, so a headless runner has
nothing to execute. What CI can prove is that configuring succeeded, that every
target linked, and that every executable exists. This script turns that proof
into an artifact: one zip per platform holding every tutorial executable next
to the assets it loads at runtime, so a build can be exercised on a machine
that has no OpenGL development files installed.

Usage (usually called from the workflow, but works locally, too):

    python3 .github/scripts/package.py --config RelWithDebInfo

Exits non-zero if any expected executable is missing, so the workflow step
fails as well.
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent

ADD_EXECUTABLE_RE = re.compile(r"add_executable\s*\(\s*([A-Za-z0-9_.+-]+)([^)]*)\)", re.S)
OPTION_KEYWORDS = {"win32", "macosx_bundle", "exclude_from_all"}

# Directories whose non-source content is irrelevant to the artifact (only the
# exe is staged); everything else is copied as-is, which is exactly what the
# tutorials need: the exe loads shaders/textures/models from its directory.
BARE_DIRS = {"distrib"}

# Not needed to run an exe: build inputs, reference screenshots of the old
# (removed) automated screenshot tests, and OS/editor noise.
SKIP_DIRS = {"screenshots", "__pycache__", ".git", ".hg"}
SKIP_SUFFIXES = {".cpp", ".hpp", ".c", ".h", ".cxx", ".cc", ".ipp", ".inl",
                 ".bak", ".orig", ".pyc"}
# Build outputs of any platform: never runtime assets, and a source directory
# left over from a Windows build (.exe/.dll) must not leak into another
# platform's artifact. NOTE: .obj is deliberately not here - the tutorials load
# Wavefront models with that extension.
SKIP_BUILD_SUFFIXES = {".exe", ".pdb", ".dll", ".ilk", ".exp", ".lib", ".a",
                       ".o", ".so", ".dylib", ".app"}
SKIP_FILENAMES = {".ds_store", "thumbs.db", ".gitignore", ".hgignore",
                  "build.log", "screenshot.bmp"}

PLATFORM_NAMES = {"Windows": "windows", "Darwin": "macos", "Linux": "linux"}

# Shared libraries the artifact must not bundle: everything below these
# prefixes belongs to the OS and every target machine already has it. Anything
# else (a Homebrew dylib, a lib gdm fetched and built as a shared library, ...)
# travels with the exe and is patched to load from the exe's own directory.
SYSTEM_LIB_PREFIXES = {
    "Darwin": ("/usr/lib/", "/System/Library/", "@executable_path/",
               "@loader_path/", "@rpath/"),
    "Linux": ("/lib/", "/usr/lib/", "/lib64/", "/usr/lib64/"),
}
NON_DYNAMIC_MARKERS = ("statically linked", "not a dynamic executable",
                       "linux-vdso", "ldd:")

REQUIREMENTS = {
    "windows": (
        "A GPU/driver exposing a modern OpenGL. Windows only ships opengl32.dll,\n"
        "  which is an OpenGL 1.1 software rasterizer; the tutorials need at least\n"
        "  GL 3.3 from the graphics driver."
    ),
    "macos": (
        "macOS with the built-in OpenGL.framework (deprecated by Apple, but still\n"
        "  shipped and sufficient for these tutorials, which stay below GL 4.1)."
    ),
    "linux": (
        "X11 and Mesa's runtime GL library (libGL.so.1 plus the X11 client\n"
        "  libraries). Desktop Linux already has them; on a minimal system install\n"
        "  e.g. `libgl1-mesa-dri libx11-6` (Debian/Ubuntu) or `mesa-libGL libX11`\n"
        "  (Fedora). This is the one platform whose OpenGL pieces cannot be bundled."
    ),
}

README_TEMPLATE = """ogl-gdm tutorials - {plat} build
Commit {sha}{config}

Each directory holds one or more tutorial executables together with the assets
they load at runtime. Run them from inside their directory, e.g.:

    cd tutorial01_first_window
    ./tutorial01_first_window{exe_note}

Requirements on the machine that runs these:
{requirements}

Everything else travels with these executables: gdm's dependencies are built
statically where possible, and any dependency that came out as a shared library
(different when a developer machine already has it installed, e.g. via Homebrew)
was copied into each tutorial directory and repointed at it, so no third-party
library archive has to be installed.
"""


def parse_targets(cmake_file: Path, cmake_dir: Path):
    """[(target name, source dir), ...] declared by add_executable() in a file."""
    text = cmake_file.read_text(errors="replace")
    targets = []
    for m in ADD_EXECUTABLE_RE.finditer(text):
        name = m.group(1)
        args = m.group(2).split()
        source = next((a for a in args if a.lower() not in OPTION_KEYWORDS), None)
        if source is None:
            continue
        targets.append((name, (cmake_dir / source).parent))
    return targets


def read_cache(build_dir: Path):
    values = {}
    cache_file = build_dir / "CMakeCache.txt"
    if cache_file.is_file():
        for line in cache_file.read_text(errors="replace").splitlines():
            m = re.match(r"^([A-Za-z0-9_]+):[A-Z_]*=(.*)$", line)
            if m:
                values[m.group(1)] = m.group(2)
    return values


def exe_suffix():
    return ".exe" if os.name == "nt" else ""


def find_executable(name, source_dir, build_dir, config):
    """Where the build put the exe: source dir (POST_BUILD copy / Xcode), build
    dir, or multi-config subdir. Falls back to a bounded search of the build
    tree, which covers generators we did not anticipate."""
    exe = name + exe_suffix()
    candidates = [source_dir / exe, build_dir / exe]
    if config:
        candidates.insert(1, build_dir / config / exe)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    for root, dirs, files in os.walk(build_dir):
        if exe in files:
            return Path(root) / exe
        dirs[:] = [d for d in dirs
                   if d not in ("CMakeFiles", "_gdm_deps", "_gdm_extract",
                                "_gdm_downloads")]
    return None


def copy_sources(source_dir: Path, dest_dir: Path, exe_names):
    """Copy a target's source directory minus build inputs and reference art."""
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel = Path(root).relative_to(source_dir)
        target_root = dest_dir / rel
        target_root.mkdir(parents=True, exist_ok=True)
        for filename in files:
            if filename in SKIP_FILENAMES or filename in exe_names:
                continue
            suffix = Path(filename).suffix.lower()
            if suffix in SKIP_SUFFIXES or suffix in SKIP_BUILD_SUFFIXES:
                continue
            shutil.copy2(Path(root) / filename, target_root / filename)


def dynamic_dependencies(binary):
    """Absolute paths of the shared libraries `binary` loads ([] on Windows)."""
    if os.name == "nt":
        return []
    command = (["otool", "-L", str(binary)]
               if platform.system() == "Darwin" else ["ldd", str(binary)])
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    dependencies = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if any(marker in line for marker in NON_DYNAMIC_MARKERS):
            continue
        path = line.split(" => ", 1)[-1].split(" (")[0].strip()
        if os.path.isabs(path) and os.path.exists(path):
            dependencies.append(path)
    return dependencies


def dump_dependencies(binary):
    """Raw otool/ldd listing of `binary`, for the manifest."""
    if os.name == "nt":
        return []
    command = (["otool", "-L", str(binary)]
               if platform.system() == "Darwin" else ["ldd", str(binary)])
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return [f"<{command[0]} not runnable>"]
    if result.returncode != 0:
        return [f"<{command[0]} failed: {result.stderr.strip()}>"]
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if lines and lines[0].startswith(str(binary)):  # otool's "path:" header
        lines = lines[1:]
    return lines


def is_system_lib(path):
    prefixes = SYSTEM_LIB_PREFIXES.get(platform.system(), ("/usr/",))
    normalized = os.path.normpath(path)
    return any(normalized.startswith(p) for p in prefixes)


def repoint(binary, dep, name):
    """Make `binary` load its bundled copy `name` from the exe's directory."""
    if platform.system() == "Darwin":
        subprocess.run(["install_name_tool", "-change", dep,
                        f"@executable_path/{name}", str(binary)],
                       check=True, capture_output=True)
        # install_name_tool invalidates the (ad-hoc) code signature, and macOS
        # then refuses to exec the file at all - SIGKILL, no diagnostic.
        subprocess.run(["codesign", "--force", "--sign", "-", str(binary)],
                       check=True, capture_output=True)
    else:
        if not shutil.which("patchelf"):
            raise SystemExit(
                f"error: '{binary}' needs non-system library {dep}; bundling it "
                "requires patchelf (apt-get install patchelf) to set $ORIGIN rpath")
        subprocess.run(["patchelf", "--set-rpath", "$ORIGIN", str(binary)],
                       check=True, capture_output=True)


def bundle_libs(binary, dest_dir):
    """Copy every non-system library `binary` needs into dest_dir (recursively)
    and repoint the copy at it; only the staged exe is patched, never the build
    output. Returns [bundled library names]."""
    bundled, queue, seen = {}, [Path(binary)], set()
    while queue:
        current = queue.pop()
        for dep in dynamic_dependencies(current):
            if dep in seen or is_system_lib(dep):
                continue
            seen.add(dep)
            name = Path(dep).name
            target = dest_dir / name
            if not target.exists():
                shutil.copy2(dep, target)
                queue.append(target)
                if platform.system() == "Darwin":
                    subprocess.run(["install_name_tool", "-id",
                                    f"@executable_path/{name}", str(target)],
                                   check=True, capture_output=True)
                    subprocess.run(["codesign", "--force", "--sign", "-",
                                    str(target)], check=True, capture_output=True)
            bundled[dep] = name
            repoint(current, dep, name)
    return sorted(set(bundled.values()))


def stage_target(name, source_dir, exe_path, build_dir, config, stage_root,
                 repo_root, extra_dlls):
    try:
        rel = source_dir.resolve().relative_to(repo_root)
    except ValueError:
        rel = Path(source_dir.name)
    dest = stage_root / rel
    dest.mkdir(parents=True, exist_ok=True)
    if source_dir.name not in BARE_DIRS:
        copy_sources(source_dir, dest, {name + exe_suffix()})
    shutil.copy2(exe_path, dest / exe_path.name)
    # Best-effort companions so a crash on the test machine can be diagnosed.
    for suffix in (".pdb", ".ilk", ".exp"):
        candidate = exe_path.with_suffix(suffix)
        if candidate.is_file():
            shutil.copy2(candidate, dest / candidate.name)
        elif config:
            candidate = build_dir / config / (name + suffix)
            if candidate.is_file():
                shutil.copy2(candidate, dest / candidate.name)
    if extra_dlls:
        for dll in extra_dlls:
            target = dest / dll.name
            if not target.exists():
                shutil.copy2(dll, target)
    # gdm prefers an already-installed package when one exists, so a developer
    # machine (Homebrew, ...) links shared libraries a clean machine builds
    # statically. Bundle whatever is non-system either way.
    return dest / exe_path.name, bundle_libs(dest / exe_path.name, dest)


def write_manifest(stage_root: Path, records, plat, sha, config):
    """records: (target, build exe, staged exe, path to display, size, bundled)."""
    lines = [
        f"ogl-gdm {plat} build - commit {sha}"
        + (f" - configuration {config}" if config else ""),
        f"targets: {len(records)}",
        "",
        "%-38s %-46s %10s" % ("target", "path", "size"),
        "-" * 96,
    ]
    for name, _exe, _staged, display, size, bundled in records:
        lines.append("%-38s %-46s %10s" % (name, display, size))
        if bundled:
            lines.append("%-38s %s" % ("", "bundled: "
                                       + ", ".join(sorted(set(bundled)))))
    lines.append("")
    lines.append("Dependencies of the staged executables:")
    dumped = False
    for _name, _exe, staged, _display, _size, _bundled in records:
        if os.name == "nt" or not Path(staged).is_file():
            continue
        dumped = True
        lines.append(f"  {Path(staged).name}:")
        lines += ["    " + dep for dep in dump_dependencies(staged)]
    if not dumped:
        lines.append("  <not collected on this platform>")
    (stage_root / "MANIFEST.txt").write_text("\n".join(lines) + "\n")


def write_readme(stage_root: Path, plat, sha, config):
    note = ".exe (Windows)" if plat == "windows" else ""
    (stage_root / "README.txt").write_text(README_TEMPLATE.format(
        plat=plat, sha=sha, config=f" - configuration {config}" if config else "",
        requirements=REQUIREMENTS[plat],
        exe_note=note,
    ))


def human_size(num_bytes):
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024 or unit == "GB":
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024


def git_sha(repo_root):
    try:
        out = subprocess.run(["git", "-C", str(repo_root), "rev-parse", "--short=7",
                              "HEAD"], capture_output=True, text=True, timeout=30)
        return out.stdout.strip() or "local"
    except (OSError, subprocess.SubprocessError):
        return "local"


def collect_dlls(build_dir, config):
    """Every DLL the build produced. Windows loads a DLL from the exe's own
    directory, so nothing has to be repointed - just copied next to the exe."""
    if os.name != "nt":
        return []
    dlls, seen = [], set()
    prune = ("CMakeFiles", "_gdm_extract", "_gdm_downloads")
    for root, dirs, files in os.walk(build_dir):
        if any(part in prune for part in Path(root).parts):
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in prune]
        for filename in sorted(files):
            if filename.lower().endswith(".dll") and filename not in seen:
                seen.add(filename)
                dlls.append(Path(root) / filename)
    return dlls


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT,
                        help="repository checkout (default: %(default)s)")
    parser.add_argument("--build-dir", type=Path, default=None,
                        help="CMake build dir (default: <repo-root>/build)")
    parser.add_argument("--config", default="",
                        help="multi-config generator configuration, e.g. RelWithDebInfo")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="where the zip is written "
                             "(default: $ARTIFACT_DIR or <repo-root>/dist)")
    parser.add_argument("--include-distrib", dest="include_distrib",
                        action="store_true", default=None,
                        help="also expect the Windows-only distrib/ targets "
                             "(-DINCLUDE_DISTRIB=true)")
    parser.add_argument("--no-include-distrib", dest="include_distrib",
                        action="store_false",
                        help="ignore the distrib/ targets even if configured")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    build_dir = args.build_dir or repo_root / "build"
    out_dir = args.out_dir or Path(os.environ.get("ARTIFACT_DIR", repo_root / "dist"))
    config = args.config

    plat = PLATFORM_NAMES.get(platform.system(), platform.system().lower())
    sha = git_sha(repo_root)

    cache = read_cache(build_dir)
    include_distrib = args.include_distrib
    if include_distrib is None:
        include_distrib = (os.name == "nt"
                           and cache.get("INCLUDE_DISTRIB", "OFF").upper() == "ON")

    targets = list(parse_targets(repo_root / "CMakeLists.txt", repo_root))
    if include_distrib and (repo_root / "distrib" / "CMakeLists.txt").is_file():
        targets += parse_targets(repo_root / "distrib" / "CMakeLists.txt",
                                 repo_root / "distrib")

    if not targets:
        print(f"error: no executables declared in {repo_root / 'CMakeLists.txt'}",
              file=sys.stderr)
        return 1

    # --- verify: the "configure and build succeeded" proof -------------------
    print(f"ogl-gdm {plat} build{(' - ' + config) if config else ''} "
          f"(commit {sha}, {build_dir})")
    found, missing = [], []
    for name, source_dir in targets:
        exe = find_executable(name, source_dir, build_dir, config)
        (found if exe else missing).append((name, source_dir, exe))

    print(f"\n{len(found)}/{len(targets)} targets built:")
    for name, source_dir, exe in found:
        print(f"  OK   {name:<40} {exe}")
    for name, source_dir, _ in missing:
        print(f"  FAIL {name:<40} not found")

    if missing:
        print(f"\nerror: {len(missing)} target(s) produced no executable; "
              "the build did not complete", file=sys.stderr)
        return 1

    # --- package --------------------------------------------------------------
    stage_root = Path(tempfile.mkdtemp(prefix=f"ogl-gdm-{plat}-"))
    try:
        records, dlls = [], collect_dlls(build_dir, config)
        bundled_total = 0
        for name, source_dir, exe in found:
            staged, bundled = stage_target(name, source_dir, exe, build_dir,
                                          config, stage_root, repo_root, dlls)
            bundled_total += len(bundled)
            try:
                rel = exe.resolve().relative_to(repo_root)
            except ValueError:
                rel = Path(exe.name)
            records.append((name, exe, staged, rel, human_size(exe.stat().st_size),
                            bundled))
        write_manifest(stage_root, records, plat, sha, config)
        write_readme(stage_root, plat, sha, config)

        out_dir.mkdir(parents=True, exist_ok=True)
        zip_path = out_dir / f"ogl-gdm-{plat}-{sha}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(stage_root.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(stage_root))
        print(f"\npackaged {len(found)} executables, "
              f"{bundled_total} non-system librar(ies), {len(dlls)} dll(s) "
              f"-> {zip_path} ({human_size(zip_path.stat().st_size)})")
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
