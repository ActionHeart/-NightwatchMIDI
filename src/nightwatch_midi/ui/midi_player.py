import math
import os
import re
import shutil
import tempfile
import traceback
from bisect import bisect_right
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget, QFileDialog, QListWidgetItem

from .player_view import LibraryItemDelegate, build_view, info_html

from ..game.diagnostics import capture_foreground, foreground_window, format_snapshot
from ..input.backend import MockInputBackend
from ..input.sendinput import SendInputBackend
from ..library import SongLibrary
from ..mapping.profile import load_profile
from ..mapping.plan import build_plan, slice_plan, TIMINGS
from ..mapping.melody import rank_melodies
from ..midi.parser import read_midi
from ..playback.engine import PlaybackEngine
from ..score import (KEY_EXAMPLE, NUMBERED_EXAMPLE, build_midi, build_song,
                     parse_directives, parse_keys, parse_numbered, safe_track_name)


class MidiPlayer(QWidget):
    def __init__(self):
        super().__init__()
        self.profile = load_profile(name="delta_harmonica.json")
        self.song = self.plan = self.engine = None
        self.backend = MockInputBackend()
        self._snapshot = ""
        self._target = None
        self._reported = False
        self._adapting = False
        self.start_at = 0.0
        self.filename = ''
        self._loaded_path = None
        self.library = SongLibrary()
        build_view(self)
        self.select_preset("balance")
        self.refresh_library()
        self.library_list.itemSelectionChanged.connect(self.update_library_actions)
        self.library_list.itemDoubleClicked.connect(lambda _: self.load_from_library())
        self.library_list.itemDelegate().favorite_toggled.connect(self.toggle_favorite_path)
        self.library_search.textChanged.connect(lambda _: self.refresh_library())
        self.library_favorites_only.toggled.connect(lambda _: self.refresh_library())
        self.library_sort.currentIndexChanged.connect(lambda _: self.refresh_library())
        self.progress.valueChanged.connect(self.seek_changed)
        self.score_format.currentIndexChanged.connect(self.score_format_changed)
        for widget, signal in ((self.voicing, "currentIndexChanged"), (self.density, "currentIndexChanged"),
                               (self.onset_window, "valueChanged"), (self.speed, "valueChanged"),
                               (self.trim, "toggled"), (self.note_gap, "valueChanged"),
                               (self.timing_preset, "currentIndexChanged"),
                               (self.transpose, "valueChanged"), (self.fold, "toggled"),
                               (self.range_mode, "currentIndexChanged")):
            getattr(widget, signal).connect(self._deselect_presets)
        for combo in (self.track, self.channel):
            combo.currentIndexChanged.connect(self.selection_changed)
        self.voicing.currentIndexChanged.connect(self.rebuild)
        self.transpose.valueChanged.connect(self.rebuild)
        self.fold.toggled.connect(self.rebuild)
        self.drums.toggled.connect(self.rebuild)
        self.note_gap.valueChanged.connect(self.rebuild)
        self.speed.valueChanged.connect(self.rebuild)
        self.timing_preset.currentIndexChanged.connect(self.change_timing)
        self.density.currentIndexChanged.connect(self.rebuild)
        self.trim.toggled.connect(self.rebuild)
        self.onset_window.valueChanged.connect(self.rebuild)
        self.range_mode.currentIndexChanged.connect(self.apply_range)
        self.transpose.valueChanged.connect(self.mark_custom)
        self.fold.toggled.connect(self.mark_custom)
        self.basic_speed.currentIndexChanged.connect(lambda: self.speed.setValue(self.basic_speed.currentData()))
        self.basic_delay.currentIndexChanged.connect(lambda: self.delay.setValue(self.basic_delay.currentData()))
        self.speed.valueChanged.connect(lambda v: self.sync_choice(self.basic_speed, v, f"{v:g}x（自定义）"))
        self.delay.valueChanged.connect(lambda v: self.sync_choice(self.basic_delay, v, f"{v} 秒（自定义）"))
        self.input_mode.currentIndexChanged.connect(lambda: self.set_real_input(self.input_mode.currentData()))
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.poll)
        self.timer.start()

    @staticmethod
    def sync_choice(combo, value, text):
        combo.blockSignals(True)
        index = combo.findData(value)
        if index < 0:
            combo.addItem(text, value)
            index = combo.count() - 1
        combo.setCurrentIndex(index)
        combo.blockSignals(False)

    @staticmethod
    def clock_text(seconds):
        seconds = max(0, int(seconds))
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    def recommended_shift(self):
        options = [(shift, self.compile_plan(transpose=shift)) for shift in (-24, -12, 0, 12, 24)]
        return min(options, key=lambda pair: (pair[1].skipped + pair[1].folded, abs(pair[0])))[0]

    def mark_custom(self, *_):
        if not self._adapting:
            self.sync_choice(self.range_mode, "custom", "自定义")

    PRESET_LABELS = {"balance": "平衡", "stable": "稳定", "fidelity": "高还原", "fast": "高速"}

    def _deselect_presets(self, *_):
        if self._adapting:
            return
        for preset in self.preset_buttons.values():
            preset.blockSignals(True)
            preset.setChecked(False)
            preset.blockSignals(False)

    def select_preset(self, key):
        for name, preset in self.preset_buttons.items():
            preset.blockSignals(True)
            preset.setChecked(name == key)
            preset.blockSignals(False)

    def apply_preset(self, key):
        if not self.song:
            self.status.setText("请先选择乐谱，再应用演奏预设。")
            self.select_preset(None)
            return
        config = {
            "balance": dict(timing="stable", onset=0, density="score", voicing=False, trim=True, speed=None, original=False),
            "stable": dict(timing="stable", onset=20, density="score", voicing=False, trim=True, speed=None, original=False),
            "fidelity": dict(timing="standard", onset=0, density="score", voicing=False, trim=False, speed=1.0, original=True),
            "fast": dict(timing="fast", onset=0, density="score", voicing=False, trim=True, speed=1.5, original=False),
        }[key]
        widgets = (self.timing_preset, self.onset_window, self.density, self.voicing, self.trim,
                   self.range_mode, self.transpose, self.fold, self.speed, self.note_gap)
        blocked = {widget: widget.blockSignals(True) for widget in widgets}
        self._adapting = True
        try:
            self.timing_preset.setCurrentIndex(self.timing_preset.findData(config["timing"]))
            self.note_gap.setValue(round(TIMINGS[config["timing"]].gap * 1000))
            self.onset_window.setValue(config["onset"])
            self.density.setCurrentIndex(self.density.findData(config["density"]))
            self.voicing.setCurrentIndex(self.voicing.findData(config["voicing"]))
            self.trim.setChecked(config["trim"])
            if config["speed"] is not None:
                self.speed.setValue(config["speed"])
            if config["original"]:
                self.range_mode.setCurrentIndex(self.range_mode.findData("original"))
                self.transpose.setValue(0)
                self.fold.setChecked(False)
        finally:
            for widget, state in blocked.items():
                widget.blockSignals(state)
            self._adapting = False
        self.sync_choice(self.basic_speed, self.speed.value(), f"{self.speed.value():g}x（自定义）")
        self.rebuild()
        self.select_preset(key)
        self.status.setText(f"已应用「{self.PRESET_LABELS[key]}」预设；可在高级设置中微调，改动后预设会自动取消。")

    def _update_play_button(self):
        if self.plan and self.start_at > 0.05:
            self.play_button.setText(f"从 {self.clock_text(self.start_at)} 开始演奏")
        else:
            self.play_button.setText("开始演奏")

    def set_start_position(self, position):
        if not self.plan:
            return
        self.start_at = max(0.0, min(position, self.plan.duration))
        self.progress.blockSignals(True)
        self.progress.setValue(int(1000 * self.start_at / max(self.plan.duration, 0.001)))
        self.progress.blockSignals(False)
        self.update_library_info()
        if not (self.engine and not self.engine.done.is_set()):
            self.time_label.setText(f"{self.clock_text(self.start_at)} / {self.clock_text(self.plan.duration)}")
        self._update_play_button()

    def seek_changed(self, value):
        if self.engine and not self.engine.done.is_set():
            return
        if self.plan:
            self.set_start_position(value / 1000 * self.plan.duration)

    def current_position(self):
        if self.engine and not self.engine.done.is_set():
            return self.engine.position
        return self.start_at

    def seek_relative(self, delta):
        if not self.plan:
            return
        playing = bool(self.engine and not self.engine.done.is_set())
        target = max(0.0, min(self.current_position() + delta, self.plan.duration))
        if playing:
            self.restart_playback(target, delay=0.0)
        else:
            self.set_start_position(target)
            self.status.setText(f"播放起点设为 {self.clock_text(target)}；点「{self.play_button.text()}」即可。")

    def seek_backward(self):
        self.seek_relative(-10.0)

    def seek_forward(self):
        self.seek_relative(10.0)

    def restart_from_start(self):
        if not self.plan or not self.plan.actions:
            return
        position = self.start_at
        if self.engine and not self.engine.done.is_set():
            self.restart_playback(position, delay=self.delay.value())
        else:
            self.set_start_position(position)
            self.play()
        self.status.setText(f"从 {self.clock_text(position)} 重新开始。")

    def global_hotkeys(self):
        return {0x77: self.hotkey_restart, 0x78: self.hotkey_seek_back, 0x79: self.hotkey_seek_forward}

    def _hotkeys_enabled(self):
        return self.hotkeys_enable.isChecked()

    def hotkey_restart(self):
        if self._hotkeys_enabled() and self.plan:
            self.restart_from_start()

    def hotkey_seek_back(self):
        if self._hotkeys_enabled():
            self.seek_backward()

    def hotkey_seek_forward(self):
        if self._hotkeys_enabled():
            self.seek_forward()

    def restart_playback(self, position, delay=0.0):
        engine = self.engine
        if engine:
            if not engine.stop():
                self.status.setText("上一个播放线程尚未结束，请重试重新定位")
                return
            try:
                engine.retry_release()
            except Exception as exc:
                self.emergency_stop()
                self.status.setText(f"重新定位失败，输入已释放：{exc}")
                return
            self.engine = None
        self.start_at = max(0.0, min(position, self.plan.duration))
        self._start_playback(self.start_at, delay=delay)
        if self.engine:
            self.status.setText(f"已从 {self.clock_text(self.start_at)} 继续播放。")

    def selection_changed(self, *_):
        if self.range_mode.currentData() == "auto":
            self.apply_range()
        else:
            self.rebuild()

    def apply_range(self, *_):
        mode = self.range_mode.currentData()
        if mode == "custom":
            self.tabs.setCurrentWidget(self.advanced_page)
            self.advanced.setCurrentIndex(0)
            return
        self._adapting = True
        try:
            self.fold.setChecked(mode == "auto")
            self.transpose.setValue(self.recommended_shift() if mode == "auto" and self.song else 0)
        finally:
            self._adapting = False
        self.rebuild()

    def optimize(self):
        if not self.song:
            return
        before = self.plan
        self.suggest_melody()
        self.sync_choice(self.range_mode, "auto", "自动适配")
        self.apply_range()
        # Optimize articulation at the user's speed, never solve density by
        # silently changing the tempo of the whole piece. The existing grouping
        # option is bounded to 30 ms; prefer the smallest effective window.
        if not self.voicing.currentData():
            windows = sorted({self.onset_window.value(), 0, 10, 20, 30})
            candidates = [(window, self.compile_plan(onset_window=window / 1000, density="score"))
                          for window in windows]
            window, _ = min(candidates, key=lambda item: (item[1].density_dropped, item[0]))
            self.onset_window.setValue(window)
        self.density.setCurrentIndex(self.density.findData("score"))
        self.apply_range()
        self._deselect_presets()
        self._save_optimization(self.plan)
        was = before.density_dropped if before else 0
        now = self.plan.density_dropped if self.plan else 0
        self.status.setText(f"优化完成：跳过 {was} → {now} 音；移调 {self.transpose.value():+d} 半音，"
                            f"折回 {self.plan.folded} 音，起音归组 {self.onset_window.value()} ms，"
                            f"速度保持 {self.speed.value():.2f}x。可以开始演奏了。")

    def _save_optimization(self, plan):
        if plan is None or self._loaded_path is None or not self.library.contains(self._loaded_path):
            return
        self.library.set_optimized(self._loaded_path, {
            "transpose": self.transpose.value(),
            "folded": plan.folded,
            "density_dropped": plan.density_dropped,
            "onset_window_ms": self.onset_window.value(),
            "speed": round(self.speed.value(), 2),
        })
        self.refresh_library(select=self._loaded_path)

    def _set_file_name(self, name=None, tooltip=""):
        self.file_label.setText(name or "尚未选择乐谱")
        self.file_label.setProperty("empty", "false" if name else "true")
        self.file_label.setToolTip(tooltip or "尚未选择文件")
        self.file_label.style().unpolish(self.file_label)
        self.file_label.style().polish(self.file_label)

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 MIDI", "", "MIDI (*.mid *.midi)")
        if path:
            self.load_file(path)

    def load_file(self, path, from_library=False):
        if not self.emergency_stop():
            return
        try:
            song = read_midi(path)
        except Exception as exc:
            self.library_prompt.hide()
            self.status.setText(f"载入失败：{exc}")
            return
        self.load_song(song, Path(path), from_library=from_library)

    def load_song(self, song, path=None, *, title=None, from_library=False):
        try:
            self.song = song
            self.track.blockSignals(True)
            self.track.clear()
            self.track.addItem("全部音轨", None)
            for i, name in enumerate(song.track_names):
                count = sum(n.track == i for n in song.notes)
                self.track.addItem(f"{i + 1}. {name}（{count} 音符）", i)
            self.track.blockSignals(False)
            self.filename = Path(path).name if path else f"{title or '谱曲作品'}.mid"
            self._loaded_path = Path(path) if path else None
            self._set_file_name(self.filename, str(path) if path else "谱曲生成，可保存到曲库")
            self.now_playing.setText(self.filename)
            self.now_playing.setToolTip(self.filename)
            self.suggest_melody()
            self.apply_range()
            self.set_start_position(0.0)
            self.update_library_prompt(from_library or path is None)
            if self._loaded_path is not None and self.library.contains(self._loaded_path):
                self.library.mark_played(self._loaded_path, self._song_meta())
                self.refresh_library(select=self._loaded_path)
            if self.plan:
                self.status.setText(f"乐谱已就绪，已自动推荐旋律；点击「开始演奏」即可预览。"
                                    f"当前移调 {self.transpose.value():+d} 半音，折回 {self.plan.folded} 音。"
                                    "保留原音高可选择「原始」音域。")
        except Exception as exc:
            self.library_prompt.hide()
            self.status.setText(f"载入失败：{exc}")

    @staticmethod
    def _meta_from_song(song):
        bpms = [60000000 / tempo.microseconds for tempo in song.rhythm.tempos]
        bpm = f"{min(bpms):.1f}" if max(bpms) == min(bpms) else f"{min(bpms):.1f}–{max(bpms):.1f}"
        return {"duration": round(song.duration, 1), "notes": len(song.notes), "bpm": bpm}

    def _song_meta(self):
        return self._meta_from_song(self.song) if self.song else {}

    def update_library_prompt(self, from_library):
        if from_library or self._loaded_path is None:
            self.library_prompt.hide()
            return
        if self.library.contains(self._loaded_path):
            self.library_prompt.hide()
            return
        self.library_prompt_label.setText(f"把《{self.filename}》加入曲库？")
        self.library_prompt.show()

    def refresh_library(self, select=None):
        query = self.library_search.text().strip().casefold()
        favorites_only = self.library_favorites_only.isChecked()
        entries = [entry for entry in self.library.songs()
                   if (not query or query in entry["title"].casefold())
                   and (not favorites_only or entry.get("favorite"))]
        order = self.library_sort.currentData()
        if order == "recent":
            entries.sort(key=lambda entry: entry.get("last_played") or "", reverse=True)
        elif order == "added":
            entries.sort(key=lambda entry: entry.get("added") or "", reverse=True)
        else:
            entries.sort(key=lambda entry: entry["title"].casefold())
        self.library_list.clear()
        for entry in entries:
            item = QListWidgetItem(entry["title"])
            item.setData(Qt.ItemDataRole.UserRole, str(entry["path"]))
            item.setData(LibraryItemDelegate.DATA_ROLE, self._library_row(entry))
            item.setToolTip(f"{entry['path']}\n加入时间：{entry.get('added', '—')}\n双击直接演奏")
            self.library_list.addItem(item)
        if select is not None:
            target = Path(select).resolve()
            for index in range(self.library_list.count()):
                data = self.library_list.item(index).data(Qt.ItemDataRole.UserRole)
                if data and Path(data).resolve() == target:
                    self.library_list.setCurrentRow(index)
                    break
        self.library_list.setToolTip(f"曲库位置：{self.library.root}\n单击选中；双击载入；点左侧星标收藏")
        self.update_library_empty(len(entries), bool(query or favorites_only))
        self.update_library_info()
        self.update_library_actions()

    @staticmethod
    def _library_row(entry):
        meta = entry.get("meta") or {}
        parts = []
        if meta.get("duration") is not None:
            parts.append(f"时长 {MidiPlayer.clock_text(meta['duration'])}")
        if meta.get("notes") is not None:
            parts.append(f"{meta['notes']} 音符")
        if meta.get("bpm"):
            parts.append(f"BPM {meta['bpm']}")
        play_count = int(entry.get("play_count", 0) or 0)
        if play_count:
            parts.append(f"播放 {play_count} 次")
        last = entry.get("last_played")
        if last:
            parts.append(str(last).replace("T", " ")[:16])
        return {
            "title": entry["title"],
            "favorite": bool(entry.get("favorite")),
            "badge": "已优化" if entry.get("optimized") else "",
            "meta": " · ".join(parts) if parts else "尚未播放，双击即可演奏",
        }

    def update_library_empty(self, count, filtered):
        if count:
            self.library_empty.hide()
            return
        if filtered:
            self.library_empty.setText("没有符合条件的曲目：试试清空搜索并取消「只看收藏」。")
        else:
            self.library_empty.setText("曲库还是空的：点右上角「＋ 从文件导入」，或在演奏页导入后选择加入曲库。")
        self.library_empty.show()

    def open_library_folder(self):
        try:
            self.library.root.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.library.root)))
        self.status.setText(f"已在资源管理器中打开曲库文件夹：{self.library.root}")

    def score_format_changed(self, *_):
        keys_mode = self.score_format.currentData() == "keys"
        self.score_key.setEnabled(not keys_mode)
        self.score_key.setToolTip("按键谱由乐器配置决定音高，无需调号" if keys_mode else "简谱中 1 对应的调")

    def load_score_example(self):
        example = KEY_EXAMPLE if self.score_format.currentData() == "keys" else NUMBERED_EXAMPLE
        self.score_editor.setPlainText(example)
        self.score_result.setText("已载入示例；点「解析预览」检查，或直接「生成并演奏」。")
        self.status.setText("已载入谱曲示例")

    def _parsed_score(self):
        text = self.score_editor.toPlainText()
        if not text.strip():
            raise ValueError("谱面为空：请粘贴文本或点「载入示例」")
        directives = parse_directives(text)
        bpm = directives.get("bpm", self.score_bpm.value())
        numerator, denominator = directives.get("meter", self.score_meter.currentData())
        if self.score_format.currentData() == "keys":
            score = parse_keys(text, self.profile, bpm=bpm,
                               numerator=numerator, denominator=denominator)
        else:
            key = directives.get("key", self.score_key.currentData())
            score = parse_numbered(text, key=key, bpm=bpm,
                                   numerator=numerator, denominator=denominator)
        return replace(score, title=self.score_title.text().strip() or "谱曲作品")

    def _score_failed(self, exc):
        self.score_result.setText(f"解析失败：{exc}")
        self.status.setText(f"谱曲解析失败：{exc}")

    def preview_score(self):
        try:
            score = self._parsed_score()
        except Exception as exc:
            self._score_failed(exc)
            return
        warning = ("；".join(score.warnings) + "。" if score.warnings else "")
        self.score_result.setText(
            f"解析成功：{len(score.notes)} 个音符，{score.bpm} BPM，"
            f"{score.numerator}/{score.denominator}，时长 {self.clock_text(score.duration)}。{warning}")
        self.status.setText("谱面解析成功，可「生成并演奏」或「保存到曲库」。")

    def play_score(self):
        try:
            score = self._parsed_score()
            song = build_song(score)
        except Exception as exc:
            self._score_failed(exc)
            return
        if not self.emergency_stop():
            return
        self.load_song(song, None, title=score.title)
        self.tabs.setCurrentWidget(self.play_page)
        self.status.setText(f"已生成《{score.title}》：{len(score.notes)} 个音符；点「开始演奏」即可。")

    def save_score_to_library(self):
        try:
            score = self._parsed_score()
            midi = build_midi(score, track_name=safe_track_name(score.title))
        except Exception as exc:
            self._score_failed(exc)
            return
        safe = re.sub(r'[\\/:*?"<>|]', "_", score.title).strip() or "谱曲作品"
        temp_dir = Path(tempfile.mkdtemp(prefix="nightwatch-score-"))
        try:
            path = temp_dir / f"{safe}.mid"
            midi.save(path)
            song = build_song(score)
            entry = self.library.add(path, meta=self._meta_from_song(song))
        except Exception as exc:
            self.status.setText(f"保存到曲库失败：{exc}")
            return
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
        self.refresh_library(select=self.library.root / entry["file"])
        self.status.setText(f"已保存到曲库：{entry['title']}。可在「曲库」分页编辑或载入。")

    def _selected_library_entry(self):
        item = self.library_list.currentItem()
        if item is None:
            return None
        data = item.data(Qt.ItemDataRole.UserRole)
        entry = self.library.find(Path(data)) if data else None
        return {**entry, "path": self.library.root / entry["file"]} if entry else None

    def update_library_actions(self):
        entry = self._selected_library_entry()
        selected = entry is not None
        self.library_load_button.setEnabled(selected)
        self.library_remove_button.setEnabled(selected)
        self.library_favorite_button.setEnabled(selected)
        self.library_favorite_button.setText("★ 取消收藏" if entry and entry.get("favorite") else "☆ 收藏")
        self.update_library_info()

    def update_library_info(self):
        entries = self.library.songs()
        total = len(entries)
        favorites = sum(1 for entry in entries if entry.get("favorite"))
        entry = self._selected_library_entry()
        if entry is None:
            self.library_info.setText(
                f"共 {total} 首 · 收藏 {favorites} 首；选中曲目可查看时长、播放次数与优化状态。")
            return
        meta = entry.get("meta") or {}
        duration = self.clock_text(meta["duration"]) if meta.get("duration") is not None else "—"
        parts = [f"时长 {duration}", f"音符 {meta.get('notes', '—')}", f"原谱 BPM {meta.get('bpm', '—')}"]
        last = entry.get("last_played")
        played = f"最近播放 {str(last).replace('T', ' ')}（{entry.get('play_count', 0)} 次）" if last else "尚未播放"
        optimized = entry.get("optimized")
        if optimized:
            opt = (f"已优化：移调 {int(optimized.get('transpose', 0)):+d} · 折回 {optimized.get('folded', 0)} · "
                   f"跳过 {optimized.get('density_dropped', 0)} · {optimized.get('speed', 1):.2f}x")
        else:
            opt = "未记录优化；在演奏页点「一键优化」后会保存结果"
        self.library_info.setText(" · ".join(parts) + "\n" + played + " · " + opt)

    def load_from_library(self):
        item = self.library_list.currentItem()
        if item is None:
            return
        self.tabs.setCurrentWidget(self.play_page)
        self.load_file(Path(item.data(Qt.ItemDataRole.UserRole)), from_library=True)

    def import_to_library(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入曲库", "", "MIDI (*.mid *.midi)")
        if not path:
            return
        meta = {}
        try:
            meta = self._meta_from_song(read_midi(path))
        except Exception:
            pass
        try:
            entry = self.library.add(Path(path), meta=meta)
        except Exception as exc:
            self.status.setText(f"曲库导入失败：{exc}")
            return
        self.refresh_library(select=self.library.root / entry["file"])
        self.status.setText(f"已导入曲库：{entry['title']}。双击或点「载入所选曲目」即可演奏。")

    def toggle_favorite(self):
        entry = self._selected_library_entry()
        if entry is not None:
            self.toggle_favorite_path(entry["path"])

    def toggle_favorite_path(self, path):
        entry = self.library.find(Path(path)) if path else None
        if entry is None:
            return
        favorite = not entry.get("favorite")
        self.library.update(Path(path), favorite=favorite)
        self.refresh_library(select=Path(path))
        self.status.setText(("已收藏：" if favorite else "已取消收藏：") + entry["title"])

    def remove_from_library(self):
        item = self.library_list.currentItem()
        if item is None:
            return
        title = item.text()
        if self.library.remove(Path(item.data(Qt.ItemDataRole.UserRole))):
            self.refresh_library()
            self.status.setText(f"已从曲库移除：{title}")
        else:
            self.status.setText("移除失败：曲库中找不到该条目")

    def add_to_library(self):
        if self._loaded_path is None:
            return
        try:
            entry = self.library.add(self._loaded_path)
        except Exception as exc:
            self.status.setText(f"加入曲库失败：{exc}")
            return
        self.refresh_library(select=self.library.root / entry["file"])
        self.library_prompt.hide()
        self.status.setText(f"已加入曲库：{entry['title']}。可在「曲库」分页中直接选择。")

    def dismiss_library_prompt(self):
        self.library_prompt.hide()
        self.status.setText("未加入曲库；之后仍可通过「选择 MIDI 文件」再次导入。")

    def change_timing(self, *_):
        self.note_gap.setValue(round(TIMINGS[self.timing_preset.currentData()].gap * 1000))
        self.rebuild()

    def suggest_melody(self):
        if not self.song:
            return
        choices = rank_melodies(self.song, self.profile)
        if choices:
            best = choices[0]
            self.track.blockSignals(True)
            self.channel.blockSignals(True)
            self.track.setCurrentIndex(self.track.findData(best.track))
            self.channel.setCurrentIndex(self.channel.findData(best.channel))
            self.track.blockSignals(False)
            self.channel.blockSignals(False)
            self.track.setToolTip(f"推荐声部 {best.track + 1} / 乐器通道 {best.channel + 1}：{best.reason}")
            self.status.setText("已推荐旋律，可直接开始预览；如需更换声部，请展开高级设置。")
        else:
            self.channel.blockSignals(True)
            self.channel.setCurrentIndex(0)
            self.channel.blockSignals(False)
            self.status.setText("未找到合适的旋律，请在高级设置中选择声部。")
        self.rebuild()

    def compile_plan(self, **overrides):
        options = dict(track=self.track.currentData(), channel=self.channel.currentData(),
                       transpose=self.transpose.value(), fold=self.fold.isChecked(),
                       chords=self.voicing.currentData(), exclude_drums=self.drums.isChecked(),
                       note_gap=self.note_gap.value() / 1000, speed=self.speed.value(),
                       timing=TIMINGS[self.timing_preset.currentData()], density=self.density.currentData(),
                       trim_leading=self.trim.isChecked(), onset_window=self.onset_window.value() / 1000)
        options.update(overrides)
        return build_plan(self.song, self.profile, **options)

    def suggest_octave(self):
        if not self.song:
            return
        shift = self.recommended_shift()
        self.transpose.setValue(shift)
        self.status.setText(f"已推荐 {shift:+d} 半音（整八度）移调；可手动调整。")

    def suggest_speed(self):
        if not self.song:
            return
        current = round(self.speed.value() * 100)
        strategy = self.density.currentData() if self.density.currentData() != "complete" else "score"
        best_speed, best_plan = self.speed.value(), self.compile_plan(density=strategy)
        for percent in sorted({current, 25, *range(current // 5 * 5, 24, -5)}, reverse=True):
            candidate = self.compile_plan(speed=percent / 100, density=strategy)
            if candidate.density_dropped < best_plan.density_dropped:
                best_speed, best_plan = percent / 100, candidate
            if candidate.density_dropped == 0:
                best_speed, best_plan = percent / 100, candidate
                break
        self.speed.setValue(best_speed)
        self.density.setCurrentIndex(self.density.findData(strategy))
        self.status.setText(f"建议 {best_speed:.2f} 倍速：过密跳过 {best_plan.density_dropped} 个。音轨和复音取舍仍需按听感调整。")

    def restore_original(self):
        self.speed.setValue(1.0)
        self.onset_window.setValue(0)
        self.density.setCurrentIndex(self.density.findData("score"))
        self.trim.setChecked(False)
        self.rebuild()
        self.status.setText("已恢复原始起音节奏。键鼠时序限制仍可能要求跳过过密音符，详见计数。")

    def choose_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择乐器配置", "", "JSON (*.json)")
        if not path or not self.emergency_stop():
            return
        try:
            profile = load_profile(Path(path))
            if not profile.midi_notes:
                raise ValueError("配置中没有 MIDI 音高映射")
            self.profile = profile
            self.profile_label.setText(f"乐器：{profile.name}")
            self.suggest_melody()
            self.apply_range()
        except Exception as exc:
            self.status.setText(f"乐器配置载入失败：{exc}")

    def rebuild(self, *_):
        if not self.song:
            return
        try:
            self.plan = self.compile_plan()
            p = self.plan
            self.rhythm_info.setText(self.song.rhythm.describe(self.speed.value()))
            self.update_beat(0)
            self.summary.setText(
                f"预计 {p.duration:.1f} 秒 | 原谱按倍速 {p.source_duration:.1f} 秒 | 实际编排 {p.played} 音\n"
                f"选中 {p.selected} | 复音简化 {p.simplified} | 折回 {p.folded} | 超音域跳过 {p.skipped} | 过密跳过 {p.density_dropped}\n"
                f"最大顺延 {p.max_shift * 1000:.0f} ms。过密跳过较多时请降低倍速或选择音符优先。\n"
                + "；".join(self.song.warnings)
            )
            self.play_button.setEnabled(bool(p.actions))
            self.optimize_button.setEnabled(True)
            bpms = [60000000 / t.microseconds for t in self.song.rhythm.tempos]
            bpm = f"{min(bpms):.1f}" if max(bpms) == min(bpms) else f"{min(bpms):.1f}–{max(bpms):.1f}"
            default = "默认" if not self.song.rhythm.tempos[0].explicit else ""
            bpm_text = f"{bpm}（{default}）" if default else bpm
            self.file_info.setText(info_html(self.clock_text(self.song.duration), bpm_text,
                                            str(len(self.song.notes))))
            self.file_info.setToolTip(self.song.rhythm.describe())
            notes = sorted((n for n in self.song.notes if
                            (self.track.currentData() is None or n.track == self.track.currentData()) and
                            (self.channel.currentData() is None or n.channel == self.channel.currentData()) and
                            (not self.drums.isChecked() or n.channel != 9)), key=lambda n: n.start)
            # Diagnostic only: count onset groups, never alter the compiled timeline.
            chords, group_start, count = 0, None, 0
            for note in notes:
                if group_start is None or note.start - group_start > self.onset_window.value() / 1000 + 1e-9:
                    chords += int(count > 1)
                    group_start, count = note.start, 1
                else:
                    count += 1
            chords += int(count > 1)
            outside = sum(self.profile.binding(n.pitch + self.transpose.value()) is None for n in notes)
            recommended = bool(rank_melodies(self.song, self.profile))
            shift = self.recommended_shift()
            dense = p if self.density.currentData() == "score" else self.compile_plan(density="score")
            track_text = "全部声部" if self.track.currentData() is None else f"声部 {self.track.currentData() + 1}"
            channel_text = "全部通道" if self.channel.currentData() is None else f"通道 {self.channel.currentData() + 1}"
            advice = ("音域与节奏已适配，可直接演奏。" if dense.density_dropped == 0
                      else "仍有音符过快，点「一键优化」或降低速度可减少漏音。")
            self.analysis_label.setText(
                f"{'已找到推荐旋律' if recommended else '未找到推荐旋律，请手动选择'} · 推荐移调 {shift:+d} 半音 · "
                f"{track_text} / {channel_text} · 超音域 {outside} · 和弦 {chords} 组 · 过快 {dense.density_dropped}\n"
                f"当前编排：实际演奏 {p.played} 音，预计 {p.duration:.1f} 秒。{advice}")
            self.analysis_label.setToolTip("统计当前声部与移调后的音符。和弦指同时或在归组窗口内开始的多个音；"
                                          "过快指当前速度下无法按原谱时刻容纳、需要跳过的音。超音域在八度折回前统计。")
            if self.start_at > p.duration:
                self.start_at = 0.0
            self.set_start_position(self.start_at)
        except Exception as exc:
            self.plan = None
            self.play_button.setEnabled(False)
            self.status.setText(f"无法生成播放计划：{exc}")

    def set_real_input(self, enabled):
        if not self.emergency_stop():
            return
        try:
            self.backend = SendInputBackend(self.profile) if enabled else MockInputBackend()
            self.enable.blockSignals(True)
            self.enable.setChecked(enabled)
            self.enable.blockSignals(False)
            self.mode.setText("游戏演奏：开始后请在倒计时内切回游戏。" if enabled else "预览只检查演奏进度，不发声，也不控制游戏。")
            self.status.setText("游戏演奏模式已就绪：点击「开始演奏」，并在倒计时内切回游戏。"
                                if enabled else "已切回预览模式：只显示进度，不发送按键。")
            self.sync_choice(self.input_mode, enabled, "游戏演奏模式" if enabled else "预览模式")
            self.refresh_emergency_style()
        except Exception as exc:
            self.status.setText(f"无法启用真实输入：{exc}")

    def _before_play(self):
        # Worker-only: no Qt widget access here.
        if isinstance(self.backend, MockInputBackend):
            self._snapshot = "预览播放：未访问真实桌面，未发送真实输入。"
            return
        snapshot = capture_foreground()
        self._snapshot = format_snapshot(snapshot)
        self._target = snapshot["window_handle"]
        if snapshot["target"]["pid"] == os.getpid():
            raise RuntimeError("倒计时结束时仍在本软件，请切回游戏后再试")
        sender = snapshot["sender"]["integrity"]
        target = snapshot["target"]["integrity"]
        if sender is not None and target is not None and target > sender:
            raise RuntimeError("游戏权限高于测试器，请以匹配权限重新启动测试器")

    def _guard(self):
        return isinstance(self.backend, MockInputBackend) or foreground_window() == self._target

    def play(self):
        if not self.plan or not self.plan.actions or self.engine and not self.engine.done.is_set():
            return
        try:
            self._start_playback(self.start_at)
        except Exception as exc:
            self.emergency_stop()
            self.status.setText(f"播放失败：{exc}")

    def _start_playback(self, position=None, delay=None):
        if not self.plan or not self.plan.actions:
            return
        position = self.start_at if position is None else max(0.0, min(position, self.plan.duration))
        sliced = slice_plan(self.plan, position)
        if not sliced.actions:
            self.set_start_position(0.0)
            self.status.setText("该位置之后没有可演奏的音符，已回到起点。")
            return
        self.start_at = position
        self._snapshot, self._target, self._reported = "", None, False
        self.progress.blockSignals(True)
        self.progress.setValue(int(1000 * position / max(self.plan.duration, 0.001)))
        self.progress.blockSignals(False)
        self.diagnostics.clear()
        self.engine = PlaybackEngine(self.backend, before_play=self._before_play, guard=self._guard)
        self.lock(True)
        self.engine.start(sliced, speed=self.speed.value(),
                          delay=self.delay.value() if delay is None else delay, start_at=position)

    def lock(self, busy):
        if busy:
            self.tabs.setCurrentWidget(self.play_page)
        for widget in self.settings:
            widget.setEnabled(not busy)
        self.enable.setEnabled(not busy)
        self.input_mode.setEnabled(not busy)
        # Keep the stop controls reachable: no page switching while busy.
        for page in (self.library_page, self.score_page, self.advanced_page):
            self.tabs.setTabEnabled(self.tabs.indexOf(page), not busy)
        self.update_library_actions()
        self.progress.setEnabled(not busy and bool(self.plan))
        self.seek_back_button.setEnabled(bool(self.plan))
        self.seek_forward_button.setEnabled(bool(self.plan))
        self.play_button.setVisible(not busy)
        self.pause_button.setVisible(busy)
        self.play_button.setEnabled(not busy and bool(self.plan and self.plan.actions))
        self.optimize_button.setEnabled(not busy and self.song is not None)
        self._update_play_button()
        self.refresh_emergency_style()

    def refresh_emergency_style(self):
        active = self.enable.isChecked() or self.engine is not None
        self.stop_button.setStyleSheet("background: #ac243b; color: white; font-weight: bold;" if active else "")
        self.stop_button.setText("停止演奏 · F12" if self.engine else "紧急停止 · F12")

    def poll(self):
        engine = self.engine
        if not engine:
            return
        if self._snapshot and self.diagnostics.toPlainText() != self._snapshot:
            self.diagnostics.setPlainText(self._snapshot)
        if engine.done.is_set():
            if self._reported:
                return
            self._reported = True
            error = engine.error
            completed = engine.state == "completed"
            was_mock = isinstance(engine.backend, MockInputBackend)
            if not self.emergency_stop():
                return
            if error:
                self.status.setText(f"播放已停止：{error}")
                self.diagnostics.appendPlainText("".join(traceback.format_exception(error)))
            elif completed:
                self.start_at = 0.0
                self.progress.blockSignals(True)
                self.progress.setValue(1000)
                self.progress.blockSignals(False)
                self._update_play_button()
                self.time_label.setText(f"{self.clock_text(engine.duration)} / {self.clock_text(engine.duration)}")
                self.status.setText("整曲预览完成（未发送真实输入）" if was_mock else "演奏完成，已释放输入并回到预览模式")
            return
        if engine.state == "countdown":
            hint = "预览不会发声" if isinstance(self.backend, MockInputBackend) else "请切回游戏"
            prefix = f"从 {self.clock_text(engine.base)} " if engine.base > 0.05 else ""
            remaining = max(0.0, engine.origin - engine.clock())
            self.progress_header.setCurrentIndex(1)
            self.countdown_label.setText(str(max(0, math.ceil(remaining - 0.05))))
            self.status.setText(f"{prefix}{remaining:.1f} 秒后开始，{hint}")
        else:
            self.progress_header.setCurrentIndex(0)
            self.progress.blockSignals(True)
            self.progress.setValue(int(1000 * engine.position / max(engine.duration, 0.001)))
            self.progress.blockSignals(False)
            self.update_beat(engine.position)
            self.time_label.setText(f"{self.clock_text(engine.position)} / {self.clock_text(engine.duration)}")
            self.status.setText("正在预览，不会控制游戏或发声。" if isinstance(self.backend, MockInputBackend) else "正在游戏中演奏；F12 停止，F9/F10 前后 10 秒。")

    def update_beat(self, position):
        if not self.song or not self.plan:
            return
        p = self.plan
        if self.density.currentData() == "complete" and p.source_cues:
            index = max(0, bisect_right([t for t, _ in p.source_cues], position) - 1)
            source = p.source_cues[index][1]
            prefix = "顺延模式，最近起音原谱拍位"
        else:
            source = p.trimmed + max(0.0, position - (p.timing.lead if p.timing else 0)) * (p.compiled_speed or 1)
            prefix = "原谱拍位"
        beat = self.song.rhythm.at(source)
        self.beat_label.setText(
            f"{prefix}：第 {beat.bar} 小节 / 第 {beat.beat:.2f} 拍（{beat.numerator}/{beat.denominator}） | "
            f"当前四分音符 BPM {beat.quarter_bpm * self.speed.value():.2f}"
        )

    def emergency_stop(self):
        resume_at = self.start_at
        try:
            if self.engine:
                if not self.engine.stop():
                    raise RuntimeError("播放线程尚未结束，请重试停止")
                if self.engine.state not in ("ready", "countdown"):
                    resume_at = self.engine.position
                self.engine.retry_release()
            else:
                self.backend.release_all()
        except Exception as exc:
            self.lock(True)
            self.status.setText(f"停止/释放尚未完成，请重试：{exc}")
            return False
        self.engine = None
        self.backend = MockInputBackend()
        self.enable.blockSignals(True)
        self.enable.setChecked(False)
        self.enable.blockSignals(False)
        self.progress_header.setCurrentIndex(0)
        self.countdown_label.setText("")
        self.lock(False)
        self.set_start_position(resume_at)
        self.sync_choice(self.input_mode, False, "预览模式")
        self.mode.setText("预览只检查演奏进度，不发声，也不控制游戏。")
        self.status.setText("已停止，输入已释放")
        return True

    def closeEvent(self, event):
        event.accept() if self.emergency_stop() else event.ignore()
