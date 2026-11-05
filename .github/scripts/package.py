#!/usr/bin/env python3
"""Verify the ogl-gdm tutorial build and package it into a runnable artifact.

The CI (see .github/workflows/ci.yml) builds every CMake target but never runs
them: the tutorials are interactive OpenGL programs, so a headless runner has
nothing to execute. What CI can prove is that configuring succeeded, that every
target linked, and that every executable exists. This script turns that proof
into an artifact: every tutorial executable next to the assets it loads at
runtime, so a build can be exercised on a machine that has no OpenGL
development files installed.

Two outputs, both optional in combination:
  * a zip (--out-dir) - what you hand to someone else
  * the unpacked payload (--payload-dir) - what actions/upload-artifact should
    get, so the downloaded artifact expands straight into the tutorials instead
    of into another archive (upload-artifact always zips what it is given)

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
import stat
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

# gdm's own examples built only when GDM_BUILD_EXAMPLES=ON.
EXAMPLES_DIR = "external/gdm/examples"

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
        "  GL 3.3 from the graphics driver. Nothing else to install."
    ),
    "macos": (
        "Nothing to install: OpenGL.framework and the other frameworks these\n"
        "  executables use ship with macOS itself (OpenGL has been deprecated\n"
        "  since 10.14, but it is still there and sufficient for these tutorials,\n"
        "  which stay below GL 4.1).\n"
        "\n"
        "If a library ever reports as missing, the matching Homebrew packages are:\n"
        "      brew install glfw glm cpptrace\n"
        "\n"
        "These executables are not notarized - that needs a paid Apple Developer\n"
        "  ID, which a tutorial project has no use for - so Gatekeeper stops the\n"
        "  first launch (\"... cannot be opened because Apple cannot check it\").\n"
        "  Approve each file once in System Settings > Privacy & Security > Open\n"
        "  Anyway, or clear the download marker for the whole folder at once:\n"
        "      xattr -dr com.apple.quarantine ."
    ),
    "linux": (
        "X11 and Mesa are not part of the tutorials, so they must come from your\n"
        "  distribution. Install them with the package manager:\n"
        "\n"
        "  Debian/Ubuntu:\n"
        "      sudo apt-get install -y libgl1 libglu1-mesa libx11-6 libxext6 \\\n"
        "        libxrandr2 libxinerama1 libxcursor1 libxi6 mesa-utils \\\n"
        "        mesa-dri-drivers libwayland-client0 libwayland-cursor0 \\\n"
        "        libwayland-egl1 libxkbcommon0\n"
        "\n"
        "  Fedora:\n"
        "      sudo dnf install -y mesa-libGL mesa-libGLU libX11 libXext \\\n"
        "        libXrandr libXinerama libXcursor libXi mesa-dri-drivers \\\n"
        "        mesa-utils libwayland-client libwayland-cursor libwayland-egl \\\n"
        "        libxkbcommon\n"
        "\n"
        "  Arch:\n"
        "      sudo pacman -S mesa libglu libx11 libxext libxrandr libxinerama \\\n"
        "        libxcursor libxi mesa-utils wayland libxkbcommon\n"
        "\n"
        "Mesa (llvmpipe) provides the software fallback, so these also run on a\n"
        "  machine with no GPU. Headless, run them under an X server: xvfb-run -a\n"
        "  ./tutorial01_first_window\n"
        "\n"
        "The GLU library, the X11 client libraries and the Wayland/xkbcommon\n"
        "  packages are needed because the tutorials link -lGLU and GLFW builds\n"
        "  its X11 and Wayland backends by default; an X11 session (or XWayland)\n"
        "  satisfies the Wayland ones."
    ),
}

README_TEMPLATE = """ogl-gdm tutorials - {plat} build
Commit {sha}{config}

Each directory holds one or more tutorial executables together with the assets
they load at runtime. Run them from inside their directory, e.g.:

    cd tutorial01_first_window
    ./tutorial01_first_window{exe_note}

Every third-party library the tutorials use (GLFW, GLEW, GLM, Assimp,
AntTweakBar, Bullet) is linked in, or shipped in the lib/ directory next to
these folders. You never install those by hand; only what your system does not
already provide is described below. The executables are stripped: debug
information is not included, so rebuild locally if you need line-accurate
tracebacks.

To run them in sequence, run the smoke test script in this directory. Each
tutorial runs one at a time and waits until you close its window (Esc), then
moves on to the next one, with the executable's output inline - which is how you
read the probe's report below. The script waits for Enter at the end, so the
output does not disappear with the window:

    macOS / Linux:  ./smoke-test.sh
    Windows:        .\\smoke-test.ps1

