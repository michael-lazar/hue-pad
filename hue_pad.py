#!/usr/bin/env python

"""
Control lighting effects with a MIDI Pad Controller.

This script will watch for incoming MIDI events from an Akai LPD8 and use them
to update lighting/color effects through a Philips Hue Bridge.
"""

import os
import time
import json
import atexit
import logging
import threading

import phue
import click
from pygame import midi

CONFIG_DIR = click.get_app_dir('hue-pad')
DEFAULT_DATABASE = os.path.join(CONFIG_DIR, 'default.json')

_logger = logging.getLogger('hue_pad')


def init_lpd8():
    """
    Connect to the midi controller and open a device handle.    
    """
    midi.init()

    device = None
    for i in range(midi.get_count()):
        # Device info is returned as a tuple in the form:
        #    (interf, name, input, output, opened)
        info = midi.get_device_info(i)
        _logger.debug('Device %s: %s', i, info)
        if 'LPD8' in info[1] and info[2] == 1:
            device = midi.Input(i)
            _logger.info('Connected to device: %s', info)
            atexit.register(device.close)

    if not device:
        raise RuntimeError('LPD8 MIDI device not found')

    return device


def init_hue(hue_ip):
    """
    Connect to the philips hue bridge. The first time that a connection is
    made, you will need to press the button on the Philips bridge to generate
    user credentials. Credentials are then stored in the home directory for
    future sessions.
    """
    bridge = phue.Bridge(hue_ip)
    _logger.debug(bridge.get_api())

    for i, light in enumerate(bridge.lights, start=1):
        light.on = True
        _logger.info('Found light %s: %s', i, light.name)

    for i, group in enumerate(bridge.groups, start=1):
        _logger.info('Found group %s: %s', i, group.name)

    return bridge


class MidiController(object):

    def __init__(self, device, bridge, queue, db_filename, light_ids):

        self.device = device
        self.bridge = bridge
        self.queue = queue
        self.light_ids = light_ids
        self.update_pad_flag = False

        self.db_filename = db_filename
        self.db = None
        self.load_db()

    def loop_forever(self):
        """
        Loop and watch for MIDI events.
        
        Akai LPD8 midi controller codes:

            Each message is encoded as [status, data1, data2, data3]
    
            Mode PAD   : controller will send MIDI notes
            Mode CHNG  : controller will send Program Change
            Mode CC    : controller will send MIDI Control Change
    
                           Program #   Pad/Knob #  Intensity  N/A
                           ---------   ----------  ---------  ---
            Knobs          176-179     1-8         0-127      0
            CC Hit         176-179     1-6/8-9     0-127      0
            CC Release     176-179     1-6/8-9     0          0
            PAD Hit        144-147     36-43       0-127      0
            PAD Release    128-131     36-43       127        0
            CHNG Hit       192-195     0-7         0          0
            CHNG Release   -           -           -          -
        """
        while True:
            while self.device.poll():
                event, timestamp = self.device.read(1)[0]
                _logger.debug(event)

                if 176 <= event[0] <= 179:
                    self.knob(event[1], event[2])

                elif 144 <= event[0] <= 147:
                    self.pad_hit(event[0] - 143, event[1])

                elif 128 <= event[0] <= 131:
                    self.pad_release(event[0] - 127, event[1])

                elif 192 <= event[0] <= 195:
                    self.pad_prog_chng(event[1])

            time.sleep(0.01)

    def load_db(self):
        """
        Store lighting presets for the pads in a JSON file.
        """

        # Make sure the directory exists for saving later
        try:
            os.makedirs(os.path.dirname(self.db_filename))
        except os.error:
            pass

        try:
            with open(self.db_filename) as fp:
                self.db = json.load(fp)
            _logger.info('Opened %s', self.db_filename)
        except IOError as e:
            _logger.error(e)
            self.db = {}

        for key, item in sorted(self.db.items()):
            _logger.debug('Loaded DB - %s: %s', key, item)

        self.db.setdefault('selected_lights', self.light_ids)
        for i in range(1, 9):
            data = {j: {'bri': 254, 'ct': 0} for j in self.light_ids}
            self.db.setdefault(str(i), data)

    def save_db(self):
        """
        Save lighting presets back to the JSON file.
        """

        try:
            with open(self.db_filename, 'wb') as fp:
                json.dump(self.db, fp, indent=2, sort_keys=True)
        except IOError as e:
            _logger.error(e)

    def knob(self, num, intensity):
        """
        Twisting the knobs controls lighting characteristics.
        
        Light colors can be defined as:
            brightness + hue/saturation
            brightness + ct (color temperature)
            brightness + x/y

        Intensity ranges:
            bri [0-254]
            sat [0-254]
            hue [0-65535]
            ct  [154-500] (mireds)
                   
        The lights will switch to whichever mode the last command used
        (e.g. if we send a hue command, the lights will switch to hue/saturation
        mode and discard any ct values). The x/y controls are not useful for a
        knob because they don't provide a smooth transition between colors.
        """

        if num == 5:
            data = {'bri': intensity * 2}
        elif num == 6:
            data = {'hue': intensity * 516, 'sat': 254}
        elif num == 7:
            data = {'ct': int((intensity * 2.7322) + 153)}
        else:
            return

        # Queue the update to be sent to the hue lights
        for light in self.db['selected_lights']:
            self.queue[light] = data

        self.update_pad_flag = True

    def pad_hit(self, prog, num):
        """
        Striking a pad in PAD mode.
        """

        if prog == 1:
            pad = str([36, 37, 38, 39, 40, 41, 42, 43].index(num) + 1)

            for light, data in self.db[pad].items():
                self.queue[light] = data
            self.update_pad_flag = False

        elif prog == 2:
            pad = str([35, 36, 42, 39, 37, 38, 46, 44].index(num) + 1)

            for light, data in self.db[pad].items():
                blink_data = data.copy()
                blink_data['bri'] = 'blink'
                self.queue[light] = blink_data

    def pad_release(self, prog, num):
        """
        Releasing a pad in PAD mode.
        """

        if prog == 1 and self.update_pad_flag:
            pad = str([36, 37, 38, 39, 40, 41, 42, 43].index(num) + 1)

            for light in self.db['selected_lights']:

                state = self.bridge.get_light(int(light))['state']
                self.db[pad][light]['bri'] = state['bri']
                if state['colormode'] == 'hs':
                    self.db[pad][light] = {
                        'bri': state['bri'],
                        'hue': state['hue'],
                        'sat': state['sat']}
                else:
                    self.db[pad][light] = {
                        'bri': state['bri'],
                        'ct': state['ct']}

            _logger.info('Saving update to pad %s', pad)
            self.save_db()
            self.update_pad_flag = False

    def pad_prog_chng(self, num):
        """
        Striking a pad in PROG CHNG mode.
        """

        if num == 0:
            # Pad 0 selects all of the lights at once
            self.db['selected_lights'] = self.light_ids
        elif num <= len(self.light_ids):
            # The other pads select a single light
            self.db['selected_lights'] = [self.light_ids[num - 1]]
        else:
            return

        _logger.info('Switching to lights %s', self.db['selected_lights'])
        self.save_db()


