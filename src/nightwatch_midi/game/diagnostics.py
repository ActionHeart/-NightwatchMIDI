"""Read-only window/token metadata. Never sends input or reads process memory."""
import ctypes
import json
import os
import sys
from ctypes import wintypes as w
from datetime import datetime


def _dll(name):
    if sys.platform != "win32":
        raise OSError("Windows diagnostics require Windows")
    return ctypes.WinDLL(name, use_last_error=True)


def _bind(dll, name, args, result):
    fn = getattr(dll, name)
    fn.argtypes = args
    fn.restype = result
    return fn


def _check(ok):
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())


def process_integrity(pid: int) -> dict:
    """Query only PROCESS_QUERY_LIMITED_INFORMATION / TOKEN_QUERY access."""
    result = {"pid": pid, "integrity": None, "error": None}
    process = token = None
    close = None
    try:
        kernel = _dll("kernel32")
        advapi = _dll("advapi32")
        close = _bind(kernel, "CloseHandle", [w.HANDLE], w.BOOL)
        open_process = _bind(kernel, "OpenProcess", [w.DWORD, w.BOOL, w.DWORD], w.HANDLE)
        open_token = _bind(advapi, "OpenProcessToken", [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)], w.BOOL)
        get_info = _bind(advapi, "GetTokenInformation", [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD)], w.BOOL)
        get_count = _bind(advapi, "GetSidSubAuthorityCount", [ctypes.c_void_p], ctypes.POINTER(ctypes.c_ubyte))
        get_sub = _bind(advapi, "GetSidSubAuthority", [ctypes.c_void_p, w.DWORD], ctypes.POINTER(w.DWORD))
        process = open_process(0x1000, False, pid)
        _check(process)
        token = w.HANDLE()
        _check(open_token(process, 0x0008, ctypes.byref(token)))
        needed = w.DWORD()
        get_info(token, 25, None, 0, ctypes.byref(needed))  # TokenIntegrityLevel
        if not needed.value:
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_string_buffer(needed.value)
        _check(get_info(token, 25, buffer, needed.value, ctypes.byref(needed)))
        # TOKEN_MANDATORY_LABEL starts with SID_AND_ATTRIBUTES, whose first field is PSID.
        sid = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0]
        count = get_count(sid)[0]
        if count == 0:
            raise ValueError("Integrity SID has no sub-authority")
        result["integrity"] = int(get_sub(sid, count - 1)[0])
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        if close:
            if token:
                close(token)
            if process:
                close(process)
    return result


def capture_foreground() -> dict:
    user = _dll("user32")
    foreground = _bind(user, "GetForegroundWindow", [], w.HWND)
    get_pid = _bind(user, "GetWindowThreadProcessId", [w.HWND, ctypes.POINTER(w.DWORD)], w.DWORD)
    get_title = _bind(user, "GetWindowTextW", [w.HWND, w.LPWSTR, ctypes.c_int], ctypes.c_int)
    hwnd = foreground()
    if not hwnd:
        raise OSError("No foreground window is available")
    pid = w.DWORD()
    _check(get_pid(hwnd, ctypes.byref(pid)))
    title = ctypes.create_unicode_buffer(1024)
    get_title(hwnd, title, len(title))
    return {
        "time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "window_title": title.value,
        "window_handle": int(hwnd),
        "sender": process_integrity(os.getpid()),
        "target": process_integrity(pid.value),
    }


def foreground_window() -> int:
    user = _dll("user32")
    return int(_bind(user, "GetForegroundWindow", [], w.HWND)() or 0)


def format_snapshot(snapshot: dict) -> str:
    def describe(info):
        rid = info["integrity"]
        if rid is None:
            return f"PID {info['pid']}，权限未知：{info['error']}"
        label = {0x1000: "低", 0x2000: "中（普通）", 0x2100: "中+", 0x3000: "高（提升）", 0x4000: "系统"}.get(rid, "其他")
        return f"PID {info['pid']}，完整性级别 {label} / 0x{rid:X}"

    sender, target = snapshot["sender"], snapshot["target"]
    lines = [
        f"发送前快照：{snapshot['time']}",
        f"前台窗口：{snapshot['window_title'] or '（无标题）'}",
        f"测试器：{describe(sender)}",
        f"目标：{describe(target)}",
    ]
    if sender["integrity"] is None or target["integrity"] is None:
        lines.append("权限信息不完整，不能判断是否存在权限差异。")
    elif target["integrity"] > sender["integrity"]:
        lines.append("目标完整性级别更高：存在 Windows UIPI 权限限制条件。")
    else:
        lines.append("未发现目标完整性级别高于测试器；仍不代表游戏会接收合成输入。")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(json.dumps([process_integrity(int(pid)) for pid in sys.argv[1:]], ensure_ascii=False))
    else:
        print(format_snapshot(capture_foreground()))