Every executable runs, all of them, including the two or three that share a
source folder (misc05_picking alone covers picking by three different
techniques). Output appears in the console in both modes. If nobody is watching,
the timed mode runs each for a few seconds and then kills it, only reporting
whether it started at all:

    macOS / Linux:  ./smoke-test.sh --timed 5
    Windows:        .\\smoke-test.ps1 -Timed 5

{probe}Requirements on the machine that runs these:
{requirements}
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


def probe_targets(repo_root: Path, cache: dict):
    """[(target, source dir), ...] of gdm's examples, when they were built.

    Parsed from the fetched gdm sources instead of hardcoded, so an upstream gdm
    that gains an example brings it along by itself. Empty and silent when
    GDM_BUILD_EXAMPLES is OFF - the default here, since GDM is a dependency.
    """
    if cache.get("GDM_BUILD_EXAMPLES", "OFF").upper() != "ON":
        return []
    examples_cmake = repo_root / EXAMPLES_DIR / "CMakeLists.txt"
    if not examples_cmake.is_file():
        raise SystemExit(f"error: GDM_BUILD_EXAMPLES=ON, but {EXAMPLES_DIR} is "
                         "missing; the gdm sources were not fetched")
    parsed = parse_targets(examples_cmake, repo_root / EXAMPLES_DIR)
    if not parsed:
        raise SystemExit(f"error: GDM_BUILD_EXAMPLES=ON, but no add_executable() "
                         f"in {EXAMPLES_DIR}/CMakeLists.txt")
    return parsed


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


def find_executable(name, source_dir, build_dir, config, repo_root=None):
    """Where the build put the exe: source dir (POST_BUILD copy / Xcode), build
    dir, or multi-config subdir. Targets declared in a subdirectory of the source
    tree keep that layout under build/ too - gdm's examples land in
    build/external/gdm/examples/ - so those paths are probed before the bounded
    search of the build tree, which covers generators we did not anticipate."""
    exe = name + exe_suffix()
    candidates = [source_dir / exe, build_dir / exe]
    if config:
        candidates.insert(1, build_dir / config / exe)
    if repo_root is not None:
        try:
            source_rel = source_dir.resolve().relative_to(repo_root)
        except ValueError:
            source_rel = None
        if source_rel:
            sub = build_dir / source_rel
            candidates += [sub / exe, sub / config / exe if config else None]
            candidates = [c for c in candidates if c is not None]
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


EXECUTABLE_MAGICS = (b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe",  # Mach-O
                     b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",  # universal
                     b"\xfe\xed\xfa\xcf", b"\xfe\xed\xfa\xce")  # Mach-O, other endian


def is_executable_file(path: Path) -> bool:
    """Mach-O / ELF / PE, so the artifact's permissions can be normalized by
    content instead of by name."""
    try:
        with open(path, "rb") as handle:
            head = handle.read(4)
    except OSError:
        return False
    return (head.startswith(b"MZ") or head.startswith(b"\x7fELF")
            or head in EXECUTABLE_MAGICS)


WINDOWS_FORBIDDEN_CHARS = '<>:"|?*'
WINDOWS_RESERVED_STEMS = ({"CON", "PRN", "AUX", "NUL"}
                          | {f"COM{i}" for i in range(1, 10)}
                          | {f"LPT{i}" for i in range(1, 10)})
PLATFORM_MAGIC = {
    "windows": (b"MZ",),                                # PE
    "macos": tuple(EXECUTABLE_MAGICS),                  # Mach-O / universal
    "linux": (b"\x7fELF",),
}


