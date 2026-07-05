from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path
import sys
from typing import Optional
import hashlib

LOGGER = logging.getLogger("osfr_launcher")

_PBKDF2_ITERATIONS = 200_000
_KEY_FILE = ".launcher_key"
_CRED_FILE = ".launcher_cred"

# ── File-based encryption helpers (no external deps) ────────────────────

def _load_or_create_master_key(app_dir: Path) -> bytes:
    key_path = app_dir / _KEY_FILE
    if key_path.exists():
        return key_path.read_bytes()
    key = os.urandom(32)
    key_path.write_bytes(key)
    # Restrict permissions on POSIX; best-effort on Windows.
    try:
        key_path.chmod(0o600)
    except OSError:
        pass
    return key


def _encrypt_token(plaintext: str, master_key: bytes) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", master_key, salt, _PBKDF2_ITERATIONS, dklen=32)
    plain_bytes = plaintext.encode("utf-8")
    result = bytearray()
    counter = 0
    offset = 0
    while offset < len(plain_bytes):
        chunk = plain_bytes[offset : offset + 32]
        keystream = hashlib.sha256(dk + counter.to_bytes(4, "big")).digest()[: len(chunk)]
        for a, b in zip(chunk, keystream):
            result.append(a ^ b)
        offset += 32
        counter += 1
    return base64.b64encode(salt + bytes(result)).decode("ascii")


