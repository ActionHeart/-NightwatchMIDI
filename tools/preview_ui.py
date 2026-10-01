"""Render the default Mock UI offscreen without interacting with the desktop."""
import os
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--scale", type=float, default=1)
parser.add_argument("--advanced", action="store_true")
parser.add_argument("--library", action="store_true")
parser.add_argument("--score", action="store_true")
parser.add_argument("--playing", action="store_true")
parser.add_argument("--size", default="", help="custom logical size WxH, e.g. 1400x820")
parser.add_argument("--file", default="tests/fixtures/twinkle_twinkle.mid")
args = parser.parse_args()
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_SCALE_FACTOR"] = str(args.scale)
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QFont
from nightwatch_midi.ui.main_window import MainWindow

app = QApplication([])
font_file = Path("C:/Windows/Fonts/msyh.ttc")
if font_file.exists():
    font_id = QFontDatabase.addApplicationFont(str(font_file))
    families = QFontDatabase.applicationFontFamilies(font_id)
    if families:
        app.setFont(QFont(families[0], 9))
window = MainWindow()
root = Path(__file__).resolve().parents[1]
window.player.load_file(root / args.file)
player = window.player
page = (player.advanced_page if args.advanced else player.score_page if args.score
        else player.library_page if args.library else player.play_page)
player.tabs.setCurrentWidget(page)
if args.score:
    player.load_score_example()
    player.preview_score()
if args.playing:
    player.play()  # Default mock backend only; never sends desktop input.
if args.size:
    width, height = (int(value) for value in args.size.lower().split("x"))
    window.resize(width, height)
window.show()
app.processEvents()
player.poll()
output = root / "artifacts"
output.mkdir(exist_ok=True)
name = "midi_player" if args.scale == 1 else f"midi_player_{round(args.scale * 100)}"
name += f"_{args.size.lower()}" if args.size else ""
name += "_advanced" if args.advanced else "_library" if args.library else "_score" if args.score else ""
name += "_playing" if args.playing else ""
window.grab().save(str(output / f"{name}.png"))
report = {"scale": args.scale, "logical_size": [window.width(), window.height()],
          "physical_size": [round(window.width() * args.scale), round(window.height() * args.scale)],
          "page": player.tabs.tabText(player.tabs.currentIndex()),
          "basic_controls_visible": all(w.isVisible() and window.rect().contains(w.mapTo(window, w.rect().bottomRight()))
                                        for w in (player.open_button, player.input_mode, player.stop_button)),
          "advanced_visible": player.advanced.isVisible(),
          "library_items": player.library_list.count(),
          "playing": args.playing}
if not args.size:
    assert window.height() <= 650, "Main controls must fit the 1080p / 150% work area"
(output / f"{name}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
window.close()
print(json.dumps(report))