def validate_payload(stage_root: Path, plat: str):
    """Refuse to ship something the target OS cannot use.

    A directory that Explorer or `dir` reports as corrupted, or an executable
    that fails with 0x0000007B (ERROR_INVALID_NAME), is a payload problem long
    before it is a code problem, so catch the two ways it can happen: an entry
    name the file system rejects, and a staged executable that is not one.
    """
    problems = []
    magic_ok = PLATFORM_MAGIC.get(plat, (b"MZ", b"\x7fELF") + EXECUTABLE_MAGICS)
    for path in sorted(stage_root.rglob("*")):
        name = path.name
        rel = path.relative_to(stage_root)
        if plat == "windows":
            forbidden = [c for c in name if c in WINDOWS_FORBIDDEN_CHARS
                         or ord(c) < 32]
            if forbidden:
                problems.append(f"{rel}: name contains {forbidden!r}")
            if name.rstrip() != name or name.rstrip(".") != name:
                problems.append(f"{rel}: trailing space or dot")
            stem = name.split(".")[0].upper()
            if stem in WINDOWS_RESERVED_STEMS:
                problems.append(f"{rel}: '{stem}' is a reserved device name")
            if len(str(rel)) > 200:
                problems.append(f"{rel}: relative path is {len(str(rel))} chars")
        if not path.is_file():
            continue
        with open(path, "rb") as handle:
            head = handle.read(4)
        if is_executable_file(path) and not any(head.startswith(m)
                                                for m in magic_ok):
            problems.append(f"{rel}: not a {plat} executable "
                            f"(magic {head.hex()})")
        if name.lower().endswith(".exe") and plat == "windows" \
                and not head.startswith(b"MZ"):
            problems.append(f"{rel}: .exe that is not a PE image")
    return problems


MACHO_ARCHS = {0x00000007: "x86", 0x01000007: "x86_64",
               0x0000000C: "arm", 0x0100000C: "arm64"}


def describe_binary(path: Path) -> str:
    """'Mach-O arm64 (3.6 MB)', 'PE (2.1 MB)', ... - what the payload holds,
    so a reviewer on another machine can tell without running anything."""
    with open(path, "rb") as handle:
        head = handle.read(8)
    size = human_size(path.stat().st_size)
    if head.startswith(b"MZ"):
        return f"PE ({size})"
    if head.startswith(b"\x7fELF"):
        return f"ELF ({size})"
    if head[:4] in EXECUTABLE_MAGICS:
        cputype = int.from_bytes(head[4:8], "little")
        return f"Mach-O {MACHO_ARCHS.get(cputype, 'arch 0x%x' % cputype)} ({size})"
    return f"unknown format ({size})"


def strip_debug_info(path: Path):
    """Drop debug/symbol information from a staged executable.

    RelWithDebInfo embeds the debug info of the tutorial *and* of every
    statically linked library (GLEW, cpptrace/libdwarf, GLFW, Assimp, Bullet)
    into each of the 26 executables - tens of megabytes repeated. GCC/Clang put
    it in the binary itself, MSVC moves it to a sidecar .pdb, which is why a
    Linux artifact dwarfs a Windows one. Only the staged copies are touched;
    the build tree keeps its symbols for anyone who needs a traceback.
    """
    if os.name == "nt":
        return  # MSVC keeps debug info in the .pdb; there is nothing to strip
    command = (["strip", "-S", "-x"] if platform.system() == "Darwin"
               else ["strip", "--strip-unneeded", str(path)])
    try:
        subprocess.run(command + [str(path)], check=True, capture_output=True)
    except (OSError, subprocess.SubprocessError) as error:
        print(f"warning: could not strip {path}: {error}", file=sys.stderr)
        return
    if platform.system() == "Darwin":
        # stripping rewrites the binary, so re-sign it ad-hoc
        subprocess.run(["codesign", "--force", "--sign", "-", str(path)],
                       check=True, capture_output=True)


def relax_permissions(path: Path, executable: bool = False):
    """A downloaded artifact must be usable without escalating privileges.

    copy2 preserves the source mode, and the sources we bundle can be read-only
    (Homebrew's dylibs are mode 444). Removing the quarantine marker macOS puts
    on a download - `xattr -d com.apple.quarantine` - needs write access to the
    file, so a read-only bundled library makes the one-command remedy fail.
    """
    mode = 0o755 if executable else 0o644
    try:
        if path.stat().st_mode & 0o777 != mode:
            path.chmod(mode)
    except OSError:
        pass  # best effort; some filesystems forbid chmod (e.g. mounted volumes)


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
            relax_permissions(target_root / filename)


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


LIB_DIR_NAME = "lib"
# The payload keeps its libraries one level above each tutorial directory, and
# both depths are searched so it makes no difference where an exe sits.
EXE_RPATH = {"Darwin": ["@executable_path/lib", "@executable_path/../lib"],
             "Linux": ["$ORIGIN/lib", "$ORIGIN/../lib"]}
LIB_RPATH = {"Darwin": ["@loader_path/"], "Linux": ["$ORIGIN"]}


