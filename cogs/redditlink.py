import asyncio
import os
import re
import sys
import aiohttp

import discord
# import ffmpeg
import youtube_dl
from discord.ext import commands
from discord_slash import cog_ext

from functions import MessageColors, embed
from typing_extensions import TYPE_CHECKING
from functions import MyContext

if TYPE_CHECKING:
  from index import Friday as Bot


ytdl_format_options = {
    # 'format': 'bestvideo+bestaudio/worstvideo+worstaudio',
    'format': 'worstvideo+worstaudio/worstvideo',
    # 'audioformat': 'mp3',
    'merge_output_format': 'mp4',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    # 'max_filesize': '8M',
    'postprocessors': [{
        'key': 'FFmpegVideoConvertor',
        'preferedformat': 'webm'
    }],
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    # 'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # bind to ipv4 since ipv6 addresses cause issues sometimes
}
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class redditlink(commands.Cog):
  def __init__(self, bot: "Bot"):
    self.bot = bot
    self.emoji = "🔗"
    self.lock = asyncio.Lock()
    self.pattern = r"https://www.reddit.com/r/[a-zA-Z0-9-_]+/comments/[a-zA-Z0-9]+/[a-zA-Z0-9_-]+"
    self.patternspoiler = r"||https://www.reddit.com/r/[a-zA-Z0-9-_]+/comments/[a-zA-Z0-9]+/[a-zA-Z0-9_-]+||"

  async def request(self, url):
    async with self.lock:
      async with self.bot.session.get(
              url,
              headers={
                  'User-Agent':
                  f'DiscordBot (https://github.com/Rapptz/discord.py {discord.__version__}) Python/{sys.version_info.major}.{sys.version_info.minor} aiohttp/{aiohttp.__version__}'
              }) as r:
        if r.status == 200:
          return await r.json()

  @commands.Cog.listener()
  async def on_message(self, message: discord.Message):
    if message.author.bot:
      return
    # required_perms = [("add_reactions",True)]
    # guild = ctx.guild
    # me = guild.me if guild is not None else self.bot.user
    # permissions = ctx.channel.permissions_for(me)
    # missing = [perm for perm,value in required_perms if getattr(permissions,perm) != value]

    # if missing:
    #   return

    # TODO: remove this check when members intent
    if not message.guild:
      return

    if (await self.bot.get_context(message)).command is not None:
      return

    reg = re.findall(self.pattern, message.content)
    # spoiler = re.findall(self.patternspoiler,ctx.content)

    if len(reg) != 1:
      return

    body = await self.request(reg[0] + ".json")

    data = None
    video = None
    embeded = None
    image = None
    try:
      data = body[0]["data"]["children"][0]["data"]["crosspost_parent_list"][0]
    except BaseException:
      data = body[0]["data"]["children"][0]["data"]
      # try:
      # except:
      #   pass

    try:
      if data["media"] != "null":
        video = data["media"]["reddit_video"]["hls_url"]
      # elif len(data["crosspost_parent_list"]) > 0:
      #   video = data["crosspost_parent_list"][0]["media"]["reddit_video"]["hls_url"]
    except BaseException:
      # raise
      pass

    try:
      embeded = data["media"]["oembed"]
    except BaseException:
      pass
    if "i.redd.it" in data["url"]:
      image = data["url"]

    if data["url"] in message.content:
      return

    if data["url"].endswith(".html"):
      return

    if data is None and video is None and embeded is None and image is None:
      return

    try:
      await message.add_reaction(self.emoji)
    except discord.Forbidden:
      pass
    except discord.NotFound:
      pass

  @commands.Cog.listener()
  async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
    if payload.user_id == self.bot.user.id:
      return
    # channel = self.bot.get_guild(payload.guild_id).get_channel(payload.channel_id)
    # async with channel.typing():
    if payload.guild_id:
      message = None
      try:
        message = await (self.bot.get_channel(payload.channel_id)).fetch_message(payload.message_id)
      except discord.NotFound:
        return
    # TODO: When members intent change for the check below
    elif not payload.guild_id:
      return
    # else:
    #   message = await (self.bot.get_user(payload.user_id)).dm_channel.fetch_message(payload.message_id)
    guild = self.bot.get_guild(payload.guild_id)
    channel = self.bot.get_channel(payload.channel_id)
    # message = await channel.fetch_message(payload.message_id)
    if self.bot.user.id == payload.user_id or (payload.member and self.bot.user == payload.member.bot):
      return
    if payload.user_id != message.author.id:
      return
    if payload.emoji.name != self.emoji:
      return
    if len([react.emoji for react in message.reactions if react.me and react.emoji == self.emoji]) < 1:
      return
    try:
      await asyncio.gather(
          message.remove_reaction(self.emoji, self.bot.user),
          message.remove_reaction(self.emoji, payload.member)
      )
    except BaseException:
      pass
    async with channel.typing():
      try:
        await self.extract(message.content, payload=payload, guild=guild, channel=channel, message=message)
      except Exception as e:
        await message.reply(embed=embed(title="Something went wrong", description="Please try again later. I have notified my boss of this error", color=MessageColors.ERROR), mention_author=False)
        raise e

  @commands.command(name="redditextract", help="Extracts the media from the reddit post")
  async def norm_extract(self, ctx: "MyContext", link: str):
    if not ctx.is_interaction():
      async with ctx.typing():
        return await self.extract(query=link, command=True, ctx=ctx, guild=ctx.guild, channel=ctx.channel)
    return await self.extract(query=link, command=True, ctx=ctx, guild=ctx.guild, channel=ctx.channel)

  @cog_ext.cog_slash(name="redditextract", description="Extracts the file from the reddit post")
  async def slash_extract(self, ctx, link: str):
    await ctx.defer()
    await self.extract(query=link, command=True, ctx=ctx, guild=ctx.guild, channel=ctx.channel)

  async def extract(self, query, command: bool = False, payload: discord.RawReactionActionEvent = None, ctx: "MyContext" = None, guild=None, channel: discord.TextChannel = None, message: discord.Message = None):
    if ctx is None and message is not None:
      ctx = await self.bot.get_context(message)
    if guild is None and not ctx.guild_id:
      raise commands.ArgumentParsingError()
    if channel is None and not ctx.channel_id:
      raise commands.ArgumentParsingError()
    if message is None and not command:
      raise commands.ArgumentParsingError()
    # TODO: check the max file size of the server and change the quality of the video to match
    reg = re.findall(self.pattern, query)

    if len(reg) != 1:
      return await ctx.send(embed=embed(title="That is not a reddit post url", color=MessageColors.ERROR))

    body = None
    try:
      body = await self.request(reg[0] + ".json")
    except BaseException:
      pass

    try:
      try:
        data = body[0]["data"]["children"][0]["data"]["crosspost_parent_list"][0]
      except BaseException:
        data = body[0]["data"]["children"][0]["data"]
    except KeyError:
      return await ctx.send(embed=embed(title="There was a problem connecting to reddit", color=MessageColors.ERROR))

    link = None
    linkdata = None
    video = False
    # try:
    if data["media"] is not None and "reddit_video" in data["media"]:
      link = data["media"]["reddit_video"]["hls_url"]
      loop = asyncio.get_event_loop()
      linkdata = await loop.run_in_executor(None, lambda: ytdl.extract_info(link, download=True))
      ext = "webm"  # linkdata['ext']
      video = True
      # linkdata = await ytdl.extract_info(link, download=True)

      if 'entries' in linkdata:
        # take first item from a playlist
        linkdata = linkdata['entries'][0]
      # link = linkdata["url"]
      # pprint.pprint(linkdata)
      # print(f'{linkdata["extractor"]}-{linkdata["id"]}-{linkdata["title"]}.{linkdata["ext"]}')
      # link = data["media"]["reddit_video"]["fallback_url"]
    else:
      link = data["url"]
    # except:
    #   raise

    # TODO: Does not get url for videos atm
    channel = message.channel if payload is not None else ctx.channel
    nsfw = channel.nsfw if channel is not None and not isinstance(channel, discord.Thread) else channel.parent.nsfw if channel is not None and isinstance(channel, discord.Thread) else False
    if (nsfw is True and data["over_18"] is True) or (nsfw is False and data["over_18"] is False) or (nsfw is True and data["over_18"] is False):
      spoiler = False
    else:
      spoiler = True

    if video is True:
      thispath = os.getcwd()
      if "\\" in thispath:
        seperator = "\\\\"
      else:
        seperator = "/"
      mp4file = f'{thispath}{seperator}{linkdata["extractor"]}-{linkdata["id"]}-{linkdata["title"]}.{ext}'
      try:
        # name = f'{linkdata["extractor"]}-{linkdata["id"]}-{linkdata["title"]}.{linkdata["ext"]}'
        name = data["title"].split()
        return await ctx.send(file=discord.File(fp=mp4file, filename=f'friday-bot.com_{"_".join(name)}.{ext}', spoiler=spoiler))
      except discord.HTTPException:
        return await ctx.send(embed=embed(title="This file is too powerful to be uploaded", description="You will have to open reddit to view this", color=MessageColors.ERROR))
      finally:
        try:
          os.remove(mp4file)
        except PermissionError:
          pass
    else:
      if spoiler is True:
        return await ctx.send(content="||" + link + "||")
      else:
        return await ctx.send(content=link)
    # elif reaction.message.channel.nsfw == False and data["over_18"] == False:

    # print(len(body))
    # if ctx.channel.nsfw and body["data"]["over_18"]:

    # await ctx.reply(embed=embed(title="Meme"))
    # return embed(title="Meme")
    # if self.bot.user == reaction.message.reactions


def setup(bot):
  bot.add_cog(redditlink(bot))