class LightMonitorThread(threading.Thread):
    """
    Background thread that continuously check for changes to the lights
    and issues commands to the Philips Hue bridge. This is throttled
    to only update every 100ms to conform to the API specification.

    Only the most recent un-applied updates will be pulled from the queue.
    This is done to prevent something like twisting a knob from generating
    100+ API requests in a short time span.
    """

    def __init__(self, bridge):

        self.bridge = bridge
        self.queue = {}
        self.active = None

        super(LightMonitorThread, self).__init__()

    def update_light(self, light, data):
        light = int(light)

        if data.get('bri') == 'blink':
            data['bri'] = 254
            self.bridge.set_light(light, parameter=data, transitiontime=0)
            self.bridge.set_light(light, parameter={'bri': 0}, transitiontime=2)
            self.bridge.set_light(light, parameter={'sat': 0}, transitiontime=0)
        else:
            self.bridge.set_light(light, parameter=data)

    def run(self):

        _logger.info('Starting Light Monitor Thread')

        self.active = True
        while self.active:
            # Make a copy of the queue to safeguard against it being updated
            # while we're iterating through the items
            queue_copy = self.queue.copy()
            self.queue.clear()

            # Use threads to send out all of the requests at the same time
            # This is important for synchronizing the blinking between lights
            threads = []
            for light, data in queue_copy.items():
                thread = threading.Thread(target=self.update_light, args=(light, data))
                thread.start()
                threads.append(thread)

            for thread in threads:
                thread.join()

            # The API guidelines suggest waiting 100ms between requests
            # We can squeak out a little bit of latency though
            time.sleep(0.05)

        _logger.info('Exiting Light Monitor Thread')


@click.command()
@click.option('--debug/--no-debug', default=False, help='Enable verbose logging.')
@click.option('--hue-ip', default='10.0.0.33', help='IP address of the Philips Hue Bridge.')
@click.option('--db-file', default=DEFAULT_DATABASE, help='JSON file with lighting scene data.')
@click.option('--light-ids', default='1,2', show_default=True, help='Comma separated list of light IDs to control.')
def main(debug, hue_ip, db, light_ids):
    """
    Control lighting effects with a MIDI Pad Controller.

    This script will watch for incoming MIDI events from an Akai LPD8 and use them
    to update lighting/color effects through a Philips Hue Bridge.
    """

    if debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    light_ids = light_ids.split(',')
    _logger.info('Light ids %s', light_ids)

    bridge = init_hue(hue_ip)
    thread = LightMonitorThread(bridge)
    thread.start()

    device = init_lpd8()
    controller = MidiController(device, bridge, thread.queue, db, light_ids)

    try:
        controller.loop_forever()
    except KeyboardInterrupt:
        pass

    thread.active = False
    thread.join()


if __name__ == "__main__":
    main()
