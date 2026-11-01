"""Peak memory of this process in MB, on Linux and Windows."""
import sys


def peak_mb():
    if sys.platform == "win32":
        import ctypes
        import ctypes.wintypes as wt

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t), ("a", ctypes.c_size_t), ("b", ctypes.c_size_t),
                        ("c", ctypes.c_size_t), ("d", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]

        k = ctypes.WinDLL("kernel32")
        k.GetCurrentProcess.restype = wt.HANDLE
        p = ctypes.WinDLL("psapi")
        p.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]
        m = PMC()
        m.cb = ctypes.sizeof(m)
        p.GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(m), m.cb)
        return m.PeakWorkingSetSize / 2**20
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
