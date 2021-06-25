# Mystic Bot
import os
import discord
import asyncio
import json
import difflib
import requests
import validators

TOKEN = ""
client = discord.Client()

#<pokemon_name>: [canBeTraded, shinyAvailable, thumbnailName]
pokemonTable = {}
messageHistory = {
    "Direct": {}, #messageId: [posterId, offererId, offeringPokemon, tradingPokemon]
    "Trades": {} #messageId: [channelId, posterId, wantList, tradingPokemon]
}

DELETE_DELAY = 10
RESPONSE_TIMEOUT = 180
WANT_LIMIT = 10
CLOSENESS_CUTOFF = .75
TRADES_CHANNEL_ID = 780928559912583198
BOT_EDIT_CHANNEL_ID = 780928875089494076
BOT_USER_ID = 388430144122912769

def SavePokemonTable():
    with open("Pokemon Table.json", "w") as jsonFile:
        json.dump(pokemonTable, jsonFile)

def LoadPokemonTable():
    global pokemonTable
    with open("Pokemon Table.json") as jsonFile:
        pokemonTable = json.load(jsonFile)

def LoadMessageHistory():
    global messageHistory
    with open("Message History.json") as jsonFile:
        messageHistory = json.load(jsonFile)

def SaveMessageHistory():
    with open("Message History.json", "w") as jsonFile:
        json.dump(messageHistory, jsonFile)

def DeleteMessageFromHistory(msgType, msgID):
    if msgID in messageHistory[msgType]:
        del messageHistory[msgType][msgID]
        SaveMessageHistory()

@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')
    channel = client.get_channel(TRADES_CHANNEL_ID)
    msgList = []
    async for msg in channel.history(limit = 250):
        if str(msg.id) not in messageHistory["Trades"]:
            msgList.append(msg)
    await channel.delete_messages(msgList)

