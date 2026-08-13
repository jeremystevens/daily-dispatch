"""
Reusable building blocks — classic tk widgets with direct bg/fg/font.
ttkbootstrap never touches these, so they work on every version.
"""

import threading
import tkinter as tk

import theme as T


def divider(master, pad=None):
    """1 px hairline."""
    d = tk.Frame(master, height=1, bg=T.BORDER, bd=0, highlightthickness=0)
    if pad is not None:
        d.pack(fill="x", pady=pad)
    return d


class Card(tk.Frame):
    """Flat raised surface. Put children in ``card.body``."""

    def __init__(self, master, title=None, subtitle=None):
        super().__init__(master, bg=T.SURFACE, bd=0, highlightthickness=0)
        p = T.S["xl"]
        self._inner = tk.Frame(self, bg=T.SURFACE)
        self._inner.pack(fill="both", expand=True, padx=p, pady=p)
        if title:
            tk.Label(self._inner, text=title, bg=T.SURFACE, fg=T.FG,
                     font=T.F["card_title"], anchor="w").pack(fill="x")
            if subtitle:
                tk.Label(self._inner, text=subtitle, bg=T.SURFACE, fg=T.MUTED,
                         font=T.F["sm"], anchor="w").pack(fill="x", pady=(2, 0))
            divider(self._inner, pad=(T.S["md"], T.S["lg"]))
        self.body = tk.Frame(self._inner, bg=T.SURFACE)
        self.body.pack(fill="both", expand=True)


class FormRow(tk.Frame):
    """Label + hint above a control slot. Put inputs in ``row.control``."""

    def __init__(self, master, label, hint=None):
        super().__init__(master, bg=T.SURFACE)
        top = tk.Frame(self, bg=T.SURFACE)
        top.pack(fill="x")
        tk.Label(top, text=label, bg=T.SURFACE, fg=T.FG,
                 font=T.F["base_bold"], anchor="w").pack(side="left")
        if hint:
            tk.Label(top, text=hint, bg=T.SURFACE, fg=T.MUTED,
                     font=T.F["sm"]).pack(side="right")
        self.control = tk.Frame(self, bg=T.SURFACE)
        self.control.pack(fill="x", pady=(T.S["sm"], 0))


class StatusChip(tk.Frame):
    """Coloured dot + label — for connectivity / status readouts."""

    def __init__(self, master, text="", color=T.MUTED, bg=T.SIDEBAR):
        super().__init__(master, bg=bg)
        self._bg = bg
        self._dot = tk.Canvas(self, width=10, height=10, bg=bg,
                              bd=0, highlightthickness=0)
        self._oval = self._dot.create_oval(1, 1, 9, 9, fill=color, outline="")
        self._dot.pack(side="left", padx=(0, T.S["sm"]))
        self._lbl = tk.Label(self, text=text, bg=bg, fg=T.MUTED,
                             font=T.F["sm"])
        self._lbl.pack(side="left")

    def set(self, text, color):
        self._lbl.configure(text=text)
        self._dot.itemconfigure(self._oval, fill=color)


def run_async(root, work, on_done):
    """Run work() in a thread, deliver result to on_done(result, error)
    on the Tk main thread."""
    def runner():
        try:
            r, e = work(), None
        except Exception as exc:
            r, e = None, exc
        root.after(0, lambda: on_done(r, e))
    threading.Thread(target=runner, daemon=True).start()
