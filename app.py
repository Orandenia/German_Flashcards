"""Tkinter Oberfläche: liest vocabulary.json (gTTS + pygame)."""

from __future__ import annotations

import atexit
import json
import os
import random
import tempfile
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox

import pygame
from gtts import gTTS


def _normalize_german_for_tts(text: str) -> str:
    return text.replace(" / ", ", ").replace("/", ", ")


def load_vocabulary(json_path: Path) -> list[dict]:
    if not json_path.is_file():
        raise FileNotFoundError(str(json_path.resolve()))
    try:
        raw = json_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"JSON 解析失败（第 {e.lineno} 行附近）：{e.msg}\n请检查 vocabulary.json 是否为合法 UTF-8 JSON。"
        ) from e
    except OSError as e:
        raise ValueError(f"无法读取词表文件：{e}") from e

    if isinstance(data, dict) and "words" in data:
        items = data["words"]
    elif isinstance(data, list):
        items = data
    else:
        raise ValueError('词表格式无效：应为 JSON 数组，或形如 {"words": [...] } 的对象。')

    if not isinstance(items, list) or not items:
        raise ValueError("词表为空：请至少添加一条词条。")

    out: list[dict] = []
    for i, it in enumerate(items, start=1):
        if not isinstance(it, dict):
            raise ValueError(f"第 {i} 条词条不是对象（{{...}}）。")
        de = it.get("de")
        zh = it.get("zh")
        if de is None or zh is None or str(de).strip() == "" or str(zh).strip() == "":
            raise ValueError(f"第 {i} 条词条缺少有效的 de 或 zh 字段。")
        ex_de = it.get("example_de") or ""
        ex_zh = it.get("example_zh") or ""
        out.append(
            {
                "de": str(de).strip(),
                "zh": str(zh).strip(),
                "example_de": str(ex_de).strip(),
                "example_zh": str(ex_zh).strip(),
            }
        )

    return out


def run() -> None:
    vocab_path = Path(__file__).resolve().parent / "vocabulary.json"
    dialog_root = tk.Tk()
    dialog_root.withdraw()
    dialog_root.update_idletasks()

    try:
        words = load_vocabulary(vocab_path)
    except FileNotFoundError:
        messagebox.showerror(
            "找不到 vocabulary.json",
            f"没有找到词表文件：\n{vocab_path}\n\n"
            "请把 vocabulary.json 放回与 app.py、main.py 同一文件夹（或从 Git/备份还原），再重新启动程序。",
            parent=dialog_root,
        )
        dialog_root.destroy()
        return
    except ValueError as e:
        messagebox.showerror("词表无法使用", str(e), parent=dialog_root)
        dialog_root.destroy()
        return
    except Exception as e:
        messagebox.showerror(
            "词表读取出错",
            f"加载 vocabulary.json 时发生意外错误：\n{e!s}\n\n如需帮助，可把该文件内容与报错交给维护者查看。",
            parent=dialog_root,
        )
        dialog_root.destroy()
        return

    dialog_root.destroy()

    app = FlashcardApp(words)
    app.mainloop()


