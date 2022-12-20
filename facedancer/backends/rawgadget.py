import fcntl
import os
import struct
import typing
from enum import IntEnum

from facedancer.core import FacedancerApp
import logging

from construct import *

from ..core import *
from ..USB import *
from ..USBEndpoint import USBEndpoint

# from facedancer.future import USBConfiguration, USBEndpoint
# from facedancer.future.device import USBBaseDevice
# from facedancer.future.request import USBControlRequest

usb_ctrlrequest = Struct(
    'bRequestType' / Int8un,
    'bRequest' / Int8un,
    'wValue' / Int16ul,
    'wIndex' / Int16ul,
    'wLength' / Int16ul
)

usb_connectrequest = Struct()

usb_raw_event = Struct(
    'type' / Enum(Int32un, empty=0, connect=1, ctrl=2),
    'length' / Int32un,
    'data' / Byte[this.length]
)


usb_raw_ep_caps = BitsSwapped(BitStruct(
    'type_control' / Bit,
    'type_iso' / Bit,
    'type_bulk' / Bit,
    'type_int' / Bit,
    'dir_in' / Bit,
    'dir_out' / Bit,
    Padding(26),
))

usb_raw_ep_limits = Struct(
    'maxpacket_limit' / Int16un,
    'max_streams' / Int16un,
    'reserved' / Int32un
)

USB_RAW_EPS_NUM_MAX = 30
USB_RAW_EP_NAME_MAX = 16
usb_raw_ep_info = Struct(
    'name' / PaddedString(USB_RAW_EP_NAME_MAX, 'ascii'),
    'addr' / Int32un,
    'caps' / usb_raw_ep_caps,
    'limits' / usb_raw_ep_limits,
)
usb_raw_eps_info = Struct(
    'eps' / usb_raw_ep_info[USB_RAW_EPS_NUM_MAX]
)

class IOCTLRequest:
    IOC_WRITE = 1
    IOC_READ = 2
    IOC_NONE = 0

    IOC_NRBITS = 8
    IOC_TYPEBITS = 8

    IOC_SIZEBITS = 14
    IOC_DIRBITS = 2

    # define _IOC_NRMASK	((1 << _IOC_NRBITS)-1)
    # define _IOC_TYPEMASK	((1 << _IOC_TYPEBITS)-1)
    # define _IOC_SIZEMASK	((1 << _IOC_SIZEBITS)-1)
    # define _IOC_DIRMASK	((1 << _IOC_DIRBITS)-1)

    IOC_NRSHIFT = 0
    IOC_TYPESHIFT = (IOC_NRSHIFT + IOC_NRBITS)
    IOC_SIZESHIFT = (IOC_TYPESHIFT + IOC_TYPEBITS)
    IOC_DIRSHIFT = (IOC_SIZESHIFT + IOC_SIZEBITS)

    @staticmethod
    def IOC(dir, _type, nr, size):
        # print(type(dir), type(_type), type(nr), type(size))
        if isinstance(size, str):
            size = struct.calcsize(size)
        if isinstance(_type, str):
            _type = ord(_type[0])
        if isinstance(dir, str):
            dir = {'': IOCTLRequest.IOC_NONE, 'R': IOCTLRequest.IOC_READ, 'W': IOCTLRequest.IOC_WRITE,
                   'WR': IOCTLRequest.IOC_WRITE | IOCTLRequest.IOC_READ}[dir]

        # print(type(dir), type(_type), type(nr), type(size))
        return dir << IOCTLRequest.IOC_DIRSHIFT | _type << IOCTLRequest.IOC_TYPESHIFT | nr << IOCTLRequest.IOC_NRSHIFT | size << IOCTLRequest.IOC_SIZESHIFT

    @staticmethod
    def ioc(dir, _type, nr, fmt):

        def fn(fd, *args, data=b''):
            if isinstance(fmt, str):
                if fmt=="@I" and len(args)==1:
                    buf = args[0]
                else:
                    buf = struct.pack(fmt, *args)
                    buf += data
            else:
                buf = data + bytes(fmt - len(data))

            req = IOCTLRequest.IOC(dir, _type, nr, fmt)
            if not isinstance(buf,int):
                # print(nr, ':', req, ':', len(buf), buf)
                buf = bytearray(buf)
                if len(buf) == 0:
                    buf = 0
            else:
                # print(nr, ':', req, ':', buf)
                pass
            resp = fcntl.ioctl(fd, req, buf, True)
            # print(f"{resp=} {buf=}")
            return resp, buf

        return fn


