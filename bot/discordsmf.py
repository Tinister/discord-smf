"""Handles running a bot that receives messages from Discord and sends
them to an SMF forum."""
import argparse
import asyncio
import configparser
import datetime
import discord
import logging
import logging.handlers
import os
import sys
import time

config = None

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.NullHandler())

heartbeat_task = None

client = discord.Client()
discord_server = None
discord_channel = None
top_role = None

def setup_logging(filename):
    """Sets up logging to log to the given filename"""
    handler = logging.handlers.TimedRotatingFileHandler(
        filename, encoding='utf-8',
        when='midnight', atTime=datetime.time(10), utc=True,
        backupCount=3)
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S")
    formatter.converter = time.gmtime

    handler.setLevel(logging.INFO)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

@client.event
async def on_ready():
    """Event that fires when the client connects to Discord"""
    global discord_server, discord_channel, top_role

    logger.info("=== CONNECTED ===")
    logger.info("Call me {} ({})".format(client.user.name, client.user.id))
    logger.info("Member of {} servers".format(len(client.servers)))

    server_find = config.server_name.casefold()
    try:
        discord_server = next((s for s in client.servers
                               if s.name.casefold() == server_find))
    except StopIteration:
        logger.error(
            "Not a member of any server named '{}'!"
            .format(config.server_name))
        await client.close()
        return

    channel_find = config.channel_name.casefold()
    try:
        discord_channel = next((c for c in discord_server.channels
                                if c.name.casefold() == channel_find))
    except StopIteration:
        logger.error(
            "'{}' does not have any channels named '{}'!"
            .format(discord_server.name, config.channel_name))
        await client.close()
        return

    logger.info(
        "Listening to #{} on '{}'"
        .format(discord_channel.name, discord_server.name))

    top_role = max(discord_server.roles, key=lambda r: r.position)
    logger.info(
        "Treating members in '{}' a little bit better than everyone else"
        .format(top_role.name))

    #logger.info('Emojis:')
    #for e in discord_server.emojis:
    #    logger.info('\t{} ({}) {}'.format(e.name, e.id, e.url))

@client.event
async def on_message(message):
    """Event that fires when the client receives a new message"""
    if message.channel != discord_channel:
        return
    logger.info("<{}> {}".format(
        message.author.nick or message.author.name,
        message.content))

@client.event
async def on_message_edit(before, after):
    """Event that fires when a message is edited"""
    if after.channel != discord_channel:
        return
    if before.content == after.content:
        return # an edit other than changing content
    logger.info("EDITED: <{}> {}->{}".format(
        after.author.nick or after.author.name,
        before.id, after.id))
    logger.info("\t{}".format(before.content))
    logger.info("\t{}".format(after.content))

@client.event
async def on_message_delete(message):
    """Event that fires when a message is deleted"""
    if message.channel != discord_channel:
        return
    logger.info("DELTEATED: <{}> {}".format(
        message.author.nick or message.author.name,
        message.content))

async def heartbeat(interval):
    """Heartbeat task"""
    # TODO should send the messages to the board...
    while True:
        await asyncio.sleep(interval)
        if client.is_closed:
            return
        logger.info("/thump/")

async def quit():
    """Quits the bot"""
    if heartbeat_task:
        heartbeat_task.cancel()
    await client.close()

def main():
    """Main method of the module"""
    global heartbeat_task
    logger.info("=== STARTED ===")
    heartbeat_task = asyncio.ensure_future(
        heartbeat(config.send_interval),
        loop=client.loop)
    client.run(config.token)
    logger.info("=== STOPPED ===")

def _config_prop_build(name, datatype=str):
    """Builds a property for the config class"""
    def get(self):
        if self.config.default_section not in self.config:
            return None
        section = self.config[self.config.default_section]
        try:
            if datatype is bool:
                return section.getboolean(name)
            if datatype is int:
                return section.getint(name)
            if datatype is float:
                return section.getfloat(name)
            return section.get(name)
        except:
            return None

    def set(self, value):
        if value is None:
            return
        if self.config.default_section not in self.config:
            self.config[self.config.default_section] = {}
        self.config[self.config.default_section][name] = str(value)

    return property(get, set)

class BotConfig(object):
    """Holds the configurable attributes of the bot"""
    def __init__(self, path):
        """Initializes the object

        Args:
            path: Path where the config file is stored.
                If the file doesn't exist, an empty object is created.

        Raises:
            ValueError: If the path is not a valid path.
        """
        if (not os.path.isfile(path) and
                not os.access(os.path.dirname(path), os.W_OK)):
            raise ValueError("'{}' is not a valid path type")
        self.path = path
        self.config = configparser.ConfigParser()
        if os.path.isfile(path):
            self.config.read(self.path)

    log_path = _config_prop_build('log_path')
    server_name = _config_prop_build('server_name')
    channel_name = _config_prop_build('channel_name')
    send_interval = _config_prop_build('send_interval', float)
    token = _config_prop_build('token')

    def save_changes(self):
        """Save changes to the config object back to file passed in
        __init__
        """
        with open(self.path, 'w+') as f:
            self.config.write(f)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file", help="Path to the config file.")
    cli_args = parser.parse_args()
    config = BotConfig(cli_args.config_file)

    try:
        setup_logging(config.log_path)
    except:
        pass # Guess there's no logging

    main()
