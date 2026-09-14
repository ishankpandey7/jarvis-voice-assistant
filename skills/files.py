"""
Finding files and tidying folders.
"""
import shutil
import time
from datetime import datetime
from pathlib import Path

from .winutil import KNOWN_FOLDERS, home, open_path

# Which file types go into which folder.
CATEGORIES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".heic", ".ico"},
    "Videos": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".flv"},
    "Music": {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".xls", ".xlsx", ".ppt",
                  ".pptx", ".csv", ".odt", ".md", ".rtf"},
    "Installers": {".exe", ".msi", ".apk"},
    "Zips": {".zip", ".rar", ".7z", ".tar", ".gz", ".iso"},
    "Code": {".py", ".js", ".ts", ".html", ".css", ".json", ".java", ".c",
             ".cpp", ".sh", ".ps1"},
}

# Searching these is a waste of time.
SKIP_DIRS = {
    "node_modules", "AppData", ".git", "__pycache__", "venv", ".venv",
    "Windows", "Program Files", "Program Files (x86)", "$Recycle.Bin",
    "OneDriveTemp", ".cache", "site-packages",
}

# Where to look.
SEARCH_ROOTS = ["desktop", "downloads", "documents", "pictures", "videos", "music"]


def _category_of(suffix: str) -> str:
    for name, extensions in CATEGORIES.items():
        if suffix.lower() in extensions:
            return name
    return "Other"


def _humansize(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} GB"


def search(query: str, limit: int = 8, seconds: float = 12.0) -> dict:
    """Find a file by name. Time limited so Jarvis never hangs."""
    needle = query.lower().strip()
    if len(needle) < 2:
        return {"speak": "Give me a longer part of the file name.", "results": []}

    deadline = time.time() + seconds
    hits = []

    for key in SEARCH_ROOTS:
        root = KNOWN_FOLDERS[key]
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if time.time() > deadline:
                break
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if not path.is_file():
                continue
            if needle in path.name.lower():
                try:
                    stat = path.stat()
                except OSError:
                    continue
                hits.append({
                    "name": path.name,
                    "path": str(path),
                    "folder": str(path.parent),
                    "size": _humansize(stat.st_size),
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%d %b %Y"),
                    "_mtime": stat.st_mtime,
                })
        if time.time() > deadline:
            break

    hits.sort(key=lambda item: item["_mtime"], reverse=True)   # newest first
    hits = hits[:limit]
    for item in hits:
        item.pop("_mtime", None)

    if not hits:
        return {"speak": f"I found no file called '{query}'.", "results": []}
    if len(hits) == 1:
        return {"speak": f"Found it: {hits[0]['name']}, in {hits[0]['folder']}.",
                "results": hits}
    return {"speak": f"Found {len(hits)} files. Click one in the list to open it.",
            "results": hits}


# For "where are my PDFs" -- a type was named, not a file name.
TYPE_WORDS = {
    "pdf": {".pdf"},
    "photo": CATEGORIES["Images"], "photos": CATEGORIES["Images"],
    "image": CATEGORIES["Images"], "images": CATEGORIES["Images"],
    "video": CATEGORIES["Videos"], "videos": CATEGORIES["Videos"],
    "song": CATEGORIES["Music"], "songs": CATEGORIES["Music"],
    "music": CATEGORIES["Music"],
    "excel": {".xls", ".xlsx", ".csv"},
    "word": {".doc", ".docx"},
    "ppt": {".ppt", ".pptx"}, "presentation": {".ppt", ".pptx"},
    "zip": CATEGORIES["Zips"],
}


def search_by_type(word: str, limit: int = 10) -> dict:
    """The newest files of one type -- all the PDFs, for example."""
    wanted = TYPE_WORDS.get(word.lower().strip())
    if not wanted:
        return {"speak": f"I do not know the file type '{word}'.", "results": []}

    found = []
    deadline = time.time() + 12
    for key in SEARCH_ROOTS:
        root = KNOWN_FOLDERS[key]
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if time.time() > deadline:
                break
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.suffix.lower() in wanted and path.is_file():
                try:
                    stat = path.stat()
                except OSError:
                    continue
                found.append((stat.st_mtime, path, stat.st_size))

    found.sort(reverse=True, key=lambda row: row[0])
    results = [{"name": p.name, "path": str(p), "folder": str(p.parent),
                "size": _humansize(s),
                "modified": datetime.fromtimestamp(m).strftime("%d %b %Y")}
               for m, p, s in found[:limit]]

    if not results:
        return {"speak": f"I found no {word} files.", "results": []}
    return {"speak": f"The {len(results)} newest {word} files:", "results": results}