@client.event
async def on_message(message):
    if message.author == client.user or not (message.channel.id == TRADES_CHANNEL_ID or message.channel.id == BOT_EDIT_CHANNEL_ID):
        return

    content = message.content
    if content[:6] == "!trade":
        fullPokemon = content[7:]
        fullPokemon = fullPokemon.lower()

        if "shadow" in fullPokemon:
            #reject, shadows can't be traded
            sentMsg = await message.channel.send("Shadow Pokémon cannot be traded")
            await message.delete(delay = DELETE_DELAY)
            await sentMsg.delete(delay = DELETE_DELAY)
        
        elif "lucky" in fullPokemon:
            #reject, luckies can't be traded
            sentMsg = await message.channel.send("Lucky Pokémon cannot be traded")
            await message.delete(delay = DELETE_DELAY)
            await sentMsg.delete(delay = DELETE_DELAY)

        else:
            #check if pokemon is available in Pokemon GO
            shortPokemon = fullPokemon

            if "shiny" in fullPokemon:
                #remove "shiny" from the entry
                shortPokemon = fullPokemon[6:]

            if shortPokemon not in pokemonTable:
                #pokemon could not be found in the table 
                closeSpelling = difflib.get_close_matches(shortPokemon, pokemonTable.keys(), 1, CLOSENESS_CUTOFF)
                sentMsg = None
                if len(closeSpelling) > 0:
                    sentMsg = await message.channel.send("Pokémon could not be found. Did you mean " + closeSpelling[0].title() + "?")
                else:
                    sentMsg = await message.channel.send("Pokémon could not be found")
                await message.delete(delay = DELETE_DELAY)
                await sentMsg.delete(delay = DELETE_DELAY)

            #check if pokemon can be traded
            elif not pokemonTable[shortPokemon][0]:
                sentMsg = await message.channel.send("This Pokémon cannot be traded")
                await message.delete(delay = DELETE_DELAY)
                await sentMsg.delete(delay = DELETE_DELAY)

            else:
                #check if pokemon can be shiny
                if "shiny" in fullPokemon and not pokemonTable[shortPokemon][1]:
                    sentMsg = await message.channel.send("This Pokémon cannot be shiny")
                    await message.delete(delay = DELETE_DELAY)
                    await sentMsg.delete(delay = DELETE_DELAY)
                    
                else:
                    #all checks passed, report trade offer
                    sentMsg = await message.channel.send("What Pokémon you like in return for your " + fullPokemon.title() + "?")

                    def validateResponse(msg):
                        return msg.author == message.author and msg.channel == message.channel
                    
                    try:
                        responseMsg = await client.wait_for("message", check = validateResponse, timeout = RESPONSE_TIMEOUT)
                        wantList = responseMsg.content.replace(", ", ",").lower().split(",")
                        sender = message.author
                        finalWantList = []

                        #iterate over wantList to see which pokemon are available
                        for pokemon in wantList:
                            if ("shiny" in pokemon and pokemon[6:] in pokemonTable and pokemonTable[pokemon[6:]][1] and pokemonTable[pokemon[6:]][0]) or (pokemon in pokemonTable and pokemonTable[pokemon][0]) or (pokemon == "obo") or (pokemon == "any"):
                                #pokemon is acceptable
                                finalWantList.append(pokemon)
                            if len(finalWantList) == WANT_LIMIT:
                                break
                        finalWantList = list(dict.fromkeys(finalWantList))

                        for i, pokemon in enumerate(finalWantList):
                            if pokemon == "any":
                                finalWantList.append(finalWantList.pop(i))
                                break
                        for i, pokemon in enumerate(finalWantList):
                            if pokemon == "obo":
                                finalWantList.append(finalWantList.pop(i))
                                break

                        if len(finalWantList) == 0:
                            errorMsg = await message.channel.send("Invalid Pokémon want list")
                            await message.delete(delay = DELETE_DELAY)
                            await sentMsg.delete(delay = DELETE_DELAY)
                            await responseMsg.delete(delay = DELETE_DELAY)
                            await errorMsg.delete(delay = DELETE_DELAY)
                        
                        else:
                            #create and send the embed message
                            desc = "**Wants:**\n"

                            for i, pokemon in enumerate(finalWantList):
                                if pokemon != "obo" and pokemon != "any":
                                    desc += ":regional_indicator_" + chr(ord('`') + i + 1) + ": " + pokemon.title() + "\n"

                            count = len(finalWantList)
                            if count == 0:
                                count = 1
                            if "any" in finalWantList:
                                desc += ":regional_indicator_" + chr(ord('`') + count - 1) + ": Any Pokémon\n"
                            if "obo" in finalWantList:
                                desc += ":regional_indicator_" + chr(ord('`') + count) + ": OBO\n"

                            desc += "\n Trade posted by " + sender.mention
                            embedMsg = discord.Embed(title = fullPokemon.title() + " for Trade", description = desc, color = 0x3299fa)

                            thumbnailName = pokemonTable[shortPokemon][2]
                            if "shiny" in fullPokemon:
                                thumbnailName = thumbnailName + "_shiny"
                            file = discord.File("Pokemon Thumbnails/" + thumbnailName + ".png", filename = "image.png")
                            embedMsg.set_thumbnail(url = "attachment://image.png")

                            tradeMsg = await message.channel.send(file = file, embed = embedMsg)
                            messageHistory["Trades"][str(tradeMsg.id)] = [tradeMsg.channel.id, message.author.id, finalWantList, fullPokemon]
                            SaveMessageHistory()
                            await message.delete()
                            await sentMsg.delete()
                            await responseMsg.delete()

                            for i in range(len(finalWantList)):
                                #add reactions
                                await tradeMsg.add_reaction(chr(0x0001F1E6 + i))
                            await tradeMsg.add_reaction(chr(0x0000274C))

                    except asyncio.TimeoutError:
                        #timed out, user did not respond
                        print("timed out")

    elif content[:4].lower() == "!iso":
        #ISO command
        print("ISO command")

    elif content[:5] == "!help":
        if message.author != client.user:
            embedDM = discord.Embed(title = "Mystic Bot Trades Help Menu", description = "", color = 0xfa4632)
            embedDM.add_field(name = "Commands", value = "!trade <Pokémon>\n!help", inline = True)
            embedDM.add_field(name = "Description", value = "post a Pokémon for trade\nview this help menu", inline = True)
            embedDM.add_field(name = "Syntax", value = "Do not wrap any Pokémon names in quotation marks\nlist multiple Pokémon with commas separating them\ninclude all proper punctuation in Pokémon names", inline = False)
            embedDM.add_field(name = "Miscellaneous", value = "use :x: to delete trades you have posted\nreact with :capital_abcd: to offer the corresponding Pokémon\nuse \'OBO\' to say that you will accept the best offer\nuse \'any\' to say that you will accept any Pokémon\nwanted Pokémon are limited to 10", inline = False)
            await message.author.send(embed = embedDM)
            await message.delete()

    elif content[:5] == "!edit" and message.channel.id == BOT_EDIT_CHANNEL_ID:
        for role in message.author.roles:
            if role.name == "Admin" or role.name == "Moderator":
                #edit
                messageParts = message.content[6:].replace(", ", ",").split(",")
                messageParts[0] = messageParts[0].lower()
                messageParts[1] = messageParts[1].lower()
                errorMsg = None
                successMsg = None
                thumbnailMsg = None
                shinyThumbnailMsg = None

                if len(messageParts) < 3:
                    errorMsg = "Too few arguments"
                elif len(messageParts) > 3:
                    errorMsg = "Too many arguments"
                elif messageParts[1] != "tradeable" and messageParts[1] != "shiny" and messageParts[1] != "thumbnail" and messageParts[1] != "shiny thumbnail":
                    errorMsg = "Invalid field argument"
                elif (messageParts[1] == "tradeable" or messageParts[1] == "shiny") and messageParts[2].lower() != "true" and messageParts[2].lower() != "false":
                    errorMsg = "Argument #2 must be True/False"
                elif messageParts[1] == "tradeable" or messageParts[1] == "shiny":
                    messageParts[2] = messageParts[2].lower() == "true"
                elif (messageParts[1] == "thumbnail" or messageParts[1] == "shiny thumbnail"):
                    valid = validators.url(messageParts[2])
                    if valid != True:
                        errorMsg = "Argument #2 must be a valid URL"

                if messageParts[0] not in pokemonTable:
                    errorMsg = "Pokémon not in database"

                if errorMsg == None:
                    if messageParts[1] == "tradeable":
                        pokemonTable[messageParts[0]][0] = messageParts[2]
                        SavePokemonTable()
                    elif messageParts[1] == "shiny":
                        pokemonTable[messageParts[0]][1] = messageParts[2]
                        SavePokemonTable()
                    elif messageParts[1] == "thumbnail":
                        os.remove("Pokemon thumbnails/" + messageParts[0] + ".png")
                        image_url = messageParts[2]
                        imgData = requests.get(image_url).content
                        with open('Pokemon Thumbnails/' + messageParts[0] + '.png', 'wb') as handler:
                            handler.write(imgData)
                    elif messageParts[1] == "shiny thumbnail":
                        os.remove("Pokemon thumbnails/" + messageParts[0] + "_shiny.png")
                        image_url = messageParts[2]
                        imgData = requests.get(image_url).content
                        with open('Pokemon Thumbnails/' + messageParts[0] + '_shiny.png', 'wb') as handler:
                            handler.write(imgData)

                    successMsg = await message.channel.send("Entry successfully updated: " + messageParts[0] + ": [" + str(pokemonTable[messageParts[0]][0]) + ", " + str(pokemonTable[messageParts[0]][1]) + "]")
                    file = discord.File("Pokemon Thumbnails/" + messageParts[0] + ".png", filename = "image.png")
                    thumbnailMsg = await message.channel.send("Thumbnail image:", file = file)
                    file = discord.File("Pokemon Thumbnails/" + messageParts[0] + "_shiny.png", filename = "image.png")
                    shinyThumbnailMsg = await message.channel.send("Shiny thumbnail image:", file = file)
                else:
                    errorMsg = await message.channel.send(errorMsg)

                await message.delete(delay = DELETE_DELAY)
                if errorMsg != None:
                    await errorMsg.delete(delay = DELETE_DELAY)
                if successMsg != None:
                    await successMsg.delete(delay = DELETE_DELAY)
                    await thumbnailMsg.delete(delay = DELETE_DELAY)
                    await shinyThumbnailMsg.delete(delay = DELETE_DELAY)

                break

    elif content[:4] == "!add" and message.channel.id == BOT_EDIT_CHANNEL_ID:
        for role in message.author.roles:
            if role.name == "Admin" or role.name == "Moderator":
                #add
                messageParts = message.content[5:].replace(", ", ",").split(",")
                messageParts[0] = messageParts[0].lower()
                messageParts[1] = messageParts[1].lower()
                messageParts[2] = messageParts[2].lower()
                errorMsg = None
                successMsg = None
                thumbnailMsg = None
                shinyThumbnailMsg = None

                if len(messageParts) < 5:
                    errorMsg = "Too few arguments"
                elif len(messageParts) > 5:
                    errorMsg = "Too many arguments"
                elif messageParts[1].lower() != "true" and messageParts[1].lower() != "false":
                    errorMsg = "Argument #2 must be True/False"
                elif messageParts[2].lower() != "true" and messageParts[2].lower() != "false":
                    errorMsg = "Argument #3 must be True/False"
                elif validators.url(messageParts[3]) != True:
                    errorMsg = "Argument #4 must be a valid URL"
                elif validators.url(messageParts[4]) != True:
                    errorMsg = "Argument #5 must be a valid URL"
                else:
                    messageParts[1] = messageParts[1].lower() == "true"
                    messageParts[2] = messageParts[2].lower() == "true"

                if messageParts[0] in pokemonTable:
                    errorMsg = "Pokémon already in database"

                if errorMsg == None:
                    image_url = messageParts[3]
                    imgData = requests.get(image_url).content
                    with open('Pokemon Thumbnails/' + messageParts[0] + '.png', 'wb') as handler:
                        handler.write(imgData)

                    image_url = messageParts[4]
                    imgData = requests.get(image_url).content
                    with open('Pokemon Thumbnails/' + messageParts[0] + '_shiny.png', 'wb') as handler:
                        handler.write(imgData)

                    pokemonTable[messageParts[0]] = [messageParts[1], messageParts[2], messageParts[0]]
                    SavePokemonTable()
                    successMsg = await message.channel.send("New entry successfully added: " + messageParts[0] + ": [" + str(messageParts[1]) + ", " + str(messageParts[2]) + "]")
                    file = discord.File("Pokemon Thumbnails/" + messageParts[0] + ".png", filename = "image.png")
                    thumbnailMsg = await message.channel.send("Thumbnail image:", file = file)
                    file = discord.File("Pokemon Thumbnails/" + messageParts[0] + "_shiny.png", filename = "image.png")
                    shinyThumbnailMsg = await message.channel.send("Shiny thumbnail image:", file = file)
                else:
                    errorMsg = await message.channel.send(errorMsg)

                await message.delete(delay = DELETE_DELAY)
                if errorMsg != None:
                    await errorMsg.delete(delay = DELETE_DELAY)
                if successMsg != None:
                    await successMsg.delete(delay = DELETE_DELAY)
                    await thumbnailMsg.delete(delay = DELETE_DELAY)
                    await shinyThumbnailMsg.delete(delay = DELETE_DELAY)

                break
    elif content[:7] == "!delete" and message.channel.id == BOT_EDIT_CHANNEL_ID:
        for role in message.author.roles:
            if role.name == "Admin" or role.name == "Moderator":
                #delete
                pokemon = message.content[8:].lower()
                errorMsg = None
                successMsg = None
                if pokemon in pokemonTable:
                    del pokemonTable[pokemon]
                    SavePokemonTable()
                    successMsg = await message.channel.send("Successfully deleted entry " + pokemon + " from the database")
                else:
                    errorMsg = await message.channel.send("Entry not found in database")

                await message.delete(delay = DELETE_DELAY)
                if errorMsg != None:
                    await errorMsg.delete(delay = DELETE_DELAY)
                if successMsg != None:
                    await successMsg.delete(delay = DELETE_DELAY)
                
                break

    else:
        await message.delete(delay = DELETE_DELAY)

