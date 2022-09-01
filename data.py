import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

from hexbytes import HexBytes
from tqdm import tqdm
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

if not os.path.exists('points.json'):
    json.dump([], fp=open('points.json', 'w'))

# temp cache
blocks = {}
for block in json.load(fp=open('points.json', 'r')):
    blocks[block['number']] = block

T = 10 ** 12
P = T * 1000
degree = int(os.environ['DEGREE'])
step = int(os.environ['STEP'])
tolerance = counter = int(os.environ['TOLERANCE'])
block_interval = int(os.environ['ETH_INTERVAL'])
interval = int(os.environ['INTERVAL'])
if os.environ.get('INFURA_URL'):
    http_url = os.environ.get('INFURA_URL')
else:
    http_url = os.environ.get('LOCAL_URL')


def format_block(block):
    n_block = {}
    for k in ['number', 'totalDifficulty', 'difficulty', 'timestamp', 'hash']:
        v = block.get(k)
        if type(v) is HexBytes:
            n_block[k] = str(v.hex())
        else:
            n_block[k] = v
    return n_block


def get_block(web3, blockn='latest'):
    block = blocks.get(blockn)
    if not block:
        if type(blockn) is int and blockn > get_block('latest')['number']:
            return blocks.get('latest')
        blocks[blockn] = format_block(web3.eth.get_block(blockn))
    return blocks.get(blockn)


def block_by_time(web3, timestamp, prev_block, next_block):
    global counter
    global tolerance

    prev = max(1, prev_block['number'])
    next = min(get_block(web3, 'latest')['number'], next_block['number'])

    if prev == next:
        counter = 0
        tolerance = 0
        return prev_block

    t0, t1 = prev_block['timestamp'], next_block['timestamp'],

    blocktime = (t1 - t0) / (next - prev)
    k = (timestamp - t0) / (t1 - t0)
    block_predicted = int(prev + k * (next - prev))

    time_predicted = get_block(web3, block_predicted)['timestamp']

    blocks_diff = int((timestamp - time_predicted) / blocktime)
    adjustment = block_predicted + blocks_diff

    r = abs(blocks_diff)

    # tolerance
    if r <= tolerance:
        return get_block(web3, adjustment)

    counter += 1
    if counter > 10:
        tolerance += 1
    return block_by_time(web3, timestamp, get_block(web3, adjustment - r), get_block(web3, adjustment + r))


def get_point_thread(web3, point_count, latest_block, max_workers=20):
    search_range = int(interval / block_interval) + 1
    points, futures = {}, []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        with tqdm(total=point_count) as progress:
            for point in range(0, point_count):
                block_ts = latest_block['timestamp'] - latest_block['timestamp'] % interval - point * interval
                future = executor.submit(block_by_time, web3, block_ts,
                                         get_block(web3, latest_block['number'] - search_range * (point + 1)),
                                         get_block(web3, latest_block['number'] - search_range * (point - 1)))
                future.add_done_callback(lambda p: progress.update())
                futures.append(future)
    for future in futures:
        point = future.result()
        points[point['number']] = point
    # for point in range(0, point_count):
    #     block_ts = latest_block['timestamp'] - latest_block['timestamp'] % interval - point * interval
    #     block = block_by_time(web3, block_ts,
    #                           get_block(web3, latest_block['number'] - search_range * (point + 1)),
    #                           get_block(web3, latest_block['number'] - search_range * (point - 1)))
    #     print(block_ts, latest_block['number'] - search_range * (point + 1), block['number'])
    #     points[block['number']] = block
    return points


def get_points(span=30 * 24 * 60 * 60):
    web3 = Web3(Web3.HTTPProvider(http_url))
    latest_block = get_block(web3, 'latest')
    print(latest_block)
    point_count = int(span / interval) + 1
    points = {}
    temp_points = get_point_thread(web3, point_count, latest_block)
    tolerance_range = 2
    for number, point in temp_points.items():
        is_exist = False
        for tol in range(tolerance_range * -1, tolerance_range):
            fuzzy = point['number'] + tol
            if points.get(fuzzy):
                is_exist = True
                break
        if not is_exist:
            points[number] = point
    points = sorted(points.values(), key=lambda x: x.get('number'), reverse=False)

    json.dump(points, fp=open('points.json', 'w'), indent=2)


def update():
    web3 = Web3(Web3.HTTPProvider(http_url))
    latest_block = get_block(web3, 'latest')
    points, point_list = {}, json.load(fp=open('points.json', 'r'))
    for block in point_list:
        points[block['number']] = block
    timestamp = latest_block['timestamp']

    if timestamp - point_list[-1]['timestamp'] > interval:
        point_count, tolerance_range = int((timestamp - point_list[-1]['timestamp']) / interval) + 1, 2
        temp_points = get_point_thread(web3=web3, point_count=point_count, latest_block=latest_block)
        for number, point in temp_points.items():
            is_exist = False
            for tol in range(tolerance_range * -1, tolerance_range):
                fuzzy = number + tol
                if points.get(fuzzy):
                    is_exist = True
                    break
            if not is_exist:
                points[number] = point

        points = sorted(points.values(), key=lambda x: x.get('number'), reverse=False)
        json.dump(points, fp=open('points.json', 'w'), indent=2)


def read_points():
    point_list = json.load(fp=open('points.json', 'r'))
    for block in point_list:
        print(block['number'], time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(block['timestamp'])))


if __name__ == "__main__":
    get_points()
    # update()
    # read_points()
