import requests
import sys
import threading
import time

from teleg_helper import TelegHelper

class Docter(TelegHelper):
    def __init__(self, token) -> None:
        super().__init__(token)

    def notify(self, id, name, chat_id):
        url = 'https://curative.com/sites/{}'.format(id)
        message = '{} has slots left: {}'.format(name, url)
        self.SendMessage(chat_id, message)

    def any_slots_available(self, windows):
        for window in windows:
            if window['public_slots_available'] > 0 or window['slots_available'] > 0:
                return True
        return False


    def monitor_vaccine_site(self, sites, chat_id):
        self.vaccine_log[chat_id] = ""
        for site in sites:
            for service in site['services']:
                if 'vaccine' in service:
                    if self.any_slots_available(site['appointment_windows']):
                        self.notify(site['id'], site['name'], chat_id)
                    else:
                        self.vaccine_log[chat_id] += "{} has no vaccine left".format(site['name'])
                    break


    def search_vaccine(self, location, radius, chat_id):
        while self.userStatus[chat_id] != TelegHelper.StatusKill:
            url = 'https://labtools.curativeinc.com/api/v1/testing_sites/get_by_geolocation?h3={}&radius={}'.format(location,
                                                                                                                    radius)
            req = requests.request(method='GET', url=url)
            sites = req.json()
            self.monitor_vaccine_site(sites, chat_id)
            time.sleep(self.timeout[chat_id])

    def engine(self):
        while True:
            sym = self.queue.get(block=True)
            location = sym['location']
            radius = sym['radius']
            chat_id = sym['chat_id']
            x = threading.Thread(target=self.search_vaccine, args=(location, radius, chat_id,))
            x.start()

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: find_vaccine TOKEN")
        exit(0)

    doc = Docter(sys.argv[1])
    bot = doc.engine()