class RawGadgetRequests(IOCTLRequest):
    UDC_NAME_LENGTH_MAX = 128
    USB_RAW_IOCTL_INIT = IOCTLRequest.ioc('W', 'U', 0, f"@{UDC_NAME_LENGTH_MAX}s{UDC_NAME_LENGTH_MAX}sB")
    USB_RAW_IOCTL_RUN = IOCTLRequest.ioc('', 'U', 1, "")
    USB_RAW_IOCTL_EVENT_FETCH = IOCTLRequest.ioc('R', 'U', 2, "@II0B")
    USB_RAW_IOCTL_EP0_WRITE = IOCTLRequest.ioc('W', 'U', 3, "@HHI0B")
    USB_RAW_IOCTL_EP0_READ = IOCTLRequest.ioc('WR', 'U', 4, "@HHI0B")
    USB_RAW_IOCTL_EP_ENABLE = IOCTLRequest.ioc('W', 'U', 5, 9)
    USB_RAW_IOCTL_EP_DISABLE = IOCTLRequest.ioc('W', 'U', 6, "@I")
    USB_RAW_IOCTL_EP_WRITE = IOCTLRequest.ioc('W', 'U', 7, "@HHI0B")
    USB_RAW_IOCTL_EP_READ = IOCTLRequest.ioc('WR', 'U', 8, "@HHI0B")
    USB_RAW_IOCTL_CONFIGURE = IOCTLRequest.ioc('', 'U', 9, "")
    USB_RAW_IOCTL_VBUS_DRAW = IOCTLRequest.ioc('W', 'U', 10, "@I")
    USB_RAW_IOCTL_EPS_INFO = IOCTLRequest.ioc('R', 'U', 11, 960)
    USB_RAW_IOCTL_EP0_STALL = IOCTLRequest.ioc('', 'U', 12, "")
    USB_RAW_IOCTL_EP_SET_HALT = IOCTLRequest.ioc('W', 'U', 13, "@I")
    USB_RAW_IOCTL_EP_CLEAR_HALT = IOCTLRequest.ioc('W', 'U', 14, "@I")
    USB_RAW_IOCTL_EP_SET_WEDGE = IOCTLRequest.ioc('W', 'U', 15, "@I")
    USB_RAW_IOCTL_EP_FIFO_STATUS = IOCTLRequest.ioc('W', 'U', 16, "@I")
    USB_RAW_IOCTL_EP_WRITE_ASYNC = IOCTLRequest.ioc('W', 'U', 17, "@HHI0B")
    USB_RAW_IOCTL_EP_READ_ASYNC = IOCTLRequest.ioc('WR', 'U', 18, "@HHI0B")


class UsbDeviceSpeed(IntEnum):
    USB_SPEED_UNKNOWN = 0
    USB_SPEED_LOW = 1
    USB_SPEED_FULL = 2
    USB_SPEED_HIGH = 3
    USB_SPEED_WIRELESS = 4
    USB_SPEED_SUPER = 5
    USB_SPEED_SUPER_PLUS = 6


