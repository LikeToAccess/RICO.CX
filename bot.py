# -*- coding: utf-8 -*-
# filename          : bot.py
# description       : Discord bot interface for adding content to Plex
# author            : Ian Ault
# email             : liketoaccess@protonmail.com
# date              : 01-07-2023
# version           : v1.0
# usage             : python bot.py
# notes             :
# license           : MIT
# py version        : 3.11.1 (must run on 3.6 or higher)
#==============================================================================
import json
import discord

from discord.ext import commands

from download import threaded_download
from scraper import Scraper
from settings import DISCORD_BOT_TOKEN


scraper = Scraper()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
		command_prefix=(
			"please ",
			"Please ",
			"PLEASE ",
			"pls ",
			"Pls ",
			"PLS ",
		),
		intents=intents,
		case_insensitive=True
	)


@bot.event
async def on_ready():
	print(f"{bot.user} successfuly connected!")
	activity = "Free Movies on Plex!"
	await bot.change_presence(status=discord.Status.online, activity=discord.Game(activity))

@bot.command(name="search", help="Search for a movie and return the results.")
async def search(ctx, *query):
	query = " ".join(query) if isinstance(query, tuple) else query
	print(f"DEBUG (query): {query}")
	results = scraper.searchone(query)

	if results == 404:
		await ctx.reply("No results found", mention_author=False)
	results = json.dumps(results, indent=4)
	await ctx.reply(f"```js\n{results}```", mention_author=False)

@bot.command(name="download", aliases=["add"], help="Download a movie onto the Plex server.")
async def download(ctx, *query):
	query = " ".join(query) if isinstance(query, tuple) else query
	print(f"DEBUG (query): {query}")
	message = await ctx.send("Searching...")
	data = scraper.searchone(query)

	if data == 404:
		await message.edit(content="No results found.")
		return
	await message.edit(content=f"Found {data['title']}. Initializing download...")
	page_url = data["page_url"]
	url = scraper.get_video(page_url)
	if url == 225:
		await message.edit(content="Captcha!")
		# TODO: Add captcha solving
		return
	await message.edit(content="Starting download...")
	threaded_download(url, data)
	await message.edit(content="Download started.")

@bot.command(name="react", help="Post a reaction.")
async def react(ctx):
	await ctx.message.add_reaction("\U0001F44D")


if __name__ == "__main__":
	bot.run(DISCORD_BOT_TOKEN)
