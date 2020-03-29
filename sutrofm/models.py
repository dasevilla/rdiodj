from django.contrib.auth.models import AbstractUser
from django.db.models import Sum, Value, When, Case, Count
from django.utils.timezone import now

from django.db import models
from model_utils.fields import AutoCreatedField
from model_utils.models import TimeStampedModel

from sutrofm.spotify_api_utils import get_track_duration


class User(AbstractUser):
  parties = models.ManyToManyField('Party', through='UserPartyPresence')

  # related fields:
  # messages
  # queued_items
  # votes

  def check_in_to_party(self, party):
    UserPartyPresence.objects.get_or_create(user=self, party=party).update(last_check_in=now())


class UserPartyPresence(models.Model):
  user = models.ForeignKey('User', on_delete=models.CASCADE)
  party = models.ForeignKey('Party', on_delete=models.CASCADE)

  first_joined = AutoCreatedField()
  last_check_in = models.DateTimeField(default=now)


class Party(TimeStampedModel):
  name = models.CharField(max_length=128, unique=True, db_index=True)
  playing_item = models.ForeignKey('QueueItem', related_name='playing_party', on_delete=models.DO_NOTHING,
                                   blank=True, null=True)
  theme = models.TextField()

  users = models.ManyToManyField('User', through='UserPartyPresence')

  def play_next_queue_item(self):
    prev_item = self.playing_item
    self.playing_item = QueueItem.get_next(self)
    prev_item.delete()

  def user_count(self):
    return self.users.count()

  def __str__(self):
    return self.name


class ChatMessage(TimeStampedModel):
  user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='messages')
  party = models.ForeignKey('Party', on_delete=models.CASCADE, related_name='messages')
  message = models.TextField()


class QueueItem(TimeStampedModel):
  service = models.CharField(default='Spotify', max_length=32)
  identifier = models.CharField(max_length=128)
  title = models.TextField()
  artist_name = models.TextField()
  playing_start_time = models.DateTimeField(blank=True, null=True)
  duration_ms = models.IntegerField(blank=True, null=True)

  user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='queued_items')
  party = models.ForeignKey('Party', on_delete=models.CASCADE, related_name='queue')

  def load_duration(self):
    self.duration_ms = get_track_duration(self.identifier)
    self.save()

  def vote_score(self):
    return self.votes.aggregate(vote_sum=Sum('value'))['vote_sum'] or 0

  def should_skip(self):
    user_count = self.party.user_count()
    skip_count = self.votes.aggregate(skip_count=Count(Case(When(is_skip=True, then=Value(1)))))['skip_count']
    return skip_count > (user_count / 2)

  @staticmethod
  def get_next(party):
    return QueueItem.list_for_party_queryset(party).first()

  @staticmethod
  def list_for_party_queryset(party):
    # TODO: order by sum of votes -- may want to automatically cache them on the QueueItem
    return QueueItem.objects.filter(party=party, playing_start_time=None).order_by('created')

  def __str__(self):
    return f'{self.identifier}: {self.artist_name} - {self.title}'


class UserVote(TimeStampedModel):
  user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='votes')
  queue_item = models.ForeignKey('QueueItem', on_delete=models.CASCADE, related_name='votes')
  value = models.SmallIntegerField()  # set to 1 or -1 for easy summing
  is_skip = models.BooleanField(default=False)