def patch(binary, arguments):
    """Run a Mach-O/ELF patching tool, then re-sign on Darwin: any
    install_name_tool change invalidates the (ad-hoc) signature, and macOS then
    refuses to exec the file at all - SIGKILL, no diagnostic."""
    subprocess.run(arguments, check=True, capture_output=True)
    if platform.system() == "Darwin":
        subprocess.run(["codesign", "--force", "--sign", "-", str(binary)],
                       check=True, capture_output=True)


def rpath_entries(binary):
    if platform.system() != "Darwin":
        return []
    listing = subprocess.run(["otool", "-l", str(binary)],
                             capture_output=True, text=True).stdout
    return [m.group(1) for m in re.finditer(r"^\s*path (.+) \(offset", listing, re.M)]


def ensure_rpath(binary, rpaths):
    """Let `binary` find the payload's lib/ directory, and nothing else.

    The build tree can rpath in the machine's own library directories - CMake
    adds $(brew --prefix)/lib on a Homebrew machine, and dyld honours rpaths in
    order, so an inherited entry would resolve our @rpath names to the build
    machine's copies instead of the shipped ones. Every other entry is therefore
    deleted; on Linux patchelf's --set-rpath replaces the whole list anyway.
    """
    rpaths = list(rpaths)
    if platform.system() == "Darwin":
        foreign = [r for r in rpath_entries(binary) if r not in rpaths]
        for rpath in foreign:
            try:
                patch(binary, ["install_name_tool", "-delete_rpath", rpath,
                               str(binary)])
            except subprocess.CalledProcessError:
                pass  # duplicate entry: already gone
        for rpath in rpaths:
            if rpath not in rpath_entries(binary):
                patch(binary, ["install_name_tool", "-add_rpath", rpath,
                               str(binary)])
    else:
        if not shutil.which("patchelf"):
            raise SystemExit(
                f"error: '{binary}' needs non-system libraries from {LIB_DIR_NAME}/; "
                "bundling them requires patchelf (apt-get install patchelf) to set "
                "an $ORIGIN rpath")
        patch(binary, ["patchelf", "--set-rpath", ":".join(rpaths), str(binary)])


def repoint(binary, dep, name):
    """Make `binary` load the bundled copy `name` through the rpath."""
    if platform.system() == "Darwin":
        patch(binary, ["install_name_tool", "-change", dep,
                       f"@rpath/{name}", str(binary)])
    # Linux: DT_NEEDED already holds the soname, so the rpath alone is enough.


def bundle_libs(binary, lib_dir):
    """Copy every non-system library `binary` needs into the payload's single
    lib/ directory (recursively), and repoint the staged copies at it. Nothing
    outside the OS is shipped more than once; only the staged files are patched,
    never the build outputs. Returns [bundled library names]."""
    binary = Path(binary)
    bundled, queue, seen = {}, [binary], set()
    while queue:
        current = queue.pop()
        for dep in dynamic_dependencies(current):
            if dep in seen or is_system_lib(dep):
                continue
            seen.add(dep)
            name = Path(dep).name
            target = lib_dir / name
            if not target.exists():
                lib_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dep, target)
                relax_permissions(target)
                queue.append(target)
                if platform.system() == "Darwin":
                    patch(target, ["install_name_tool", "-id",
                                   f"@rpath/{name}", str(target)])
                ensure_rpath(target, LIB_RPATH[platform.system()])
            bundled[dep] = name
            repoint(current, dep, name)
        if current == binary and bundled:
            ensure_rpath(binary, EXE_RPATH[platform.system()])
    # install_name_tool rewrites its input through a temporary file, which drops
    # the executable bit; a payload full of "permission denied" is not a useful
    # artifact, so re-normalize after every patch.
    relax_permissions(binary, executable=True)
    for staged_lib in sorted(lib_dir.glob("*")):
        if staged_lib.is_file():
            relax_permissions(staged_lib)
    return sorted(set(bundled.values()))


