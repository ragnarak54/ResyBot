import logging

import config
from reservation import Reservation

import asyncio
from bisect import bisect_left
from datetime import datetime, timedelta
from io import BytesIO, StringIO
import json
import pycurl
import tenacity
from tenacity import retry, stop, wait_chain, wait_fixed
from urllib.parse import urlencode
from zoneinfo import ZoneInfo


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ExistingReservationError(Exception):
    pass


class ResyWorkflow:
    headers = [
        'Host: api.resy.com',
        'authorization: ResyAPI api_key="{}"',
        'user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'x-resy-auth-token: {}',
    ]
    post_headers = [
        'origin: https://widgets.resy.com',
        'referer: https://widgets.resy.com/',
    ]
    reservation: Reservation
    time_zone: ZoneInfo

    def __init__(self, reservation, api_key, auth_token, time_zone):
        self.headers[1] = self.headers[1].format(api_key)
        self.headers[3] = self.headers[3].format(auth_token)
        self.reservation = reservation
        self.set_time_zone(time_zone)

    def set_time_zone(self, time_zone):
        tz = time_zone.lower()
        if tz == "central":
            self.time_zone = ZoneInfo("America/Chicago")
        elif tz == "west":
            self.time_zone = ZoneInfo("America/Los_Angeles")
        elif tz == "mountain":
            self.time_zone = ZoneInfo("America/Denver")
        else:
            self.time_zone = ZoneInfo("America/New_York")

    async def snipe_reservation(self):
        now = datetime.now(tz=self.time_zone)
        print(f"currently {now}")
        schedule_time = datetime.strptime(f'{now.date() + timedelta(days=1)} {self.reservation.snipe_time}:05',
                                          '%Y-%m-%d %H:%M:%S').replace(tzinfo=self.time_zone)
        time_left = schedule_time - now
        sleep_time = time_left.total_seconds()  # seconds from now until the next tables become available
        print(f"reservation request confirmed, waiting {int(sleep_time)} seconds to snipe")
        await asyncio.sleep(sleep_time)
        return self.resy_workflow()

    @retry(stop=stop.stop_after_delay(35),
           wait=wait_chain(*[wait_fixed(0.5) for i in range(30)] +
                            [wait_fixed(1.5) for i in range(20)]),
           retry=tenacity.retry_if_not_exception_type(ExistingReservationError),
           before_sleep=tenacity.before_sleep_log(logger, logging.INFO))
    def resy_workflow(self):
        log("starting snipe attempt")
        available_slots = self.find_reservations()
        if len(available_slots) == 0:
            log("No availability found")
            raise Exception
        log(f"found {len(available_slots)} slots, searching for best")
        best_match = find_closest_match(available_slots, self.reservation)
        config_token = best_match['config']['token']
        log("available table found, attempting to get book token")
        book_token, payment_id = self.get_book_token(config_token)
        log("got book token! attempting to snipe...")
        self.book_reservation(book_token, payment_id)
        return best_match['date']['start']

    def find_reservations(self):
        buffer = BytesIO()
        c = pycurl.Curl()
        c.setopt(c.URL,
                 f'https://api.resy.com/4/find?lat=0&long=0'
                 f'&day={self.reservation.date}'
                 f'&party_size={self.reservation.party_size}'
                 f'&venue_id={self.reservation.venue_id}')
        c.setopt(pycurl.WRITEFUNCTION, buffer.write)
        c.setopt(pycurl.HTTPHEADER, self.headers)

        c.perform()
        log(f'/find returned {c.getinfo(pycurl.RESPONSE_CODE)}')
        c.close()
        response = json.loads(buffer.getvalue())
        try:
            return response['results']['venues'][0]['slots']
        except KeyError as e:
            print(response)
            raise e

    def get_book_token(self, config_token):
        buffer = BytesIO()

        c = pycurl.Curl()
        c.setopt(c.URL, "https://api.resy.com/3/details")
        body = {
            'commit': 1,
            'config_id': config_token,
            'day': self.reservation.date,
            'party_size': self.reservation.party_size
        }
        c.setopt(pycurl.POST, 1)
        c.setopt(pycurl.READDATA, StringIO(json.dumps(body)))
        c.setopt(pycurl.POSTFIELDSIZE, len(json.dumps(body)))
        c.setopt(pycurl.WRITEFUNCTION, buffer.write)
        c.setopt(pycurl.HTTPHEADER, self.headers + self.post_headers + ['content-type: application/json'])

        c.perform()
        log(f'/details returned {c.getinfo(pycurl.RESPONSE_CODE)}')
        c.close()
        response = json.loads(buffer.getvalue())
        if not response.get('book_token') or not response.get('user'):
            print(response)
        return response['book_token']['value'], response['user']['payment_methods'][0]['id']

    def book_reservation(self, book_token, payment_id):
        buffer = BytesIO()

        c = pycurl.Curl()
        c.setopt(pycurl.VERBOSE, 1)
        c.setopt(c.URL, "https://api.resy.com/3/book")
        body = {
            'book_token': book_token,
            'struct_payment_method': f'{{"id":{payment_id}}}',
            'source_id': 'resy.com-venue-details'
        }
        c.setopt(pycurl.POST, 1)
        c.setopt(pycurl.HTTPHEADER, self.headers + self.post_headers)
        c.setopt(pycurl.POSTFIELDS, urlencode(body))
        c.setopt(pycurl.WRITEFUNCTION, buffer.write)

        c.perform()
        log(f'/book returned {c.getinfo(pycurl.RESPONSE_CODE)}')
        c.close()
        response = json.loads(buffer.getvalue())
        print(response)
        if c.getinfo(pycurl.RESPONSE_CODE) == 412:
            raise ExistingReservationError


def get_datetime_from_slot(slot):
    return datetime.strptime(slot['date']['start'], '%Y-%m-%d %H:%M:%S')


def find_closest_match(available_slots, reservation):
    target = datetime.strptime(f'{reservation.date} {reservation.res_time}', '%Y-%m-%d %H:%M')
    pos = bisect_left(available_slots, target, key=get_datetime_from_slot)
    return get_best_match_from_position(available_slots, pos, target)


def get_best_match_from_position(available_slots, pos, target):
    if pos == 0:
        return available_slots[0]
    if pos == len(available_slots):
        return available_slots[-1]
    before = available_slots[pos - 1]
    after = available_slots[pos]
    if get_datetime_from_slot(after) - target < target - get_datetime_from_slot(before):
        return after
    else:
        return before


def log(message):
    now = datetime.now()
    print(f'{now.strftime("%H:%M:%S")}: {message}')


# res = Reservation(52013, 2, "2024-03-21", "18:45", "10:00")
# workflow = ResyWorkflow(res, config.api_key, config.auth_token, "east")
# workflow.resy_workflow()