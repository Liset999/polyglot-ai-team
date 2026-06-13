import os
import platform
import subprocess


def memory_usage_percent():
    system = platform.system().lower()
    if system == "windows":
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        return float(status.dwMemoryLoad)

    if os.path.exists("/proc/meminfo"):
        values = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                key, value = line.split(":", 1)
                values[key] = int(value.strip().split()[0])
        total = values["MemTotal"]
        available = values.get("MemAvailable", values.get("MemFree", 0))
        return (total - available) / total * 100

    if system == "darwin":
        output = subprocess.check_output(["vm_stat"], text=True)
        pages = {}
        for line in output.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                pages[key] = int(value.strip().strip("."))
        used = pages.get("Pages active", 0) + pages.get("Pages wired down", 0)
        free = pages.get("Pages free", 0) + pages.get("Pages inactive", 0)
        return used / max(used + free, 1) * 100

    raise RuntimeError(f"Unsupported platform: {platform.system()}")


if __name__ == "__main__":
    print(f"Memory usage: {memory_usage_percent():.1f}%")
