import local_cache
import h3
import pgeocode
import queue

from telegram import Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import InlineQueryResultArticle, InputTextMessageContent
from numpy import nan

class TelegHelper():
    StatusNone = 0
    StatusAddZipcode = 1
    StatusAddRadius = 2
    StatusKill = 3

    def __init__(self, token, boss_id) -> None:
        self.timeout = {}
        self.gSym = {}
        self.gChatId = []
        self.userStatus = {}
        self.vaccine_log = {}
        self.symCachePath = {}
        self.boss_id = int(boss_id)
        self.queue = queue.Queue()
        self.nomi = pgeocode.Nominatim('us')
        self.updater = Updater(token=token, use_context=True)
        self.dispatcher = self.updater.dispatcher
        self.updater.start_polling()
        self.AddCommandHandler("start", self.CommandStart)
        self.AddCommandHandler("remove_from_watchlist", self.CommandRemoveFromWatchList)
        self.AddCommandHandler("show_latest_result", self.CommandShowWatchlist)
        self.AddCommandHandler("source_code", self.CommandSourceCode)
        self.AddMessageHandler(self.MessageUnknowText)
        self.initCache()
    
    def initNewUser(self, chat_id):
        self.gChatId.append(chat_id)
        self.symCachePath[chat_id] = "./sym-"+str(chat_id)
        self._getLocalSym(chat_id)
        self.userStatus[chat_id] = TelegHelper.StatusNone
        self.timeout[chat_id] = 60*2

    def initCache(self):
        ids = self._getLocalChatId()
        for a_id in ids:
            if a_id not in self.gChatId:
                self.initNewUser(a_id)
                print("Monitoring for {}".format(a_id))
    
    def CommandStart(self, update, context):
        chat_id = update.effective_chat.id
        print("new start: {}".format(chat_id))
        if chat_id not in self.gChatId:
            self.initNewUser(chat_id)
            local_cache.writeToChatIdCache("./chat_id", chat_id)
        self.SetupZipcode(chat_id)
    
    def SetupZipcode(self, chat_id):
        self.SendMessage(chat_id, "Zip code:")
        self.userStatus[chat_id] = TelegHelper.StatusAddZipcode
    
    def SetupRadius(self, chat_id):
        self.SendMessage(chat_id, "Radius in miles:")
        self.userStatus[chat_id] = TelegHelper.StatusAddRadius
    
    def MessageUnknowText(self, update, context):
        chat_id = update.effective_chat.id
        if update.effective_user == None:
            return
        user_id = update.effective_user.id
        if user_id not in self.userStatus:
            self.SendMessage(chat_id, "You shouldn't reply other's query")
            return
        if not self._isChatRegistered(chat_id):
            return

        if self.userStatus[user_id] == TelegHelper.StatusAddZipcode:
            self.userStatus[user_id] = self.StatusNone
            val = self.Zipcode2url(update.message.text)
            if val == None:
                self.SendMessage(chat_id, "Invalid zipcode: {}".format(update.message.text))
                return
            self.gSym[chat_id]['location'] = val
            self.SetupRadius(chat_id)
        elif self.userStatus[user_id] == TelegHelper.StatusAddRadius:
            self.userStatus[user_id] = self.StatusNone
            try:
                distance = int(update.message.text)
                if distance > 150:
                    self.SendMessage(chat_id, "radius is too big")
                    self.SetupRadius(chat_id)
                    return
                self.gSym[chat_id]['radius'] = distance
                self.SendMessage(chat_id, "You will get a notification at once there is a available slot")
                self.PutQueue(self.gSym[chat_id])
            except:
                self.SendMessage(chat_id, "Invalid radius")
        if update.message.text == "BuyMeOrange":
            self.timeout[chat_id] = 1*60
        if update.message.text[:11] == "GlobalCall:" and chat_id == self.boss_id:
            global_message = update.message.text[11:]
            for each in self.gChatId:
                self.SendMessage(each, global_message)
    
    def AddCommandHandler(self, str, func):
        handler = CommandHandler(str, func)
        self.dispatcher.add_handler(handler)
    
    def AddMessageHandler(self, func):
        handler = MessageHandler(Filters.text & (~ Filters.command), func)
        self.dispatcher.add_handler(handler)
    
    def CommandRemoveFromWatchList(self, update, context):
        chat_id = update.effective_chat.id
        self.userStatus[chat_id] = TelegHelper.StatusKill
        self.SendMessage(chat_id, "You are removed")
        local_cache.removeUser(chat_id)
        self.gChatId.remove(chat_id)

    def CommandShowWatchlist(self, update, context):
        chat_id = update.effective_chat.id
        self.SendMessage(chat_id, self.vaccine_log[chat_id])
    
    def CommandSourceCode(self, update, context):
        chat_id = update.effective_chat.id
        self.SendMessage(chat_id, "Find me at https://github.com/plummm/WhereIsMyVaccine")

    def PutQueue(self, sym):
        if 'radius' in sym and 'location' in sym and 'chat_id' in sym:
            local_cache.writeToSymsCache(self.symCachePath[sym['chat_id']], sym)
            self.queue.put(sym)

    def Zipcode2url(self, zipcode):
        geo = self.nomi.query_postal_code(zipcode)
        if geo.latitude == nan or geo.longitude == nan:
            return None
        h3_val = h3.geo_to_h3(geo.latitude, geo.longitude, 8)
        return h3_val

    def SendMessage(self, chat_id, message):
        try:
            self.updater.bot.send_message(chat_id=chat_id, text=message)
        except:
            print("exception occurs at chat {}".format(chat_id))
    
    def _getLocalChatId(self):
        ids = local_cache.readFromChatIdCache("./chat_id")
        return ids
    
    def _getLocalSym(self, chat_id):
        sym = local_cache.readFromSymsCache(self.symCachePath[chat_id])
        if sym != {}:
            self.gSym[chat_id] = sym
            self.PutQueue(self.gSym[chat_id])
        else:
            self.gSym[chat_id] = {}
            self.gSym[chat_id]['chat_id'] = chat_id
    
    def _isChatRegistered(self, chat_id):
        if chat_id not in self.gChatId:
            self.SendMessage(chat_id, "/start first.")
            return False
        return True