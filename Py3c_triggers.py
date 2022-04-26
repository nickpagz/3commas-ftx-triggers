import ccxt
import time
import math
import config
import sys
from time import gmtime, strftime
from py3cw.request import Py3CW
from pathlib import Path

#   3Commas trigger bot.
#   1 - setup a sub-account in ftx.com, connect to 3Commas via API. Get account ID in 3Commas
#   2 - Use existing functions to create script to generate bots for all pairs except those bloack listed.
#       Generate for both long and short bots. Store bot names and ID's in a file for later use.
#   3 - Less important, but a script for updating bots is needed.
#   4 - Add a flag for no shorts, or no longs
#   5 - MAX_OPEN_POSITIONS is the number of bots, put a warning when getting close to this to increase bot usage instead

## VER 3
# this version matches version 3 of PvVol - ie. it looks at market movement to determine a swith or cut.


# Setup
p3cw = Py3CW(
    key=config.TC_API_KEY,
    secret=config.TC_API_SECRET,
    request_options={
        'request_timeout': 30,
        'nr_of_retries': 1,
        'retry_status_codes': [502]
    }
)

ftx = ccxt.ftx({
    'apiKey': config.API_KEY,
    'secret': config.SECRET_KEY,
    'headers': {'FTX-SUBACCOUNT': config.SUB_ACCOUNT}
})

#ftx.verbose = True


def get_markets():
    trycnt = 3
    while trycnt > 0:
        try:
            all_markets = ftx.load_markets(True)
            trycnt = 0
        except Exception as e:
            print("Connection error, trying again...")
            f = open("3ctrigger_log.txt", "a")
            f.write(f'FTX cononnection error at {strftime("%Y-%m-%d %H:%M:%S", gmtime())} UTC\n')
            f.close()
            trycnt -= 1
            time.sleep(3)
        else:
            return all_markets
            

def get_price(markets):
    perps = {}
    for key in markets:
        if "PERP" in markets[key]['id'] and not any(perp in markets[key]['id'] for perp in config.PAIRS_BLACKLIST):
            if "last" in markets[key]["info"]:
                perps[markets[key]['id']] = markets[key]["info"]["last"]
    return perps


def get_tradeable_balance():
    account_balances = ftx.fetch_balance()
    balance = account_balances["total"]["USD"]
    print(f'Balance: {balance}')
    return balance


def change(old, new):
    changes = {}
    bullish = []
    bearish = []
    for key in old:
        diff = float(new[key]) - float(old[key])
        percent_diff = (diff / float(old[key])) * 100
        changes[key] = percent_diff
        if diff >= 0:
            bullish.append(key)
        elif diff < 0:
            bearish.append(key)
    longs = len(bullish)
    shorts = len(bearish)
    return changes, longs, shorts


def top_pairs(price_change):
    top_pairs_list = {}
    sorted_dict = {}
    for key in price_change:
        if price_change[key] > config.LTF_BULL_CHANGE:
            top_pairs_list[key] = price_change[key]
            sorted_list = sorted(top_pairs_list.items(), key=lambda x: x[1], reverse=True)
            sorted_dict = dict(sorted_list)
    return sorted_dict


def bottom_pairs(price_change):
    bottom_pairs_list = {}
    sorted_dict = {}
    for key in price_change:
        if price_change[key] < config.LTF_BEAR_CHANGE:
            bottom_pairs_list[key] = price_change[key]
            sorted_list = sorted(bottom_pairs_list.items(), key=lambda x: x[1])
            sorted_dict = dict(sorted_list)
    return sorted_dict


def get_first_key(dictionary):
    for key in dictionary:
        return key
    raise IndexError


def get_nth_key(dictionary, n=0):
    if n < 0:
        n += len(dictionary)
    for i, key in enumerate(dictionary.keys()):
        if i == n:
            return key
    raise IndexError("dictionary index out of range")


def send_bull_trigger(pair, ids):
    bot_id = ids["USD_"+pair]
    f = open("3ctrigger_log.txt", "a")
    f.write(f'Long {pair} at {strftime("%Y-%m-%d %H:%M:%S", gmtime())} UTC\n')
    f.close()
    error, bot_trigger = p3cw.request(
        entity = 'bots',
        action = 'start_new_deal',
        action_id = bot_id
    )   
    print(f'Long trigger for {pair}')
    return bot_trigger


def send_bear_trigger(pair, ids):
    bot_id = ids["USD_"+pair]
    f = open("3ctrigger_log.txt", "a")
    f.write(f'Short {pair} at {strftime("%Y-%m-%d %H:%M:%S", gmtime())} UTC\n')
    f.close()
    error, bot_trigger = p3cw.request(
        entity = 'bots',
        action = 'start_new_deal',
        action_id = bot_id
    )
    print(f'Short trigger for {pair}')
    return bot_trigger


