"""Optional native hash on ARMv7; the public Python solver stays the fallback."""
from pathlib import Path
import platform
import time


def native_library(path=None):
    try:
        import ctypes
        if path is None:
            if not platform.machine().lower().startswith('arm') or ctypes.sizeof(ctypes.c_void_p)!=4:return None
            path=Path(__file__).with_name('libmkekino_pow_armv7.so')
        lib=ctypes.CDLL(str(path))
        lib.mk_pow_find.argtypes=[ctypes.c_char_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_uint32]
        lib.mk_pow_find.restype=ctypes.c_int64
        lib.mk_pow_zero_bits.argtypes=[ctypes.c_char_p,ctypes.c_uint32]
        lib.mk_pow_zero_bits.restype=ctypes.c_uint32
        # Fixed, non-secret test vector; reject an incompatible library.
        if lib.mk_pow_zero_bits(b'example:0',9)!=2:return None
        return lib
    except (ImportError,OSError,AttributeError):return None


def make_solver(path=None):
    lib=native_library(path)
    if lib is None:return None
    def solve(nonce,difficulty,timeout,progress=None):
        if difficulty<=0:return '0',0
        value=bytes(ord(ch)&255 for ch in nonce)
        if len(value)>4096 or not 0<=difficulty<=256:return None,0
        start=time.monotonic();shown=start;counter=0
        while counter<2**32:
            count=min(256,2**32-counter)
            result=lib.mk_pow_find(value,len(value),counter,count,difficulty)
            if result>=0:return str(result),result+1
            if result!=-1:return None,counter
            counter+=count
            now=time.monotonic()
            if now-start>=timeout:return None,counter
            if progress and now-shown>=1:
                shown=now;progress(int(now-start))
        return None,counter
    return solve
