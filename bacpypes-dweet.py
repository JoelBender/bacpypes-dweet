#!/usr/bin/env python3

"""
bacpypes-dweet

This application reads the values of BACnet points, packages them up into a
JSON document and it to https://dweet.io where it is very simple to follow
the values and create a dashboard.

This application requires the BACpypes and dweepy library, both are available
in PyPI.

    $ pip install bacpypes dweepy

For a description of the contents of the JSON configuration file, see the
README.
"""

import os
import sys
import signal
import json
import logging

from time import time, sleep
from threading import Thread
from collections import namedtuple, OrderedDict
from configparser import ConfigParser as _ConfigParser

from bacpypes.debugging import bacpypes_debugging, ModuleLogger
from bacpypes.consolelogging import ArgumentParser

from bacpypes.core import run, deferred
from bacpypes.iocb import IOCB

from bacpypes.pdu import Address
from bacpypes.object import get_datatype

from bacpypes.apdu import ReadPropertyRequest
from bacpypes.primitivedata import Unsigned
from bacpypes.constructeddata import Array

from bacpypes.app import BIPSimpleApplication
from bacpypes.service.device import LocalDeviceObject

import dweepy

# some debugging
_debug = 0
_log = ModuleLogger(globals())

# settings
BACPYPES_INI = os.getenv('BACPYPES_INI', 'BACpypes.ini')
SETTINGS = os.getenv("SETTINGS", "bacpypes-dweet.json")

# globals
this_application = None

#
#   DweetThread
#

@bacpypes_debugging
class DweetThread(Thread):

    def __init__(self, dweet):
        if _debug: DweetThread._debug("__init__ %r", dweet)
        Thread.__init__(self)

        # save the parameters for reference
        self.thing_name = dweet.thingName
        self.point_list = dweet.tagList
        self.interval = dweet.interval

        # this is a daemon
        self.daemon = True

        # run after the core is ready
        deferred(self.start)

    def run(self):
        if _debug: DweetThread._debug("run")

        while True:
            # sleep until the next interval
            now = time()
            sleep(self.interval - (now % self.interval))
            if _debug: DweetThread._debug("    - awake")

            # gathering spot for the data
            dweet_data = OrderedDict()

            # loop through the points
            for point in self.point_list:
                # build a request
                request = ReadPropertyRequest(
                    destination=Address(point.address),
                    objectIdentifier=(point.objectType, point.objectInstance),
                    propertyIdentifier=getattr(point, 'property', 'presentValue'),
                    )
                if _debug: DweetThread._debug("    - request: %r", request)

                # make an IOCB
                iocb = IOCB(request)
                if _debug: DweetThread._debug("    - iocb: %r", iocb)

                # give it to the application
                this_application.request_io(iocb)

                # wait for the response
                iocb.wait()

                if iocb.ioResponse:
                    apdu = iocb.ioResponse

                    # find the datatype
                    datatype = get_datatype(apdu.objectIdentifier[0], apdu.propertyIdentifier)
                    if _debug: DweetThread._debug("    - datatype: %r", datatype)
                    if not datatype:
                        raise TypeError("unknown datatype")

                    # special case for array parts, others are managed by cast_out
                    if issubclass(datatype, Array) and (apdu.propertyArrayIndex is not None):
                        if apdu.propertyArrayIndex == 0:
                            value = apdu.propertyValue.cast_out(Unsigned)
                        else:
                            value = apdu.propertyValue.cast_out(datatype.subtype)
                    else:
                        value = apdu.propertyValue.cast_out(datatype)
                    if _debug: DweetThread._debug("    - value: %r", value)

                    if value == 'active' and hasattr(point, 'active'):
                        value = getattr(point, 'acitve', value)
                    elif value == 'inactive':
                        value = getattr(point, 'inactive', value)

                    # trim the display
                    if isinstance(value, float) and hasattr(point, 'decnum'):
                        value = round(value, point.decnum)
                        if _debug: DweetThread._debug("    - rounded: %r", value)

                    # save the value
                    dweet_data[point.tag] = value

                if iocb.ioError:
                    if _debug: DweetThread._debug("    - error: %r", iocb.ioError)

            # send the data
            if dweet_data:
                if _debug: DweetThread._debug(self.thing_name + ' ' + ', '.join("{}: {}".format(k,v) for k, v in dweet_data.items()) + '\n')
                dweepy.dweet_for(self.thing_name, dweet_data)


