import socket
import platform
from typing import Optional
from src.exceptions import AvailablePortNotFoundError


def find_port(port: int, max_port: int = 49151) -> int:
    """Find a port not in ues starting at given port"""
    if port > max_port:
        raise AvailablePortNotFoundError(
            f"Failed to found an available port lesser than \
                or equal to {max_port}"
        )
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("localhost", port)) == 0:
            return find_port(port=port + 1)
        else:
            return port


def get_device_id() -> Optional[str]:
    def get_linux_id() -> Optional[str]:
        try:
            with open("/etc/machine-id") as f:
                return f.read().strip()
        except FileNotFoundError:
            return None  # Not found

    def get_windows_id() -> Optional[str]:
        import ctypes

        try:
            vol_serial = ctypes.c_uint32(0)
            ctypes.windll.kernel32.GetVolumeInformationW(
                "C:\\", None, 0, ctypes.byref(vol_serial), None, 0, None, 0
            )
            return f"{vol_serial.value:08X}"  # 8-digit hex
        except Exception:
            return None

    def get_mac_id() -> Optional[str]:
        import subprocess

        try:
            output = subprocess.check_output(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"]
            ).decode()
            for line in output.splitlines():
                if "IOPlatformUUID" in line:
                    return line.split("=")[-1].strip().strip('"')
        except Exception:
            return None

    os_name = platform.system()
    if os_name == "Linux":
        return get_linux_id()
    elif os_name == "Windows":
        return get_windows_id()
    elif os_name == "Darwin":
        return get_mac_id()
    else:
        return None
        # Fallback: MAC + Hostname
        # return f"{hex(uuid.getnode())[2:]}-{socket.gethostname()}"
