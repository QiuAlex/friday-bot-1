import discord
from discord.ext import commands

from discord_slash import cog_ext,SlashContext

from functions import embed

class Info(commands.Cog):
  def __init__(self,bot):
    self.bot = bot

  @commands.group(name="info",description="Displays some information about myself :)")
  async def norm_info(self,ctx):
    post = await self.info(ctx)
    await ctx.reply(**post)

  @cog_ext.cog_slash(name="info",description="Displays some information about myself :)")
  async def slash_info(self,ctx):
    await ctx.respond()
    post = await self.info(ctx)
    await ctx.send(**post)

  async def info(self,ctx):
    return dict(
      embed=embed(
        title=f"{self.bot.user.name} - Info",
        thumbnail=self.bot.user.avatar_url,
        description="Some information about me, Friday ;)",
        fieldstitle=["Username","Guilds joined","Status","Latency","Shards","Audio Nodes","Loving Life","Existed since"],
        fieldsval=[self.bot.user.name,len(self.bot.guilds),ctx.me.activity.name,f"{self.bot.latency*1000:,.0f} ms",self.bot.shard_count,len(self.bot.wavelink.nodes),"True",self.bot.user.created_at]
      )
    )

def setup(bot):
  bot.add_cog(Info(bot))