def evaluate_positions(positions, price, bulls, bears):
    cut = []
    switch = []
    #print("We're evaluating positions")
    for key in positions:
        entry_price = abs(float(positions[key][3]))
        current_price = float(price[key])
        percent_change = ((current_price - entry_price) / entry_price)*100
        #print(f'Pair: {key}, Entry price: {entry_price}, Current price: {current_price}, Change: {percent_change}')
        if positions[key][1] == "buy" and percent_change < config.SWITCH_PERCENT:
            if key in bears:
                switch.append(key)
            elif key in bulls:
                pass
            else:
                cut.append(key)
        elif positions[key][1] == "sell" and percent_change > abs(config.SWITCH_PERCENT):
            if key in bulls:
                switch.append(key)
            elif key in bears:
                pass
            else:
                cut.append(key)
    return cut, switch


def close_deal(pair, side, long_bots, short_bots):
    if side == "buy":
        bot_id = long_bots["USD_"+pair]
    elif side == "sell":
        bot_id = short_bots["USD_"+pair]
    f = open("3ctrigger_log.txt", "a")
    f.write(f'Panic Close - {pair} at {strftime("%Y-%m-%d %H:%M:%S", gmtime())} UTC\n')
    f.close()
    error, deal_close = p3cw.request(
        entity = 'bots',
        action = 'panic_sell_all_deals',
        action_id = bot_id
    )
    print(f'Panic Close - {pair}')
    time.sleep(5)
    enable_bot(pair, bot_id)
    return deal_close


def get_positions():
    open_positions = {}
    all_positions = ftx.fetchPositions(None, {"showAvgPrice": True})
    for x in all_positions:
        future = (x["future"])
        size = (x["size"])
        side = (x["side"])
        cost = (x["cost"])
        recentAverageOpenPrice = (x["recentAverageOpenPrice"])
        if size != '0.0':
            open_positions[future] = size, side, cost, recentAverageOpenPrice
    return open_positions


def load_bot_ids(filename):
    d = {}
    with open(filename) as f:
        for line in f:
            (key, val) = line.split(':')
            d[key] = val.rstrip('\n')
    return d


def get_max_bot_usage(balance):
    if config.MARTINGALE_VOLUME_COEFFICIENT == 1.0:
        max_bot_usage = config.BASE_ORDER_VOLUME + (config.SAFETY_ORDER_VOLUME*config.MAX_SAFETY_ORERS) / config.LEVERAGE_CUSTOM_VALUE
    else:
        max_bot_usage = (config.BASE_ORDER_VOLUME + (config.SAFETY_ORDER_VOLUME*(config.MARTINGALE_VOLUME_COEFFICIENT**config.MAX_SAFETY_ORERS - 1) / (config.MARTINGALE_VOLUME_COEFFICIENT - 1))) / config.LEVERAGE_CUSTOM_VALUE
    return max_bot_usage

def enable_bot(pair, bot_id):
    error, data = p3cw.request(
        entity='bots',
        action='enable',
        action_id = bot_id,
    )
    print(f'Error: {error}')
    print(f'Bot USD_{pair} - {bot_id} > re-enabled after panic sell')



perp_change = {}

top_bull_pairs = {}

top_bear_pairs = {}

open_positions = {}

all_open_positions = {}

min_price = {}

##    <<<<<<<<<<<   START LOOP HERE     >>>>>>>>>>>>>>>>>

# Check for existing list of bot id's and load into a dictionary
longbots_file = Path("lbotid_list.txt")
shortbots_file = Path("sbotid_list.txt")

if not longbots_file.is_file() or not shortbots_file.is_file():
    print("No (or only one) bot ID lists were found. Create bots and ID list before continuing.")
    print("Bye!")
    sys.exit()

#load files into a dictionary

long_bot_ids = {}
short_bot_ids = {}

long_bot_ids = load_bot_ids("lbotid_list.txt")
short_bot_ids = load_bot_ids("sbotid_list.txt")

tradeable_balance = get_tradeable_balance()

bot_usage = get_max_bot_usage(tradeable_balance)

print(f'Max bot usage: {bot_usage}')

# Calc max number of bots - constrained by bot usage

if math.floor((float(tradeable_balance) * config.FUNDS_USAGE) / bot_usage) < config.MAX_OPEN_POSITIONS:
    max_positions = math.floor((float(tradeable_balance) * config.FUNDS_USAGE) / bot_usage)
else:
    max_positions = config.MAX_OPEN_POSITIONS

print(f'Max positions: {max_positions}')

last_balance_check = strftime("%Y-%m-%d", gmtime())

f = open("3ctrigger_log.txt", "a")
f.write("<<<<>>>>\n")
f.write(f'Script Run at {strftime("%Y-%m-%d %H:%M:%S", gmtime())} UTC\n')
f.write(f'Delay: {config.LTF_DELAY}\n')
f.write(f'Interval: {config.LTF_INTERVALS}\n')
f.write(f'Change trigger: {config.LTF_BULL_CHANGE}, {config.LTF_BEAR_CHANGE}\n')
f.write(f'Balance: {tradeable_balance}, Max Positions: {max_positions}\n')
f.write("<<<<>>>>\n")
f.close()