def stage_target(name, source_dir, exe_path, build_dir, config, stage_root,
                 repo_root, extra_dlls, lib_dir, exe_names, dest_dir=None):
    """dest_dir: stage the exe directly there, with no sources copied - for
    gdm's examples, whose directory holds one .cpp and no runtime assets."""
    try:
        rel = source_dir.resolve().relative_to(repo_root)
    except ValueError:
        rel = Path(source_dir.name)
    dest = dest_dir if dest_dir is not None else stage_root / rel
    dest.mkdir(parents=True, exist_ok=True)
    if dest_dir is None and source_dir.name not in BARE_DIRS:
        # exe_names: every target's file name, so a shared source directory
        # (three exes live in tutorial09_vbo_indexing/, misc05_picking/, ...)
        # never re-stages a sibling that an earlier target already patched -
        # re-copying it would undo its permission normalization.
        copy_sources(source_dir, dest, exe_names)
    shutil.copy2(exe_path, dest / exe_path.name)
    relax_permissions(dest / exe_path.name, executable=True)
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
        # Windows has no rpath: the loader searches the executable's directory
        # only, so DLLs must sit next to each exe. (gdm builds static there, so
        # this list is normally empty.)
        for dll in extra_dlls:
            target = dest / dll.name
            if not target.exists():
                shutil.copy2(dll, target)
                relax_permissions(target)
    # gdm prefers an already-installed package when one exists, so a developer
    # machine (Homebrew, ...) links shared libraries a clean machine builds
    # statically. Bundle whatever is non-system either way - once, in lib/.
    bundled = bundle_libs(dest / exe_path.name, lib_dir)
    return dest / exe_path.name, bundled


def write_manifest(stage_root: Path, records, plat, sha, config):
    """records: (target, build exe, staged exe, path to display, size, bundled)."""
    lines = [
        f"ogl-gdm {plat} build - commit {sha}"
        + (f" - configuration {config}" if config else ""),
        f"targets: {len(records)}",
        "",
    ]
    lib_names = sorted({lib for _, _, _, _, _, libs in records for lib in libs})
    if lib_names:
        lines.append(f"libraries: {LIB_DIR_NAME}/ (shared by every executable)")
        lines.append("")

    # Column widths are taken from the content, never hardcoded. The path is the
    # only unbounded column (tutorial06_keyboard_and_mouse/... is 67 chars), so
    # it goes last: a fixed-width path column would push the size right out of
    # alignment, while trailing overflow costs nothing.
    name_width = max([len("target")] + [len(r[0]) for r in records])
    size_width = max([len("size")] + [len(r[4]) for r in records])
    indent = " " * (name_width + size_width + 3)
    header = f"{'target':<{name_width}} {'size':>{size_width}}  path"
    lines.append(header)
    lines.append("-" * len(header))
    for name, _exe, staged, display, size, bundled in records:
        lines.append(f"{name:<{name_width}} {size:>{size_width}}  {display}")
        lines.append(f"{indent}{describe_binary(staged)}")
        if bundled:
            lines.append(f"{indent}loads from lib/: "
                        + ", ".join(sorted(set(bundled))))
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


def stage_smoke_tests(stage_root: Path, plat: str):
    """Ship the bulk smoke test scripts inside the artifact, so whoever gets it
    can run every tutorial at once instead of one by one. Only this platform's
    script is copied - the others would be dead weight."""
    for script in sorted(SCRIPT_DIR.glob("smoke-test.*")):
        if plat == "windows" and script.suffix != ".ps1":
            continue
        if plat != "windows" and script.suffix != ".sh":
            continue
        shutil.copy2(script, stage_root / script.name)
        relax_permissions(stage_root / script.name,
                          executable=script.suffix == ".sh")


PROBE_PARAGRAPH = """Not a tutorial: the probe in this directory prints this machine's OpenGL
environment - GL version, vendor, renderer, capability limits, GPU memory and
supported extensions - then draws a triangle until you close its window. Run it
when you report a problem and attach the output: it tells which environment
produced the error.

    macOS / Linux:  ./{exe}
    Windows:        {exe}.exe

"""


