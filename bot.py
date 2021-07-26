"""
Bot codes
"""


import os
import asyncio
import pydash

from dotenv import load_dotenv

# DB
from sqlalchemy import create_engine

# Discord
import discord
from discord.ext import commands

# DB
from db.db import bind_engine, Session
from db.models.team_members import TeamMembers


# Riot util func.
# pylint: disable=unused-import
from riot_api import (
    get_summoner_rank,
    previous_match,
    create_summoner_list,
    check_cached,
)

# from riot_api import check_cached

from utils.embed_object import EmbedData
from utils.utils import create_embed, get_file_path, normalize_name, create_team_string
from utils.make_teams import make_teams
from utils.constants import (
    TIER_RANK_MAP,
    MAX_NUM_PLAYERS_TEAM,
    UNCOMMON_TIERS,
    UNCOMMON_TIER_DISPLAY_MAP,
)
from utils.help_commands import (
    create_help_fields,
    create_help_embed,
    create_help_title_desc,
)

intents = discord.Intents.default()
# pylint: disable=assigning-non-slot
intents.members = True  # Subscribe to the privileged members intent.


load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
LOCAL_BOT_PREFIX = os.getenv("LOCAL_BOT_PREFIX")
DB_URL = os.getenv("DB_URL")

# differ by env.
# Connec to DB.
engine = create_engine(DB_URL)
bind_engine(engine)
session = Session()

# ADD help_command attribute to remove default help command
bot = commands.Bot(
    command_prefix=commands.when_mentioned_or(LOCAL_BOT_PREFIX),
    intents=intents,
    help_command=None,
)

# folder and path for data json
data_folder_path = get_file_path("data/")
json_path = data_folder_path + "data.json"


@bot.event
async def on_ready():
    """Prints that the bot is connected"""
    print(f"{bot.user.name} has connected to Discord!")


@bot.event
async def on_member_join(member):
    """Sends personal discord message to the membed who join"""
    # create a direct message channel.
    await member.create_dm()
    # Send welcome msg.
    await member.dm_channel.send(f"Hi {member.name}, welcome to 관전남 월드!")


# Custom help command
@bot.command(
    name="help",
    help="Displays the syntax and the description of all the commands.",
)
async def help_command(ctx, name=None):
    """Help command outputs description about all the commands"""
    try:
        # typing indicator
        async with ctx.typing():
            await asyncio.sleep(1)

        list_commands = []  # make dictionary to store all commands
        for command in bot.commands:
            # check if the user input specific command after help
            if command.name == name:
                # for commands that receive multiple parameter
                if command.name in ["add", "remove"]:
                    return await command(ctx)
                return await command(ctx, "help")
            list_commands.append(
                {"command": f"{command.name}", "description": f"{command.help}"}
            )
        # sort commands alphabetically
        list_commands = sorted(list_commands, key=lambda x: x["command"])

        embed_data = EmbedData()
        embed_data.title = f"How to use {bot.user.name}"
        embed_data.description = f"** **\n<@!{bot.user.id}> <command> --help\
              \n\n`--help` shows the information of the command:"
        embed_data.color = discord.Color.gold()

        # ADD thumbnail (Image can be changed whatever we want. eg.our logo)
        embed_data.thumbnail = "https://emoji.gg/assets/emoji/3907_lol.png"

        embed_data.fields = []
        embed_data.fields.append(
            {"name": "** **", "value": "**\nCommands:**", "inline": False}
        )

        for command in list_commands:
            if command["command"] == "help":
                embed_data.fields.append(
                    {
                        "name": "** **",
                        "value": "**{}** `command_name`\n{}".format(
                            command["command"],
                            "Display the information of the command",
                        ),
                        "inline": False,
                    }
                )
            elif command["command"] in ["list", "teams", "clear"]:
                embed_data.fields.append(
                    {
                        "name": "** **",
                        "value": "**{}**\n{}".format(
                            command["command"], command["description"]
                        ),
                        "inline": False,
                    }
                )

            else:
                embed_data.fields.append(
                    {
                        "name": "** **",
                        "value": "**{}** `summoner_name`\n{}".format(
                            command["command"],
                            command["description"],
                        ),
                        "inline": False,
                    }
                )
        embed_data.fields.append(
            {"name": "** **", "value": "`All Data from NA server`", "inline": False}
        )
        await ctx.send(embed=create_embed(embed_data))

    # pylint: disable=broad-except
    except Exception:
        err_embed = discord.Embed(
            title="Error",
            description="Oops! Something went wrong.\
              \n\n Please type  `rank --help`  to see how to use and try again!",
            color=discord.Color.red(),
        )

        await ctx.send(embed=err_embed)


