import requests
import sys
import threading
import time
import datetime
import h3

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


    def search_vaccine(self, index, location, radius, chat_id):
        nround = 0
        try:
            while self.userThread[chat_id] == index:
                nround += 1
                url = 'https://labtools.curativeinc.com/api/v1/testing_sites/get_by_geolocation?h3={}&radius={}'.format(location,
                                                                                                                        radius)
                req = requests.request(method='GET', url=url)
                sites = req.json()
                self.monitor_vaccine_site(sites, chat_id)
                if nround == 1:
                    lines = self.vaccine_log[chat_id].split('\n')
                    if len(lines) == 2 and lines[1]=="":
                        coordinates = h3.h3_to_geo(location)
                        if len(coordinates) == 2:
                            url = "https://curative.com/sites#10/{}/{}".format(coordinates[0], coordinates[1])
                        else:
                            url = "https://curative.com/search"
                        self.SendMessage(chat_id, "There is no vaccination sites in your area round {} miles".format(radius))
                        self.SendMessage(chat_id, "Using a bigger radius may help, but it doesn't cover all sites in the area due to the maximum number of sites for each query")
                        self.SendMessage(chat_id, "You may change to a nearby zip code where has a vaccination site(NOT TEST ONLY SITE), the information can be found at {}".format(url))
                        self.userStatus[chat_id] = TelegHelper.StatusKill
                time.sleep(self.timeout[chat_id])
        except Exception as e:
            self.logger.info("{}: An unexpected error occur at search_vaccine(): {}".format(chat_id, e))
        self.logger.info("{} exits".format(chat_id))

    def engine(self):
        index = 0
        while True:
            sym = self.queue.get(block=True)
            location = sym['location']
            radius = sym['radius']
            chat_id = sym['chat_id']
            self.logger.info("Monitoring for {}".format(chat_id))
            x = threading.Thread(target=self.search_vaccine, args=(index, location, radius, chat_id,), name="Thread-{}".format(chat_id))
            index += 1
            x.start()
            time.sleep(10)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: find_vaccine TOKEN boss_id")
        exit(0)

    doc = Docter(sys.argv[1], sys.argv[2])
    doc.engine()
