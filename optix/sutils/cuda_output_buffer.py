import enum, re

import numpy as np
import cupy as cp

from OpenGL.GL import glGenBuffers, glBindBuffer, glBufferData, glBindBuffer, GL_ARRAY_BUFFER, GL_STREAM_DRAW

from optix.sutils.vecmath import vtype_to_dtype


class CudaOutputBufferType(enum.Enum):
    CUDA_DEVICE = 0, # not preferred, typically slower than ZERO_COPY
    GL_INTEROP  = 1, # single device only, preferred for single device
    ZERO_COPY   = 2, # general case, preferred for multi-gpu if not fully nvlink connected
    CUDA_P2P    = 3, # fully connected only, preferred for fully nvlink connected


class CudaOutputBuffer:
    __slots__ = ['_pixel_format', '_buffer_type', '_width', '_height',
            '_device', '_device_idx', '_device', '_stream', 
            '_host_buffer', '_device_buffer', '_pbo']

    def __init__(self, buffer_type, pixel_format, width, height, device_idx=0):
        for attr in self.__slots__:
            setattr(self, attr, None)

        self.device_idx = device_idx
        self.pixel_format = pixel_format
        self.buffer_type = buffer_type
        self.resize(width, height)
        self._reallocate_buffers()
    
    def resize(self, width, height):
        self.width = width
        self.height = height

    def get_host_buffer(self):
        if buffer_type is CudaOutputBufferType.CUDA_DEVICE:
            self.copy_device_to_host()
            return self._host_buffer
        else:
            msg = f'Buffer type {buffer_type} has not been implemented yet.'
            raise NotImplementedError(msg)

    def map(self):
        self._make_current()
        if (self._host_buffer is None) or (self._device_buffer is None):
            self._reallocate_buffers()
        return self._device_buffer.data.ptr

    def unmap(self):
        self._make_current()
        if buffer_type is CudaOutputBufferType.CUDA_DEVICE:
            self._stream.synchronize()
        else:
            msg = f'Buffer type {buffer_type} has not been implemented yet.'
            raise NotImplementedError(msg)

    def get_pbo(self):
        buffer_type = self.buffer_type

        self._make_current()

        if self._pbo is None:
            self._pbo = glGenBuffers(1)

        if buffer_type is CudaOutputBufferType.CUDA_DEVICE:
            self.copy_device_to_host()
            self.copy_host_to_pbo()
        else:
            msg = f'Buffer type {buffer_type} has not been implemented yet.'
            raise NotImplementedError(msg)

        return self._pbo

    def delete_pbo(self):
        if self._pbo is None:
            return
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glDeleteBuffers(1, self._pbo)
        self._pbo = None

    def copy_device_to_host(self):
        cp.cuda.runtime.memcpy(self._host_buffer.__array_interface__['data'][0], 
                self._device_buffer.data.ptr, self._host_buffer.nbytes, cp.cuda.runtime.memcpyDeviceToHost)
    
    def copy_host_to_pbo(self):
        glBindBuffer(GL_ARRAY_BUFFER, self._pbo)
        glBufferData(GL_ARRAY_BUFFER, self._host_buffer, GL_STREAM_DRAW)
        glBindBuffer(GL_ARRAY_BUFFER, 0)

    def _make_current(self):
        self._device.use()

    def _reallocate_buffers(self):
        buffer_type = self.buffer_type
            
        dtype = self.pixel_format
        shape = (self.width, self.height)

        if buffer_type is CudaOutputBufferType.CUDA_DEVICE:
            self._host_buffer = np.empty(shape=shape, dtype=dtype)
            self._device_buffer = cp.empty(shape=shape, dtype=dtype)
            if self._pbo is not None:
                glBindBuffer(GL_ARRAY_BUFFER, self._pbo)
                glBufferData(GL_ARRAY_BUFFER, self._host_buffer, GL_STREAM_DRAW)
                glBindBuffer(GL_ARRAY_BUFFER, 0)
        else:
            msg = f'Buffer type {buffer_type} has not been implemented yet.'
            raise NotImplementedError(msg)
    
    def _get_pixel_format(self):
        return self._pixel_format
    def _set_pixel_format(self, value):
        if isinstance(value, str):
            value = vtype_to_dtype(value)
        assert isinstance(value, np.dtype) or issubclass(value, np.generic), value
        if value != self._pixel_format:
            self._pixel_format = value
            self._host_buffer = None
            self._device_buffer = None
    pixel_format = property(_get_pixel_format, _set_pixel_format)
    
    def _get_buffer_type(self):
        return self._buffer_type
    def _set_buffer_type(self, value):
        assert isinstance(value, CudaOutputBufferType), type(value)
        if value != self._buffer_type:
            self._buffer_type = value
            self._host_buffer = None
            self._device_buffer = None
    buffer_type = property(_get_buffer_type, _set_buffer_type)

    def _get_width(self):
        return self._width
    def _set_width(self, value):
        assert value >= 1, value
        value = np.int32(np.asscalar(value))
        if value != self._width:
            self._width = value
            self._host_buffer = None
            self._device_buffer = None
    width = property(_get_width, _set_width)
    
    def _get_height(self):
        return self._height
    def _set_height(self, value):
        assert value >= 1, value
        value = np.int32(np.asscalar(value))
        if value != self._height:
            self._height = value
            self._host_buffer = None
            self._device_buffer = None
    height = property(_get_height, _set_height)
    
    def _get_device_idx(self):
        return self._device
    def _set_device_idx(self, value):
        if value is None:
            device_idx = 0
        assert value >= 0, value
        value = int(value)
        if value != self._device_idx:
            self._device_idx = value
            self._device = cp.cuda.Device(value)
            self._host_buffer = None
            self._device_buffer = None
    device_idx = property(_get_device_idx, _set_device_idx)
    
    def _get_stream(self):
        return self._stream
    def _set_stream(self, value):
        if value is None:
            value = cp.cuda.Stream.null
        assert isinstance(stream, cp.cuda.Stream), type(stream)
        self._stream = value
    stream = property(_get_stream, _set_stream)
