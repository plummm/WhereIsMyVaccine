import requests
import sys
import threading
import time
import datetime

from teleg_helper import TelegHelper

class Docter(TelegHelper):
    def __init__(self, token, boss_id) -> None:
        super().__init__(token, boss_id)

    def notify(self, id, name, chat_id):
        url = 'https://curative.com/sites/{}'.format(id)
        message = '{} has slots left: {}'.format(name, url)
        self.SendMessage(chat_id, message)
        self.logger.info("{}: {}".format(chat_id, message))

    def any_slots_available(self, windows):
        for window in windows:
            if window['status'] == 'Active' and window['slots_available'] > 0:
                self.logger.info("{} {}".format(window['end_time'], window['slots_available']))
                return True
        return False


    def monitor_vaccine_site(self, sites, chat_id):
        now = datetime.datetime.now()
        date_time = now.strftime("%m/%d/%Y, %H:%M:%S")
        self.vaccine_log[chat_id] = date_time + "\n"
        for site in sites:
            for service in site['services']:
                if 'vaccine' in service.lower():
                    if self.any_slots_available(site['appointment_windows']):
                        self.notify(site['id'], site['name'], chat_id)
                    else:
                        self.vaccine_log[chat_id] += "{} has no vaccine left\n".format(site['name'])
                    break


    def search_vaccine(self, location, radius, chat_id):
        while self.userStatus[chat_id] != TelegHelper.StatusKill:
            url = 'https://labtools.curativeinc.com/api/v1/testing_sites/get_by_geolocation?h3={}&radius={}'.format(location,
                                                                                                                    radius)
            req = requests.request(method='GET', url=url)
            sites = req.json()
            self.monitor_vaccine_site(sites, chat_id)
            lines = self.vaccine_log[chat_id].split('\n')
            if len(lines) == 2 and lines[1]=="":
                self.SendMessage(chat_id, "There is no vaccination sites in your area round {} miles".format(radius))
                self.SendMessage(chat_id, "Using a bigger radius may help, but it doesn't cover all sites in the given radius due to the maximum number of sites for each query")
                self.SendMessage(chat_id, "You may change to a nearby zip code where has a vaccination site(NOT TEST ONLY SITE), the information can be found at https://curative.com/sites")
                self.userStatus[chat_id] = TelegHelper.StatusKill
            time.sleep(self.timeout[chat_id])

    def engine(self):
        while True:
            sym = self.queue.get(block=True)
            location = sym['location']
            radius = sym['radius']
            chat_id = sym['chat_id']
            self.logger.info("Monitoring for {}".format(chat_id))
            x = threading.Thread(target=self.search_vaccine, args=(location, radius, chat_id,))
            x.start()
            time.sleep(10)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: find_vaccine TOKEN boss_id")
        exit(0)

    doc = Docter(sys.argv[1], sys.argv[2])
    doc.engine()
