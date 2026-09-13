"""Shared local work-folder browsing and file operations."""
import shutil
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, simpledialog, messagebox
from .settings import WINDOWS

def resolve_shared_work(mounts):
    """Locate the actual host bind mount; never guess which folder is shared."""
    mount = next((item for item in mounts if item.get("Destination") == "/home/max/work"), None)
    if not mount or mount.get("Type") != "bind":
        raise RuntimeError("This container needs a shared host folder mounted at /home/max/work.")
    source = mount["Source"]
    if WINDOWS:
        for prefix in ("/run/desktop/mnt/host/", "/host_mnt/", "/mnt/host/"):
            if source.startswith(prefix):
                rest = source[len(prefix):]
                if len(rest) > 2 and rest[1] == "/":
                    source = rest[0].upper() + ":/" + rest[2:]
                break
    path = Path(source).resolve()
    if not path.is_dir():
        raise RuntimeError(f"The shared folder is not accessible from this computer:\n{path}")
    return path, bool(mount.get("RW", False))


class LocalFilesWindow(tk.Toplevel):
    def __init__(self, parent, root, writable):
        super().__init__(parent)
        self.title("Local Quantum Mobile Files")
        self.geometry("820x520")
        self.root_folder = root.resolve()
        self.folder = self.root_folder
        self.writable = writable
        self.entries = {}
        panel = ttk.Frame(self, padding=12)
        panel.pack(fill="both", expand=True)
        self.location = tk.StringVar()
        ttk.Label(panel, textvariable=self.location, wraplength=770).pack(anchor="w")
        ttk.Label(panel, text="These are shared files: changes also affect your Windows/Mac work folder.").pack(anchor="w", pady=6)
        row = ttk.Frame(panel)
        row.pack(fill="x", pady=8)
        for label, command in [("Up", self.up), ("Refresh", self.refresh), ("Open Folder", self.enter),
                               ("Import Files", self.import_files), ("New Folder", self.new_folder),
                               ("Rename", self.rename), ("Delete", self.delete)]:
            button = ttk.Button(row, text=label, command=lambda fn=command: self.guarded(fn))
            button.pack(side="left", padx=2)
            if not writable and label in ("Import Files", "New Folder", "Rename", "Delete"):
                button.configure(state="disabled")
        self.tree = ttk.Treeview(panel, columns=("kind", "size"), selectmode="browse")
        self.tree.heading("#0", text="Name")
        self.tree.heading("kind", text="Type")
        self.tree.heading("size", text="Bytes")
        self.tree.column("#0", width=440)
        self.tree.column("kind", width=90)
        self.tree.column("size", width=100)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda event: self.guarded(self.enter))
        self.notice = tk.StringVar(value="Double-click a folder to open it. Files can be imported from your computer.")
        ttk.Label(panel, textvariable=self.notice, wraplength=770).pack(anchor="w", pady=8)
        self.guarded(self.refresh)

    def guarded(self, action):
        try:
            action()
        except Exception as error:
            messagebox.showerror("Local files", str(error), parent=self)

    def checked(self, path):
        resolved = path.resolve()
        try:
            resolved.relative_to(self.root_folder)
        except ValueError:
            raise RuntimeError("This item points outside the shared work folder.") from None
        return resolved

    def selected(self):
        selection = self.tree.selection()
        if not selection:
            raise RuntimeError("Select a file or folder first.")
        item = self.entries[selection[0]]
        if item.is_symlink():
            raise RuntimeError("Symbolic links cannot be opened or changed in this file manager.")
        self.checked(item)
        return item

    def refresh(self):
        self.checked(self.folder)
        self.tree.delete(*self.tree.get_children())
        self.entries.clear()
        relative = self.folder.relative_to(self.root_folder)
        self.location.set(f"Container: /home/max/work/{relative.as_posix()}\nComputer: {self.folder}")
        for item in sorted(self.folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            link = item.is_symlink()
            kind = "Link" if link else "Folder" if item.is_dir() else "File"
            size = "" if link or item.is_dir() else str(item.stat().st_size)
            key = self.tree.insert("", "end", text=item.name, values=(kind, size))
            self.entries[key] = item

    def enter(self):
        path = self.selected()
        if not path.is_dir():
            self.notice.set("This is a file. Select a folder to navigate, or use Rename/Delete.")
            return
        self.folder = path
        self.refresh()

    def up(self):
        if self.folder != self.root_folder:
            self.folder = self.checked(self.folder.parent)
        self.refresh()

    def name_prompt(self, title, initial=""):
        name = simpledialog.askstring(title, "Name (without folder separators):", initialvalue=initial, parent=self)
        if name is None:
            return None
        name = name.strip()
        if not name or name in (".", "..") or any(c in name for c in '/\\:\x00\r\n'):
            raise RuntimeError("Enter a single valid file or folder name.")
        target = self.folder / name
        self.checked(target)
        if target.exists() or target.is_symlink():
            raise RuntimeError("An item with that name already exists.")
        return target

    def new_folder(self):
        if not self.writable:
            return
        target = self.name_prompt("New folder")
        if target:
            target.mkdir()
            self.refresh()
            self.notice.set("Folder created.")

    def import_files(self):
        if not self.writable:
            return
        sources = filedialog.askopenfilenames(title="Import into the shared work folder", parent=self)
        count = 0
        for source in sources:
            destination = self.folder / Path(source).name
            self.checked(destination)
            # Exclusive creation prevents accidental replacement of existing work.
            with open(source, "rb") as reader, open(destination, "xb") as writer:
                shutil.copyfileobj(reader, writer)
            count += 1
            self.refresh()
            self.notice.set(f"Imported {count} file(s). Existing files are never overwritten.")

    def rename(self):
        if not self.writable:
            return
        source = self.selected()
        target = self.name_prompt("Rename", source.name)
        if target:
            source.rename(target)
            self.refresh()
            self.notice.set("Item renamed.")

    def delete(self):
        if not self.writable:
            return
        target = self.selected()
        if target.is_dir() and any(target.iterdir()):
            raise RuntimeError("This folder is not empty. Delete its files individually first.")
        if messagebox.askyesno("Delete permanently?", f"Delete {target.name}?\n\nThis also removes it from the shared computer folder. It will not go to the Recycle Bin.", parent=self):
            self.checked(target)
            target.rmdir() if target.is_dir() else target.unlink()
            self.refresh()
            self.notice.set("Item deleted.")