@client.event
async def on_raw_reaction_add(payload):
    if payload.user_id != BOT_USER_ID: # and payload.user_id != tradeMsg[2]:
        if str(payload.message_id) in messageHistory["Trades"]:
            tradeMsg = messageHistory["Trades"][str(payload.message_id)]
            if payload.emoji.name == chr(0x0000274C):
                try:
                    channel = client.get_channel(payload.channel_id)
                    msg = await channel.fetch_message(payload.message_id)
                    await msg.delete()
                    DeleteMessageFromHistory("Trades", str(payload.message_id))
                except Exception as e:
                    print("fetch_message exception:")
                    print(e)
            else:
                finalWantList = tradeMsg[2]
                fullPokemon = tradeMsg[3]
                try:
                    sender = await client.fetch_user(tradeMsg[1])
                    reactionSender = await client.fetch_user(payload.user_id)
                    for i in range(len(finalWantList)):
                        if payload.emoji.name == chr(0x0001F1E6 + i):
                            if finalWantList[i] == "any" or finalWantList[i] == "obo":
                                desc = "**" + str(reactionSender) + " wants:**\n" + fullPokemon.title() + "\n\nDM them to discuss"
                                embedDM = discord.Embed(title = "Trade interest received", description = desc, color = 0xfaf732)

                                thumbnailName = ""
                                if "shiny" in fullPokemon:
                                    thumbnailName = thumbnailName + "_shiny"
                                else:
                                    pokemonTable[shortPokemon][2]
                                file = discord.File("Pokemon Thumbnails/" + thumbnailName + ".png", filename = "image.png")
                                embedDM.set_thumbnail(url = "attachment://image.png")
                                directMsg = await sender.send(file = file, embed = embedDM)
                                messageHistory["Direct"][str(directMsg.id)] = [sender.id, reactionSender.id]
                                SaveMessageHistory()

                            else:
                                desc = "**" + str(reactionSender) + " offers:**\n" + finalWantList[i].title() + "\n\n**Wants:**\n" + fullPokemon.title() + "\n\n✅ Accept offer \n❎ Reject offer"
                                embedDM = discord.Embed(title = "Trade offer received", description = desc, color = 0x32a84e)

                                thumbnailName = ""
                                if "shiny" in fullPokemon:
                                    thumbnailName = pokemonTable[(finalWantList[i])[6:]][2] + "_shiny"
                                else:
                                    thumbnailName = pokemonTable[finalWantList[i]][2]
                                file = discord.File("Pokemon Thumbnails/" + thumbnailName + ".png", filename = "image.png")
                                embedDM.set_thumbnail(url = "attachment://image.png")

                                directMsg = await sender.send(file = file, embed = embedDM)
                                await directMsg.add_reaction("✅")
                                await directMsg.add_reaction("❎")
                                messageHistory["Direct"][str(directMsg.id)] = [sender.id, reactionSender.id, finalWantList[i], fullPokemon]
                                SaveMessageHistory()
                except Exception as e:
                    print("fetch_user exception:")
                    print(e)

        elif str(payload.message_id) in messageHistory["Direct"]:
            if payload.emoji.name == "✅" or payload.emoji.name == "❎":
                directMsg = messageHistory["Direct"][str(payload.message_id)]
                desc = "**They listed:**\n" + directMsg[2] + "\n\n**You offered:**\n" + directMsg[3]
                title = ""
                color = 0xFFFFFF
                poster = client.get_user(directMsg[0])
                offerer = client.get_user(directMsg[1])

                if payload.emoji.name == "✅":
                    #accept offer
                    title = "Trade Offer Accepted"
                    desc = str(poster) + " accepted your trade offer\n\n" + desc
                    color = 0x32a84e

                elif payload.emoji.name == "❎":
                    #reject offer
                    title = "Trade Offer Denied"
                    desc = str(poster) + " denied your trade offer\n\n" + desc
                    color = 0xfa4632

                embedDM = discord.Embed(title = title, description = desc, color = color)
                thumbnailName = ""
                
                if "shiny" in directMsg[3]:
                    thumbnailName = pokemonTable[(directMsg[3])[6:]][2] + "_shiny"
                else:
                    thumbnailName = pokemonTable[directMsg[3]][2]
                file = discord.File("Pokemon Thumbnails/" + thumbnailName + ".png", filename = "image.png")
                embedDM.set_thumbnail(url = "attachment://image.png")

                directMsg = await offerer.send(file = file, embed = embedDM)

LoadMessageHistory()
LoadPokemonTable()
client.run(TOKEN)
