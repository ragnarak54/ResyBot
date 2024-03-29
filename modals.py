import resy
from reservation import Reservation
from resy import ResyWorkflow

import discord
from discord.ext import commands
from discord import ui
import json


class ResyModal(ui.Modal, title="New Reservation"):
    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    venue_id = ui.TextInput(label="Venue ID", required=True)
    party_size = ui.TextInput(label="Party size", required=True)
    date = ui.TextInput(label="Date", placeholder="YYYY-MM-DD", required=True)
    res_time = ui.TextInput(label="Time", placeholder="18:30", required=True)
    snipe_time = ui.TextInput(label="Snipe time", placeholder="09:00", required=True)
    reservation: Reservation

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.reservation = Reservation(venue_id=int(self.venue_id.value),
                                       party_size=int(self.party_size.value),
                                       date=str(self.date),
                                       res_time=str(self.res_time),
                                       snipe_time=str(self.snipe_time))
        embed = discord.Embed(title="Reservation Request Details:",
                              description=f"Venue ID: {self.venue_id}\n"
                                          f"Party size: {self.party_size}\n"
                                          f"Reservation date: {self.date}\n"
                                          f"Reservation time: {self.res_time}\n"
                                          f"Sniping tomorrow at: {self.snipe_time}",
                              colour=discord.Colour.dark_teal())
        # get user's api keys
        # if they dont exist, send error
        with open('user_tokens.json') as f:
            print(f'{interaction.user.id} requesting reservation')
            data = json.load(f)[str(interaction.user.id)]
            api_key, auth_token, time_zone = data.get('api_key'), data.get('auth_token'), data.get('time_zone')
        if not (api_key and auth_token and time_zone):
            await interaction.response.send_message(
                "Couldn't find token info for your account. Use the /register command to register your account")
            return
        embed.set_author(name=interaction.user.name,
                         icon_url=None if not interaction.user.avatar else interaction.user.avatar.url)
        await interaction.response.send_message(embed=embed)
        try:
            workflow = ResyWorkflow(self.reservation, api_key, auth_token, time_zone)
            time_booked = await workflow.snipe_reservation()
            message = f"Reservation successfully booked, {time_booked}!"
        except resy.ExistingReservationError:
            message = "You already have a reservation that day"
        except:
            message = "Failed to book"
        await interaction.user.send(message)


class RegistrationModal(ui.Modal, title="Register Account and API Keys"):
    api_key = ui.TextInput(label="API key", placeholder='"Authorization" header', required=True)
    resy_token = ui.TextInput(label="Auth Token", placeholder='"X-Resy-Auth-Token" header', required=True,
                              style=discord.TextStyle.long)
    time_zone = ui.TextInput(label="Time zone", placeholder='west, mountain, central, or east')

    async def on_submit(self, interaction: discord.Interaction) -> None:
        with open('user_tokens.json') as f:
            data = dict(json.load(f))
        data[str(interaction.user.id)] = {
            'api_key': self.api_key.value,
            'auth_token': self.resy_token.value,
            'time_zone': self.time_zone.value
        }
        with open('user_tokens.json', 'w') as f:
            json.dump(data, f, indent=4)
        await interaction.response.send_message(f'Tokens registered')
