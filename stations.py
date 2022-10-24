'''
現在時刻から直近の乗換案内を検索して、到着時間を表示する
Yahoo乗換から到着時間をスクレイピングで抽出している
'''
from operator import truediv
from sys import float_repr_style
from tkinter.messagebox import RETRY
import urllib.request
from bs4 import BeautifulSoup
import urllib.parse  # URLエンコード、デコード
import datetime as dt
import re
from statistics import mean


class Trip():
    def __init__(self, origin, destination) -> None:
        self.origin = origin
        self.destination = destination


class SearchedTrainTrip(Trip):
    def __init__(self, origin, destination, given_datetime, depart_time, arrive_time, fare, transfer) -> None:
        super().__init__(origin, destination)

        self.givin_datetime = given_datetime
        self.depart_time = depart_time
        self.arrive_time = arrive_time
        self.fare = fare
        self.transfer = transfer

        self.time_on_train = arrive_time - depart_time


def search_trip(origin, destination, year, month, day, hh, m1, m2, type, disp_count_set):
    '''
    URL解析とスクレイピング
    前後の車両を含めて、基礎的な情報（出発・到着時間、乗換回数、費用）を取り出す
    '''

    def get_relative_soup(soup, number):

        def get_next_url(soup):
            next_url = soup.select_one('li.next')
            next_url = 'https://transit.yahoo.co.jp' + \
                next_url.contents[0].attrs['href']
            req = urllib.request.urlopen(next_url)
            html = req.read().decode('utf-8')
            soup = BeautifulSoup(html, 'html.parser')
            return soup

        def get_prev_url(soup):
            prev_url = soup.select_one('li.prev')
            prev_url = 'https://transit.yahoo.co.jp' + \
                prev_url.contents[0].attrs['href']
            req = urllib.request.urlopen(prev_url)
            html = req.read().decode('utf-8')
            soup = BeautifulSoup(html, 'html.parser')
            return soup

        if number > 0:
            for i in range(number):
                soup = get_next_url(soup)
        elif number < 0:
            for i in range(abs(number)):
                soup = get_prev_url(soup)

        return soup

    origin_encoded = urllib.parse.quote(origin)  # encode
    destination_encoded = urllib.parse.quote(destination)  # encode
    url0 = 'https://transit.yahoo.co.jp/search/result?from='
    url1 = '&to='
    url2 = f'&fromgid=&togid=&flatlon=&tlatlon=&via=&viacode=&y={year}&m={month}&d={day}&hh={hh}&m1={m1}&m2={m2}&type={type}&ticket=ic&expkind=1&userpass=1&ws=3&s=0&al=1&shin=1&ex=1&hb=1&lb=1&sr=1'
    url = ''.join([url0, origin_encoded, url1, destination_encoded, url2])

    req = urllib.request.urlopen(url)
    html = req.read().decode('utf-8')
    soup = BeautifulSoup(html, 'html.parser')

    # 前後の検索のsoupを取得
    soup_list = [get_relative_soup(soup, n) for n in disp_count_set]

    # 前後のsoupを含めて一気に情報を抽出する
    depart_t_list = []
    arrive_t_list = []
    fare_list = []
    transfer_list = []

    for disp_count, soup in zip(disp_count_set, soup_list):
        time = soup.select("li.time")
        # list that [info you searched, info of train No.1, info of train No.2, ...]
        fare = soup.select('li.fare')
        transfer = soup.select('li.transfer')
        # list that [info of train No.1, info of train No.2, ...]

        # print(f'===  {disp_count}  のTripを抽出  ===')
        t = time[1].text.strip()  # sth. like '11:39→12:0930分'
        depart_time_train = dt.datetime.strptime(t[:5], '%H:%M')
        arrive_time_train = dt.datetime.strptime(t[6:11], '%H:%M')

        trip_fare = fare[0].text.strip()
        trip_fare = re.sub(r"\D", "", trip_fare)
        trip_fare = float(trip_fare)

        trip_transfer = transfer[0].text.strip()
        trip_transfer = re.sub(r"\D", "", trip_transfer)
        trip_transfer = int(trip_transfer)

        assert 0 <= trip_fare <= 10000, f'{origin}から{destination}の費用が{trip_fare}になっている'
        assert 0 <= trip_transfer <= 10, f'{origin}から{destination}の乗換回数が{trip_transfer}になっている'

        depart_t_list.append(depart_time_train)
        arrive_t_list.append(arrive_time_train)
        fare_list.append(trip_fare)
        transfer_list.append(trip_transfer)

        # print(f'{depart_time_train.hour}:{depart_time_train.minute} to {arrive_time_train.hour}:{arrive_time_train.minute}',
        #       trip_fare, trip_transfer)

    return depart_t_list, arrive_t_list, fare_list, transfer_list


def get_trip(origin: str = '東京', destination: str = '横浜', arrive=True,
             given_datetime=dt.datetime(2022, 8, 20, 12, 10), ):
    '''
    for each 'origin - destination' combination, 
    return [time on the train, fare, n_transfer, time interval] 

    '''

    print(f'from {origin} to {destination}, time is {given_datetime}')
    # print(f'arrive is {arrive}, ')

    year = str(given_datetime.year)
    month = str(given_datetime.month).zfill(2)
    day = str(given_datetime.day).zfill(2)
    hh = str(given_datetime.hour).zfill(2)
    mm = str(given_datetime.minute).zfill(2)
    m1, m2 = mm[0], mm[1]

    if arrive:
        type = 4
    else:
        type = 1

    disp_count_set = [-1, 0, 1]
    depart_t_list, arrive_t_list, fare_list, transfer_list = search_trip(
        origin, destination, year, month, day, hh, m1, m2, type, disp_count_set)

    # consider the time interval of trains
    time_interval = (
        arrive_t_list[-1] - arrive_t_list[0])/(len(arrive_t_list) - 1)
    time_interval = time_interval.seconds/60

    index = disp_count_set.index(0)

    depart_time = depart_t_list[index]
    arrive_time = arrive_t_list[index]
    trip_time = (arrive_time - depart_time).seconds/60
    assert 0 < trip_time < 1000, f'{origin}から{destination}の時間が{trip_time}になっている, {depart_time}, {arrive_time}'
    fare = fare_list[index]
    transfer = transfer_list[index]

    # print(f'{depart_time.hour}:{depart_time.minute} to {arrive_time.hour}:{arrive_time.minute}')
    # print(trip_time, fare, transfer, time_interval)
    return trip_time, fare, transfer, time_interval


def find_first_monday(year, month):
    d = dt.datetime(year, int(month), 7)
    offset = d.weekday()  # weekday = 0 means monday
    day = d - dt.timedelta(offset)
    return day.replace(hour=8, minute=45)


def get_accessibility(origin, main_stations, date, weights):

    a = []
    b = []
    c = []
    d = []
    for destination in main_stations:
        trip_time, fare, transfer, time_interval = get_trip(
            origin, destination, given_datetime=date)
        a.append(trip_time)
        b.append(fare)
        c.append(transfer)
        d.append(time_interval)

    return a@weights, b@weights, c@weights, d@weights


# if __name__ == '__main__':

#     main_stations = ['東京', '新宿', '品川', '横浜', '柏']

#     # first Monday in November
#     arrive_datetime = find_first_monday(2022, 11)
#     arrive_datetime = arrive_datetime.replace(hour=8, minute=45)

#     print(get_accessibility('横浜', main_stations, [arrive_datetime]))
