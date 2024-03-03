import asyncio
from datetime import datetime

import tenacity.stop

import config
from reservation import Reservation

from io import BytesIO, StringIO
import json
import pycurl
from tenacity import retry
from urllib.parse import urlencode


headers = [
    'Host: api.resy.com',
    f'authorization: ResyAPI api_key="{config.api_key}"',
    'user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    f'x-resy-auth-token: {config.auth_token}',

]
post_headers = [
    'content-type: application/json',
    'origin: https://widgets.resy.com',
    'referer: https://widgets.resy.com/',
]


async def snipe_reservation(reservation, user_id):
    now = datetime.now()
    schedule_time = datetime.strptime(f'{now.date()} {reservation.snipe_time}:00', '%Y-%m-%d %H:%M:%S')
    time_left = schedule_time - now
    sleep_time = time_left.total_seconds()  # seconds from now until the next tables become available
    await asyncio.sleep(sleep_time)
    return resy_workflow(reservation)


@retry(stop=tenacity.stop.stop_after_delay(15))
def resy_workflow(reservation: Reservation):
    config_token = find_reservations(reservation)
    print(config_token)
    book_token, payment_id = get_book_token(config_token, reservation.date, reservation.party_size)
    print(book_token, payment_id)
    # book_reservation(book_token, payment_id)
    return book_token


def find_reservations(reservation: Reservation):
    buffer = BytesIO()
    c = pycurl.Curl()
    c.setopt(c.URL, f'https://api.resy.com/4/find?lat=0&long=0&day={reservation.date}&party_size={reservation.party_size}&venue_id={reservation.venue_id}')
    c.setopt(pycurl.WRITEFUNCTION, buffer.write)
    c.setopt(pycurl.HTTPHEADER, headers)

    c.perform()
    response = json.loads(buffer.getvalue())
    # search the response for the closest time to reservation.res_time
    return response['results']['venues'][0]['slots'][0]['config']['token']


def get_book_token(config_token, date, party_size):
    buffer = BytesIO()

    c = pycurl.Curl()
    c.setopt(c.URL, "https://api.resy.com/3/details")
    body = {
        'commit': 1,
        'config_id': config_token,
        'day': date,
        'party_size': party_size
    }
    c.setopt(pycurl.POST, 1)
    c.setopt(pycurl.READDATA, StringIO(json.dumps(body)))
    c.setopt(pycurl.POSTFIELDSIZE, len(json.dumps(body)))
    c.setopt(pycurl.WRITEFUNCTION, buffer.write)
    c.setopt(pycurl.HTTPHEADER, headers + post_headers)

    c.perform()
    c.close()
    response = json.loads(buffer.getvalue())
    return response['book_token']['value'], response['user']['payment_methods'][0]['id']


def book_reservation(book_token, payment_id):
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
    c.setopt(pycurl.POSTFIELDS, urlencode(body))
    c.setopt(pycurl.WRITEFUNCTION, buffer.write)
    c.setopt(pycurl.HTTPHEADER, headers + post_headers)

    c.perform()
    c.close()
    response = json.loads(buffer.getvalue())
    return response['book_token']['value'], response['user']['payment_methods']['id']