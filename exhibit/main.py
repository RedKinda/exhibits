import os
from typing import Optional, TypedDict
import discord
from discord.ext import commands
from exhibit.db import DB
from pydantic import BaseModel


description = """Example bot to showcase user apps with translation."""

intents = discord.Intents.default()

bot = commands.Bot(command_prefix="?", description=description, intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")  # type: ignore
    print("------")

    # sync commands
    # await bot.tree.sync()


db = DB(os.environ.get("DATAFILE_LOCATION", "exhibit_data.json"))


class Exhibit(BaseModel):
    id: int
    owner_id: int
    author_id: int
    author_name: str
    author_profile_url: str
    guild_id: Optional[int]
    channel_id: int
    message_id: int
    content: str
    attachment_url: Optional[str]

    reply_content: Optional[str] = None


def get_user_exhibits(user_id: int):
    exhibit_ids = db.get(f"exhibits-{user_id}", [])
    return [
        Exhibit(**db.get(f"exhibit-{user_id}-{exhibit_id}"))
        for exhibit_id in exhibit_ids
    ]


@discord.app_commands.user_install()
@discord.app_commands.allow_contexts(guilds=True, private_channels=True)
@discord.app_commands.context_menu(name="Save Exhibit")
async def save_exhibit(interaction: discord.Interaction, message: discord.Message):
    """Save an exhibit for later display."""
    user_exhibits = get_user_exhibits(interaction.user.id)
    next_exhibit_id = max([exhibit.id for exhibit in user_exhibits], default=0) + 1

    new_exhibit = Exhibit(
        id=next_exhibit_id,
        owner_id=interaction.user.id,
        author_id=message.author.id,
        author_name=message.author.name,
        author_profile_url=str(message.author.display_avatar.url),
        guild_id=message.guild.id if message.guild else None,
        channel_id=message.channel.id,
        message_id=message.id,
        content=message.content,
        attachment_url=message.attachments[0].url if message.attachments else None,
    )

    user_id = interaction.user.id
    db.set(f"exhibit-{user_id}-{next_exhibit_id}", new_exhibit)
    db.set(f"exhibits-{user_id}", db.get(f"exhibits-{user_id}", []) + [next_exhibit_id])

    await interaction.response.send_message(
        f"Exhibit number {next_exhibit_id} saved!", embed=get_exhibit_embed(new_exhibit)
    )


bot.tree.add_command(save_exhibit)


async def exhibit_autocomplete(
    interaction: discord.Interaction,
    current: str,
):
    user_exhibits = get_user_exhibits(interaction.user.id)

    choices = [
        discord.app_commands.Choice(
            name=f"{exhibit.id} - {exhibit.author_name} - {discord.utils.remove_markdown(exhibit.content, ignore_links=False) + ' '}{'<image>' if exhibit.attachment_url else ''}"[
                :95
            ],
            value=exhibit.id,
        )
        for exhibit in user_exhibits
        if current in exhibit.content
        or current in str(exhibit.id)
        or current in exhibit.author_name
    ]
    # only take last 25 choices
    return choices[::-1][:25]


def get_exhibit_embed(exhibit: Exhibit):
    jump_url = f"https://discord.com/channels/{exhibit.guild_id if exhibit.guild_id else '@me'}/{exhibit.channel_id}/{exhibit.message_id}"
    embed = discord.Embed(
        title=f"Exhibit n. {exhibit.id}",
        description=exhibit.content + f"\n[Jump to message]({jump_url})",
        color=discord.Color.blurple(),
    )

    embed.timestamp = discord.utils.snowflake_time(exhibit.message_id)
    embed.set_author(
        name=exhibit.author_name,
        icon_url=exhibit.author_profile_url,
        url=jump_url,
    )

    if exhibit.attachment_url:
        embed.set_image(url=exhibit.attachment_url)

    return embed


@discord.app_commands.user_install()
@discord.app_commands.allow_contexts(guilds=True, dms=True, private_channels=True)
@discord.app_commands.command()
@discord.app_commands.autocomplete(number=exhibit_autocomplete)
async def exhibit(interaction, number: int, ephemeral: bool = False):
    """Display an exhibit."""

    exhibit = db.get(f"exhibit-{interaction.user.id}-{number}")
    if exhibit is None:
        return await interaction.response.send_message(
            "Exhibit not found.", ephemeral=ephemeral
        )

    embed = get_exhibit_embed(exhibit)

    await interaction.response.send_message(embed=embed, ephemeral=ephemeral)


bot.tree.add_command(exhibit)


bot.run(os.environ["DISCORD_TOKEN"])