# =================
@bot.command(name="rank", help="Displays the information about the summoner.")
async def get_rank(ctx, name="--help"):  # set name attribute to default help command
    """Sends the summoner's rank information to the bot"""
    try:
        # typing indicator
        async with ctx.typing():
            await asyncio.sleep(1)

        # displays the get_rank's help command
        if name == "--help":
            create_help_title_desc(bot, f"{get_rank.name}", True)

            # pylint: disable=line-too-long
            create_help_fields(
                [
                    "This command displays the information about the summoner.",
                    "The information includes the summoner's name, rank, total games played and the win rate.",
                    f"__NOTE__:   **{get_rank.name}** command only accepts one summoner name.",
                ]
            )

            return await ctx.send(embed=create_help_embed())

        summoner_info = get_summoner_rank(name)

        embed_data = EmbedData()
        embed_data.title = "Solo/Duo Rank"
        embed_data.color = discord.Color.dark_gray()

        # Add author, thumbnail, fields, and footer to the embed
        embed_data.author = {}
        embed_data.author = {
            "name": summoner_info["summoner_name"],
            # For op.gg link, we have to remove all whitespace.
            "url": "https://na.op.gg/summoner/userName={0}".format(
                summoner_info["summoner_name"].replace(" ", "")
            ),
            "icon_url": summoner_info["summoner_icon_image_url"],
        }

        # Upload tier image to discord to use it as thumbnail of embed using full path of image.
        file = discord.File(summoner_info["tier_image_path"])

        # Embed thumbnail image of tier at the side of the embed
        # Note: This takes the 'file name', not a full path.
        embed_data.thumbnail = "attachment://{0[tier_image_name]}".format(summoner_info)

        # Setting variables for summoner information to display as field
        summoner_total_game = summoner_info["solo_win"] + summoner_info["solo_loss"]

        # Due to zero division error, need to handle situation where total games are zero
        solo_rank_win_percentage = (
            0
            if summoner_total_game == 0
            else int(summoner_info["solo_win"] / summoner_total_game * 100)
        )

        embed_data.description = "**{0[tier]}**   {0[league_points]}LP \
                    \nTotal Games Played: {1}\n{0[solo_win]}W {0[solo_loss]}L {2}%".format(
            summoner_info,
            summoner_total_game,
            solo_rank_win_percentage,
        )

        embed_data.fields = []
        embed_data.fields.append(
            {
                "name": "** **",
                "value": "`All Data from NA server`",
                "inline": False,
            }
        )

        await ctx.send(file=file, embed=create_embed(embed_data))

    # pylint: disable=broad-except
    except Exception as e_values:
        # 404 error means Data not found in API
        if "404" in str(e_values):
            error_title = f'Summoner "{name}" is not found'
            error_description = f"Please check the summoner name agian \n \
              \n __*NOTE*__:   **{get_rank.name}** command only accepts one summoner name.\
              \n\n Please type  `rank --help`  to see how to use"
        else:
            error_title = "Error"
            error_description = "Oops! Something went wrong.\
              \n\nPlease type  `rank --help`  to see how to use and tyr again!"

        embed_data = EmbedData()
        embed_data.title = ":x:   {0}".format(error_title)
        embed_data.description = "{0}".format(error_description)
        embed_data.color = discord.Color.red()

        await ctx.send(embed=create_embed(embed_data))


