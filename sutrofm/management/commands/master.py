import logging
import time
from datetime import datetime, timedelta

import requests
import simplejson as json
from django.conf import settings
from django.core.management.base import BaseCommand
from redis import ConnectionPool, StrictRedis

from sutrofm.redis_models import Party, Message

redis_connection_pool = ConnectionPool(**settings.WS4REDIS_CONNECTION)

RDIO_OAUTH2_KEY = 'c2y48bscf6hpd768b6cwvafy'
RDIO_OAUTH2_SECRET = 'sHf9GavUrP'

WAIT_FOR_USERS = timedelta(minutes=5)


class Command(BaseCommand):
  def add_arguments(self, parser):
    parser.add_argument('room_id', type=str)

  def __init__(self, *args, **kwargs):
    super(Command, self).__init__(*args, **kwargs)
    self.redis = None
    self.party = None
    self.party_id = None
    self.currently_playing = None
    self.current_track_duration = None
    self.current_start_time = None
    self.keep_running = True

  def handle(self, room_id, *args, **kwargs):
    self.party_id = room_id
    self.redis = StrictRedis(connection_pool=redis_connection_pool)
    self.party = Party.get(self.redis, room_id)

    self.currently_playing = None
    self.current_track_duration = None
    self.current_start_time = None

    self.play_track(self.party.playing_track_key)

    self.run()

  def run(self):
    while self.keep_running:
      try:
        self.keep_running = self.tick()
      except Exception:
        logging.exception("AH DAEMON PROBLEM")
      time.sleep(1)

  def get_duration(self, track_key):
    response = requests.post('https://services.rdio.com/api/1/get', {
      'keys': track_key,
      'method': 'get',
      'access_token': settings.RDIO_ACCESS_TOKEN
    })
    return json.loads(response.text)['result'][track_key]['duration']

  def play_track(self, track_key):
    self.current_track_duration = None
    self.current_start_time = None
    self.currently_playing = None

    if track_key:
      self.currently_playing = track_key
      self.current_track_duration = self.get_duration(track_key)
      self.current_start_time = self.party.playing_track_start_time

  def play_next_track(self):
    # Refresh party data
    self.party.play_next_track()
    self.party.save(self.redis)
    self.party.broadcast_player_state(self.redis)
    self.party.broadcast_queue_state(self.redis)

    self.play_track(self.party.playing_track_key)
    self.send_play_track_message(self.currently_playing)

  def send_play_track_message(self, rdio_track_key):
    message = Message.make_now_playing_message(self.redis, self.party, rdio_track_key)
    message.save(self.redis)
    self.party.broadcast_message_added(self.redis, message)

  def tick(self):
    # Refresh the party data
    self.party = Party.get(self.redis, self.party_id)

    position = (datetime.utcnow() - (self.current_start_time or datetime.utcnow())).seconds
    if not self.currently_playing or (position > self.current_track_duration) or self.party.should_skip():
      self.play_next_track()
    return self.should_keep_running()

  def should_keep_running(self):
    """ Kill if no one is online in the room any more """
    return True # TODO when User models are more fleshed out
