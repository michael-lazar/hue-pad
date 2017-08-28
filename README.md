# Hue Pad
Control Philips Hue Lights with a MIDI Pad Controller

Parts
-----

<table>
  <tr>
    <td><a href="http://www.akaipro.com/products/pad-controllers/lpd-8">Akai LPDD8 Laptop Pad Controller</a></td>
    <td align="center"><img src="https://github.com/michael-lazar/hue-pad/blob/master/images/lpd8.png" height=200></img></td>
  </tr>
  <tr>
    <td><a href="https://www.raspberrypi.org/products/raspberry-pi-3-model-b/">Raspberry Pi 3</a></td>
    <td align="center"><img src="https://github.com/michael-lazar/hue-pad/blob/master/images/raspberry_pi_3.png" height=200></img></td>
  </tr>
  <tr>
    <td><a href="http://www2.meethue.com/en-us/p/046677456214">Philips Hue Starter Kit</a></td>
    <td align="center"><img src="https://github.com/michael-lazar/hue-pad/blob/master/images/hue_light.png" height=200></img></td>
  </tr>
</table>

Database
--------

Every pad on the LPD8 can be programmed to store a different lighting
"scene". A lighting scene consists of brightness & color values for
one or more lights. These scenes are stored in a persistent JSON
document in the application's configuration directory.

The Hue Bridge API has it's own concept of "scenes" and "groups" that
are built into the firmware. However, accessing and storing these
settings introduces a noticeable latency when using the MIDI controller.
Therefore, this application only stores and sends commands to lights
using their unique IDs.

Installation
------------

Install the python script

```bash
$ git clone https://github.com/michael-lazar/hue-pad.git
$ cd hue-pad
$ python setup.py install
```

Register the systemd service

```bash
$ sudo cp hue-pad.service /etc/systemd/system
$ sudo systemctl daemon-reload
$ sudo systemctl enable hue-pad.service
$ sudo systemctl start hue-pad.service
```

License
-------

MIT
