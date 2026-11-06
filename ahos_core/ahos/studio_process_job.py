"""Owned process-tree lifetime limits; NOT a filesystem/network sandbox."""
from __future__ import annotations
import ctypes
from ctypes import wintypes as w
import os,time

class WindowsJob:
    def __init__(self, memory_bytes=256*1024*1024):
        class Basic(ctypes.Structure):
            _fields_=[('User',ctypes.c_int64),('Job',ctypes.c_int64),('Flags',w.DWORD),('Min',ctypes.c_size_t),('Max',ctypes.c_size_t),('Active',w.DWORD),('Affinity',ctypes.c_size_t),('Priority',w.DWORD),('Scheduling',w.DWORD)]
        class IO(ctypes.Structure):
            _fields_=[(name,ctypes.c_uint64) for name in ('ReadOps','WriteOps','OtherOps','ReadBytes','WriteBytes','OtherBytes')]
        class Extended(ctypes.Structure):
            _fields_=[('Basic',Basic),('IO',IO),('ProcessMemory',ctypes.c_size_t),('JobMemory',ctypes.c_size_t),('PeakProcess',ctypes.c_size_t),('PeakJob',ctypes.c_size_t)]
        self.api=ctypes.WinDLL('kernel32',use_last_error=True)
        for name,args,result in [('CreateJobObjectW',[ctypes.c_void_p,w.LPCWSTR],w.HANDLE),('SetInformationJobObject',[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD],w.BOOL),('AssignProcessToJobObject',[w.HANDLE,w.HANDLE],w.BOOL),('CloseHandle',[w.HANDLE],w.BOOL),('TerminateJobObject',[w.HANDLE,w.UINT],w.BOOL),('QueryInformationJobObject',[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD,ctypes.c_void_p],w.BOOL)]:
            fn=getattr(self.api,name);fn.argtypes=args;fn.restype=result
        self.handle=self.api.CreateJobObjectW(None,None)
        if not self.handle:raise ctypes.WinError(ctypes.get_last_error())
        info=Extended();info.Basic.Flags=0x2000|0x200|0x8 # kill on close, total job memory, active process cap
        info.Basic.Active=16;info.JobMemory=memory_bytes
        if not self.api.SetInformationJobObject(self.handle,9,ctypes.byref(info),ctypes.sizeof(info)):
            error=ctypes.get_last_error();self.close();raise ctypes.WinError(error)
    def assign(self,process):
        if not self.api.AssignProcessToJobObject(self.handle,w.HANDLE(int(process._handle))):
            raise ctypes.WinError(ctypes.get_last_error())
    def close(self):
        if not self.handle:return True
        class Accounting(ctypes.Structure):
            _fields_=[('User',ctypes.c_int64),('Kernel',ctypes.c_int64),('PeriodUser',ctypes.c_int64),('PeriodKernel',ctypes.c_int64),('Faults',w.DWORD),('Total',w.DWORD),('Active',w.DWORD),('Terminated',w.DWORD)]
        self.api.TerminateJobObject(self.handle,124)
        deadline=time.monotonic()+3;verified=False
        while time.monotonic()<deadline:
            info=Accounting()
            if self.api.QueryInformationJobObject(self.handle,1,ctypes.byref(info),ctypes.sizeof(info),None) and info.Active==0:
                verified=True;break
            time.sleep(.01)
        self.api.CloseHandle(self.handle);self.handle=None
        return verified
