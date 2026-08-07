import base64
import ctypes
import sys
from ctypes import wintypes


class DataBlob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_byte))]


def _local_free(pointer: ctypes.POINTER(ctypes.c_byte)) -> None:
    local_free = ctypes.windll.kernel32.LocalFree
    local_free.argtypes = [ctypes.c_void_p]
    local_free.restype = ctypes.c_void_p
    local_free(pointer)


def protect_api_key(api_key: str) -> str:
    """使用 Windows DPAPI 为当前账户加密密钥。"""
    if not api_key:
        return ""
    if sys.platform != "win32":
        raise OSError("当前系统不支持 Windows 密钥加密。")

    raw = api_key.encode("utf-8")
    raw_buffer = ctypes.create_string_buffer(raw)
    input_blob = DataBlob(len(raw), ctypes.cast(raw_buffer, ctypes.POINTER(ctypes.c_byte)))
    output_blob = DataBlob()
    crypt32 = ctypes.windll.crypt32
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(DataBlob),
        ctypes.c_wchar_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(DataBlob),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    if not crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        "Remielle Desktop Pet API key",
        None,
        None,
        None,
        0,
        ctypes.byref(output_blob),
    ):
        raise ctypes.WinError()
    try:
        encrypted = ctypes.string_at(output_blob.data, output_blob.size)
        return base64.b64encode(encrypted).decode("ascii")
    finally:
        _local_free(output_blob.data)


def unprotect_api_key(encrypted_api_key: str) -> str:
    """解密当前 Windows 账户保存的密钥。"""
    if not encrypted_api_key or sys.platform != "win32":
        return ""
    try:
        raw = base64.b64decode(encrypted_api_key, validate=True)
    except (ValueError, TypeError) as exc:
        raise OSError("保存的密钥格式无法识别。") from exc

    raw_buffer = ctypes.create_string_buffer(raw)
    input_blob = DataBlob(len(raw), ctypes.cast(raw_buffer, ctypes.POINTER(ctypes.c_byte)))
    output_blob = DataBlob()
    crypt32 = ctypes.windll.crypt32
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(DataBlob),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    if not crypt32.CryptUnprotectData(
        ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output_blob)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output_blob.data, output_blob.size).decode("utf-8")
    finally:
        _local_free(output_blob.data)