def write_readme(stage_root: Path, plat, sha, config, probe_names=()):
    probe = PROBE_PARAGRAPH.format(exe=probe_names[0]) if probe_names else ""
    note = ".exe (Windows)" if plat == "windows" else ""
    (stage_root / "README.txt").write_text(README_TEMPLATE.format(
        plat=plat, sha=sha, config=f" - configuration {config}" if config else "",
        requirements=REQUIREMENTS[plat],
        exe_note=note,
        probe=probe,
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
    parser.add_argument("--payload-dir", type=Path, default=None,
                        help="also leave the unpacked payload in this directory "
                             "(for upload-artifact, which zips it once); if it "
                             "exists it is replaced")
    parser.add_argument("--no-strip", dest="strip", action="store_false",
                        default=True,
                        help="keep debug information in the executables "
                             "(default: strip it, which cuts the artifact "
                             "substantially; the build tree keeps its symbols)")
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
    probes = probe_targets(repo_root, cache)
    targets += probes

    if not targets:
        print(f"error: no executables declared in {repo_root / 'CMakeLists.txt'}",
              file=sys.stderr)
        return 1

    # --- verify: the "configure and build succeeded" proof -------------------
    print(f"ogl-gdm {plat} build{(' - ' + config) if config else ''} "
          f"(commit {sha}, {build_dir})")
    found, missing = [], []
    for name, source_dir in targets:
        exe = find_executable(name, source_dir, build_dir, config, repo_root)
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
    keep_staging = args.payload_dir is not None
    stage_root = args.payload_dir
    if keep_staging:
        if stage_root.exists() and not stage_root.is_dir():
            print(f"error: --payload-dir {stage_root} is not a directory",
                  file=sys.stderr)
            return 1
        if stage_root.resolve() == repo_root or stage_root == Path(stage_root.anchor):
            print(f"error: refusing to use --payload-dir {stage_root}",
                  file=sys.stderr)
            return 1
        if stage_root.exists():
            shutil.rmtree(stage_root)
    else:
        stage_root = Path(tempfile.mkdtemp(prefix=f"ogl-gdm-{plat}-"))
    try:
        records, dlls = [], collect_dlls(build_dir, config)
        exe_names = {name + exe_suffix() for name, _ in targets}
        lib_dir = stage_root / LIB_DIR_NAME
        bundled_total = 0
        examples_bin_dir = (repo_root / EXAMPLES_DIR).resolve()
        for name, source_dir, exe in found:
            # gdm's examples go to the payload root, next to the README that
            # explains them, with no source files copied.
            dest_dir = stage_root if source_dir.resolve() == examples_bin_dir else None
            staged, bundled = stage_target(name, source_dir, exe, build_dir,
                                          config, stage_root, repo_root, dlls,
                                          lib_dir, exe_names, dest_dir=dest_dir)
            bundled_total += len(bundled)
            try:
                rel = exe.resolve().relative_to(repo_root)
            except ValueError:
                rel = Path(exe.name)
            if dest_dir is not None:
                # the MANIFEST's path column is payload-relative, and a probe
                # is staged by hand, not where its sources live
                rel = staged.relative_to(stage_root)
            records.append((name, exe, staged, rel, human_size(exe.stat().st_size),
                            bundled))
        write_manifest(stage_root, records, plat, sha, config)
        write_readme(stage_root, plat, sha, config, [n for n, _ in probes])
        stage_smoke_tests(stage_root, plat)

        # Final pass by content, not by name: every executable in the payload
        # (including ones an earlier target already patched and a later sibling
        # may have re-staged with a temporary mode) ends up runnable, and
        # everything else stays writable.
        for path in sorted(stage_root.rglob("*")):
            if not path.is_file():
                continue
            if args.strip and is_executable_file(path):
                strip_debug_info(path)
            # never take an execute bit away: the smoke-test script is a shell
            # script, not a binary, but it must still be runnable as ./smoke-test.sh
            relax_permissions(path,
                              executable=is_executable_file(path)
                              or os.access(path, os.X_OK))

        if bundled_total:
            names = sorted({lib for _, _, _, _, _, libs in records for lib in libs})
            print(f"\n{len(names)} non-system librar(ies) bundled once in "
                  f"{LIB_DIR_NAME}/ ({bundled_total} references): "
                  + ", ".join(names))
            if plat == "macos":
                print("         a downloaded copy asks Gatekeeper approval for each of\n"
                      "         these files once; `xattr -dr com.apple.quarantine .`\n"
                      "         in the payload root clears them all at once.",
                      file=sys.stderr)

        out_dir.mkdir(parents=True, exist_ok=True)
        zip_path = out_dir / f"ogl-gdm-{plat}-{sha}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(stage_root.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(stage_root))
        # a truncated or CRC-broken entry is what Explorer reports as a
        # "corrupted" directory, so prove the archive before handing it over
        with zipfile.ZipFile(zip_path) as zf:
            corrupt = zf.testzip()
        if corrupt:
            print(f"error: archive entry is corrupt: {corrupt}", file=sys.stderr)
            return 1

        problems = validate_payload(stage_root, plat)
        if problems:
            print("error: the payload is not usable on this platform:",
                  file=sys.stderr)
            for problem in problems:
                print(f"  {problem}", file=sys.stderr)
            return 1

        print(f"\npackaged {len(found)} executables, "
              f"{bundled_total} non-system librar(ies), {len(dlls)} dll(s) "
              f"-> {zip_path} ({human_size(zip_path.stat().st_size)})")
        if keep_staging:
            print(f"payload tree kept at {stage_root}")
    finally:
        if not keep_staging:
            shutil.rmtree(stage_root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