#
#   load_settings
#

@bacpypes_debugging
def load_settings(*signal_args):
    """Call to stop running, may be called with a signum and frame
    parameter if called as a signal handler."""
    if _debug: load_settings._debug("load_settings %r", signal_args)
    global args, settings

    if signal_args:
        sys.stderr.write("===== HUP Signal, %s\n" % time.strftime("%d-%b-%Y %H:%M:%S"))
        sys.stderr.flush()

    with open(args.settings) as settings_file:
        settings = json.load(
            settings_file,
            object_hook=lambda d: namedtuple('Settings', d.keys())(*d.values())
            )
        if _debug: load_settings._debug("    - settings: %r", settings)

    # add the points
    for dweet in settings.dweets:
        if _debug: load_settings._debug("    - dweet: %r", dweet)

        # make a thing
        dweet_thing = DweetThread(dweet)
        if _debug: load_settings._debug("    - dweet_thing: %r", dweet_thing)

# set a TERM signal handler
if hasattr(signal, 'SIGHUP'):
    signal.signal(signal.SIGHUP, load_settings)


#
#   main
#

def main():
    global args, settings, this_application

    # build a parser for the command line arguments
    parser = ArgumentParser(description=__doc__)

    # add a way to read a configuration file
    parser.add_argument('--ini', type=str,
        help="device object configuration file",
        )

    # settings file name
    parser.add_argument(
        "--settings", type=str,
        default=SETTINGS,
        help="settings file",
        )

    # parse the command line arguments
    args = parser.parse_args()

    if _debug: _log.debug("initialization")
    if _debug: _log.debug("    - args: %r", args)

    # load the settings
    load_settings()

    # read in the configuration file
    if args.ini:
        config = _ConfigParser()

        # case sensitive
        config.optionxform = str

        # read in the file
        config.read(args.ini)
        if _debug: _log.debug("    - config: %r", config)

        # check for BACpypes section
        if not config.has_section('BACpypes'):
            raise RuntimeError("INI file with BACpypes section expected")

        # convert the contents to an object
        ini_obj = type('ini', (object,), dict(config.items('BACpypes')))
        if _debug: _log.debug("    - ini_obj: %r", ini_obj)

        # add the object to the parsed arguments
        setattr(args, 'ini', ini_obj)

    # only one configuration
    if hasattr(settings, "config") and args.ini:
        raise RuntimeError("ambiguous settings")
    elif hasattr(settings, "config"):
        device_settings = settings.config
    elif args.ini:
        device_settings = args.ini
    else:
        raise RuntimeError("missing settings")
    if _debug: _log.debug("    - device_settings: %r", device_settings)

    # make a device object
    this_device = LocalDeviceObject(
        objectName=device_settings.objectName,
        objectIdentifier=int(device_settings.objectIdentifier),
        maxApduLengthAccepted=int(device_settings.maxApduLengthAccepted),
        segmentationSupported=device_settings.segmentationSupported,
        vendorIdentifier=int(device_settings.vendorIdentifier),
        )

    # make a simple application
    this_application = BIPSimpleApplication(this_device, device_settings.address)

    # get the services supported
    services_supported = this_application.get_services_supported()
    if _debug: _log.debug("    - services_supported: %r", services_supported)

    # let the device object know
    this_device.protocolServicesSupported = services_supported.value

    _log.debug("running")

    run()

    _log.debug("fini")

if __name__ == "__main__":
    main()

