# -*- coding: utf-8 -*-
"""
  monotonic
  ~~~~~~~~~

  This module provides a ``monotonic()`` function which returns the
  value (in fractional seconds) of a clock which never goes backwards.

  On Python 3.3 or newer, ``monotonic`` will be an alias of
  ``time.monotonic`` from the standard library. On older versions,
  it will fall back to an equivalent implementation:

  +-------------+----------------------------------------+
  | Linux, BSD  | ``clock_gettime(3)``                   |
  +-------------+----------------------------------------+
  | Windows     | ``GetTickCount`` or ``GetTickCount64`` |
  +-------------+----------------------------------------+
  | OS X        | ``mach_absolute_time``                 |
  +-------------+----------------------------------------+

  If no suitable implementation exists for the current platform,
  attempting to import this module (or to import from it) will
  cause a ``RuntimeError`` exception to be raised.


  Copyright 2014, 2015, 2016 Ori Livneh <ori@wikimedia.org>

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.

"""
try:
    import ctypes
    import ctypes.util
except ImportError:  # like in static python
    ctypes = None
import os
import sys
import threading
import time

__all__ = ('monotonic',)

try:
    monotonic = time.monotonic
except AttributeError:
    # if ctypes is not available, use the standard time, no luck here
    if ctypes is None:
        monotonic = time.time
    else:
        try:
            if sys.platform == 'darwin':  # OS X, iOS
                # See Technical Q&A QA1398 of the Mac Developer Library:
                #  <https://developer.apple.com/library/mac/qa/qa1398/>
                libc = ctypes.CDLL('/usr/lib/libc.dylib', use_errno=True)
                
                
                class mach_timebase_info_data_t(ctypes.Structure):
                    """System timebase info. Defined in <mach/mach_time.h>."""
                    _fields_ = (('numer', ctypes.c_uint32),
                                ('denom', ctypes.c_uint32))
                
                
                mach_absolute_time = libc.mach_absolute_time
                mach_absolute_time.restype = ctypes.c_uint64
                
                timebase = mach_timebase_info_data_t()
                libc.mach_timebase_info(ctypes.byref(timebase))
                ticks_per_second = timebase.numer / timebase.denom * 1.0e9
                
                
                def monotonic():
                    """Monotonic clock, cannot go backward."""
                    return mach_absolute_time() / ticks_per_second
            
            elif sys.platform.startswith('win32') or sys.platform.startswith('cygwin'):
                if sys.platform.startswith('cygwin'):
                    # Note: cygwin implements clock_gettime (CLOCK_MONOTONIC = 4) since
                    # version 1.7.6. Using raw WinAPI for maximum version compatibility.
                    
                    # Ugly hack using the wrong calling convention (in 32-bit mode)
                    # because ctypes has no windll under cygwin (and it also seems that
                    # the code letting you select stdcall in _ctypes doesn't exist under
                    # the preprocessor definitions relevant to cygwin).
                    # This is 'safe' because:
                    # 1. The ABI of GetTickCount and GetTickCount64 is identical for
                    #    both calling conventions because they both have no parameters.
                    # 2. libffi masks the problem because after making the call it doesn't
                    #    touch anything through esp and epilogue code restores a correct
                    #    esp from ebp afterwards.
                    try:
                        kernel32 = ctypes.cdll.kernel32
                    except OSError:  # 'No such file or directory'
                        kernel32 = ctypes.cdll.LoadLibrary('kernel32.dll')
                else:
                    kernel32 = ctypes.windll.kernel32
                
                GetTickCount64 = getattr(kernel32, 'GetTickCount64', None)
                if GetTickCount64:
                    # Windows Vista / Windows Server 2008 or newer.
                    GetTickCount64.restype = ctypes.c_ulonglong
                    
                    
                    def monotonic():
                        """Monotonic clock, cannot go backward."""
                        return GetTickCount64() / 1000.0
                
                else:
                    # Before Windows Vista.
                    GetTickCount = kernel32.GetTickCount
                    GetTickCount.restype = ctypes.c_uint32
                    
                    get_tick_count_lock = threading.Lock()
                    get_tick_count_last_sample = 0
                    get_tick_count_wraparounds = 0
                    
                    
                    def monotonic():
                        """Monotonic clock, cannot go backward."""
                        global get_tick_count_last_sample
                        global get_tick_count_wraparounds
                        
                        with get_tick_count_lock:
                            current_sample = GetTickCount()
                            if current_sample < get_tick_count_last_sample:
                                get_tick_count_wraparounds += 1
                            get_tick_count_last_sample = current_sample
                            
                            final_milliseconds = get_tick_count_wraparounds << 32
                            final_milliseconds += get_tick_count_last_sample
                            return final_milliseconds / 1000.0
            
            else:
                try:
                    clib_path = ctypes.util.find_library('c')
                    if clib_path:
                        # NOTE: on alpine linux 2.7, there is a issue with find(c) that is giving back
                        # the full path instead of just the lib name, so use os.path.basename() to strip it
                        clib_path = os.path.basename(clib_path)
                    # NOTE: if none, will get libc :)
                    clock_gettime = ctypes.CDLL(clib_path, use_errno=True).clock_gettime
                except (RuntimeError, AttributeError):  # Exception can very based on system and python compilation
                    rt_path = ctypes.util.find_library('rt')
                    if rt_path is None:
                        raise Exception('The system rt librairy is missing, please install it')
                    clock_gettime = ctypes.CDLL(os.path.basename(rt_path), use_errno=True).clock_gettime
                
                
                class timespec(ctypes.Structure):
                    """Time specification, as described in clock_gettime(3)."""
                    _fields_ = (('tv_sec', ctypes.c_long),
                                ('tv_nsec', ctypes.c_long))
                
                
                if sys.platform.startswith('linux'):
                    CLOCK_MONOTONIC = 1
                elif sys.platform.startswith('freebsd'):
                    CLOCK_MONOTONIC = 4
                elif sys.platform.startswith('sunos5'):
                    CLOCK_MONOTONIC = 4
                elif 'bsd' in sys.platform:
                    CLOCK_MONOTONIC = 3
                elif sys.platform.startswith('aix'):
                    CLOCK_MONOTONIC = ctypes.c_longlong(10)
                
                
                def monotonic():
                    """Monotonic clock, cannot go backward."""
                    ts = timespec()
                    if clock_gettime(CLOCK_MONOTONIC, ctypes.pointer(ts)):
                        errno = ctypes.get_errno()
                        raise OSError(errno, os.strerror(errno))
                    return ts.tv_sec + ts.tv_nsec / 1.0e9
            
            # Perform a sanity-check.
            if monotonic() - monotonic() > 0:
                raise ValueError('monotonic() is not monotonic!')
        
        except Exception as exp:
            from opsbro.log import logger
            
            logger.debug('DEV-WARNING: No suitable implementation of a monotonic clock for this system (%s:%s), using standard time' % (type(exp), exp))
            monotonic = time.time