def open_file(path: str) -> str:
    target = Path(path)
    if not target.exists():
        return "That file is not there any more."
    ok, err = open_path(str(target))
    return f"Opening {target.name}." if ok else f"Could not open it: {err}"


def organize(folder_name: str = "downloads", do_it: bool = False) -> dict:
    """
    Sort a folder's files into sub-folders by type.
    With do_it=False it only describes the plan -- nothing is moved.
    """
    folder = KNOWN_FOLDERS.get(folder_name.lower(), home() / folder_name)
    if not folder.exists():
        return {"speak": f"There is no folder called {folder_name}.", "plan": []}

    plan = {}
    for item in folder.iterdir():
        if item.is_dir() or item.name.startswith("."):
            continue
        if item.name.lower().endswith((".lnk", ".tmp", ".crdownload", ".part")):
            continue
        plan.setdefault(_category_of(item.suffix), []).append(item)

    if not plan:
        return {"speak": f"{folder.name} is already tidy. Nothing worth moving.",
                "plan": []}

    summary = [{"category": name, "count": len(items),
                "examples": [f.name for f in items[:3]]}
               for name, items in sorted(plan.items())]
    total = sum(len(items) for items in plan.values())

    if not do_it:
        parts = ", ".join(f"{row['count']} {row['category']}" for row in summary)
        return {
            "speak": f"{folder.name} has {total} files: {parts}. "
                     f"Shall I sort them into folders? Say yes.",
            "plan": summary,
            "needs_confirm": True,
            "confirm_action": {"skill": "files.organize", "folder": folder_name},
        }

    moved, failed = 0, 0
    for name, items in plan.items():
        target_dir = folder / name
        target_dir.mkdir(exist_ok=True)
        for item in items:
            target = target_dir / item.name
            counter = 1
            while target.exists():                  # same name, so add a number
                target = target_dir / f"{item.stem} ({counter}){item.suffix}"
                counter += 1
            try:
                shutil.move(str(item), str(target))
                moved += 1
            except OSError:
                failed += 1

    note = f" I skipped {failed} files that were in use." if failed else ""
    return {"speak": f"Sorted {moved} files.{note} The folder is tidy now.",
            "plan": summary}


def recent_files(count: int = 8) -> dict:
    """Files touched recently."""
    items = []
    cutoff = time.time() - 3 * 24 * 3600            # the last 3 days
    for key in SEARCH_ROOTS:
        root = KNOWN_FOLDERS[key]
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if any(part in SKIP_DIRS for part in path.parts) or not path.is_file():
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime > cutoff:
                items.append((mtime, path))

    items.sort(reverse=True)
    results = [{"name": p.name, "path": str(p), "folder": str(p.parent),
                "modified": datetime.fromtimestamp(m).strftime("%d %b, %I:%M %p")}
               for m, p in items[:count]]
    if not results:
        return {"speak": "Nothing new in the last 3 days.", "results": []}
    return {"speak": f"{len(results)} files from the last 3 days:", "results": results}


def big_files(count: int = 8) -> dict:
    """The biggest files -- useful when you need disk space back."""
    items = []
    for key in SEARCH_ROOTS:
        root = KNOWN_FOLDERS[key]
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if any(part in SKIP_DIRS for part in path.parts) or not path.is_file():
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > 50 * 1024 * 1024:             # bigger than 50 MB
                items.append((size, path))

    items.sort(reverse=True)
    results = [{"name": p.name, "path": str(p), "folder": str(p.parent),
                "size": _humansize(s)} for s, p in items[:count]]
    if not results:
        return {"speak": "No large files found. You are fine on space.", "results": []}
    total = _humansize(sum(s for s, _ in items[:count]))
    return {"speak": f"Your {len(results)} biggest files, {total} in total:",
            "results": results}