class RawGadget:

    def __init__(self):
        self.fd = None
        self.last_ep_addr = 0

    def open(self):
        self.fd = open('/dev/raw-gadget', 'bw')

    def close(self):
        self.fd.close()

    def init(self, driver: str, device: str, speed: UsbDeviceSpeed):
        RawGadgetRequests.USB_RAW_IOCTL_INIT(self.fd, driver.encode(), device.encode(), speed)

    def run(self):
        RawGadgetRequests.USB_RAW_IOCTL_RUN(self.fd)

    def event_fetch(self) -> usb_raw_event:
        ctrlevent = bytes(usb_ctrlrequest.sizeof())
        rv, resp = RawGadgetRequests.USB_RAW_IOCTL_EVENT_FETCH(self.fd, 0, len(ctrlevent), data=ctrlevent)
        parsed_resp = usb_raw_event.parse(resp)
        return parsed_resp

    def eps_info(self):
        num,resp = RawGadgetRequests.USB_RAW_IOCTL_EPS_INFO(self.fd)
        return usb_raw_ep_info[num].parse(resp)

    #
    # def assign_ep_address(self, ep_info, ep):
    #     if usb_endpoint_num(ep) != 0:
    #         return False  # Already assigned
    #     if usb_endpoint_dir_in(ep) and ep_info.caps.dir_in == 0:
    #         return False
    #     if usb_endpoint_dir_out(ep) and ep_info.caps.dir_out == 0:
    #         return False
    #     if usb_endpoint_type(ep) == USB_ENDPOINT_XFER_BULK:
    #         if ep_info.caps.type_bulk == 0:
    #             return False
    #     elif usb_endpoint_type(ep) == USB_ENDPOINT_XFER_INT:
    #         if ep_info.caps.type_int == 0:
    #             return False
    #     else:
    #         assert False, "Unsupported EP type"
    #         # return False
    #     if ep_info.addr == USB_RAW_EP_ADDR_ANY:
    #         self.last_ep_addr += 1
    #         ep.bEndpointAddress |= self.last_ep_addr
    #     else:
    #         ep.bEndpointAddress |= ep_info.addr
    #     return True

    def ep_enable(self, ep_desc):
        rv, resp = RawGadgetRequests.USB_RAW_IOCTL_EP_ENABLE(self.fd, data=ep_desc)
        print(f"ep_enable {rv=}")
        return rv

    def vbus_draw(self, power):
        RawGadgetRequests.USB_RAW_IOCTL_VBUS_DRAW(self.fd, power)

    def configure(self):
        RawGadgetRequests.USB_RAW_IOCTL_CONFIGURE(self.fd)

    def ep0_write(self, data, flags=0):
        return RawGadgetRequests.USB_RAW_IOCTL_EP0_WRITE(self.fd, 0, flags, len(data), data=data)

    def ep0_read(self, data, flags=0):
        return RawGadgetRequests.USB_RAW_IOCTL_EP0_READ(self.fd, 0, flags, len(data), data=data)

    def ep_write(self, ep, data, flags=0):
        return RawGadgetRequests.USB_RAW_IOCTL_EP_WRITE(self.fd, ep, flags, len(data), data=data)

    def ep_read(self, ep, data, flags=0):
        return RawGadgetRequests.USB_RAW_IOCTL_EP_READ(self.fd, ep, flags, len(data), data=data)

    def ep_read_async(self, ep, data, flags=0):
        return RawGadgetRequests.USB_RAW_IOCTL_EP_READ_ASYNC(self.fd, ep, flags, len(data), data=data)

    def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def disable_ep(self, num):
        return RawGadgetRequests.USB_RAW_IOCTL_EP_DISABLE(self.fd, num)

    def ep_stall(self, num):
        if num==0:
            RawGadgetRequests.USB_RAW_IOCTL_EP0_STALL(self.fd)

    def fifo_status(self, num):
        RawGadgetRequests.USB_RAW_IOCTL_EP_FIFO_STATUS(self.fd, num)



