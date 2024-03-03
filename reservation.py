from dataclasses import dataclass


@dataclass
class Reservation:
    venue_id: int
    party_size: int
    date: str
    res_time: str
    snipe_time: str
