"""
View - Main UI rendering for Pagergotchi
Adapted from original pwnagotchi for native Pager display

Uses native C library for rendering instead of PIL
"""

import threading
import logging
import random
import time
from threading import Lock

import pwnagotchi_port as pwnagotchi
import pwnagotchi_port.plugins as plugins
import pwnagotchi_port.ui.faces as faces
import pwnagotchi_port.utils as utils

from pwnagotchi_port.ui.components import Text, LabeledValue, Line
from pwnagotchi_port.ui.state import State
from pwnagotchi_port.voice import Voice
from pwnagotchi_port.ui.hw.pager import (
    PagerDisplay, FONT_SMALL, FONT_MEDIUM, FONT_LARGE, FONT_XLARGE,
    COLOR_BLACK, COLOR_WHITE
)


class View:
    """
    Main UI View for Pagergotchi

    Renders to native Pager display using libpager.so
    """

    def __init__(self, config, impl=None, state=None):
        self._agent = None
        self._config = config
        self._lock = Lock()
        self._frozen = False
        self._render_cbs = []

        # Initialize display
        self._display = PagerDisplay(config)
        self._display.initialize()

        # Get layout from display
        self._layout = self._display.layout()
        self._width = self._layout['width']
        self._height = self._layout['height']

        # Initialize voice
        lang = config.get('main', {}).get('lang', 'en')
        self._voice = Voice(lang=lang)

        # Setup faces from config
        faces_config = config.get('ui', {}).get('faces', {})
        faces.load_from_config(faces_config)

        # Initialize UI state with elements
        self._state = State(state={
            'channel': LabeledValue(color=0, label='CH ', value='00',
                                   position=self._layout['channel']),
            'aps': LabeledValue(color=0, label='APS ', value='0',
                               position=self._layout['aps']),
            'uptime': LabeledValue(color=0, label='UP ', value='00:00:00',
                                  position=self._layout['uptime']),
            'line1': Line(self._layout['line1'], color=0),
            'line2': Line(self._layout['line2'], color=0),
            'face': Text(value=faces.SLEEP,
                        position=self._layout['face'],
                        color=0),
            'friend_name': Text(value=None,
                               position=self._layout['friend_name'],
                               color=0),
            'name': Text(value='%s>' % pwnagotchi.name(),
                        position=self._layout['name'],
                        color=0),
            'status': Text(value=self._voice.default(),
                          position=self._layout['status']['pos'],
                          color=0,
                          wrap=True,
                          max_length=self._layout['status']['max']),
            'shakes': LabeledValue(label='PWND ', value='0',
                                  color=0,
                                  position=self._layout['shakes']),
            'gps': Text(value='',
                       position=self._layout['gps'],
                       color=0),
            'battery': Text(value='BAT ?',
                           position=self._layout['mode'],
                           color=0),
        })

        # Set font sizes
        self._state._state['face'].font_size = FONT_XLARGE  # Larger face
        self._state._state['name'].font_size = FONT_MEDIUM
        self._state._state['status'].font_size = FONT_MEDIUM

        if state:
            for key, value in state.items():
                self._state.set(key, value)

        plugins.on('ui_setup', self)

        # Start refresh thread
        fps = config.get('ui', {}).get('fps', 2.0)
        if fps > 0.0:
            self._ignore_changes = ()
            threading.Thread(target=self._refresh_handler, daemon=True).start()
        else:
            self._ignore_changes = ('uptime', 'name')

    def set_agent(self, agent):
        self._agent = agent

    def has_element(self, key):
        return self._state.has_element(key)

    def add_element(self, key, elem):
        self._state.add_element(key, elem)

    def remove_element(self, key):
        self._state.remove_element(key)

    def width(self):
        return self._width

    def height(self):
        return self._height

    def on_state_change(self, key, cb):
        self._state.add_listener(key, cb)

    def on_render(self, cb):
        if cb not in self._render_cbs:
            self._render_cbs.append(cb)

    def _refresh_handler(self):
        """Background thread to refresh display"""
        delay = 1.0 / self._config.get('ui', {}).get('fps', 2.0)
        while True:
            try:
                self.update()
            except Exception as e:
                logging.warning(f"Display update error: {e}")
            time.sleep(delay)

    def set(self, key, value):
        self._state.set(key, value)

    def get(self, key):
        return self._state.get(key)

    def _get_random_face(self, face_or_faces):
        if isinstance(face_or_faces, list):
            return random.choice(face_or_faces)
        return face_or_faces

    def on_starting(self):
        self.set('status', self._voice.on_starting())
        self.set('face', self._get_random_face(faces.AWAKE))
        self.update()

    def on_manual_mode(self, last_session):
        self.set('mode', 'MANU')
        self.set('face', self._get_random_face(faces.SAD) if (last_session.epochs > 3 and last_session.handshakes == 0) else self._get_random_face(faces.HAPPY))
        self.set('status', self._voice.on_last_session_data(last_session))
        self.update()

    def is_normal(self):
        face = self._state.get('face')
        return face not in (
            faces.INTENSE, faces.COOL, faces.BORED, faces.HAPPY,
            faces.EXCITED, faces.MOTIVATED, faces.DEMOTIVATED,
            faces.SMART, faces.SAD, faces.LONELY
        )

    def on_keys_generation(self):
        self.set('face', self._get_random_face(faces.AWAKE))
        self.set('status', self._voice.on_keys_generation())
        self.update()

    def on_normal(self):
        self.set('face', self._get_random_face(faces.AWAKE))
        self.set('status', self._voice.on_normal())
        self.update()

    def set_closest_peer(self, peer, num_total):
        if peer is None:
            self.set('friend_name', None)
        else:
            name = f'{peer.name()} ({peer.pwnd_total()})'
            self.set('friend_name', name)
        self.update()

    def on_new_peer(self, peer):
        if peer.first_encounter():
            face = self._get_random_face(random.choice([faces.AWAKE, faces.COOL]))
        elif peer.is_good_friend(self._config):
            face = self._get_random_face(random.choice([faces.MOTIVATED, faces.FRIEND, faces.HAPPY]))
        else:
            face = self._get_random_face(random.choice([faces.EXCITED, faces.HAPPY, faces.SMART]))

        self.set('face', face)
        self.set('status', self._voice.on_new_peer(peer))
        self.update()
        time.sleep(3)

    def on_lost_peer(self, peer):
        self.set('face', self._get_random_face(faces.LONELY))
        self.set('status', self._voice.on_lost_peer(peer))
        self.update()

    def on_free_channel(self, channel):
        self.set('face', self._get_random_face(faces.SMART))
        self.set('status', self._voice.on_free_channel(channel))
        self.update()

    def on_reading_logs(self, lines_so_far=0):
        self.set('face', self._get_random_face(faces.SMART))
        self.set('status', self._voice.on_reading_logs(lines_so_far))
        self.update()

    def wait(self, secs, sleeping=True):
        """
        Wait for specified seconds with face animation

        This is THE KEY METHOD for pwnagotchi behavior - it cycles
        through faces and status messages during wait periods.
        """
        was_normal = self.is_normal()
        part = secs / 10.0

        for step in range(0, 10):
            # Check if exit was requested
            if self._agent and getattr(self._agent, '_exit_requested', False):
                return

            # Keep previous face/status for first few steps if not normal
            if was_normal or step > 5:
                if sleeping:
                    self.set('face', self._get_random_face(faces.SLEEP))
                    if secs > 1:
                        self.set('status', self._voice.on_napping(int(secs)))
                    else:
                        self.set('status', self._voice.on_awakening())
                else:
                    self.set('status', self._voice.on_waiting(int(secs)))

                    # Alternate looking left/right
                    good_mood = self._agent.in_good_mood() if self._agent else False
                    if step % 2 == 0:
                        self.set('face', self._get_random_face(faces.LOOK_R_HAPPY if good_mood else faces.LOOK_R))
                    else:
                        self.set('face', self._get_random_face(faces.LOOK_L_HAPPY if good_mood else faces.LOOK_L))

            # Sleep in smaller chunks so exit is responsive
            chunk = min(part, 0.5)
            remaining = part
            while remaining > 0:
                if self._agent and getattr(self._agent, '_exit_requested', False):
                    return
                time.sleep(min(chunk, remaining))
                remaining -= chunk
            secs -= part

        self.on_normal()

    def on_shutdown(self):
        self.set('face', self._get_random_face(faces.SLEEP))
        self.set('status', self._voice.on_shutdown())
        self.update(force=True)
        self._frozen = True

    def on_bored(self):
        self.set('face', self._get_random_face(faces.BORED))
        self.set('status', self._voice.on_bored())
        self.update()

    def on_sad(self):
        self.set('face', self._get_random_face(faces.SAD))
        self.set('status', self._voice.on_sad())
        self.update()

    def on_angry(self):
        self.set('face', self._get_random_face(faces.ANGRY))
        self.set('status', self._voice.on_angry())
        self.update()

    def on_motivated(self, reward):
        self.set('face', self._get_random_face(faces.MOTIVATED))
        self.set('status', self._voice.on_motivated(reward))
        self.update()

    def on_demotivated(self, reward):
        self.set('face', self._get_random_face(faces.DEMOTIVATED))
        self.set('status', self._voice.on_demotivated(reward))
        self.update()

    def on_excited(self):
        self.set('face', self._get_random_face(faces.EXCITED))
        self.set('status', self._voice.on_excited())
        self.update()

    def on_assoc(self, ap):
        self.set('face', self._get_random_face(faces.INTENSE))
        self.set('status', self._voice.on_assoc(ap))
        self.update()

    def on_deauth(self, sta):
        self.set('face', self._get_random_face(faces.COOL))
        self.set('status', self._voice.on_deauth(sta))
        self.update()

    def on_miss(self, who):
        self.set('face', self._get_random_face(faces.SAD))
        self.set('status', self._voice.on_miss(who))
        self.update()

    def on_grateful(self):
        self.set('face', self._get_random_face(faces.GRATEFUL))
        self.set('status', self._voice.on_grateful())
        self.update()

    def on_lonely(self):
        self.set('face', self._get_random_face(faces.LONELY))
        self.set('status', self._voice.on_lonely())
        self.update()

    def on_handshakes(self, new_shakes):
        self.set('face', self._get_random_face(faces.HAPPY))
        self.set('status', self._voice.on_handshakes(new_shakes))
        self.update()

    def on_unread_messages(self, count, total):
        self.set('face', self._get_random_face(faces.EXCITED))
        self.set('status', self._voice.on_unread_messages(count, total))
        self.update()
        time.sleep(5.0)

    def on_uploading(self, to):
        self.set('face', self._get_random_face(faces.UPLOAD))
        self.set('status', self._voice.on_uploading(to))
        self.update(force=True)

    def on_rebooting(self):
        self.set('face', self._get_random_face(faces.BROKEN))
        self.set('status', self._voice.on_rebooting())
        self.update()

    def on_custom(self, text):
        self.set('face', self._get_random_face(faces.DEBUG))
        self.set('status', self._voice.custom(text))
        self.update()

    def update(self, force=False, new_data=None):
        """Render all UI elements to display"""
        if new_data:
            for key, val in new_data.items():
                self.set(key, val)

        with self._lock:
            if self._frozen:
                return

            # Don't draw if pause menu is active
            if hasattr(self, '_agent') and self._agent and getattr(self._agent, '_menu_active', False):
                return

            state = self._state
            changes = state.changes(ignore=self._ignore_changes)

            if force or len(changes):
                # Clear display
                self._display.clear(COLOR_BLACK)

                # Draw all elements
                for key, elem in state.items():
                    try:
                        elem.draw(self._display)
                    except Exception as e:
                        logging.debug(f"Error drawing {key}: {e}")

                # Flip buffer to display
                self._display.flip()

                # Call render callbacks
                for cb in self._render_cbs:
                    try:
                        cb(None)  # No canvas in native mode
                    except:
                        pass

                state.reset()

    def cleanup(self):
        """Clean up display"""
        self._display.cleanup()