class RawGadgetApp(FacedancerApp):
    app_name = "RawGadget"
    app_num = 0x00  # This doesn't have any meaning for us.

    @classmethod
    def appropriate_for_environment(cls, backend_name):
        """
        Determines if the current environment seems appropriate
        for using the GoodFET::MaxUSB backend.
        """
        # Check: if we have a backend name other than greatfet,
        # the user is trying to use something else. Abort!
        if backend_name and backend_name != "rawgadget":
            return False

        # If we're not explicitly trying to use something else,
        # see if there's a connected GreatFET.
        try:
            rg = open('/dev/raw-gadget')
            rg.close()
            return True
        except ImportError:
            logging.info("Skipping RawGadget, as could not open /dev/raw-gadget .")
            return False
        except:
            logging.exception("RawGadget check fail", exc_info=True, stack_info=True)
            return False

    def __init__(self, device=None, verbose=0, quirks=None):
        self.enabled_eps = {}
        self.eps_info: typing.Optional[typing.List[usb_raw_ep_info]]= None
        from facedancer.future.device import USBBaseDevice
        self.connected_device: typing.Optional[USBBaseDevice] = None

        if 'RG_SPEED' in os.environ:
            self.speed = UsbDeviceSpeed(int(os.environ['RG_SPEED']))
        else:
            self.speed = UsbDeviceSpeed.USB_SPEED_HIGH

        if 'UDC_DEVICE' in os.environ:
            self.udc_device = os.environ['UDC_DEVICE'].lower()
        else:
            self.udc_device = "dummy_udc.0"

        if 'UDC_DRIVER' in os.environ:
            self.udc_driver = os.environ['UDC_DRIVER'].lower()
        else:
            self.udc_driver = "dummy_udc"

        self.api: RawGadget = RawGadget()

        logging.info(f"__init__({device=},{verbose=},{quirks=})")
        self.fd = open('/dev/raw-gadget')
        self.is_configured=False
        self.endpoint_recv_buffer = {}
        super().__init__(device, verbose)

    def init_commands(self):
        self.api.open()
        self.api.init(self.udc_driver, self.udc_device, self.speed)

    def connect(self, device, maxp_ep0):
        self.connected_device = device
        self.api.run()

    def disconnect(self):
        self.api.close()

    def configured(self,configuration):
        # print(f"configured {configuration=}")
        cfg: typing.Optional[USBConfiguration] = self.connected_device.configuration
        if cfg is None:
            for ep in self.enabled_eps:
                self.api.disable_ep(self.enabled_eps[ep])

            self.enabled_eps={}
            self.endpoint_recv_buffer={}
            #TODO: handle unconfiguration. By now not implemented in raw_gadget
            self.is_configured= False

        for interface in cfg.get_interfaces():
            for ep in interface.get_endpoints():
                ep_handle = self.api.ep_enable(ep.get_descriptor())
                self.enabled_eps[ep.get_address()] = ep_handle
                self.endpoint_recv_buffer[ep.get_address()]=[]
                # print(f"ASSIGNED {self.eps_info[ep_handle]=} for {ep=}")
        self.api.vbus_draw(cfg.max_power//2)
        self.api.configure()
        self.is_configured=True

    def send_on_endpoint(self,ep_num,data,blocking=True):

        if isinstance(data,tuple):
            data=bytes(data)
        elif isinstance(data,list):
            data=bytes(data)
        # print(f"send_on_endpoint {ep_num=} {len(data)=:0x}")
        if ep_num == 0:
            if len(data)==0:
                self.api.ep0_read(data)
            else:
                self.api.ep0_write(data)
        else:
            ep_num|=0x80
            self.api.ep_write(self.enabled_eps[ep_num],data)

    # def recv_on_enpoint(self,):

    def stall_endpoint(self,ep_num, direction):
        # print(f"stall_endpoint {ep_num=}")
        self.api.ep_stall(ep_num)

    def set_address(self,address, defer):
        """ Updates the device's knowledge of its own address.

        Parameters:
            address -- The address to apply.
            defer   -- If true, the address change should be deferred
                       until the next time a control request ends. Should
                       be set if we're changing the address before we ack
                       the relevant transaction.
        """
        # print(f"set_address {address=} {defer=}")
        pass

    def reset(self):
        pass

    def ack_status_stage(self, direction=0, endpoint_number=0, blocking=False):
       logging.info(f"ack_status_stage {direction=} {endpoint_number} {blocking=}")
       if direction==0 and endpoint_number==0:
           self.send_on_endpoint(0,b'')
       pass

    def stall_ep0(self):
        self.api.ep_stall(0)

    def _get_endpoint(self,addr):
        try:
            from facedancer.future import USBDirection
            return self.connected_device.get_endpoint(addr & 0x7f, USBDirection.from_endpoint_address(addr))
        except AttributeError:
            for i in self.connected_device.configuration.interfaces:
                for ep in i.endpoints:
                    if ep.get_address() == addr:
                        return ep
        return None

    def service_irqs(self):
        event = self.api.event_fetch()
        match event.type:
            case 'connect':
                self.eps_info = self.api.eps_info()

            case 'ctrl':
                # from facedancer..request import USBControlRequest
                from facedancer.future.request import USBControlRequest
                # request = USBControlRequest.from_raw_bytes(event.data, device=self.connected_device)
                request = self.connected_device.create_request(event.data)
                self.connected_device.handle_request(request)

            case 'empty':
                if self.is_configured:
                    for ep in self.enabled_eps:
                        from facedancer.future import USBDirection
                        dir =USBDirection.from_endpoint_address(ep)
                        device_ep=self._get_endpoint(ep)

                        if dir == USBDirection.IN:
                            try:
                                self.connected_device.handle_data_requested(device_ep)
                            except AttributeError:
                                pass
                        elif dir == USBDirection.OUT:
                            # print(f"{self.enabled_eps[ep]=} {dir=}")
                            ## fifo_status=self.api.fifo_status(self.enabled_eps[ep])
                            ## print(f"{fifo_status=}")
                            rv,data=self.api.ep_read_async(self.enabled_eps[ep],bytearray(device_ep.max_packet_size))
                            # print(f"{device_ep=} {rv=}")
                            if rv>0:
                                try:
                                    self.connected_device.handle_data_received(device_ep,data[8:8+rv])
                                except AttributeError:
                                    self.connected_device.handle_data_available(device_ep.get_address(),data[8:8+rv])