def _decrypt_token(payload: str, master_key: bytes) -> Optional[str]:
    try:
        data = base64.b64decode(payload)
    except (ValueError, TypeError):
        return None
    if len(data) < 16:
        return None
    salt, ciphertext = data[:16], data[16:]
    dk = hashlib.pbkdf2_hmac("sha256", master_key, salt, _PBKDF2_ITERATIONS, dklen=32)
    result = bytearray()
    counter = 0
    offset = 0
    while offset < len(ciphertext):
        chunk = ciphertext[offset : offset + 32]
        keystream = hashlib.sha256(dk + counter.to_bytes(4, "big")).digest()[: len(chunk)]
        for a, b in zip(chunk, keystream):
            result.append(a ^ b)
        offset += 32
        counter += 1
    try:
        return result.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _load_cred_file(app_dir: Path) -> dict[str, str]:
    cred_path = app_dir / _CRED_FILE
    if not cred_path.exists():
        return {}
    try:
        data = json.loads(cred_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        LOGGER.warning("Corrupt credential file %s; starting fresh", cred_path)
    return {}


def _save_cred_file(app_dir: Path, store: dict[str, str]) -> None:
    cred_path = app_dir / _CRED_FILE
    try:
        cred_path.write_text(json.dumps(store, indent=0), encoding="utf-8")
        try:
            cred_path.chmod(0o600)
        except OSError:
            pass
    except OSError as exc:
        LOGGER.error("Failed to write credential file %s: %s", cred_path, exc)


# ── File-based credential backend ──────────────────────────────────────

def _file_save(app_dir: Path, profile_key: str, username: str, password: str) -> bool:
    try:
        master_key = _load_or_create_master_key(app_dir)
        store = _load_cred_file(app_dir)
        token = _encrypt_token(password, master_key)
        store[profile_key] = token
        _save_cred_file(app_dir, store)
        LOGGER.info("Saved password to encrypted file for profile=%s", profile_key)
        return True
    except OSError as exc:
        LOGGER.error("File credential save failed for %s: %s", profile_key, exc)
        return False


def _file_load(app_dir: Path, profile_key: str) -> Optional[str]:
    try:
        master_key = _load_or_create_master_key(app_dir)
        store = _load_cred_file(app_dir)
        token = store.get(profile_key)
        if token is None:
            return None
        password = _decrypt_token(token, master_key)
        if password is None:
            LOGGER.warning("Failed to decrypt credential for profile=%s", profile_key)
        return password
    except OSError as exc:
        LOGGER.error("File credential load failed for %s: %s", profile_key, exc)
        return None


def _file_delete(app_dir: Path, profile_key: str) -> bool:
    try:
        store = _load_cred_file(app_dir)
        if profile_key in store:
            del store[profile_key]
            _save_cred_file(app_dir, store)
        LOGGER.info("Deleted encrypted credential for profile=%s", profile_key)
        return True
    except OSError as exc:
        LOGGER.error("File credential delete failed for %s: %s", profile_key, exc)
        return False


# ── Windows Credential Manager backend (ctypes, no deps) ───────────────

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes

    CRED_TYPE_GENERIC = 1
    CRED_PERSIST_LOCAL_MACHINE = 2
    _TARGET_PREFIX = "OSFRLauncher"

    class _CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", ctypes.wintypes.DWORD),
            ("Type", ctypes.wintypes.DWORD),
            ("TargetName", ctypes.wintypes.LPWSTR),
            ("Comment", ctypes.wintypes.LPWSTR),
            ("LastWritten", ctypes.wintypes.FILETIME),
            ("CredentialBlobSize", ctypes.wintypes.DWORD),
            ("CredentialBlob", ctypes.wintypes.LPBYTE),
            ("Persist", ctypes.wintypes.DWORD),
            ("AttributeCount", ctypes.wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", ctypes.wintypes.LPWSTR),
            ("UserName", ctypes.wintypes.LPWSTR),
        ]

    _advapi32 = ctypes.windll.advapi32

    _CredWriteW = _advapi32.CredWriteW
    _CredWriteW.argtypes = [ctypes.POINTER(_CREDENTIAL), ctypes.wintypes.DWORD]
    _CredWriteW.restype = ctypes.wintypes.BOOL

    _CredReadW = _advapi32.CredReadW
    _CredReadW.argtypes = [
        ctypes.wintypes.LPCWSTR,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    _CredReadW.restype = ctypes.wintypes.BOOL

    _CredDeleteW = _advapi32.CredDeleteW
    _CredDeleteW.argtypes = [ctypes.wintypes.LPCWSTR, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD]
    _CredDeleteW.restype = ctypes.wintypes.BOOL

    _CredFree = _advapi32.CredFree
    _CredFree.argtypes = [ctypes.c_void_p]
    _CredFree.restype = None

    def _cm_target(profile_key: str) -> str:
        return f"{_TARGET_PREFIX}/{profile_key}"

    def _cm_save(profile_key: str, username: str, password: str) -> bool:
        target = _cm_target(profile_key)
        pw_bytes = (password or "").encode("utf-16-le")
        pw_len = len(pw_bytes)
        cred = _CREDENTIAL(
            Flags=0,
            Type=CRED_TYPE_GENERIC,
            TargetName=target,
            Comment=None,
            LastWritten=ctypes.wintypes.FILETIME(0, 0),
            CredentialBlobSize=pw_len,
            CredentialBlob=ctypes.cast(
                ctypes.create_string_buffer(pw_bytes), ctypes.wintypes.LPBYTE
            ),
            Persist=CRED_PERSIST_LOCAL_MACHINE,
            AttributeCount=0,
            Attributes=None,
            TargetAlias=None,
            UserName=username or "",
        )
        ok = _CredWriteW(cred, 0)
        if not ok:
            LOGGER.warning(
                "CredWriteW failed for %s (error %d); falling back to file encryption",
                target,
                ctypes.GetLastError(),
            )
            return False
        return True

    def _cm_load(profile_key: str) -> Optional[str]:
        target = _cm_target(profile_key)
        p_cred = ctypes.c_void_p()
        ok = _CredReadW(target, CRED_TYPE_GENERIC, 0, ctypes.byref(p_cred))
        if not ok:
            err = ctypes.GetLastError()
            if err != 1168:
                LOGGER.debug("CredReadW failed for %s (error %d)", target, err)
            return None
        try:
            cred = ctypes.cast(p_cred, ctypes.POINTER(_CREDENTIAL)).contents
            size = cred.CredentialBlobSize
            if size == 0:
                return None
            blob = ctypes.cast(
                cred.CredentialBlob, ctypes.POINTER(ctypes.c_char * size)
            ).contents
            return blob.raw[:size].decode("utf-16-le")
        finally:
            _CredFree(p_cred)

    def _cm_delete(profile_key: str) -> bool:
        target = _cm_target(profile_key)
        ok = _CredDeleteW(target, CRED_TYPE_GENERIC, 0)
        if not ok:
            err = ctypes.GetLastError()
            if err != 1168:
                LOGGER.warning("CredDeleteW failed for %s (error %d)", target, err)
                return False
        return True

else:

    def _cm_save(profile_key: str, username: str, password: str) -> bool:
        return False

    def _cm_load(profile_key: str) -> Optional[str]:
        return None

    def _cm_delete(profile_key: str) -> bool:
        return False


# ── Public API ─────────────────────────────────────────────────────────

_APP_DIR: Optional[Path] = None
_USE_CM = sys.platform == "win32"


def init(app_dir: str | Path) -> None:
    global _APP_DIR
    _APP_DIR = Path(app_dir)


def save_password(profile_key: str, username: str, password: str) -> bool:
    global _USE_CM
    if _USE_CM and _cm_save(profile_key, username, password):
        return True
    _USE_CM = False  # Credential Manager failed; use file fallback for future ops
    if _APP_DIR is None:
        LOGGER.error("credential_store.init() not called before save_password")
        return False
    return _file_save(_APP_DIR, profile_key, username, password)


def load_password(profile_key: str) -> Optional[str]:
    global _USE_CM
    if _USE_CM:
        pw = _cm_load(profile_key)
        if pw is not None:
            return pw
    if _APP_DIR is None:
        return None
    return _file_load(_APP_DIR, profile_key)


def delete_password(profile_key: str) -> bool:
    global _USE_CM
    cm_ok = True
    if _USE_CM:
        cm_ok = _cm_delete(profile_key)
    if _APP_DIR is not None:
        _file_delete(_APP_DIR, profile_key)
    return cm_ok
