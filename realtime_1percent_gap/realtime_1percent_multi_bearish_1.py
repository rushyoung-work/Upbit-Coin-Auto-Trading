import threading
import queue
import time
import pyupbit
import datetime
from collections import deque
TICKER = "KRW-DOGE"
CASH = 90000

class Consumer(threading.Thread):
    def __init__(self, q):
        super().__init__()
        self.q = q
        self.ticker = TICKER

        self.ma5 = deque(maxlen=5)
        #self.ma10 = deque(maxlen=10)
        #self.ma15 = deque(maxlen=15)
        self.ma50 = deque(maxlen=50)
        self.ma120 = deque(maxlen=120)

        df = pyupbit.get_ohlcv(self.ticker, interval="minute1")
        self.ma5.extend(df['close'])
        #self.ma10.extend(df['close'])
        #self.ma15.extend(df['close'])
        self.ma50.extend(df['close'])
        self.ma120.extend(df['close'])


    def run(self):
        price_curr = None  # 현재 가격
        hold_flag = False  # 보유 여부
        wait_flag = False  # 대기 여부
        coin_profit = 0  # 수익률
        past_ma5 = None  # 지난 5봉 비교변수

        with open("key/upbit_key.txt", "r") as f:
            access = f.readline().strip()
            secret = f.readline().strip()

        upbit = pyupbit.Upbit(access, secret)
        #cash  = upbit.get_balance()  # 2개 이상 종목 돌릴 시 모든 cash 코드 임의 설정
        cash = CASH
        print("보유현금:", cash)

        i = 0

        while True:
            try:
                if not self.q.empty():
                    past_ma5 = sum(self.ma5) / len(self.ma5)
                    if price_curr != None:
                        self.ma5.append(price_curr)
                        #self.ma10.append(price_curr)
                        #self.ma15.append(price_curr)
                        self.ma50.append(price_curr)
                        self.ma120.append(price_curr)

                    curr_ma5 = sum(self.ma5) / len(self.ma5)
                    #curr_ma10 = sum(self.ma10) / len(self.ma10)
                    #curr_ma15 = sum(self.ma15) / len(self.ma15)
                    curr_ma50 = sum(self.ma50) / len(self.ma50)
                    curr_ma120 = sum(self.ma120) / len(self.ma120)

                    price_open = self.q.get()
                    if hold_flag == False:
                        price_buy  = price_open
                        #price_sell = price_open * 1.015
                    wait_flag  = False

                price_curr = pyupbit.get_current_price(self.ticker)
                if price_curr == None:
                    continue

                if hold_flag == False and wait_flag == False and \
                    price_curr >= price_buy and curr_ma50 >= curr_ma120 and past_ma5 < curr_ma5:
                    # 0.05%
                    while True:
                        ret = upbit.buy_market_order(self.ticker, cash * 0.9995)
                        if ret == None or "error" in ret:
                            print("<< 매수 주문 Error >>")
                            time.sleep(0.5)
                            continue
                        print("매수 주문", ret)
                        break

                    while True:
                        order = upbit.get_order(ret['uuid'])
                        if order != None and len(order['trades']) > 0:
                            print("<< 매수 주문이 체결되었습니다 >>\n", order)
                            break
                        else:
                            print("매수 주문 대기 중...")
                            time.sleep(0.5)

                    while True:
                        volume = upbit.get_balance(self.ticker)
                        if volume != None and volume != 0:
                            hold_flag = True
                            break
                        print("보유량 계산중...")
                        time.sleep(0.5)
                    
                    #cash = upbit.get_balance()
                    cash -= (price_buy * volume)

                if hold_flag == True:

                    if (price_curr / price_buy) <= 0.9:  # 10% 하락시 손절 매도 (패닉셀 대처)
                        upbit.sell_market_order(self.ticker, volume)
                        while True:
                            volume = upbit.get_balance(self.ticker)
                            if volume == 0:
                                print("<< 패닉셀 주문(-10%)이 완료되었습니다 >>")
                                cash += CASH * 0.897
                                hold_flag = False
                                wait_flag = True
                                break
                            else:
                                print("패닉셀 주문(-10%) 대기중...")
                                time.sleep(0.5)
                    
                    elif past_ma5 >= curr_ma5:  # 하락장 전환시 손절 매도
                        upbit.sell_market_order(self.ticker, volume)
                        while True:
                            volume = upbit.get_balance(self.ticker)
                            if volume == 0:
                                print("<< 손절 주문(하락장 전환)이 완료되었습니다 >>")
                                coin_profit += (price_curr / price_buy) * 0.997
                                print(f"수익률: {coin_profit}")
                                cash += CASH * ((price_curr / price_buy) * 0.997)
                                hold_flag = False
                                wait_flag = True
                                break
                            else:
                                print("손절 주문(하락장 전환) 대기중...")
                                time.sleep(0.5)

                # 8 seconds
                if i == (5 * 8):
                    print(f"[{datetime.datetime.now()}]")
                    print(f"{TICKER} 보유량:{upbit.get_balance_t(self.ticker)}, 보유KRW: {cash},  hold_flag= {hold_flag}, wait_flag= {wait_flag} signal = {curr_ma50 >= curr_ma120 and past_ma5 < curr_ma5}")
                    print(f"현재: {price_curr}, 매수 목표: {int(price_buy)}, 누적 수익률: {coin_profit}, 패닉셀 예상가: {int(price_buy * 0.9)}, past_ma5: {past_ma5}, curr_ma5: {curr_ma5}")
                    i = 0
                i += 1
            except:
                print("error")

            time.sleep(0.2)

class Producer(threading.Thread):
    def __init__(self, q):
        super().__init__()
        self.q = q

    def run(self):
        while True:
            price = pyupbit.get_current_price(TICKER)
            self.q.put(price)
            time.sleep(60)

now = datetime.datetime.now()
print(f'환영합니다 -- Upbit Auto Trading -- [{now.year}-{now.month}-{now.day} {now.hour}:{now.minute}:{now.second}]')
print('트레이딩 대기중...')
while True:
    now = datetime.datetime.now()
    if now.second == 0:  # 대기 후 정각에 시작
        q = queue.Queue()
        Producer(q).start()
        Consumer(q).start()
        break
