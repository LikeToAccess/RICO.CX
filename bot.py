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
			"!"
		),
		intents=intents,
		case_insensitive=True
	)


def create_embed(data, color=0xCBAF2F):
	title = data["title"]
	poster_url = data["poster_url"]
	page_url = data["page_url"]
	data = data["data"]
	embed = discord.Embed(
			title=title,
			description=data["genre"],
			color=color
		)

	embed.set_footer(text=data['description_preview'])
	embed.set_thumbnail(url=poster_url)
	embed.add_field(name="\U0001F4C5", value=data["release_year"], inline=True)
	embed.add_field(name="IMDb", value=data["imdb_score"], inline=True)
	embed.add_field(name="\U0001F554", value=data["duration"], inline=True)
	return embed
	# await send(embed=embed)

@bot.event
async def on_ready():
	print(f"{bot.user} successfuly connected!")
	activity = "Free Movies on Plex!"
	await bot.change_presence(status=discord.Status.online, activity=discord.Game(activity))

@bot.command(name="search", help="Search for a movie and return the results.")
async def search(ctx, *args):
	query = " ".join(args) if isinstance(args, tuple) else args
	print(f"DEBUG (query): {query}")
	results = scraper.searchone(query)

	if results == 404:
		await ctx.reply("No results found", mention_author=False)
	results = json.dumps(results, indent=4)
	await ctx.reply(f"```js\n{results}```", mention_author=False)

@bot.command(name="popular", aliases=["pop"], help="List popular movies.")
async def popular(ctx, count=5):
	results = scraper.popular()
	if results == 404:
		await ctx.reply("No results found", mention_author=False)
	# results = json.dumps(results, indent=4)
	for result in results[:count]:
		await ctx.send(embed=create_embed(result))

@bot.command(name="download", aliases=["add"], help="Download a movie onto the Plex server.")
async def download(ctx, *args):
	query = " ".join(args) if isinstance(args, tuple) else args
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
		captcha = discord.File("captcha.png")
		await ctx.send(content="Please solve using the solve command.", file=captcha)
		# TODO: Add captcha solving
		return
	await message.edit(content="Starting download...")
	threaded_download(url, data)
	await message.edit(content="Download started.")

@bot.command(name="solve", aliases=["captcha"], help="Solves a captcha.")
async def solve(ctx, solution=None):
	if solution is None:
		captcha = discord.File("captcha.png")
		await ctx.send(content="Please solve using the solve command.", file=captcha)
		return

	solution = solution.upper()
	autocorrect_dictionary = {
		"0": "O",
		"1": "I",
		"2": "Z",
		"3": "E",
		"4": "A",
		"5": "S",
		"6": "G",
		"7": "T",
		"8": "B",
		"9": "G",
		" ": ""
	}
	solution = "".join([autocorrect_dictionary.get(c, c) for c in solution])
	print(f"DEBUG (solution): {solution}")
	if not solution.isalpha() or len(solution) != 7:
		await ctx.reply("Invalid solution. Please try again.", mention_author=False)
		return

@bot.command(name="react", help="Post a reaction.")
async def react(ctx):
	await ctx.message.add_reaction("\U0001F44D")


if __name__ == "__main__":
	bot.run(DISCORD_BOT_TOKEN)