# TODO: REWORK THIS WITHOUT pd
@bot.command(
    name="last_match",
    help="Displays the information about the latest game of the summoner.",
)
async def get_last_match(ctx, name="--help"):
    """Sends the summoner's last match information to the bot"""
    try:

        # last_match_info = previous_match(name)
        embed = discord.Embed(
            title="last match",
            description="Under development",
            color=discord.Color.red(),
        )
        # dfi.export(last_match_info, "df_styled.png")
        # file = discord.File("df_styled.png")
        # embed = discord.Embed()
        # embed.set_image(url="attachment://df_styled.png")
        await ctx.send(
            embed=embed,
            # file=file
        )
        # os.remove("df_styled.png")
        # typing indicator
        async with ctx.typing():
            await asyncio.sleep(1)

        # displays the get_last_match's help command
        if name == "--help":
            create_help_title_desc(bot, f"{get_last_match.name}", True)

            # pylint: disable=line-too-long
            create_help_fields(
                [
                    "This command displays the information about the latest game of the summoner.",
                    "The information includes the name of all of the summoners, champions played, K/D/A and damage dealt",
                    f"__NOTE__:   **{get_last_match.name}** command only accepts one summoner name.",
                ]
            )

            return await ctx.send(embed=create_help_embed())

        last_match_info = previous_match(name)
        dfi.export(last_match_info, "df_styled.png")
        file = discord.File("df_styled.png")
        embed = discord.Embed()
        embed.set_image(url="attachment://df_styled.png")
        await ctx.send(embed=embed, file=file)
        os.remove("df_styled.png")

    # pylint: disable=broad-except
    except Exception as e_values:
        # 404 error means Data not found in API
        if "404" in str(e_values):
            error_title = f'Summoner "{name}" is not found'
            error_description = f"Please check the summoner name agian \n \
              \n __*NOTE*__ :   **{get_last_match.name}** command only accepts one summoner name.\
              \n\n Please type  `last_match --help`  to see how to use"

        else:
            error_title = "Error"
            error_description = "Oops! Something went wrong.\
              \n\nPlease type  `last_match --help`  to see how to use and try again!"

        embed_data = EmbedData()
        embed_data.title = ":x:   {0}".format(error_title)
        embed_data.description = "{0}".format(error_description)
        embed_data.color = discord.Color.red()

        await ctx.send(embed=create_embed(embed_data))


# pylint: disable=too-many-locals, too-many-branches, too-many-statements
@bot.command(name="add", help="Add summoner(s) to a list for making teams")
async def add_summoner(ctx, *, message="--help"):
    """Writes list of summoners to local
    json file and sends the list to the bot"""

    try:
        # typing indicator
        async with ctx.typing():
            await asyncio.sleep(1)

        # displays the add_summoner's help command
        if message == "--help":
            create_help_title_desc(bot, f"{add_summoner.name}", True)

            create_help_fields(
                [
                    "This command adds summoner(s) to a list for making teams",
                    "This command also displays the list of summoners on standby.",
                    "The information includes a summoner's name, tier division, and rank number.",
                    f"Adding multiple summoners: `@{bot.user.name} add name1, name2`",
                ]
            )

            return await ctx.send(embed=create_help_embed())

        # create a directory containing json file to store data for added summoners
        if not os.path.exists(json_path):
            os.makedirs(data_folder_path, exist_ok=True)
            with open(json_path, "w"):
                pass

        # converting the message into list of summoners
        # Split by ',' and remove leading/trailling white spaces.
        user_input_names = [x.strip() for x in message.split(",")]

        # initializing server id to a variable
        server_id = str(ctx.guild.id)

        # initializing total number of players for counting both incoming and existing summoners
        total_number_of_players = 0

        # Grab team member list from db
        members_list_record_cached = check_cached(
            server_id, TeamMembers, TeamMembers.channel_id
        )

        # If we have record;
        # Check # of players that were save in the list.
        # Remove names from user input if we already have the name in record.
        if members_list_record_cached:
            # Convert into dict.
            total_number_of_players += len(
                members_list_record_cached["dict"]["members"]
            )

            for member in members_list_record_cached["dict"]["members"]:
                record_name = member["summoner_name"]
                name_record_input_match = pydash.find(
                    user_input_names,
                    lambda input_name: (input_name == record_name),
                )

                if name_record_input_match:
                    user_input_names.remove(name_record_input_match)

        # 'user_input_names' should be filtered with names that we don't have record of.
        total_number_of_players += len(user_input_names)

        # If 'total_number_of_players' will be more than 10, error out.
        if total_number_of_players > MAX_NUM_PLAYERS_TEAM:
            raise Exception(
                "Limit Exceeded",
                "You have exceeded a limit of 10 summoners! \
                \nPlease add {0} more summoners!".format(
                    MAX_NUM_PLAYERS_TEAM
                    - total_number_of_players
                    + len(user_input_names)
                ),
            )

        # If all the summoners are already in record, return.
        if total_number_of_players == 0:
            await display_current_list_of_summoners(ctx)
            return

        # make dictionary for newly coming in players
        new_team_members = create_summoner_list(user_input_names)

        # If we had a db record, update.
        if members_list_record_cached:
            # Get original list
            members_update = members_list_record_cached["dict"]["members"]

            # Append new players
            for player_list in new_team_members:
                members_update.append(player_list)

            # Set new member list.
            # Note; was going to use members_list_record_cached['raw'] to update,
            # but looks like it doesn't work.
            member_list_query_result = (
                session.query(TeamMembers)
                .filter(TeamMembers.channel_id == server_id)
                .one_or_none()
            )
            member_list_query_result.members = members_update

            # Update record.
            # TODO: Simplify this - use base.py - update()
            try:
                session.commit()
            except Exception as e_values:
                session.rollback()
                raise e_values
            finally:
                session.close()
        else:
            # If we don't have a record, create one.
            members_create_data = []
            # TODO: No need to group by server_id once we have everything migrated to db.
            for new_player in new_team_members:
                members_create_data.append(new_player)
            create_member = TeamMembers(server_id, members_create_data)
            create_member.create()

        # display list of summoners
        await display_current_list_of_summoners(ctx)

    # pylint: disable=broad-except
    except Exception as e_values:
        if "404" in str(e_values):
            error_title = "Invalid Summoner Name"
            error_description = f"`{e_values.args[1]}` is not a valid name. \
                \n\nAdding multiple summoners:\n `@{bot.user.name} add name1, name2`"
        elif "Limit Exceeded" in str(e_values):
            error_title = e_values.args[0]
            error_description = e_values.args[1]
        else:
            error_title = f"{e_values}"
            error_description = "Oops! Something went wrong.\nTry again!"

        embed_data = EmbedData()
        embed_data.title = ":x:   {0}".format(error_title)
        embed_data.description = "{0}".format(error_description)
        embed_data.color = discord.Color.red()
        await ctx.send(embed=create_embed(embed_data))

        # display list of summoners
        # TODO this shouldn't call another decorator function.
        await display_current_list_of_summoners(ctx)


