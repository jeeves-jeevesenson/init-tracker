from __future__ import annotations

import sys
from importlib import import_module
from types import ModuleType
from typing import Any, Tuple


class _DummyTkWidget:
    def __init__(self, *args: Any, value: Any = None, **kwargs: Any) -> None:
        self._value = value
        self._items = []

    def __call__(self, *args: Any, **kwargs: Any) -> "_DummyTkWidget":
        return self

    def pack(self, *args: Any, **kwargs: Any) -> None:
        return None

    def grid(self, *args: Any, **kwargs: Any) -> None:
        return None

    def place(self, *args: Any, **kwargs: Any) -> None:
        return None

    def config(self, *args: Any, **kwargs: Any) -> None:
        return None

    configure = config

    def bind(self, *args: Any, **kwargs: Any) -> None:
        return None

    def destroy(self) -> None:
        return None

    def withdraw(self) -> None:
        return None

    def deiconify(self) -> None:
        return None

    def protocol(self, *args: Any, **kwargs: Any) -> None:
        return None

    def transient(self, *args: Any, **kwargs: Any) -> None:
        return None

    def grab_set(self) -> None:
        return None

    def wait_window(self, *args: Any, **kwargs: Any) -> None:
        return None

    def after(self, *args: Any, **kwargs: Any) -> None:
        return None

    def see(self, *args: Any, **kwargs: Any) -> None:
        return None

    def insert(self, *args: Any, **kwargs: Any) -> str:
        self._items.append((args, kwargs))
        return ""

    def delete(self, *args: Any, **kwargs: Any) -> None:
        return None

    def set(self, value: Any = None, *args: Any, **kwargs: Any) -> None:
        self._value = value

    def get(self, *args: Any, **kwargs: Any) -> Any:
        return self._value

    def cget(self, *args: Any, **kwargs: Any) -> str:
        return ""

    def yview(self, *args: Any, **kwargs: Any) -> None:
        return None

    def xview(self, *args: Any, **kwargs: Any) -> None:
        return None

    def create_window(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def create_image(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def itemconfigure(self, *args: Any, **kwargs: Any) -> None:
        return None

    itemconfig = itemconfigure

    def heading(self, *args: Any, **kwargs: Any) -> None:
        return None

    def column(self, *args: Any, **kwargs: Any) -> None:
        return None

    def bbox(self, *args: Any, **kwargs: Any) -> None:
        return None

    def curselection(self) -> Tuple[Any, ...]:
        return ()

    def selection(self) -> Tuple[Any, ...]:
        return ()

    def selection_set(self, *args: Any, **kwargs: Any) -> None:
        return None

    def get_children(self, *args: Any, **kwargs: Any) -> Tuple[Any, ...]:
        return ()

    def winfo_children(self) -> Tuple[Any, ...]:
        return ()

    def mainloop(self, *args: Any, **kwargs: Any) -> None:
        return None

    def title(self, *args: Any, **kwargs: Any) -> None:
        return None

    def geometry(self, *args: Any, **kwargs: Any) -> None:
        return None

    def resizable(self, *args: Any, **kwargs: Any) -> None:
        return None

    def clipboard_clear(self) -> None:
        return None

    def clipboard_append(self, *args: Any, **kwargs: Any) -> None:
        return None

    def update(self) -> None:
        return None

    def update_idletasks(self) -> None:
        return None

    def __getattr__(self, name: str) -> Any:
        if name == "tk":
            return self
        return lambda *args, **kwargs: None


class _DummyTkVariable(_DummyTkWidget):
    pass


def _dummy_messagebox_response(*args: Any, **kwargs: Any) -> bool:
    return False


def _dummy_dialog_value(*args: Any, **kwargs: Any) -> Any:
    return None


def _dummy_file_selection(*args: Any, **kwargs: Any) -> str:
    return ""


def _dummy_file_selections(*args: Any, **kwargs: Any) -> Tuple[Any, ...]:
    return ()


def _module_getattr(_name: str) -> Any:
    return _DummyTkWidget


def _build_headless_modules() -> Tuple[ModuleType, ModuleType, ModuleType, ModuleType, ModuleType, ModuleType, ModuleType]:
    tk = ModuleType("tkinter")
    ttk = ModuleType("tkinter.ttk")
    messagebox = ModuleType("tkinter.messagebox")
    simpledialog = ModuleType("tkinter.simpledialog")
    filedialog = ModuleType("tkinter.filedialog")
    scrolledtext = ModuleType("tkinter.scrolledtext")
    tkfont = ModuleType("tkinter.font")

    widget_names = (
        "Tk",
        "Toplevel",
        "Frame",
        "Label",
        "Button",
        "Entry",
        "Text",
        "Canvas",
        "Scrollbar",
        "Listbox",
        "Menu",
        "PhotoImage",
        "PanedWindow",
        "Spinbox",
        "Checkbutton",
        "Radiobutton",
        "OptionMenu",
        "Misc",
        "Event",
    )
    variable_names = ("StringVar", "BooleanVar", "IntVar", "DoubleVar")
    constant_map = {
        "BOTH": "both",
        "LEFT": "left",
        "RIGHT": "right",
        "TOP": "top",
        "BOTTOM": "bottom",
        "X": "x",
        "Y": "y",
        "N": "n",
        "S": "s",
        "E": "e",
        "W": "w",
        "NW": "nw",
        "NE": "ne",
        "SW": "sw",
        "SE": "se",
        "WORD": "word",
        "END": "end",
        "DISABLED": "disabled",
        "NORMAL": "normal",
        "EXTENDED": "extended",
        "VERTICAL": "vertical",
        "HORIZONTAL": "horizontal",
    }
    for name in widget_names:
        setattr(tk, name, _DummyTkWidget)
    for name in variable_names:
        setattr(tk, name, _DummyTkVariable)
    for name, value in constant_map.items():
        setattr(tk, name, value)
    tk.TclError = RuntimeError
    tk.__getattr__ = _module_getattr  # type: ignore[attr-defined]

    for name in (
        "Frame",
        "Label",
        "Button",
        "Entry",
        "Combobox",
        "Treeview",
        "Scrollbar",
        "Style",
        "PanedWindow",
        "Checkbutton",
        "LabelFrame",
        "Labelframe",
        "Spinbox",
    ):
        setattr(ttk, name, _DummyTkWidget)
    ttk.__getattr__ = _module_getattr  # type: ignore[attr-defined]

    for name in ("showinfo", "showwarning", "showerror", "askyesno", "askokcancel", "askretrycancel"):
        setattr(messagebox, name, _dummy_messagebox_response)
    messagebox.__getattr__ = lambda _name: _dummy_messagebox_response  # type: ignore[attr-defined]

    for name in ("askstring", "askinteger", "askfloat"):
        setattr(simpledialog, name, _dummy_dialog_value)
    simpledialog.Dialog = _DummyTkWidget
    simpledialog.__getattr__ = lambda _name: _dummy_dialog_value  # type: ignore[attr-defined]

    for name in ("askopenfilename", "asksaveasfilename", "askdirectory"):
        setattr(filedialog, name, _dummy_file_selection)
    filedialog.askopenfilenames = _dummy_file_selections
    filedialog.__getattr__ = lambda _name: _dummy_file_selection  # type: ignore[attr-defined]

    scrolledtext.ScrolledText = _DummyTkWidget
    scrolledtext.__getattr__ = _module_getattr  # type: ignore[attr-defined]

    tkfont.Font = _DummyTkWidget
    tkfont.nametofont = lambda *args, **kwargs: _DummyTkWidget()
    tkfont.__getattr__ = _module_getattr  # type: ignore[attr-defined]

    tk.ttk = ttk
    tk.messagebox = messagebox
    tk.simpledialog = simpledialog
    tk.filedialog = filedialog
    tk.scrolledtext = scrolledtext

    sys.modules.setdefault("tkinter", tk)
    sys.modules.setdefault("tkinter.ttk", ttk)
    sys.modules.setdefault("tkinter.messagebox", messagebox)
    sys.modules.setdefault("tkinter.simpledialog", simpledialog)
    sys.modules.setdefault("tkinter.filedialog", filedialog)
    sys.modules.setdefault("tkinter.scrolledtext", scrolledtext)
    sys.modules.setdefault("tkinter.font", tkfont)
    return tk, filedialog, messagebox, scrolledtext, simpledialog, ttk, tkfont


def load_tk_modules() -> Tuple[Any, Any, Any, Any, Any, Any, Any]:
    try:
        tk = import_module("tkinter")
        filedialog = import_module("tkinter.filedialog")
        messagebox = import_module("tkinter.messagebox")
        scrolledtext = import_module("tkinter.scrolledtext")
        simpledialog = import_module("tkinter.simpledialog")
        ttk = import_module("tkinter.ttk")
        tkfont = import_module("tkinter.font")
        return tk, filedialog, messagebox, scrolledtext, simpledialog, ttk, tkfont
    except Exception:
        return _build_headless_modules()
