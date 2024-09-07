"""
Copyright © Krypton 2019-Present - https://github.com/kkrypt0nn (https://krypton.ninja)
Description:
🐍 A simple template to start to code your own and personalized Discord bot in Python

Version: 6.2.0
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Context
from .llm_flow import rag
import re

class General(commands.Cog, name="general"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.context_menu_user = app_commands.ContextMenu(
            name="Grab ID", callback=self.grab_id
        )
        self.bot.tree.add_command(self.context_menu_user)
        self.context_menu_message = app_commands.ContextMenu(
            name="Remove spoilers", callback=self.remove_spoilers
        )
        self.bot.tree.add_command(self.context_menu_message)

    # Message context menu command
    async def remove_spoilers(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        """
        Removes the spoilers from the message. This command requires the MESSAGE_CONTENT intent to work properly.

        :param interaction: The application command interaction.
        :param message: The message that is being interacted with.
        """
        spoiler_attachment = None
        for attachment in message.attachments:
            if attachment.is_spoiler():
                spoiler_attachment = attachment
                break
        embed = discord.Embed(
            title="Message without spoilers",
            description=message.content.replace("||", ""),
            color=0xBEBEFE,
        )
        if spoiler_attachment is not None:
            embed.set_image(url=attachment.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # User context menu command
    async def grab_id(
        self, interaction: discord.Interaction, user: discord.User
    ) -> None:
        """
        Grabs the ID of the user.

        :param interaction: The application command interaction.
        :param user: The user that is being interacted with.
        """
        embed = discord.Embed(
            description=f"The ID of {user.mention} is `{user.id}`.",
            color=0xBEBEFE,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


    @commands.hybrid_command(
        name="help", description="List all commands the bot has loaded."
    )
    #@app_commands.guilds(discord.Object(id=869915828097802311))
    async def help(self, context: Context) -> None:
        prefix = self.bot.config["prefix"]
        embed = discord.Embed(
            title="Help", description="List of available commands:", color=0xBEBEFE
        )
        for i in self.bot.cogs:
            if i == "owner" and not (await self.bot.is_owner(context.author)):
                continue
            cog = self.bot.get_cog(i.lower())
            commands = cog.get_commands()
            data = []
            for command in commands:
                description = command.description.partition("\n")[0]
                data.append(f"{prefix}{command.name} - {description}")
            help_text = "\n".join(data)
            embed.add_field(
                name=i.capitalize(), value=f"```{help_text}```", inline=False
            )
        await context.send(embed=embed)

    @commands.hybrid_command(
        name="ping",
        description="Check if the bot is alive.",
    )
    async def ping(self, context: Context) -> None:
        """
        Check if the bot is alive.

        :param context: The hybrid command context.
        """
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"The bot latency is {round(self.bot.latency * 1000)}ms.",
            color=0xBEBEFE,
        )
        await context.send(embed=embed)

    @commands.hybrid_command(
        name="lore",
        description="Ask the Loremaster something about The Red Moon Saga."
    )
    async def lore(self, context: Context):
        if context.message.channel.name != self.bot.config["channel"]:
            return
        print("/lore command triggered")
        question = context.message.content.split("lore", 1)[1]
        response = await rag.prompt_rag_flow(query=question, config=self.bot.config)
        reply_content = f"```{response}```"
        message_max_length = 2000
        if len(response) > (message_max_length - 6): #subtract 6 characters for backticks to put content in quote block
            trimmed_response = response[:message_max_length-6]
            last_full_stop_idx = trimmed_response.rfind(".")
            trimmed_response = trimmed_response[:last_full_stop_idx + 1]
            reply_content = f"```{trimmed_response}```"
        
        await context.message.reply(reply_content)

    @commands.hybrid_command(
        name="last-session",
        description="Ask the Loremaster to recount the tale of the events that happened last session."
    )
    async def last_session(self, context: Context):
        if context.message.channel.name != self.bot.config["channel"]:
            return
        print("/last-session command triggered")
        response = await rag.prompt_rag_flow_last_session(config=self.bot.config)
        response_chunks = await self.chunk_message_content(response)
        for chunk in response_chunks:
            await context.message.reply(chunk)

    async def chunk_message_content(self, text):
        MAX_LENGTH = 2000
        CHUNK_SIZE = MAX_LENGTH - 6 # Reserve 6 characters for backticks for quote block
        LINE_BREAKS_PER_CHUNK = 20

        # sentences = re.split(r"(?<=[\.\!\?])\s+", text)

        # chunks = []
        # current_chunk = ""
        # current_length = 0

        # for sentence in sentences:
        #     if current_length + len(sentence) > CHUNK_SIZE:
        #         chunks.append(f"```{current_chunk.strip()}```")
        #         current_chunk = ""
        #         current_length = 0
        #     current_chunk += sentence + " "
        #     current_length += len(sentence) + 1

        lines = text.split("\n")

        chunks = []
        current_chunk = ""
        current_length = 0
        current_line_count = 0

        for line in lines:
            if current_length + len(line) + current_line_count * LINE_BREAKS_PER_CHUNK > CHUNK_SIZE:
                chunks.append(f"```{current_chunk.strip()}```")
                current_chunk = ""
                current_length = 0
            current_chunk += line + "\n"
            current_length += len(line) + 1
            current_line_count += 1
        
        if current_chunk:
            chunks.append(f"```{current_chunk.strip()}```")

        return chunks

async def setup(bot) -> None:
    await bot.add_cog(General(bot))