@bot.command(name="list", help="Display the list of summoner ranks and names added")
async def display_current_list_of_summoners(ctx, name=None):
    """For displaying current list of summoners"""
    try:
        # typing indicator
        async with ctx.typing():
            await asyncio.sleep(1)

        # displays the display_current_list_of_summoners's help command
        if name is not None:
            create_help_title_desc(
                bot, f"{display_current_list_of_summoners.name}", False
            )

            create_help_fields(
                [
                    "This command displays a list of summoner(s) on standby.",
                    "The information includes the summoner's name, tier division, and rank number.",
                ]
            )
            return await ctx.send(embed=create_help_embed())

        # server id
        server_id = str(ctx.guild.id)

        total_number_of_players = 0

        # Grab team member list from db
        members_list_record_cached = check_cached(
            server_id, TeamMembers, TeamMembers.channel_id
        )

        # If no record, error out.
        if members_list_record_cached is None:
            raise Exception("NO SUMMONERS IN THE LIST")

        # If we have record, print
        total_number_of_players += len(members_list_record_cached["dict"]["members"])

        # making embed for list of summoners
        embed_data = EmbedData()
        embed_data.title = "List of Summoners"
        embed_data.description = "** **"
        embed_data.color = discord.Color.dark_gray()

        # for saving output str
        output_str = ""
        for member in members_list_record_cached["dict"]["members"]:
            output_str += (
                "`{0}` {1}\n".format(
                    UNCOMMON_TIER_DISPLAY_MAP.get(member["tier_division"]),
                    member["summoner_name"],
                )
                if member["tier_division"] in UNCOMMON_TIERS
                else "`{0}{1}` {2}\n".format(
                    member["tier_division"][0],
                    TIER_RANK_MAP.get(member["tier_rank"]),
                    member["summoner_name"],
                )
            )

        embed_data.fields = []
        embed_data.fields.append(
            {"name": "Summoners", "value": output_str, "inline": False}
        )

        await ctx.send(embed=create_embed(embed_data))

        await ctx.send(f"Total Number of Summoners: {total_number_of_players}")

    # pylint: disable=broad-except
    except Exception:
        embed_data = EmbedData()
        embed_data.title = ":warning:   No Summoners in the List"
        embed_data.description = f"Please add summoner by `@{bot.user.name} add`"
        embed_data.color = discord.Color.orange()
        await ctx.send(embed=create_embed(embed_data))


