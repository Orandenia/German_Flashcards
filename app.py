"""Tkinter Oberfläche für Deutsch-A1-Karteikarten."""

import random
import tkinter as tk
from tkinter import font as tkfont

from words_data import WORDS


class FlashcardApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("德语 A1 单词闪卡 – 周佩瑶")
        self.geometry("560x440")
        self.minsize(480, 380)
        self.configure(bg="#1a1b26")

        self._deck: list[int] = list(range(len(WORDS)))
        random.shuffle(self._deck)
        self._deck_pos = 0
        self._show_answer = False

        self._fonts = {
            "title": tkfont.Font(family="Segoe UI", size=14, weight="bold"),
            "word": tkfont.Font(family="Segoe UI", size=22, weight="bold"),
            "hint": tkfont.Font(family="Segoe UI", size=11),
            "counter": tkfont.Font(family="Segoe UI", size=10),
        }

        outer = tk.Frame(self, bg="#1a1b26", padx=24, pady=20)
        outer.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            outer,
            text="Klick zum Umdrehen · 空格翻转 · ← → 切换",
            font=self._fonts["hint"],
            bg="#1a1b26",
            fg="#7aa2f7",
        ).pack(pady=(0, 12))

        self.card = tk.Frame(outer, bg="#24283b", relief=tk.FLAT, bd=0, highlightthickness=2, highlightbackground="#414868")
        self.card.pack(fill=tk.BOTH, expand=True, pady=8)

        self.label_side = tk.Label(
            self.card,
            text="",
            font=self._fonts["hint"],
            fg="#565f89",
            bg="#24283b",
        )
        self.label_side.pack(pady=(28, 4))

        self.label_main = tk.Label(
            self.card,
            text="",
            font=self._fonts["word"],
            fg="#c0caf5",
            bg="#24283b",
            wraplength=460,
            justify=tk.CENTER,
        )
        self.label_main.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)

        self.label_counter = tk.Label(
            outer,
            text="",
            font=self._fonts["counter"],
            fg="#565f89",
            bg="#1a1b26",
        )
        self.label_counter.pack(pady=(8, 4))

        btn_row = tk.Frame(outer, bg="#1a1b26")
        btn_row.pack(pady=12)

        self._mk_btn(btn_row, "◀ 上一张", self._prev)
        self._mk_btn(btn_row, "翻面 / Flip", self._toggle)
        self._mk_btn(btn_row, "下一张 ▶", self._next)
        self._mk_btn(btn_row, "打乱", self._shuffle_deck)

        self.card.bind("<Button-1>", lambda e: self._toggle())
        self.label_main.bind("<Button-1>", lambda e: self._toggle())

        self.bind("<space>", lambda e: self._toggle())
        self.bind("<Left>", lambda e: self._prev())
        self.bind("<Right>", lambda e: self._next())
        self.bind("<Escape>", lambda e: self.destroy())

        self._render()

    def _mk_btn(self, parent: tk.Frame, text: str, cmd) -> None:
        b = tk.Button(
            parent,
            text=text,
            command=cmd,
            font=self._fonts["hint"],
            bg="#414868",
            fg="#c0caf5",
            activebackground="#565f89",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=12,
            pady=6,
            cursor="hand2",
        )
        b.pack(side=tk.LEFT, padx=6)

    def _current_index(self) -> int:
        return self._deck[self._deck_pos]

    def _render(self) -> None:
        i = self._current_index()
        w = WORDS[i]
        if self._show_answer:
            self.label_side.config(text="中文")
            self.label_main.config(text=w["zh"])
        else:
            self.label_side.config(text="Deutsch")
            self.label_main.config(text=w["de"])
        self.label_counter.config(
            text=f"{self._deck_pos + 1} / {len(WORDS)}  ·  共 {len(WORDS)} 词"
        )

    def _toggle(self) -> None:
        self._show_answer = not self._show_answer
        self._render()

    def _next(self) -> None:
        self._deck_pos = (self._deck_pos + 1) % len(self._deck)
        self._show_answer = False
        self._render()

    def _prev(self) -> None:
        self._deck_pos = (self._deck_pos - 1) % len(self._deck)
        self._show_answer = False
        self._render()

    def _shuffle_deck(self) -> None:
        random.shuffle(self._deck)
        self._deck_pos = 0
        self._show_answer = False
        self._render()


def run() -> None:
    app = FlashcardApp()
    app.mainloop()
