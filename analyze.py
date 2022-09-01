import json
import os
import time
import warnings

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

T = 10 ** 12
P = T * 1000
degree = int(os.environ['DEGREE'])
step = int(os.environ['STEP'])
tolerance = counter = int(os.environ['TOLERANCE'])
block_interval = int(os.environ['ETH_INTERVAL'])
interval = int(os.environ['INTERVAL'])

time_target = int(os.environ['TIME_TARGET'])
time_span = int(os.environ['TIME_SPAN'])
ttd_target = float(os.environ['TTD_TARGET'])

warnings.filterwarnings('ignore')

spans = {'7d': int(7 * 24 * 3600 / interval), '14d': int(14 * 24 * 3600 / interval),
         '28d': int(28 * 24 * 3600 / interval)}


def moving_average(data, step=30):
    ma_data = []
    for index in range(data.size - step):
        ma_data.append(sum(data[index:index + step]) // step)
    return ma_data


def adjust_length(data, step=30):
    return data[step:]


def poly_predict(t, ttd):
    l = len(t)
    coeff = {}
    coeff['coeff_ttd'] = np.polyfit(t, ttd, degree)

    # Errors
    err_h = []
    err_l = []
    err = []
    coeff['poly_value'] = []
    for i in range(l):
        coeff['poly_value'].append(np.polyval(coeff['coeff_ttd'], t[i]))
        diff = abs(coeff['poly_value'][-1] - ttd[i])
        err.append(diff ** 2)
        err_h.append(diff + ttd[i])
        err_l.append(ttd[i] - diff)

    coeff['coeff_h'] = np.polyfit(t, err_h, degree)
    coeff['coeff_l'] = np.polyfit(t, err_l, degree)

    # Mean squared error
    MSE = np.average(err)
    # print("MSE: ", MSE)

    # Training split
    train_size = int((l - 1) * 0.75)
    t_train = t[0:train_size]
    ttd_train = ttd[0:train_size]

    coeff['coeff_train'] = np.polyfit(t_train, ttd_train, degree)

    # Print the equation
    # i = 0
    # while i <= degree:
    #     if i == degree:
    #         print("(%.10f)" % (coeff['coeff_ttd'][i]))
    #         break
    #     print("(%.10f*x^%d)+" % (coeff['coeff_ttd'][i], degree - i,), end="")
    #     i += 1

    return coeff


def choosing_roots(roots):
    for root in roots:
        root = int(root)
        if root < 0:
            continue
        if abs(root - time_target) >= time_span:
            continue

        return root


def estimate_ttd(polynom_ttd, ttd, coeff_h, coeff_l):
    # Find x for given y
    result = {}
    substitute = np.copy(polynom_ttd)
    substitute[-1] -= ttd_target
    result['point'] = choosing_roots(np.roots(substitute))

    substitute = np.copy(coeff_h)
    substitute[-1] -= ttd_target
    result['point_high'] = choosing_roots(np.roots(substitute))

    substitute = np.copy(coeff_l)
    substitute[-1] -= ttd_target
    result['point_low'] = choosing_roots(np.roots(substitute))

    # Calculated averages from data
    ttd_diff_avg = int(np.average(np.diff(ttd)))
    # time_diff_avg = int(np.average(np.diff(t)))
    return result


def analyze():
    blocks = json.load(fp=open('points.json', 'r'))
    result = {'timestamp_list': [], 'origin_curve': [], 'predict_curves': [],
              'update_info': {'number': blocks[-1]['number'], 'timestamp': blocks[-1]['timestamp']}}
    for curve_name, span in spans.items():
        data = load_data(span, blocks)
        t_data, ts_str_data, ts_data, hashrate_data, ttd_data = data['UnixTimestamp'], [], [], data['Difficulty'], data[
            'TTD']
        for index in range(data.index.size):
            t = int(data['UnixTimestamp'][index])
            ts_data.append(t)
            ts_str = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(t))
            ts_str_data.append(ts_str)

        coeff = poly_predict(t_data, ttd_data)
        roots = estimate_ttd(coeff['coeff_ttd'], ttd_data, coeff['coeff_h'], coeff['coeff_l'])
        for k, v in roots.items():
            print(k, v, time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(v)))
        predict_info = predict_line(poly_params=coeff['coeff_ttd'], ts_data=ts_data)

        if len(result['timestamp_list']) <= len(predict_info['ts_str']):
            result['timestamp_list'] = to_list(predict_info['timestamp'])
        if len(result['origin_curve']) <= ttd_data.size:
            result['origin_curve'] = to_list(ttd_data)
        result['predict_curves'].append(
            {'name': 'predict_curve_{}'.format(curve_name), 'data': to_list(predict_info['poly_value']),
             'root': [str(roots.get('point')), os.environ['TTD_TARGET']]})
    json.dump(result, indent=2, fp=open("{}.json".format('data'), 'w'))
    return result


def load_data(span, blocks):
    data = {
        'BlockNumber': [],
        'TTD': [],
        'Difficulty': [],
        'UnixTimestamp': []
    }

    for block in blocks[-span:]:
        data['BlockNumber'].append(block['number'])
        data['TTD'].append(float(block['totalDifficulty']))
        data['Difficulty'].append(block['difficulty'])
        data['UnixTimestamp'].append(block['timestamp'])
    df = pd.DataFrame(data)
    return df[['BlockNumber', 'TTD', 'Difficulty', 'UnixTimestamp']]


def predict_line(poly_params, ts_data, span=30 * 24 * 60 * 60):
    predict_dict = {'timestamp': [], 'ts_str': [], 'poly_value': []}
    for t in ts_data:
        predict_dict['timestamp'].append(t)
        predict_dict['ts_str'].append(time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(t)))
        predict_dict['poly_value'].append(np.polyval(poly_params, t))
    start = ts_data[-1] - ts_data[-1] % interval
    for t in range(start, span + start, interval):
        predict_dict['timestamp'].append(t)
        predict_dict['ts_str'].append(time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(t)))
        predict_dict['poly_value'].append(np.polyval(poly_params, t))
    return predict_dict


def to_list(data):
    lst = []
    for i in range(len(data)):
        lst.append(str(int(data[i])))
    return lst


if __name__ == "__main__":
    data = analyze()