# pylint: disable=too-many-locals
@bot.command(name="teams", help="Display TEAM BLUE and RED for a custom game")
async def display_teams(ctx, name=None):
    """Make and display teams to bot from list of summoners in json"""
    try:
        # typing indicator
        async with ctx.typing():
            await asyncio.sleep(1)

        # displays the display_teams's help command
        if name is not None:
            create_help_title_desc(bot, f"{display_teams.name}", False)

            create_help_fields(
                [
                    "This command displays TEAM BLUE and RED for a custom game.",
                    "The information includes a summoner's name, tier division, and rank number.",
                ]
            )
            return await ctx.send(embed=create_help_embed())

        # server id
        server_id = str(ctx.guild.id)

        # Grab team member list from db
        members_list_record_cached = check_cached(
            server_id, TeamMembers, TeamMembers.channel_id
        )

        # If no record, error out.
        if members_list_record_cached is None:
            raise Exception("NO SUMMONERS IN THE LIST")

        # Error out if we don't have 10 players
        if len(members_list_record_cached["dict"]["members"]) != 10:
            raise Exception("NOT ENOUGH PLAYERS")

        teams = make_teams(members_list_record_cached["dict"]["members"])

        blue_team = teams[0]
        red_team = teams[1]

        blue_team_output = create_team_string(blue_team)
        red_team_output = create_team_string(red_team)

        for team_name in ["blue", "red"]:
            embed_data = EmbedData()
            embed_data.title = f"TEAM {team_name.upper()}"
            embed_data.description = "** **"
            embed_data.color = (
                discord.Color.blue() if team_name == "blue" else discord.Color.red()
            )
            file = discord.File(get_file_path(f"images/{team_name}-minion.png"))
            embed_data.thumbnail = f"attachment://{team_name}-minion.png"
            embed_data.fields = []
            embed_data.fields.append(
                {
                    "name": "Summoners" + " " * 10,
                    "value": blue_team_output
                    if team_name == "blue"
                    else red_team_output,
                    "inline": True,
                }
            )
            await ctx.send(file=file, embed=create_embed(embed_data))

    # pylint: disable=broad-except
    except Exception as e_values:
        if str(e_values) in ["NOT ENOUGH PLAYERS", "NO SUMMONERS IN THE LIST"]:
            error_title = e_values.args[0]
            error_description = f"There are not enough players to make teams \
                \n\nTo add a summoner:\n`@{bot.user.name} add summoner_name` \
                    \n\nAdding multiple summoners:\n `@{bot.user.name} add name1, name2`"
        else:
            error_title = f"{e_values}"
            error_description = "Oops! Something went wrong.\nTry again!"

        embed_data = EmbedData()
        embed_data.title = ":x:   {0}".format(error_title)
        embed_data.description = "{0}".format(error_description)
        embed_data.color = discord.Color.red()
        await ctx.send(embed=create_embed(embed_data))