# Grab first set of market data
price = []

markets = get_markets()

price.append(get_price(markets))

# Start main loop
while True:
    print(f'Wait {config.LTF_DELAY/60:.2f} mins for updated market data. Time: {strftime("%H:%M:%S", gmtime())} UTC. [{len(price)}]/[{config.LTF_INTERVALS}]')

    time.sleep(config.LTF_DELAY)

    markets = get_markets()

    price.append(get_price(markets))

    while len(price) > config.LTF_INTERVALS:
        perp_change, longs, shorts = change(price[0], price[config.LTF_INTERVALS])

        trend_strength = longs / (longs + shorts) * 100

        no_bears = False
        no_bulls = False
        
        if trend_strength > config.TREND_STRENGTH and longs > shorts:
            no_bears = True
        elif (100 - trend_strength) > config.TREND_STRENGTH and shorts  > longs:
            no_bulls = True

        top_bull_pairs = top_pairs(perp_change)

        top_bear_pairs = bottom_pairs(perp_change)

        print("Top Bulls:")
        for key, value in top_bull_pairs.items():
            print(f'{key} - {value:.5f} %')


        print("Top Bears:")
        for key, value in top_bear_pairs.items():
            print(f'{key} - {value:.2f} %')

        print("<<<>>>")

        all_open_positions = get_positions()
        #print(f'All open positions {all_open_positions}')
        cut_positions, switch_positions = evaluate_positions(all_open_positions, price[config.LTF_INTERVALS], top_bull_pairs, top_bear_pairs)

        print(f'Cut Positions: ')
        print(f'Switch Positions: ')
        
        # execute market order close for cut positions
        x = 0
        for x in range(len(cut_positions)):
            key = cut_positions[x]
            close_deal(key, all_open_positions[key][1], long_bot_ids, short_bot_ids)
            
        # switch positions - first market close, then market open new positions
        x = 0
        for x in range(len(switch_positions)):
            key = switch_positions[x]
            close_deal(key, all_open_positions[key][1], long_bot_ids, short_bot_ids)
        time.sleep(5)

        x = 0
        for x in range(len(switch_positions)):
            key = switch_positions[x]
            if all_open_positions[key][1] == "buy" and not no_bears:
                send_bear_trigger(key, short_bot_ids)
            elif all_open_positions[key][1] == "sell" and not no_bulls:
                send_bull_trigger(key, long_bot_ids)

        # get new open positions count
        open_positions = get_positions()
        
        available_positions = max_positions - len(open_positions)
        
        if top_bull_pairs:
            number_of_pairs = len(top_bull_pairs)
            n = 0
            for n in range(number_of_pairs):
                highest_bull_pair = get_nth_key(top_bull_pairs, n)
                if highest_bull_pair not in open_positions and available_positions > 0 and not no_bulls:
                    if "USD_"+highest_bull_pair in long_bot_ids:
                        available_positions -= 1 # move after the call to 3commas, wrap in if, looking for a success message from 3c?
                        trigger_long_bot = send_bull_trigger(highest_bull_pair, long_bot_ids)
                        print("<<<>>>")

        if top_bear_pairs:
            number_of_pairs = len(top_bear_pairs)
            n = 0
            for n in range(number_of_pairs):
                highest_bear_pair = get_nth_key(top_bear_pairs, n)
                if highest_bear_pair not in open_positions and available_positions > 0 and not no_bears:
                    if "USD_"+highest_bear_pair in short_bot_ids:
                        available_positions -= 1
                        trigger_short_bot = send_bear_trigger(highest_bear_pair, short_bot_ids)
                        print("<<<>>>")

        del price[0]
        
    perp_change.clear()
    top_bull_pairs.clear()
    top_bear_pairs.clear()

    all_open_positions.clear()
    open_positions.clear()


    if strftime("%Y-%m-%d", gmtime()) > last_balance_check:
        tradeable_balance = get_tradeable_balance()
        bot_usage = get_max_bot_usage(tradeable_balance)
        if math.floor((float(tradeable_balance) * config.FUNDS_USAGE) / bot_usage) < config.MAX_OPEN_POSITIONS:
            max_positions = math.floor((float(tradeable_balance) * config.FUNDS_USAGE) / bot_usage)
        else:
            max_positions = config.MAX_OPEN_POSITIONS

        last_balance_check = strftime("%Y-%m-%d", gmtime())
        f = open("3ctrigger_log.txt", "a")
        f.write(f'Updated Balance: {tradeable_balance}, Max Positions: {max_positions} at {strftime("%Y-%m-%d %H:%M:%S", gmtime())} UTC\n')
        f.write(">>>>\n")
        f.close()
        print(f'Updated Balance: {tradeable_balance}, Max Positions: {max_positions}')
        
    




