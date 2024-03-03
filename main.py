import config
import modals

import asyncio
import discord
from discord.ext import commands


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(intents=intents, command_prefix=['?', '!'])


@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')


@bot.tree.command()
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("pong")


@bot.tree.command()
async def make_reservation(interaction: discord.Interaction):
    modal = modals.ResyModal(bot)
    await interaction.response.send_modal(modal)
    print(modal.reservation)


@bot.tree.command()
async def register(interaction: discord.Interaction):
    modal = modals.RegistrationModal()
    await interaction.response.send_modal(modal)


@bot.command()
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("synced commands")


async def main():
    async with bot:
        await bot.start(config.discord_token)

asyncio.run(main())