# pylint: disable=too-many-locals, too-many-branches, too-many-statements
@bot.command(
    name="remove", help="Remove player(s) from the list on standby for a custom game"
)
async def remove_summoner(ctx, *, message="--help"):
    """Remove summoner(s) from list
    and send  the list to the bot"""

    try:
        # typing indicator
        async with ctx.typing():
            await asyncio.sleep(1)

        # displays the remove_summoner's help command
        if message == "--help":
            create_help_title_desc(bot, f"{remove_summoner.name}", True)

            create_help_fields(
                [
                    "This command removes player(s) from the list on standby for a custom game",
                    "This command also displays the list of summoners on standby.",
                    "The information includes a summoner's name, tier division, and rank number.",
                    f"Remove multiple summoners: `@{bot.user.name} add name1, name2`",
                ]
            )

            return await ctx.send(embed=create_help_embed())

        # converting the message into list of summoners
        summoner_to_remove_input = [x.strip() for x in message.split(",")]

        # Exception case: attempt to remove more than 10 players
        if len(summoner_to_remove_input) > MAX_NUM_PLAYERS_TEAM:
            raise Exception(
                "Limit Exceeded",
                "You tried to remove more than 10 summoners! \
                \nPlease remove {0} less summoners or consider using `clear` command".format(
                    MAX_NUM_PLAYERS_TEAM - len(summoner_to_remove_input)
                ),
            )
        # initializing server id to a variable
        server_id = str(ctx.guild.id)

        # Grab team member list from db
        members_list_record_cached = check_cached(
            server_id, TeamMembers, TeamMembers.channel_id
        )

        # Exception case: data/data.json file does not exist
        if members_list_record_cached is None:
            raise Exception(
                "No summoners added",
                "There is no summoner(s) added in the game.\nPlease add summoner(s) first!",
            )

        # initializing server id to a variable
        server_id = str(ctx.guild.id)

        unmatched_summoner_name = []
        for remove_name in summoner_to_remove_input:
            # members_list_record_cached["dict"]["members"]:
            matched_summoner = pydash.find(
                members_list_record_cached["dict"]["members"],
                lambda x: normalize_name(x["summoner_name"])
                == normalize_name(remove_name),
            )

            if matched_summoner is None:
                unmatched_summoner_name.append(remove_name)
                continue

            members_list_record_cached["dict"]["members"].remove(matched_summoner)

        if len(unmatched_summoner_name) > 0:
            raise Exception(
                "Unregistered Summoner(s)",
                "Summoners: {0} were not registered for the game".format(
                    str(unmatched_summoner_name)
                ),
            )

        member_list_query_result = (
            session.query(TeamMembers)
            .filter(TeamMembers.channel_id == server_id)
            .one_or_none()
        )

        member_list_query_result.members = members_list_record_cached["dict"]["members"]

        # Update record.
        # TODO: Simplify this - use base.py - update()
        try:
            session.commit()
        except Exception as e_values:
            session.rollback()
            raise e_values
        finally:
            session.close()

        # display list of summoners
        await display_current_list_of_summoners(ctx)

    # pylint: disable=broad-except
    except Exception as e_values:
        if "Limit Exceeded" in str(e_values) or "Unregistered Summoner(s)" in str(
            e_values
        ):
            error_title = e_values.args[0]
            error_description = e_values.args[1]
        else:
            error_title = f"{e_values}"
            error_description = "Oops! Something went wrong.\nTry again!"

        embed_data = EmbedData()
        embed_data.title = ":x:   {0}".format(error_title)
        embed_data.description = "{0}".format(error_description)
        embed_data.color = discord.Color.red()
        await ctx.send(embed=create_embed(embed_data))

        # display list of summoners
        await display_current_list_of_summoners(ctx)


# pylint: disable=too-many-locals, too-many-branches, too-many-statements
@bot.command(
    name="clear", help="Clear player(s) from the list on standby for a custom game"
)
async def clear_list_of_summoners(ctx, name=None):
    """Clear out summoners from the list"""

    try:
        # typing indicator
        async with ctx.typing():
            await asyncio.sleep(1)

        # displays the clear_list_of_summoners's help command
        if name is not None:
            create_help_title_desc(bot, f"{clear_list_of_summoners.name}", False)

            create_help_fields(
                [
                    "This command clear player(s) from the list on standby for a custom game."
                ]
            )
            return await ctx.send(embed=create_help_embed())

        # for importing data from json file
        file_data = ""
        # initializing server id to a variable
        server_id = str(ctx.guild.id)
        member_list_query_result = (
            session.query(TeamMembers).filter(TeamMembers.channel_id == server_id).one()
        )
        member_list_query_result.delete(session)

        # display list of summoners
        await display_current_list_of_summoners(ctx)

    # pylint: disable=broad-except
    except Exception as e_values:
        error_title = f"{e_values}"
        error_description = "Oops! Something went wrong.\nTry again!"

        embed_data = EmbedData()
        embed_data.title = ":x:   {0}".format(error_title)
        embed_data.description = "{0}".format(error_description)
        embed_data.color = discord.Color.red()
        await ctx.send(embed=create_embed(embed_data))

        # display list of summoners
        await display_current_list_of_summoners(ctx)


@bot.event
async def on_command_error(ctx, error):
    """Checks error and sends error message if exists"""
    if isinstance(error, commands.errors.CheckFailure):
        await ctx.send("You do not have the correct role for this command.")

    # Send an error message when the user input invalid command
    elif isinstance(error, commands.CommandNotFound):
        err_embed = discord.Embed(
            title=f":warning:   {error}",
            description="Please type  `help`  to see how to use",
            color=discord.Color.orange(),
        )

        await ctx.send(embed=err_embed)


bot.run(TOKEN)