class FlashcardApp(tk.Tk):
    def __init__(self, words: list[dict]) -> None:
        super().__init__()
        self._words = words
        self.title("德语 A1 单词闪卡 – 周佩瑶")
        self.geometry("620x540")
        self.minsize(520, 480)
        self.configure(bg="#1a1b26")

        pygame.mixer.init()
        self._last_mp3_path: str | None = None
        self._tts_busy = False
        atexit.register(self._cleanup_last_mp3)

        self._deck: list[int] = list(range(len(self._words)))
        random.shuffle(self._deck)
        self._deck_pos = 0
        self._show_answer = False

        self._session_start = time.monotonic()
        self._seen_indices: set[int] = set()
        self._learned_indices: set[int] = set()

        self._fonts = {
            "hint": tkfont.Font(family="Segoe UI", size=11),
            "word": tkfont.Font(family="Segoe UI", size=22, weight="bold"),
            "counter": tkfont.Font(family="Segoe UI", size=10),
            "speak": tkfont.Font(family="Segoe UI", size=13),
            "example": tkfont.Font(family="Segoe UI", size=11),
            "stats": tkfont.Font(family="Segoe UI", size=10),
        }

        outer = tk.Frame(self, bg="#1a1b26", padx=24, pady=16)
        outer.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            outer,
            text="Klick zum Umdrehen · 空格翻转 · ← → 切换 · 🔊 朗读德语",
            font=self._fonts["hint"],
            bg="#1a1b26",
            fg="#7aa2f7",
        ).pack(pady=(0, 10))

        self.card = tk.Frame(
            outer,
            bg="#24283b",
            relief=tk.FLAT,
            bd=0,
            highlightthickness=2,
            highlightbackground="#414868",
        )
        self.card.pack(fill=tk.BOTH, expand=True, pady=6)

        self.label_side = tk.Label(
            self.card,
            text="",
            font=self._fonts["hint"],
            fg="#565f89",
            bg="#24283b",
        )
        self.label_side.pack(pady=(24, 4))

        self.content_col = tk.Frame(self.card, bg="#24283b")
        self.content_col.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 16))

        word_row = tk.Frame(self.content_col, bg="#24283b")
        word_row.pack(fill=tk.X)

        self.label_main = tk.Label(
            word_row,
            text="",
            font=self._fonts["word"],
            fg="#c0caf5",
            bg="#24283b",
            wraplength=420,
            justify=tk.CENTER,
        )
        self.label_main.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        self.btn_speak = tk.Button(
            word_row,
            text="🔊\n朗读",
            command=self._on_speak_clicked,
            font=self._fonts["speak"],
            bg="#414868",
            fg="#c0caf5",
            activebackground="#565f89",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=14,
            pady=10,
            cursor="hand2",
            justify=tk.CENTER,
        )
        self.btn_speak.pack(side=tk.RIGHT, anchor=tk.CENTER, padx=(8, 0))

        self.label_example = tk.Label(
            self.content_col,
            text="",
            font=self._fonts["example"],
            fg="#a9b1d6",
            bg="#24283b",
            wraplength=520,
            justify=tk.LEFT,
            anchor=tk.W,
        )
        self.label_example.pack(fill=tk.X, pady=(12, 0))

        self.label_counter = tk.Label(
            outer,
            text="",
            font=self._fonts["counter"],
            fg="#565f89",
            bg="#1a1b26",
        )
        self.label_counter.pack(pady=(6, 4))

        btn_row = tk.Frame(outer, bg="#1a1b26")
        btn_row.pack(pady=8)

        self._mk_btn(btn_row, "◀ 上一张", self._prev)
        self._mk_btn(btn_row, "翻面 / Flip", self._toggle)
        self._mk_btn(btn_row, "下一张 ▶", self._next)
        self._mk_btn(btn_row, "打乱", self._shuffle_deck)

        stats_frame = tk.Frame(outer, bg="#1a1b26")
        stats_frame.pack(fill=tk.X, pady=(10, 0))

        self.label_session = tk.Label(
            stats_frame,
            text="",
            font=self._fonts["stats"],
            fg="#c0caf5",
            bg="#1a1b26",
            anchor=tk.W,
            justify=tk.LEFT,
        )
        self.label_session.pack(fill=tk.X)

        self.label_progress_text = tk.Label(
            stats_frame,
            text="",
            font=self._fonts["stats"],
            fg="#565f89",
            bg="#1a1b26",
            anchor=tk.W,
        )
        self.label_progress_text.pack(fill=tk.X, pady=(4, 0))

        self.progress_canvas = tk.Canvas(
            stats_frame,
            height=12,
            bg="#24283b",
            highlightthickness=1,
            highlightbackground="#414868",
        )
        self.progress_canvas.pack(fill=tk.X, pady=(6, 0))
        self.progress_canvas.bind("<Configure>", lambda e: self._draw_progress_bar())

        self.card.bind("<Button-1>", self._on_card_background_click)
        self.label_side.bind("<Button-1>", self._on_card_background_click)
        self.content_col.bind("<Button-1>", self._on_card_background_click)
        self.label_example.bind("<Button-1>", self._on_card_background_click)

        self.label_main.bind("<Button-1>", lambda e: self._toggle())

        self.bind("<space>", lambda e: self._toggle())
        self.bind("<Left>", lambda e: self._prev())
        self.bind("<Right>", lambda e: self._next())
        self.bind("<Escape>", lambda e: self.destroy())

        self._tick_session()
        self._render()

    def _session_elapsed_seconds(self) -> int:
        return max(0, int(time.monotonic() - self._session_start))

    @staticmethod
    def _format_elapsed(total_sec: int) -> str:
        h, rem = divmod(total_sec, 3600)
        m, s = divmod(rem, 60)
        if h > 0:
            return f"{h} 小时 {m:02d} 分 {s:02d} 秒"
        return f"{m} 分 {s:02d} 秒"

    def _tick_session(self) -> None:
        if not self.winfo_exists():
            return
        self._update_stats_labels()
        self.after(1000, self._tick_session)

    def _update_stats_labels(self) -> None:
        elapsed = self._session_elapsed_seconds()
        n_total = len(self._words)
        n_seen = len(self._seen_indices)
        n_learned = len(self._learned_indices)
        self.label_session.config(
            text=f"本次学习时长：{self._format_elapsed(elapsed)}   ·   已浏览词条：{n_seen} / {n_total}"
        )
        self.label_progress_text.config(
            text=f"已翻面学习：{n_learned} / {n_total}（翻过中文面的不同单词数）"
        )

    def _draw_progress_bar(self) -> None:
        self.progress_canvas.delete("all")
        w = max(self.progress_canvas.winfo_width(), 2)
        h = self.progress_canvas.winfo_height()
        n_total = max(len(self._words), 1)
        ratio = min(1.0, len(self._learned_indices) / n_total)
        fill_w = max(int(w * ratio), 2 if ratio > 0 else 0)
        self.progress_canvas.create_rectangle(0, 0, w, h, fill="#1a1b26", outline="")
        if fill_w > 0:
            self.progress_canvas.create_rectangle(0, 0, fill_w, h, fill="#7aa2f7", outline="")

    def _register_study_progress(self) -> None:
        idx = self._current_index()
        self._seen_indices.add(idx)
        if self._show_answer:
            self._learned_indices.add(idx)

    def _cleanup_last_mp3(self) -> None:
        pygame.mixer.music.stop()
        if self._last_mp3_path and os.path.isfile(self._last_mp3_path):
            try:
                os.unlink(self._last_mp3_path)
            except OSError:
                pass
            self._last_mp3_path = None

    def _on_card_background_click(self, event: tk.Event) -> None:
        w = event.widget
        if w in (self.card, self.label_side, self.content_col, self.label_example):
            self._toggle()

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

    def _current_word(self) -> dict:
        return self._words[self._current_index()]

    def _current_index(self) -> int:
        return self._deck[self._deck_pos]

    def _render(self) -> None:
        self._register_study_progress()
        w = self._current_word()
        ex_de = w.get("example_de", "")
        ex_zh = w.get("example_zh", "")
        if self._show_answer:
            self.label_side.config(text="中文")
            self.label_main.config(text=w["zh"])
            if ex_de or ex_zh:
                self.label_example.config(
                    text=f"例 · {ex_de}\n译 · {ex_zh}" if ex_de and ex_zh else f"例 · {ex_de or ex_zh}"
                )
            else:
                self.label_example.config(text="")
        else:
            self.label_side.config(text="Deutsch")
            self.label_main.config(text=w["de"])
            self.label_example.config(text="")
        total = len(self._words)
        self.label_counter.config(text=f"{self._deck_pos + 1} / {total}  ·  共 {total} 词")
        self.btn_speak.config(state=tk.DISABLED if self._tts_busy else tk.NORMAL)
        self._update_stats_labels()
        self.after_idle(self._draw_progress_bar)

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

    def _on_speak_clicked(self) -> None:
        if self._tts_busy:
            return
        text = _normalize_german_for_tts(self._current_word()["de"])
        if not text.strip():
            return

        self._tts_busy = True
        self.btn_speak.config(state=tk.DISABLED)

        def synthesize() -> None:
            err: BaseException | None = None
            path: str | None = None
            try:
                fd, path = tempfile.mkstemp(suffix=".mp3", prefix="flashcard_de_")
                os.close(fd)
                gTTS(text=text, lang="de", slow=False).save(path)
            except BaseException as e:
                err = e
                if path and os.path.isfile(path):
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
                    path = None

            def finish_ui() -> None:
                self._tts_busy = False
                self._render()

            if err is not None:
                self.after(0, finish_ui)
                self.after(
                    0,
                    lambda e=err: messagebox.showerror(
                        "朗读失败",
                        f"无法生成或播放语音（需要能访问 Google TTS）。\n\n{e!s}",
                    ),
                )
                return

            assert path is not None
            self.after(0, lambda p=path: self._play_mp3_and_delete_previous(p))
            self.after(0, finish_ui)

        threading.Thread(target=synthesize, daemon=True).start()

    def _play_mp3_and_delete_previous(self, path: str) -> None:
        try:
            pygame.mixer.music.stop()
            if self._last_mp3_path and os.path.isfile(self._last_mp3_path):
                try:
                    os.unlink(self._last_mp3_path)
                except OSError:
                    pass
            self._last_mp3_path = path
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
        except Exception as e:
            messagebox.showerror("播放失败", f"pygame 无法播放该音频。\n\n{e!s}")
            try:
                if os.path.isfile(path):
                    os.unlink(path)
            except OSError:
                pass
            self._last_mp3_path = None
