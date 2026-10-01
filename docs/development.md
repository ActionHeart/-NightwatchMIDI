# 开发与发布

## 目录职责

```text
NightwatchMIDI/
├── src/nightwatch_midi/   应用源码（src layout）
│   ├── midi/             MIDI 解析、速度与拍号
│   ├── mapping/          乐器配置、旋律推荐、动作编排
│   ├── playback/         绝对时间调度、停止与跳转
│   ├── input/            输入接口、模拟后端、Windows SendInput
│   ├── game/             前台窗口与权限诊断
│   ├── ui/               PySide6 界面与安全快捷键
│   ├── profiles/         随包分发的 JSON 乐器配置
│   ├── library.py        本机曲库管理
│   └── score.py          按键谱、简谱解析
├── tests/                自动测试，仅模拟输入
├── examples/             三首随包乐谱
├── tools/                开发辅助与源码打包
├── assets/               应用图标源图（运行图标位于包内 assets）
├── docs/                 使用说明、开发说明、界面截图
├── pyproject.toml        项目元数据、依赖和 pytest 设置
├── start.cmd             无控制台启动入口（pythonw）
├── start-debug.cmd       带控制台输出的排查入口（python）
└── LICENSE               MIT 许可证
```

`.venv/` 是本机环境，不提交；`artifacts/` 是工具生成的临时报告和截图；`dist/` 是生成的发布包。这些目录均被 Git 忽略。运行时曲库位于 `%APPDATA%/NightwatchMIDI/library`，不属于源码目录。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
```

测试通过 fixture 阻止真实 SendInput 构造和发送，并隔离本机曲库及桌面诊断。请勿编写会向真实桌面发送事件的自动测试。

## 辅助工具

| 脚本 | 用途 |
| --- | --- |
| `tools/create_demo.py` | 重新生成 tests/fixtures 中两份测试 MIDI |
| `tools/preview_ui.py` | 离屏渲染界面，输出到 artifacts |
| `tools/analyze_playback.py` | 离线分析 examples 中的动作编排 |
| `tools/inspect_meter.py` | 查看示例速度与拍号 |
| `tools/build_source_release.py` | 生成白名单源码 ZIP 和文件校验清单 |

## 应用图标

把图标源图（方形最佳）保存为 `assets/icon.png`，生成多尺寸 `src/nightwatch_midi/assets/icon.ico`：

```powershell
.\.venv\Scripts\python.exe tools\make_icon.py
```

`make_icon.py` 用 Qt 居中裁剪并输出 16/24/32/48/64/128/256 的 PNG-in-ICO，不依赖 Pillow。生成后：源码运行会把 `src/nightwatch_midi/assets/icon.ico` 作为窗口/任务栏图标（并设置 AppUserModelID），`build_exe.py` 会自动用它作为 EXE 图标，并把运行图标随 Python 包一起分发。也可构建时用 `--icon 其他.ico` 覆盖。

## 打包 EXE

给玩家的免安装版本使用 PyInstaller 构建：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[packaging]"
.\.venv\Scripts\python.exe tools\build_exe.py
```

默认输出 `dist/NightwatchMIDI.exe`：单文件、`--windowed`（无控制台），已内置 `profiles/*.json`，并排除 QtWebEngine/QtQuick/QtMultimedia 等未使用模块以缩减体积。可选参数：

```powershell
.\.venv\Scripts\python.exe tools\build_exe.py --onedir      # 文件夹版，启动更快
.\.venv\Scripts\python.exe tools\build_exe.py --console     # 保留控制台便于排查
.\.venv\Scripts\python.exe tools\build_exe.py --icon app.ico
```

EXE 未签名，Windows SmartScreen 可能提示；它不包含本机曲库（曲库仍位于 `%APPDATA%\NightwatchMIDI\library`）。修改版本号后再构建，以便 Release 附件与源码包版本一致。

## GitHub 发布

仅将本项目目录作为仓库根目录；不要上传上一级目录、本机虚拟环境或曲库。发布前运行测试，然后生成发布资产：

```powershell
.\.venv\Scripts\python.exe tools/build_exe.py
.\.venv\Scripts\python.exe tools/build_source_release.py
```

`dist/NightwatchMIDI.exe` 作为免安装附件；`dist/NightwatchMIDI-<version>-source.zip` 是源码包（需要 Python 3.11，**不是免安装 EXE**）。源码打包脚本只收集源码、测试、文档和指定的三首乐谱及测试样例，不会收集本机报告、参考源码或个人 MIDI。

依赖的许可证由各依赖自行提供；本项目 MIT 许可不覆盖 PySide6、mido 或用户导入的歌曲。没有自动创建 GitHub 仓库或上传内容。

玩家下载建议使用 dist/NightwatchMIDI-Windows.zip，其中包含 EXE 和 examples 下的三首 MIDI；解压后选择 examples 中的歌曲即可。单独下载 EXE 不包含外置乐谱。
