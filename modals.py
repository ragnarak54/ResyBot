import json

from reservation import Reservation
import resy

import discord
from discord.ext import commands
from discord import ui


class ResyModal(ui.Modal, title="New Reservation"):
    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    venue_id = ui.TextInput(label="Venue ID", required=True)
    party_size = ui.TextInput(label="Party size", required=True)
    date = ui.TextInput(label="Date", placeholder="YYYY-MM-DD", required=True)
    res_time = ui.TextInput(label="Time", placeholder="18:30", required=True)
    snipe_time = ui.TextInput(label="Snipe Time", placeholder="09:00", required=True)
    reservation: Reservation

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.reservation = Reservation(venue_id=int(self.venue_id.value),
                                       party_size=int(self.party_size.value),
                                       date=str(self.date),
                                       res_time=str(self.res_time),
                                       snipe_time=str(self.snipe_time))
        await interaction.response.send_message(
            f'Reservation at {self.venue_id} for {self.party_size} at {self.res_time} on {self.date}')
        result = await resy.snipe_reservation(self.reservation, interaction.user)
        await interaction.user.send(f"Reservation result: {result}")


class RegistrationModal(ui.Modal, title="Register API Keys"):
    api_key = ui.TextInput(label="API key", placeholder='"Authorization" header', required=True)
    resy_token = ui.TextInput(label="Auth Token", placeholder='"X-Resy-Auth-Token" header', required=True, style=discord.TextStyle.long)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        with open('user_tokens.json') as f:
            data = json.load(f)
        data[interaction.user.id] = {
            'api_key': self.api_key.value,
            'authorization': self.resy_token.value
        }
        with open('user_tokens.json', 'w') as f:
            json.dump(data, f)
        await interaction.response.send_message(f'Tokens registered')