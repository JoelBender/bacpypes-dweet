# bacpypes-dweet

A ridiculously simple tool for reading [BACnet](http://www.bacnet.org) point values and sending them to a ridiculously
simple messaging platform for the Internet of Things.

This application was written for the hackathon portion of the **Smart Campus Summit - Beyond the Dashboard** conference
that was held at Cornell University on October 4th, 2017.  The "hackers" were given a set of schematics for the building
automation systems of [Weill Hall](https://wicmb.cornell.edu/) and asked to determine the "key performance indicators"
of the system with respect to the facility director, a controls technician, or a researcher.  They had about two hours to design a dashboard and
present it to the facility director.

The hackathon was a great success!

## Installation

There is no installation, it's just a program.  It depends on
[BACpypes](https://pypi.python.org/pypi/BACpypes) for BACnet communication and
[dweepy](https://pypi.python.org/pypi/dweepy) to send "dweets" to the
http://dweet.io service.  If you don't already have these modules installed,
get them from PyPI using **pip**:

    $ pip install bacpypes dweepy

## Configuration

All of the configuration information is contained in a
[JSON](http://www.json.org/) document that is one object containing two parts,
a `config` and a `dweets`, like this:

```json
{
    "config": {
        ...
        },
    "dweets": [
        ...
        ]
}
```

The default configuration file name is `bacpypes-dweet.json` but that can be
changed through environmental variable SETTINGS or the `--settings` command line
option.

### Config Section

The `config` section is a JSON object that contains the configuration
parameters for your server/workstation to become a member of a BACnet network.
These parameters are identical to those in the BACpypes INI file, and if you
already have an INI file then the config section is optional.

Here is the configuration that is in the project repository, you will have to
customize it with your own IP address in CIDR notation, along with a BACnet
device identifier (the object instance number of the device object) that will
be unique on your BACnet network:

```json
    "config": {
        "objectName": "bacpypes-dweet-gateway",
        "address": "10.0.1.211/24",
        "objectIdentifier": 599,
        "maxApduLengthAccepted": 1024,
        "segmentationSupported": "segmentedBoth",
        "vendorIdentifier": 999
        },
```

### Dweets Section

The `dweets` section is an array of dweet configuration information which is
the name of the thing, the rate that the values should be dweeted, and the list
of tags.  For example, this is a thing:

```json
        {
            "thingName": "bacpypes-dweet-oa-conditions",
            "interval": 30,
            "tagList": [
                {
                    "tag": "temperature",
                    "address": "10.0.1.210",
                    "objectType": "analogValue",
                    "objectInstance": 1
                }
            ]
        }
```

#### thingName

#### interval

#### tagList

#### tag

#### address

The BACnet address of the device that contains the object.  This is usually
an IP address, but may also be in the form of `net:addr` for MS/TP and ARCNET
devices that are on field networks.

#### objectType

This is the object type enumeration value for the object to read.  These are
often analog input objects or analog value objects, but they could be any
object type that BACpypes supports.  Note that the object type value matches
the naming convention used by BACpypes rather than the `analog-value` form that
appears in the standard.

#### objectInstance

This is the object instance number, as expected.

### Optional Configuration

These are optional configuration name/value pairs for a tag.

#### property

If the `property` is specified, it can be any property appropriate for the
object.  If it is not specified, `presentValue` is used.

#### decnum

If `decnum` is specified, integer and real values are rounded to the specified
number of decimal points.  A positive number such as two (2) will round to the
nearest hundredth, a value of zero (0) is rounded to the nearest integer.

While the rounding can also be applied to the value when it appears on a
dashboard or other display, it's often easier to put it in this configuration
so it doesn't appear unnaturally precise.

